"""
run_fast.py — Versão otimizada do PesquisAI.

Otimizações implementadas:
  1. Skills clonadas em PARALELO com ThreadPoolExecutor (8× mais rápido)
  2. Cache de repositórios — usa git pull --depth 1 se já existir
  3. apt-get update executado UMA ÚNICA vez (antes rodeava duas vezes)
  4. opencode já instalado é detectado e pula reinstalação
  5. pip install com --no-cache-dir evita overhead de cache
  6. Barra de progresso reflete economia de tempo real
  7. Skills definidas centralmente em constants.py (SKILL_REGISTRY)

v0.6.7 — POLÍTICA "PAINEL ÚNICO": nenhuma mensagem textual é impressa no
fluxo de inicialização (Colab). Marca, versão, estágios e progresso são
comunicados exclusivamente pelo painel da logomarca (_BootPanel via
progress_bar.show()). Falhas críticas vão para `logger` (stderr) para
não poluir o painel nem perder diagnóstico. O único trecho textual
restante é `_offline_keep_alive()` — modo .deb/offline, onde NÃO há
painel e os prints são a única saída (feedback exigido desde v0.6.1).

Uso:
    from run_fast import run
    run()
"""

import os
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from .constants import (
    DRIVE_PATH,
    SKILLS_DIR,
    SKILL_REGISTRY,
    SKILL_MAPPINGS,
    ESSENTIAL_SKILLS,
    custom_skills_dir,
    THEME_DIR,
    AGENT_DIR,
    AGENT_NAME,
    AGENT_FILE,
    LEGACY_AGENT_FILES,
    THEME_NAME,
    LEGACY_THEME_FILES,
    TUI_JSON,
    CLI_JSON,
    OPENCODE_CFG,
    OPENCODE_INSTALL_V2,
    OPENCODE_MIN_MAJOR,
    WORK_DIR,
    WRAPPER_DIR,
    TERMINAL_PORT,
    WRAPPER_PORT,
    logger,
)
from .jokes import next_joke
from .progress_bar import show as progress, finish as progress_finish
from .opencode_config import (
    build_agent_markdown,
    build_ufvai_theme,
    load_json_config,
    merge_agent_policy,
    merge_cli_theme,
    strip_frontmatter,
    write_json_atomic,
)
from .opencode_utils import find_opencode, reset_opencode_cache

# Descrição do agente UFVAI (aparece na lista de agentes da V2)
UFVAI_AGENT_DESCRIPTION = (
    "Agente de pesquisa científica com foco em dados brasileiros (IBGE, DataSUS), "
    "normas ABNT/UFV e integridade científica. Não inventa dados nem referências; "
    "não simula coleta primária."
)


# ── Utilitários ──────────────────────────────────────────────

def _run(cmd: str, **kw) -> subprocess.CompletedProcess:
    """Executa um comando shell e retorna o resultado."""
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, **kw)


def _check_bin(name: str) -> bool:
    """Verifica se um binário existe no sistema."""
    if shutil.which(name):
        return True
    for d in ["~/.local/bin", "~/.npm-global/bin", "~/.opencode/bin", "/usr/local/bin"]:
        path = os.path.expanduser(os.path.join(d, name))
        if os.path.isfile(path):
            return True
    return False


# ── v0.6.9-5: Fast-fail offline + Tela instantânea ─────────────────

def _network_ok(timeout: float = 2.5) -> bool:
    """Verifica conectividade (TCP 443) sem bloquear offline."""
    import socket as _sock
    for _host, _port in (("github.com", 443), ("opencode.ai", 443), ("pypi.org", 443)):
        try:
            with _sock.create_connection((_host, _port), timeout=timeout):
                return True
        except Exception:
            continue
    return False


