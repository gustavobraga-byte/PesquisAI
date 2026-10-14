"""
colab_cookies.py — Verifica se o Colab permite cookies de terceiros para o proxy.

A interface do UFVAI abre pelo proxy do Colab. Quando o navegador bloqueia
cookies de terceiros, esse proxy não abre. O teste roda num iframe invisível
dentro da própria saída da célula, apontando para uma página mínima servida
pelo kernel através do proxy. Essa página grava um cookie e avisa a célula por
postMessage.

**Regra de exibição (v0.6.21, pedido do autor):** o bloco de aviso é
**invisível por padrão**. Se os cookies estiverem liberados, **nada é
mostrado** — o veredito positivo é o silêncio. O aviso com o passo a passo e a
ordem de **reiniciar o UFVAI** ao terminar aparece **somente quando o bloqueio
é detectado de fato** (a página de teste carregou, mas o cookie não voltou).
Timeout, falha de rede ou erro do próprio teste **não** geram alerta: não houve
detecção de bloqueio, e não se alarma o usuário sem evidência.

**Detecção real:** a página de teste grava um cookie com valor aleatório
(`SameSite=None; Secure`) e o lê de volta — o veredito "liberado" exige que o
valor **exato** volte, nunca um cookie deixado por um teste anterior. Um
`fetch` na própria origem separa "cookie bloqueado" de "iframe não carregou".

Sem Colab (offline/.deb) o módulo não faz nada.
"""

from __future__ import annotations

import html
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .constants import logger

try:  # pragma: no cover - depende do ambiente
    import google.colab  # type: ignore  # noqa: F401
    IN_COLAB = True
except ImportError:  # pragma: no cover
    IN_COLAB = False

PROBE_PATH = "/ufvai-cookie-probe"
DEFAULT_TIMEOUT_S = 20.0
# Tempo que o servidor efêmero continua vivo depois do teste.
SERVER_GRACE_S = 10.0

# Rótulo do botão do Colab — usado na instrução de reinício.
RESTART_HINT = "Ambiente de execução → Reiniciar e executar tudo"


# Página servida pelo kernel (através do proxy). Roda como terceiro no iframe.
PROBE_PAGE = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><title>UFVAI · teste de cookies</title></head>
<body>
<script>
(function () {
  // Token novo a cada carregamento: garante que o veredito "liberado" é
  // resultado de uma gravação AGORA, nunca de um cookie deixado por um teste
  // anterior (que daria falso positivo).
  var token = "t" + Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
  var result = {
    ufvai: "cookie-probe",
    token: token,
    ok: false,
    cookieEnabled: false,
    written: false,
    fetchOk: false,
    error: ""
  };
  try { result.cookieEnabled = !!navigator.cookieEnabled; } catch (e) {}
  try {
    document.cookie = "ufvai_probe=" + token + "; path=/; max-age=600; SameSite=None; Secure";
    result.written = document.cookie.indexOf("ufvai_probe=" + token) !== -1;
  } catch (e) {
    result.error = String((e && e.message) || e);
  }
  function report() {
    try { window.parent.postMessage(result, "*"); } catch (e) {}
  }
  // Prova independente: o iframe consegue falar com o kernel pelo proxy?
  fetch(window.location.pathname + "?ping=1", {cache: "no-store"})
    .then(function (r) { result.fetchOk = r.ok; result.ok = result.written; report(); })
    .catch(function () { result.ok = false; report(); });
  // First paint: se o fetch travar, o veredito de cookie já é enviado.
  if (result.written) { result.ok = true; report(); }
  setTimeout(report, 8000);
})();
</script>
</body></html>
"""

# ÚLTIMO item do aviso: o que fazer quando terminar.
RESTART_HTML = (
    '<li style="margin-top:8px"><b>Ao terminar, reinicie o UFVAI</b> para que o teste '
    "seja refeito com a nova permiss&atilde;o: no Colab, "
    f"<code>{html.escape(RESTART_HINT)}</code> "
    "(ou execute a c&eacute;lula de boot de novo). Sem reiniciar, o proxy continua "
    "sem abrir.</li>"
)

INSTRUCTIONS_HTML = f"""
<ol style="margin:8px 0 0 18px;line-height:1.55">
  <li><b>Chrome / Edge:</b> clique no cadeado ao lado do endere&ccedil;o &rarr; <i>Configura&ccedil;&otilde;es do site</i>
      &rarr; <i>Cookies</i> &rarr; <i>Permitir</i>. Ou em <i>Configura&ccedil;&otilde;es &rarr; Privacidade e seguran&ccedil;a
      &rarr; Cookies de terceiros</i> escolha permitir e inclua <code>[*.]colab.research.google.com</code>
      e <code>[*.]prod.colab.dev</code> como exce&ccedil;&otilde;es. Os nomes dos menus podem variar conforme a vers&atilde;o.</li>
  <li><b>Firefox:</b> clique no escudo ao lado do endere&ccedil;o &rarr; <i>Desativar prote&ccedil;&atilde;o contra rastreamento
      para este site</i>. No modo <i>Estrito</i>, o bloqueio de cookies entre sites tamb&eacute;m precisa ser liberado.</li>
  <li><b>Brave:</b> clique no &iacute;cone do le&atilde;o &rarr; <i>Shields</i> &rarr; desative para este site
      (ou libere cookies para <code>colab.research.google.com</code> e <code>prod.colab.dev</code>).</li>
  <li><b>Safari:</b> <i>Ajustes &rarr; Privacidade</i>: desmarque <i>Impedir rastreamento entre sites</i> e
      <i>Bloquear todos os cookies</i>.</li>
  <li>Use uma janela <b>normal</b> (n&atilde;o an&ocirc;nima/privada).</li>
  {RESTART_HTML}