_EARLY_LOADING_HTML = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>UFVAI</title>
<style>
  *{margin:0;padding:0;box-sizing:border-box}
  body{background:#f6f5f0;color:#1f2831;display:flex;justify-content:center;align-items:center;min-height:100vh;font-family:system-ui,-apple-system,sans-serif}
  .container{text-align:center;padding:40px;max-width:420px}
  .logo{height:88px;margin-bottom:20px}
  .spinner{width:36px;height:36px;border:3px solid #e5e1d6;border-top-color:#b29149;border-radius:50%;animation:spin .8s linear infinite;margin:0 auto 16px}
  @keyframes spin{to{transform:rotate(360deg)}}
  .title{font-size:26px;font-weight:700;margin-bottom:8px;letter-spacing:-0.02em}
  .title span{color:#b29149}
  .subtitle{font-size:13px;color:#857f72;margin-bottom:6px}
  .status{font-size:14px;color:#4a5560;min-height:18px}
  .joke{font-size:12px;color:#aaa392;margin-top:14px;min-height:16px}
  .hint{font-size:11px;color:#aaa392;margin-top:18px}
</style>
</head>
<body>
<div class="container">
  {logo_img}
  <div class="spinner" id="spinner"></div>
  <div class="title">UFV<span>AI</span></div>
  <div class="subtitle">Universidade Federal de Viçosa · Inteligência Artificial</div>
  <div class="status" id="status">Iniciando...</div>
  <div class="joke" id="joke"></div>
  <div class="hint">Aguarde — primeira execução pode levar 1–2 min offline</div>
</div>
<script>
(function(){
  var jokes=["Carregando skills do IBGE...","Consultando dados do DataSUS...","Preparando inteligência científica...","Conectando à memória local...","Aquecendo os neurônios...","Compilando conhecimento...","Sincronizando bases oficiais..."];
  var i=0, el=document.getElementById('joke'); if(el){el.textContent=jokes[i]; setInterval(function(){i=(i+1)%jokes.length; el.textContent=jokes[i]},2500)}
  function poll(){
    fetch('/api/health',{cache:'no-store'}).then(function(r){return r.json().catch(function(){return {ok: r.status===403 || r.ok}})}).then(function(d){
      if(d && d.ok){ location.href='http://127.0.0.1:'+d.port+'/?_='+Date.now(); }
      else { document.getElementById('status').textContent='Preparando servidores...'; setTimeout(poll,1200); }
    }).catch(function(){ setTimeout(poll,1200); });
  }
  setTimeout(poll,1500);
})();
</script>
</body>
</html>"""

_LOADING_PORT: int = 8002

def _open_chrome_app(url: str) -> None:
    import shutil as _sh
    import webbrowser as _wb
    _attempts = []
    if _sh.which("google-chrome"):
        _attempts.append(["google-chrome", f"--app={url}", "--no-startup-window", "--class=UFVAI"])
    if _sh.which("google-chrome-stable"):
        _attempts.append(["google-chrome-stable", f"--app={url}", "--no-startup-window"])
    if _sh.which("chromium-browser"):
        _attempts.append(["chromium-browser", f"--app={url}", "--no-startup-window"])
    if _sh.which("chromium"):
        _attempts.append(["chromium", f"--app={url}", "--no-startup-window"])
    for _cmd in _attempts:
        try:
            subprocess.Popen(_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except Exception:
            continue
    try:
        _wb.open(url)
    except Exception:
        pass

def _early_loading_screen():
    """v0.6.9-6: tela instantânea na porta 8002 (visual UFVAI) com proxy /api/health.
    Só pula no Colab REAL (import google.colab), não quando /content/drive está montado via rclone."""
    try:
        import google.colab  # type: ignore  # noqa: F401
        return None
    except ImportError:
        pass
    if os.environ.get("IN_COLAB", "").strip().lower() in ("1","true","yes"):
        return None
    # já existe wrapper? não cria loading
    import socket as _sock
    try:
        with _sock.create_connection(("127.0.0.1", WRAPPER_PORT), timeout=0.5):
            return None
    except Exception:
        pass
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import threading as _th
    import base64 as _b64

    # mata resquício na 8002
    subprocess.run(["fuser", "-k", f"{_LOADING_PORT}/tcp"], capture_output=True, timeout=5)
    time.sleep(0.3)

    _logo_tag = ""
    for _cand in [os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "logo.svg"),
                  os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "logo-oficial-288.jpg"),
                  os.path.join(os.path.dirname(__file__), "assets", "logo.svg")]:
        if os.path.exists(_cand):
            try:
                with open(_cand, "rb") as _f:
                    _b = _f.read()
                _mime = "image/svg+xml" if _cand.endswith(".svg") else "image/jpeg"
                _b64s = _b64.b64encode(_b).decode("ascii")
                _logo_tag = f'<img class="logo" src="data:{_mime};base64,{_b64s}" alt="UFVAI">'
                break
            except Exception:
                continue
    if not _logo_tag:
        _logo_tag = '<div class="title">UFV<span>AI</span></div>'

    _html = _EARLY_LOADING_HTML.replace("{logo_img}", _logo_tag)

    class _H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            # proxy /api/health -> wrapper real
            if self.path.startswith("/api/health"):
                import urllib.request as _ur, urllib.error as _ue, json as _js
                _ok = False
                try:
                    _req = _ur.Request(f"http://127.0.0.1:{WRAPPER_PORT}/api/health", headers={"User-Agent":"UFVAI-Loading"})
                    with _ur.urlopen(_req, timeout=1.2) as _r:
                        _ok = True
                except _ue.HTTPError as _e:
                    # 403 com token = vivo (wrapper exige token)
                    if _e.code in (403, 401, 200):
                        _ok = True
                except Exception:
                    _ok = False
                self.send_response(200)
                self.send_header("Content-Type","application/json")
                self.send_header("Cache-Control","no-cache")
                self.end_headers()
                self.wfile.write(_js.dumps({"ok": _ok, "port": WRAPPER_PORT}).encode())
                return
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Cache-Control","no-cache")
            self.end_headers()
            self.wfile.write(_html.encode("utf-8"))
        def handle_one_request(self):
            try: super().handle_one_request()
            except Exception: pass

    try:
        _srv = HTTPServer(("0.0.0.0", _LOADING_PORT), _H)
    except OSError:
        logger.warning("Não foi possível iniciar tela de carregamento na porta %s", _LOADING_PORT)
        return None
    _t = _th.Thread(target=_srv.serve_forever, daemon=True)
    _t.start()
    # flag para launcher não abrir segunda janela
    try:
        _flag = os.path.join(os.path.expanduser("~"), "PesquisAI", ".ui_already_opened")
        os.makedirs(os.path.dirname(_flag), exist_ok=True)
        Path = __import__("pathlib").Path
        Path(_flag).write_text(str(int(time.time())), encoding="utf-8")
    except Exception:
        pass
    # UFVAI_NO_OPEN evita _auto_open_browser duplicado no launch_app
    os.environ["UFVAI_NO_OPEN"] = "1"
    _open_chrome_app(f"http://127.0.0.1:{_LOADING_PORT}")
    # carência 6s para redirect ganhar corrida mesmo se wrapper subir rápido
    return _srv


# ── Etapa 1: Google Drive ────────────────────────────────────

def setup_drive() -> tuple[str, str]:
    """Monta o Google Drive e retorna (folder_path, drive_url)."""
    progress(1, 4, "Montando Google Drive...")
    try:
        from google.colab import drive, auth  # type: ignore
        from googleapiclient.discovery import build  # type: ignore
    except ImportError:
        # v0.6.0 (offline/.deb): persistir em ~/PesquisAI (não /tmp).
        _local = os.path.join(os.path.expanduser("~"), "PesquisAI")
        try:
            os.makedirs(_local, exist_ok=True)
            if os.access(_local, os.W_OK):
                # v0.6.0: mesma estrutura prometida pelo launcher .deb
                for _sub in ("vault", "outputs", "backups", "logs", "sessions"):
                    try:
                        os.makedirs(os.path.join(_local, _sub), exist_ok=True)
                    except Exception:
                        pass
                return _local, "https://drive.google.com/drive/my-drive"
        except Exception:
            pass
        os.makedirs("/tmp/pesquisai_work", exist_ok=True)
        return "/tmp/pesquisai_work", "https://drive.google.com/drive/my-drive"

    mounted = os.path.exists("/content/drive/My Drive")
    if not mounted:
        # v0.6.8: painel único — suprimir saída ruidosa do drive.mount
        # ("Mounted at /content/drive") que poluiria o stdout. Mensagem já
        # está no painel (progress_bar 20% → "Montando Google Drive...").
        import contextlib, io
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                drive.mount("/content/drive", force_remount=False)
        except Exception:
            try:
                drive.mount("/content/drive", force_remount=False)
            except Exception:
                pass

    os.makedirs(DRIVE_PATH, exist_ok=True)
    os.chdir(DRIVE_PATH)

    folder_url: str = "https://drive.google.com/drive/my-drive"
    try:
        auth.authenticate_user()
        service = build("drive", "v3")
        result = service.files().list(
            q="name='PesquisAI' and mimeType='application/vnd.google-apps.folder' and trashed=false",
            fields="files(id)",
        ).execute()
        files = result.get("files", [])
        if files:
            folder_url = f"https://drive.google.com/drive/folders/{files[0]['id']}"
    except Exception:
        pass

    return DRIVE_PATH, folder_url


# ── Etapa 2: Dependências ────────────────────────────────────

def _install_opencode_if_missing() -> bool:
    """Garante o motor **OpenCode V2** (instala ou atualiza) no boot.

    - Já é 2.x → fast-path, sem rede.
    - Ausente → instala pelo instalador oficial V2 (`opencode.ai/v2/install`).
    - 1.x instalado → **atualiza para 2.x**: o instalador V2 substitui o
      binário no mesmo path (`~/.opencode/bin`), e V1/V2 compartilham as
      mesmas localizações de configuração, credenciais, agentes e skills —
      a migração de `tui.json` → `cli.json` é automática no 1º start.
    - Offline → mantém o que existir (V1 segue utilizável; o upgrade fica
      para o próximo boot com rede).

    Returns:
        True se ao final existe um binário utilizável.
    """
    from .opencode_utils import opencode_major, opencode_version_string

    major = opencode_major()  # None quando não há binário
    if major is not None and major >= OPENCODE_MIN_MAJOR:
        return True

    have_bin = _check_bin("opencode")
    if have_bin:
        logger.info(
            "OpenCode %s (< v%d) — atualizando para o motor V2…",
            opencode_version_string() or "v1", OPENCODE_MIN_MAJOR,
        )
    else:
        logger.info("OpenCode ausente — instalando o motor V2…")

    # v0.6.9-5: fast-fail offline — sem rede, não tenta curl
    if not _network_ok():
        if have_bin:
            logger.warning(
                "Sem rede — mantendo o OpenCode v1 instalado; "
                "o upgrade para v2 acontece no próximo boot com rede."
            )
            return True
        logger.info("Sem rede — pulando instalação do opencode (já ausente, segue sem)")
        return False

    for cmd in [
        f"curl -fsSL {OPENCODE_INSTALL_V2} | bash",
        # fallback: pacote npm oficial do CLI V2 (@opencode/cli)
        "npm install -g @opencode/cli",
    ]:
        r = _run(cmd, check=False)
        # OpenCode V2: o cache do binário pode apontar para o V1 antigo
        reset_opencode_cache()
        if not (_check_bin("opencode") and r.returncode == 0):
            continue
        new_major = opencode_major()
        if new_major is not None and new_major >= OPENCODE_MIN_MAJOR:
            logger.info("OpenCode pronto em v%s.", opencode_version_string())
            return True
        if not have_bin:
            # binário novo existe mas não respondeu a --version; não bloqueia
            return True

    if _check_bin("opencode"):
        logger.error(
            "Upgrade do opencode para v2 falhou — seguindo com o binário atual (%s).",
            opencode_version_string() or "desconhecido",
        )
        return True
    logger.error("Falha ao instalar o opencode — todas as tentativas falharam.")
    return False


def _install_system_deps() -> None:
    """Instala ttyd, uv, xclip, xsel em um único apt-get."""
    tasks: list[str] = []
    if not _check_bin("ttyd"):
        tasks.append("ttyd")
    if not _check_bin("xclip"):
        tasks.append("xclip")
    if not _check_bin("xsel"):
        tasks.append("xsel")
    if not _check_bin("tmux"):  # v0.6.22: mantém a sessão viva entre quedas do WebSocket
        tasks.append("tmux")
    tasks = list(set(tasks))

    if tasks:
        # v0.6.9-5: fast-fail offline — se sem rede e ttyd já bundle, pula apt
        if not _network_ok():
            if "ttyd" in tasks and os.path.isfile("/usr/local/bin/ttyd"):
                logger.info("Sem rede mas ttyd bundle presente — pulando apt-get")
                tasks = [t for t in tasks if t != "ttyd"]
                if not tasks:
                    # só faltava ttyd e já temos
                    pass
                else:
                    logger.info("Sem rede — pulando apt-get para %s", tasks)
                    tasks = []
            else:
                logger.info("Sem rede — pulando apt-get para %s", tasks)
                tasks = []
        if tasks:
            subprocess.run(["apt-get", "update", "-qq"], capture_output=True, text=True, check=False)
            r = subprocess.run(
                ["apt-get", "install", "-y", "-qq", *tasks],
                capture_output=True, text=True, check=False,
            )
            if r.returncode != 0:
                logger.warning("apt-get falhou (%s) — tentando download manual do ttyd...", tasks)
                if _network_ok():
                    subprocess.run(
                        ["curl", "-fsSL",
                         "https://github.com/tsl0922/ttyd/releases/latest/download/ttyd.x86_64",
                         "-o", "/usr/local/bin/ttyd"],
                        capture_output=True, text=True, check=False,
                    )
                    subprocess.run(["chmod", "+x", "/usr/local/bin/ttyd"],
                                   capture_output=True, text=True, check=False)
                else:
                    logger.info("Sem rede — pulando download manual do ttyd")

    if not _check_bin("uv"):
        if _network_ok():
            _run("curl -LsSf https://astral.sh/uv/install.sh | sh", check=False)
        else:
            logger.info("Sem rede — pulando instalação do uv")


def _install_python_deps() -> None:
    """Instala dependências Python necessárias."""
    # v0.6.9-5: fast-fail offline — pip sem rede falha rápido e polui log
    if not _network_ok():
        logger.info("Sem rede — pulando pip install")
        return
    subprocess.run(
        ["pip", "install", "--quiet", "--no-cache-dir",
         "google-api-python-client", "google-auth-httplib2",
         "google-auth-oauthlib", "cryptography", "pyyaml>=6.0"],
        capture_output=True, text=True, check=False,
    )


def ensure_ufvai_agent() -> bool:
    """Garante que o terminal do OpenCode V2 SEMPRE carregue o agente UFVAI.

    Regra do autor (14/10/2026, ajuste na v0.6.21 — SEM bump de versão):
    "sempre que atualizar o terminal o agente a ser carregado deve ser o
    ufvai, nunca deve carregar outro agente". Reprodução do defeito: ao
    adicionar uma nova chave de API o terminal reiniciava e o motor iniciava
    com o agente `build`. Causa (doc oficial V2, opencode.ai/v2/docs/agents):
    a V2 só usa `default_agent` quando o agente existe, é visível e aceita
    `primary`; caso contrário cai em `build`. Como a garantia do agente era
    regravada APENAS no boot (`_setup_theme_and_agent` via `setup_dependencies`),
    qualquer reinício do terminal fora do boot (troca de chave, idioma,
    restore/import de sessão) podia rodar sem o agente em vigor.

    Idempotente e auto-suficiente, para poder ser chamada ANTES de cada
    (re)spawn do terminal (launch_app chama `_ensure_ufvai_agent_before_spawn`
    em start_ttyd, restart_ttyd_with_lang, /api/run_terminal e /api/session):

    - regenera agents/UFVAI.md (AGENTS.md + autopilot + skills personalizadas);
    - remove agentes legados (pesquisai.md / ufvai.md) — sem duplicatas;
    - (re)grava em opencode.json preservando o resto:
      · `default_agent: "UFVAI"` (v0.6.21);
      · `agents.build.disabled: true` e `agents.plan.disabled: true`
        (v0.6.22) — build e plan saem da TUI e do fallback, e o único
        agente carregável passa a ser o UFVAI, inclusive na mensagem
        inicial de um usuário novo.

    Returns:
        False somente quando opencode.json EXISTE mas não pôde ser
        interpretado — arquivo ilegível do usuário NUNCA é sobrescrito
        (a V2, nesse caso, cairá em `build`; o chamador registra o alerta).
    """
    os.makedirs(AGENT_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(OPENCODE_CFG), exist_ok=True)

    # ── Agente UFVAI (agents/UFVAI.md) ────────────────────────
    agents_md = os.path.join(os.path.dirname(os.path.dirname(__file__)), "AGENTS.md")
    if os.path.exists(agents_md):
        with open(agents_md, encoding="utf-8") as fh:
            raw_agents = fh.read()
    else:
        raw_agents = "# PesquisAI"
    content = strip_frontmatter(raw_agents)

    # ── Injetar instruções de autopilot no prompt do agente ───
    # Isto faz o agente SALVAR AUTONOMAMENTE no vault do Obsidian
    # sem precisar que o usuário peça.
    autopilot_instructions = """

## 🤖 AUTOPILOT — Salvamento Autônomo (v0.5.1+)

Você tem uma memória persistente via Obsidian vault no Google Drive.
Use-a AUTONOMAMENTE — **não espere o usuário pedir para salvar**.

### O que você DEVE fazer automaticamente:

1. **ANTES de responder** — recorde informações relevantes:
   ```python
   from pesquisai.obsidian.autopilot import recall
   results = recall("tema da pergunta do usuário")
   # Se houver resultados, use-os como contexto
   ```

2. **DEPOIS de concluir uma tarefa** — salve o resultado:
   ```python
   from pesquisai.obsidian.autopilot import save
   save(
       title="Título da nota",
       body="## Resultados\\n\\n- ...\\n\\n[DADO CONFIRMADO]",
       tags=["pesquisai/ibge"],
       template="research",
   )
   ```

3. **Ao usar uma skill** — registre:
   ```python
   from pesquisai.obsidian.autopilot import log_skill
   log_skill("ibge-br")
   ```

4. **Ao gerar um arquivo** — registre:
   ```python
   from pesquisai.obsidian.autopilot import log_file
   log_file("resultado.csv")
   ```

5. **Ao final da conversa** — log de sessão:
   ```python
   from pesquisai.obsidian.autopilot import end_session
   end_session(summary="Resumo do que foi feito nesta sessão")
   ```

### Quando salvar AUTONOMAMENTE (sem o usuário pedir):

- ✅ Após coletar dados do IBGE/DataSUS → salve nota de datasource
- ✅ Após escrever uma seção de artigo → salve nota de research
- ✅ Após revisar um paper → salve nota de literature
- ✅ Após formular uma hipótese → salve nota de hypothesis
- ✅ Após gerar um arquivo (.md, .pdf, .csv) → registre no log
- ✅ Ao final de cada resposta substancial → salve achados

### Quando NÃO salvar:

- ❌ Respostas curtas ("sim", "não", explicações rápidas)
- ❌ Conversa informal
- ❌ Quando o usuário explicitamente disser "não salve"

### API rápida (uma linha):

```python
from pesquisai.obsidian.autopilot import save_finding
save_finding("A prevalência de diabetes é 10,2% (VIGITEL 2023)", source="VIGITEL")
```

> **Tudo é no-op se o vault não estiver disponível.** Você nunca
> quebra. Se a memória não estiver ativa, simplesmente não salva e
> continua trabalhando normalmente.
"""

    # v0.6.18: instrução de skills personalizadas — injetada no prompt do
    # agente para que novas skills solicitadas pelo usuário sejam criadas
    # na pasta persistente backups/skills-personalizadas/.
    custom_skill_instructions = f"""

## 🧩 Skills Personalizadas do Usuário (v0.6.18)

Existe uma pasta persistente de skills personalizadas em:
`{custom_skills_dir()}`

### Regras obrigatórias:

1. **Nova skill solicitada pelo usuário:** ao criar uma skill nova (por
   pedido explícito como "crie uma skill que..."), escreva-a
   OBRIGATORIAMENTE nesta pasta, em subpasta própria com `SKILL.md`
   (frontmatter `name` + `description`). Ela será carregada
   automaticamente no próximo boot.
2. **Skill já existente na pasta:** se o pedido for para corrigir/atualizar
   uma skill personalizada, edite-a diretamente na pasta (nunca apague o
   frontmatter).
3. **Validação:** uma skill só é carregada se a subpasta contiver
   `SKILL.md`. Sempre informe ao usuário o caminho onde a skill foi
   salva e avise que ela entra em vigor no próximo boot (ou imediatamente
   se copiada também para `{SKILLS_DIR}`).
4. **Nunca** salve skills personalizadas fora dessa pasta.
"""

    agent_body = f"{content}\n{autopilot_instructions}\n{custom_skill_instructions}\n"
    with open(os.path.join(AGENT_DIR, AGENT_FILE), "w", encoding="utf-8") as f:
        f.write(build_agent_markdown(UFVAI_AGENT_DESCRIPTION, "#b29149", agent_body))

    # O ID do agente na V2 é o nome do arquivo. Legados ("pesquisai.md" da
    # identidade antiga e "ufvai.md" minúsculo) são removidos para não sobrar
    # agente duplicado na lista da V2 — a presença deles NÃO impede o
    # default_agent, mas polui a lista (e o 'ufvai.md' seria um agente novo).
    for legacy_agent in LEGACY_AGENT_FILES:
        legacy_path = os.path.join(AGENT_DIR, legacy_agent)
        if os.path.exists(legacy_path):
            try:
                os.remove(legacy_path)
            except OSError:
                logger.warning("Não foi possível remover o agente antigo %s", legacy_path)

    # ── opencode.json: agente padrão (V2) ─────────────────────
    ok_cfg, cfg = load_json_config(OPENCODE_CFG)
    if ok_cfg:
        current = cfg.get("default_agent")
        if current != AGENT_NAME:
            logger.info(
                "default_agent fora do padrão (era %r → regravando %r). "
                "Sem isso o motor inicia com o agente `build`.",
                current, AGENT_NAME,
            )
        # v0.6.22: `merge_agent_policy` também DESABILITA os built-ins
        # `build` e `plan` em `agents` do opencode.json — regra do autor
        # ("exclua o build e o plan; tem que SEMPRE carregar o ufvai").
        # Assim o único fallback visível da V2 continua sendo o UFVAI.
        write_json_atomic(OPENCODE_CFG, merge_agent_policy(cfg, AGENT_NAME))
        return True
    logger.warning(
        "opencode.json não pôde ser interpretado (JSONC inválido?); o arquivo "
        "do usuário NÃO é sobrescrito e o motor pode iniciar com `build`."
    )
    return False


def preflight_ufvai_session(
    cwd: Optional[str] = None,
    timeout_s: float = 10.0,
) -> Optional[str]:
    """v0.6.22 (ajuste 15/10/2026 — SEM bump): pré-cria a sessão do terminal
    JÁ presa ao agente UFVAI, via API do opencode.

    Defeito reproduzido pelo autor: a PRIMEIRA mensagem de um usuário novo
    ("Olá! (Dica: ...)") era processada pelo agente `build` — o TUI criava a
    sessão nova com `build` mesmo com `default_agent: "UFVAI"` válido e
    confirmado em opencode.json (config escrita ANTES da criação da sessão;
    conferido por mtime 22:45:23 vs. sessão 22:45:34 em 15/10/2026). Depois de
    um clique do usuário na TUI a sessão era trocada ("switched agent from
    Build to UFVAI") — aí sim ia para o UFVAI.

    Causa [DADO CONFIRMADO]: a seleção do agente na criação de sessão da TUI
    acontece no lado cliente/serviço e pode não honrar `default_agent` na
    primeira mensagem (headless `opencode run` honra — a divergência é só na
    TUI). A doc oficial garante o caminho inverso: "changing this setting
    does not replace the agent stored on an existing session" — ou seja,
    uma sessão criada COM `agent` fixado mantém o agente.

    Solução: criar a sessão ANTES do spawn com
    `opencode api post /api/session -d '{"agent":"UFVAI", ...}'`, validar o
    retorno por `GET /api/session/<id>` (agent == UFVAI) e abrir o TUI com
    `--session <id>`. O TUI continua a sessão existente e a saudação já
    parte direto para o UFVAI — inclusive no primeiro boot de um usuário
    novo, em reinício por troca de chave/idioma e em /api/run_terminal.

    Best-effort: qualquer falha (binário ausente, serviço fora/ar, JSON
    inválido, agente não confirmado) devolve None e o chamador mantém o
    comportamento anterior (`--prompt` sem `--session`), em que os outros
    mecanismos (default_agent + built-ins desabilitados) continuam ativos.

    Args:
        cwd: projeto em que a sessão é criada (deve bater com o cwd do TUI
             que será spawnado — normalmente `os.getcwd()` do processo que
             serve o terminal). None usa o cwd atual do processo.
        timeout_s: limite de tempo total para POST + GET (best-effort).

    Returns:
        ID (`ses_*`) da sessão criada e validada, ou None em qualquer falha.
    """
    import json as _json

    try:
        opencode_bin = find_opencode()
    except FileNotFoundError:
        logger.debug("preflight_ufvai_session: opencode não encontrado")
        return None

    payload = _json.dumps({
        "agent": AGENT_NAME,
        "title": "Terminal PesquisAI (UFVAI)",
    })

    def _api(arguments: list[str]) -> dict:
        result = subprocess.run(
            [opencode_bin, "api", *arguments],
            capture_output=True, text=True, timeout=timeout_s / 2,
            cwd=cwd or os.getcwd(),
        )
        raw = result.stdout.strip()
        start = raw.find("{")
        if start < 0:
            raise ValueError(f"resposta sem JSON: {raw[:120]!r}")
        parsed = _json.loads(raw[start:])
        if not isinstance(parsed, dict):
            raise ValueError("resposta não é um objeto JSON")
        return parsed

    try:
        created = _api(["post", "/api/session", "--data", payload])
        session_id = ((created.get("data") or {}).get("id") or "").strip()
        if not session_id.startswith("ses_"):
            logger.debug("preflight_ufvai_session: id inválido no POST (%r)", session_id[:40])
            return None
        # Validação fail-closed: a sessão SÓ vale se nasceu presa ao UFVAI.
        fetched = _api(["get", f"/api/session/{session_id}"])
        agent = (fetched.get("data") or {}).get("agent")
        if agent != AGENT_NAME:
            logger.debug(
                "preflight_ufvai_session: sessão criada com agent=%r (≠ %r) — descartando",
                agent, AGENT_NAME,
            )
            return None
        return session_id
    except (subprocess.TimeoutExpired, ValueError, KeyError, OSError) as exc:
        logger.debug("preflight_ufvai_session indisponível (%s) — seguindo sem --session", exc)
        return None


def _setup_theme_and_agent() -> None:
    """Configura tema, agente UFVAI e opencode.json para o OpenCode V2.

    OpenCode V2 (v0.6.21):
    - tema UFVAI completo no formato V1 (50 chaves) em themes/pesquisai.json;
      dark e light no MESMO arquivo — o modo vai em cli.json (theme.mode);
    - cli.json é a única configuração do terminal (tui.json não é mais gravado);
    - agente e default_agent ficam a cargo de `ensure_ufvai_agent()` (definida
      acima), que também é chamada por launch_app ANTES de cada reinício do
      terminal — garantia do autor de 14/10/2026: nunca carregar outro agente.
      Arquivo do usuário que não pode ser interpretado NÃO é sobrescrito.
    """
    os.makedirs(THEME_DIR, exist_ok=True)

    # ── Tema UFVAI (um arquivo, dois modos) ───────────────────
    write_json_atomic(os.path.join(THEME_DIR, f"{THEME_NAME}.json"), build_ufvai_theme())
    for legacy_theme in LEGACY_THEME_FILES:
        legacy_path = os.path.join(THEME_DIR, legacy_theme)
        if os.path.exists(legacy_path):
            try:
                os.remove(legacy_path)
            except OSError:
                pass

    # ── cli.json: nome e modo do tema (preserva a escolha do usuário) ──
    ok_cli, existing_cli = load_json_config(CLI_JSON)
    if ok_cli:
        theme_cfg = existing_cli.get("theme")
        if isinstance(theme_cfg, dict):
            name = theme_cfg.get("name")
            mode = theme_cfg.get("mode")
        else:
            name, mode = theme_cfg, None
        if not isinstance(name, str) or not name:
            name = THEME_NAME
        if mode not in ("dark", "light"):
            mode = "dark"
        write_json_atomic(CLI_JSON, merge_cli_theme(existing_cli, name, mode))
    else:
        logger.warning("cli.json não pôde ser lido; tema do terminal mantido como está.")

    # ── Agente UFVAI + default_agent (garantia reexecutável) ──
    ensure_ufvai_agent()


def setup_dependencies() -> None:
    """Instala todas as dependências (OpenCode, sistema, Python, tema)."""
    progress(2, 4, "Instalando OpenCode, dependências de sistema e tema...")
    _install_opencode_if_missing()
    _install_system_deps()
    _install_python_deps()
    _setup_theme_and_agent()


# ── Etapa 3: Skills (paralelizadas) ──────────────────────────

def _clone_or_pull(repo_url: str, dest_name: str) -> bool:
    """Clone com cache: se já existe, faz git pull --depth 1.

    Returns:
        True se a operação foi bem-sucedida, False caso contrário.
    """
    dest = f"/tmp/skill_{dest_name}"
    if os.path.exists(dest):
        r = subprocess.run(
            ["git", "-C", dest, "pull", "--depth", "1", "--ff-only"],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode == 0:
            return True
        shutil.rmtree(dest)

    r = subprocess.run(
        ["git", "clone", "--depth", "1", "--single-branch", repo_url, dest],
        capture_output=True, text=True, timeout=60,
    )
    return r.returncode == 0


def setup_skills() -> None:
    """Clona/atualiza todas as skills em paralelo e copia para o diretório do agente.

    Skills essenciais (ESSENTIAL_SKILLS) disparam aviso se falharem.
    Skills opcionais falham silenciosamente.
    v0.6.9-5: fast-fail offline — sem rede, pula clones (evita timeout 60s ×N)
    """
    # v0.6.9-5: sem rede, não tenta git (skills já bundle no .deb ou em cache)
    if not _network_ok():
        logger.info("Sem rede — pulando clone de skills (usando cache/bundle)")
        # ainda copia o que já existe em /tmp/skill_*
        for src, dest_name in SKILL_MAPPINGS:
            dest = os.path.join(SKILLS_DIR, dest_name)
            if os.path.exists(src):
                if os.path.exists(dest):
                    shutil.rmtree(dest)
                try:
                    shutil.copytree(src, dest, dirs_exist_ok=True)
                except Exception:
                    pass
        return

    progress(3, 4, "Clonando repositórios de skills (em paralelo)...")
    os.makedirs(SKILLS_DIR, exist_ok=True)

    failed_skills: list[str] = []

    with ThreadPoolExecutor(max_workers=8) as pool:
        fut = {
            pool.submit(_clone_or_pull, repo, name): name
            for repo, name, _ in SKILL_REGISTRY
        }
        for f in as_completed(fut):
            if not f.result():
                failed_skills.append(fut[f])

    # Verificar skills essenciais
    for skill_name in failed_skills:
        if skill_name in ESSENTIAL_SKILLS:
            logger.warning(
                "Skill essencial '%s' falhou ao clonar. "
                "Algumas funcionalidades podem não estar disponíveis.",
                skill_name,
            )

    # Copiar para o diretório do agente
    for src, dest_name in SKILL_MAPPINGS:
        dest = os.path.join(SKILLS_DIR, dest_name)
        if os.path.exists(src):
            if os.path.exists(dest):
                shutil.rmtree(dest)
            shutil.copytree(src, dest, dirs_exist_ok=True)


# ── Etapa 3.1: Skills personalizadas do usuário (v0.6.18) ────

def _is_valid_skill_dir(path: str) -> bool:
    """Verifica se a pasta é uma skill OpenCode válida (contém SKILL.md)."""
    return os.path.isfile(os.path.join(path, "SKILL.md"))


def setup_custom_skills() -> list[str]:
    """Carrega as skills personalizadas do usuário a cada boot.

    Origem:  <base>/backups/skills-personalizadas/<nome-da-skill>/SKILL.md
             (base = PesquisAI no Drive no Colab · ~/PesquisAI offline)
    Destino: SKILLS_DIR (mesmo diretório das skills oficiais, lido pelo
             OpenCode ao iniciar a sessão do agente).

    - Cria a pasta (com README explicativo) se não existir;
    - Só copia subpastas que contêm SKILL.md (validação fail-closed);
    - Nunca falha o boot: erros vão para o logger.
    """
    from .constants import custom_skills_dir

    loaded: list[str] = []
    try:
        custom_dir = custom_skills_dir()
        os.makedirs(custom_dir, exist_ok=True)
        readme = os.path.join(custom_dir, "README.md")
        if not os.path.exists(readme):
            with open(readme, "w", encoding="utf-8") as f:
                f.write(
                    "# 🧩 Skills personalizadas\n\n"
                    "Coloque aqui suas skills próprias do UFVAI/OpenCode.\n\n"
                    "## Como funciona\n\n"
                    "- Cada skill deve ficar em uma **subpasta** contendo um arquivo "
                    "`SKILL.md` com frontmatter `name` e `description`.\n"
                    "- Elas são carregadas automaticamente **a cada inicialização** do "
                    "UFVAI, junto com as skills oficiais.\n"
                    "- Ao pedir para o agente criar uma nova skill, ele salva "
                    "automaticamente nesta pasta.\n\n"
                    "## Exemplo de estrutura\n\n"
                    "```\n"
                    "skills-personalizadas/\n"
                    "├── minha-skill/\n"
                    "│   └── SKILL.md\n"
                    "└── outra-skill/\n"
                    "    ├── SKILL.md\n"
                    "    └── scripts/\n"
                    "```\n"
                )
        os.makedirs(SKILLS_DIR, exist_ok=True)
        for entry in sorted(os.listdir(custom_dir)):
            src = os.path.join(custom_dir, entry)
            if entry.startswith(".") or entry == "README.md":
                continue
            if not os.path.isdir(src) or not _is_valid_skill_dir(src):
                if not entry.endswith(".md"):
                    logger.info(
                        "Skill personalizada '%s' ignorada: sem SKILL.md", entry
                    )
                continue
            dest = os.path.join(SKILLS_DIR, entry)
            try:
                if os.path.exists(dest):
                    shutil.rmtree(dest)
                shutil.copytree(src, dest)
                loaded.append(entry)
            except Exception as exc:
                logger.warning(
                    "Falha ao carregar skill personalizada '%s': %s", entry, exc
                )
        if loaded:
            logger.info("Skills personalizadas carregadas: %s", ", ".join(loaded))
    except Exception as exc:
        logger.warning("Skills personalizadas: falha geral (%s) — seguindo boot", exc)
    return loaded


# ── Etapa 3.5: Obsidian Vault (autopilot) ─────────────────────

def setup_obsidian_vault() -> None:
    """Inicializa o vault do Obsidian no Google Drive (autopilot).

    Cria a estrutura de pastas, a daily note de hoje, o MOC raiz,
    e inicia a sessão de log automático. Tudo é no-op se falhar.
    v0.6.7: sem prints — o estado é visível na interface; falha vai
    para o logger e o boot continua sem memória.
    """
    try:
        from pesquisai.obsidian.autopilot import auto_init
        auto_init()
    except Exception as exc:
        logger.warning("Obsidian memory: falha ao inicializar (%s) — continuando sem memória", exc)


# ── Etapa 4: Launch ───────────────────────────────────────────


def seed_ufvai_greeting(
    session_id,
    greeting,
    model=None,
    timeout_s=25.0,
    opencode_bin=None,
    env=None,
):
    """Envia a saudação inicial na sessão ja pinned ao UFVAI (best-effort)."""
    import os as _os
    import shutil
    import subprocess
    bin_path = opencode_bin
    if not bin_path:
        bin_path = shutil.which("opencode") or "/root/.opencode/bin/opencode"
    run_env = env if isinstance(env, dict) else dict(_os.environ)
    # Verifica disponibilidade do "big pickle free" (OpenCode Zen).
    if model is None:
        try:
            listed = subprocess.run(
                [bin_path, "models"], capture_output=True, text=True,
                timeout=10, env=run_env,
            ).stdout or ""
            if "opencode/big-pickle" in listed:
                model = "opencode/big-pickle"
            else:
                model = None
        except Exception:
            model = None
    try:
        cmd = [bin_path, "run", "--session", str(session_id)]
        if model:
            cmd += ["--model", str(model)]
        cmd += [greeting]
        result = subprocess.run(cmd,
            capture_output=True, text=True, timeout=timeout_s,
            cwd=_os.getcwd(), env=run_env,
        )
        return result.returncode == 0
    except Exception:
        return False



def setup_launch(folder_path: str, drive_url: str) -> str:
    """Inicia os servidores e a interface web.

    Returns:
        URL do banner de acesso.
    """
    progress(4, 4, "Iniciando servidores e interface web...")
    from pesquisai import launch_app as _la
    from pesquisai.launch_app import launch, set_drive_info, show_ready_message, show_launch_button
    set_drive_info(folder_path, drive_url)
    banner_url = launch()
    progress_finish()
    # v0.6.7: no Colab o card final (logomarca + botão) substitui o antigo
    # badge verde "✨ UFVAI pronto!"; fora do Colab mantém o print legado.
    if not getattr(_la, "IN_COLAB", False):
        show_ready_message()
    show_launch_button(banner_url)
    # v0.6.21 — o teste de cookies é a ÚLTIMA coisa exibida. O botão
    # "ABRIR O UFVAI" já está na tela e o bloco de diagnóstico fecha o fluxo com
    # o veredito real (✅ liberados / ❌ bloqueados). Fora do Colab devolve
    # 'skipped'. ensure_cookie_check() é idempotente: se outro caminho já
    # mostrou o bloco (notebook), aqui não repete.
    from .colab_cookies import ensure_cookie_check
    cookie_state = ensure_cookie_check()
    if cookie_state.get("state") == "error":
        logger.warning("Teste de cookies indisponível: %s", cookie_state.get("error"))
    return banner_url


# ── Orquestrador ──────────────────────────────────────────────

def _offline_keep_alive(banner_url: str) -> None:
    """v0.6.3: mantém o processo vivo no modo offline (.deb/local).

    O servidor HTTP do wrapper roda em thread daemon; se run() retornasse,
    o interpretador encerraria o processo e a porta 8001 cairia logo após a
    inicialização (ERR_CONNECTION_REFUSED). No Colab o kernel permanece vivo,
    então isto só se aplica fora dele.

    Desabilitar (scripts/testes): export UFVAI_NO_KEEPALIVE=1
    """
    import signal

    def _sigterm(_sig, _frm):
        # Encerramento limpo via `kill <pid>` (launcher grava o PID)
        print("\n👋 UFVAI encerrado (SIGTERM).")
        raise SystemExit(0)

    try:
        signal.signal(signal.SIGTERM, _sigterm)
    except Exception:
        pass

    print()
    print("🧬 UFVAI rodando em segundo plano nesta máquina.")
    print(f"   Interface: {banner_url}  ·  Terminal: http://localhost:{TERMINAL_PORT}")
    if os.environ.get("UFVAI_NO_KEEPALIVE", "").strip().lower() in ("1", "true", "yes", "on"):
        print("ℹ️  UFVAI_NO_KEEPALIVE=1 — processo NÃO será mantido vivo.")
        return
    print("   Para encerrar (foreground): Ctrl+C  ·  (background): kill $(cat ~/PesquisAI/pesquisai.pid)")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("\n👋 Encerrando UFVAI… até a próxima! 🧬")


def run() -> None:
    """Orquestrador principal do PesquisAI.

    Sequência: Drive → Dependências → Skills → Obsidian vault → Launch.
    v0.6.7: nenhuma saída textual — todo o feedback visual vem do painel
    de boot da logomarca (_BootPanel), do clone até os 100% + botão.
    v0.6.9-5: offline ganha tela instantânea 8002 (sem alterar Colab).
    """
    # v0.6.9-5: só offline — tela instantânea antes de tudo (não afeta Colab)
    _loading_server = None
    if not os.path.isdir("/content/drive"):
        try:
            from .launch_app import IN_COLAB as _ic
            if not _ic:
                _loading_server = _early_loading_screen()
        except Exception:
            _loading_server = None

    progress(0, 4, "Preparando...")

    # v0.6.7: o banner textual "🧑‍🔬 PESQUISAI (MODO RÁPIDO)" foi aposentado —
    # o painel de boot da logomarca (display "ufvai_boot_panel") já comunica
    # marca, versão e progresso desde o primeiro segundo do carregamento.

    folder_path, drive_url = setup_drive()
    setup_dependencies()
    setup_skills()
    setup_custom_skills()  # v0.6.18: skills personalizadas do usuário
    setup_obsidian_vault()
    banner_url = setup_launch(folder_path, drive_url)

    # v0.6.9-5: desliga tela de carregamento após wrapper subir (carência 6s)
    if _loading_server is not None:
        try:
            time.sleep(6)
            _loading_server.shutdown()
            _loading_server.server_close()
        except Exception:
            pass

    # v0.6.3: fora do Colab, mantém o processo vivo para que a interface
    # continue acessível (threads daemon morreriam com o fim de run()).
    if not os.path.isdir("/content/drive"):
        from .launch_app import IN_COLAB as _in_colab
        if not _in_colab:
            _offline_keep_alive(banner_url)


if __name__ == "__main__":
    run()