</ol>
"""


def probe_page_html() -> str:
    """HTML da página de teste servida pelo kernel."""
    return PROBE_PAGE


def build_status_html(probe_url: str, timeout_ms: int = int(DEFAULT_TIMEOUT_S * 1000)) -> str:
    """Bloco HTML/JS da célula: iframe de teste e aviso (mostrado só se falhar).

    O container nasce **vazio e sem borda**: nada aparece enquanto o teste não
    volta. Só quando o navegador bloqueia (ou não responde) o JS preenche o
    aviso e o transforma em cartão visível. Se os cookies estiverem liberados,
    o bloco permanece invis&iacute;vel — o veredito positivo &eacute; o sil&ecirc;ncio.
    """
    url = html.escape(probe_url, quote=True)
    return f"""
<div id="ufvai-cookie-box" style="max-width:640px;margin:10px auto;padding:0;border:0;
     border-radius:12px;background:transparent;
     font-family:system-ui,-apple-system,'Segoe UI',sans-serif;color:#1f2831">
  <div id="ufvai-cookie-status" style="display:none;font-size:15px;font-weight:600;color:#901812"></div>
  <div id="ufvai-cookie-warn" style="display:none;margin-top:12px;padding:12px 14px;
       border-radius:10px;background:#fdecea;border:1px solid #e0a09a;color:#571512">
    <div style="font-weight:700;font-size:15px">&#9888;&#65039; Cookies de terceiros bloqueados ou n&atilde;o confirmados</div>
    <div style="margin-top:6px;font-size:14px">
      A interface do UFVAI roda em <code>*.prod.colab.dev</code>. Sem cookies de terceiros,
      o endere&ccedil;o <b>n&atilde;o abre</b>. Para liberar:
    </div>
    {INSTRUCTIONS_HTML}
  </div>
  <div id="ufvai-cookie-frame-wrap" style="width:0;height:0;border:0;overflow:hidden">
    <iframe id="ufvai-cookie-frame" src="{url}" title="teste de cookies UFVAI"
            style="width:0;height:0;border:0" tabindex="-1" aria-hidden="true"></iframe>
  </div>
</div>
<script>
(function () {{
  var box = document.getElementById("ufvai-cookie-box");
  if (!box) {{ return; }}
  var statusEl = document.getElementById("ufvai-cookie-status");
  var warnEl = document.getElementById("ufvai-cookie-warn");
  var frame = document.getElementById("ufvai-cookie-frame");
  var settled = false;

  function reveal(html) {{
    // Só agora o bloco vira visível: cookies liberados = nada na tela.
    box.style.padding = "16px 18px";
    box.style.border = "1px solid rgba(43,45,58,.18)";
    box.style.background = "#f6f5f0";
    statusEl.style.display = "block";
    statusEl.innerHTML = html;
    warnEl.style.display = "block";
  }}

  function show(state, detail) {{
    // v0.6.21: o aviso SÓ aparece quando o bloqueio é DETECTADO. Qualquer
    // outro veredito — inclusive "não deu para confirmar" — é silêncio: o
    // bloco permanece invisível e o usuário não vê nada na tela.
    if (state === "blocked") {{
      if (settled) {{ return; }}
      settled = true;
      reveal("&#10060; Cookies de terceiros bloqueados neste navegador.");
    }} else if (state === "ok") {{
      settled = true;  // liberados: encerra o teste sem mostrar nada
    }}
    // "timeout" e "error" NÃO marcam settled: se o postMessage chegar depois,
    // o bloqueio ainda pode ser reportado normalmente.
  }}

  window.addEventListener("message", function (ev) {{
    if (!ev.data || ev.data.ufvai !== "cookie-probe") {{ return; }}
    if (frame && ev.source !== frame.contentWindow) {{ return; }}
    show(ev.data.ok ? "ok" : (ev.data.fetchOk ? "blocked" : "timeout"), ev.data.error);
  }});

  setTimeout(function () {{ show("timeout", ""); }}, {int(timeout_ms)});
}})();
</script>
"""


class _ProbeHandler(BaseHTTPRequestHandler):
    """Serve a página de teste. Nenhum dado do usuário é lido ou gravado."""

    def do_GET(self) -> None:  # noqa: N802 (nome exigido pelo http.server)
        body = probe_page_html().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:  # silencia o log padrão
        return


def start_probe_server() -> tuple[ThreadingHTTPServer, int]:
    """Sobe o servidor efêmero em 127.0.0.1 numa porta livre."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _ProbeHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True, name="ufvai-cookie-probe")
    thread.start()
    return server, port


def _shutdown(server: ThreadingHTTPServer) -> None:
    try:
        server.shutdown()
        server.server_close()
    except Exception:  # noqa: BLE001
        pass


# Evita dois avisos de cookies na mesma execução (o notebook e o run_fast
# podem pedir o teste; o usuário deve ver apenas um bloco).
_COOKIE_CHECK_DONE = False


def ensure_cookie_check(timeout_s: float = DEFAULT_TIMEOUT_S, force: bool = False) -> dict:
    """Dispara o teste de cookies **uma única vez** por processo.

    Usado pelo notebook e pelo `run_fast.setup_launch()`: quem rodar o UFVAI
    por qualquer caminho faz o teste uma vez só. É chamado sempre **depois** do
    botão ABRIR O UFVAI — e, se os cookies estiverem liberados, nada aparece.

    Returns:
        O dicionário de `show_cookie_check`, `{'state': 'done'}` quando já
        tinha sido disparado antes, ou `{'state': 'error', 'error': ...}` se a
        chamada falhar — nunca levanta.
    """
    global _COOKIE_CHECK_DONE
    if _COOKIE_CHECK_DONE and not force:
        return {"state": "done"}
    _COOKIE_CHECK_DONE = True
    try:
        return show_cookie_check(timeout_s=timeout_s)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Teste de cookies do Colab falhou: %s", exc)
        return {"state": "error", "error": str(exc)[:200]}


def show_cookie_check(timeout_s: float = DEFAULT_TIMEOUT_S) -> dict:
    """Mostra o teste de cookies na célula (somente no Colab).

    Não bloqueia: o resultado chega ao navegador por postMessage. Nada é exibido
    enquanto o teste não responde, e o aviso **só** aparece quando o navegador
    é detectado com os cookies de terceiros bloqueados. Todos os demais
    vereditos — inclusive "não deu para confirmar" — deixam a célula em
    silêncio.

    Returns:
        {'state': 'checking', 'port': N} quando o teste foi disparado,
        {'state': 'skipped'} fora do Colab, ou {'state': 'error', 'error': ...}.
    """
    if not IN_COLAB:
        return {"state": "skipped"}
    try:  # pragma: no cover - exige o runtime do Colab
        from google.colab import output  # type: ignore
        from IPython.display import HTML, display  # type: ignore

        server, port = start_probe_server()
        base = output.eval_js(f"google.colab.kernel.proxyPort({port})")
        probe_url = str(base).rstrip("/") + PROBE_PATH
        display(HTML(build_status_html(probe_url, timeout_ms=int(timeout_s * 1000))))
        threading.Timer(timeout_s + SERVER_GRACE_S, _shutdown, args=(server,)).start()
        return {"state": "checking", "port": port}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Teste de cookies do Colab falhou: %s", exc)
        return {"state": "error", "error": str(exc)[:200]}