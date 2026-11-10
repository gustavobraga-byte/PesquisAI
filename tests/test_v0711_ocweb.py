"""Testes da variante web (v0.7.11-web).

Cobrem o proxy que publica a SPA do OpenCode com autenticação injetada e o
tema do UFVAI, e a troca do iframe do ttyd pela URL do proxy no wrapper.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pesquisai import ocweb
from pesquisai import launch_app_responsive_v041 as wrapper_mod
from pesquisai.launch_app_responsive_v041 import create_wrapper_html


@pytest.fixture(autouse=True)
def _isolate_wrapper_dir(monkeypatch, tmp_path):
    """``create_wrapper_html`` grava em ``WRAPPER_DIR`` (padrão /tmp).

    Sem isolar, rodar os testes sobrescreve o ``index.html`` da interface em
    execução — foi o que devolveu o wrapper para ``localhost:8000`` durante a
    validação da variante web.
    """
    monkeypatch.setattr(wrapper_mod, "WRAPPER_DIR", str(tmp_path), raising=False)


def test_service_info_reads_url_and_password(monkeypatch, tmp_path):
    path = tmp_path / "service.json"
    path.write_text(
        json.dumps({"url": "http://127.0.0.1:45999", "password": "segredo"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(ocweb, "service_file", lambda: path)
    assert ocweb.service_info() == ("127.0.0.1", 45999, "segredo")


def test_service_info_missing_file(monkeypatch):
    monkeypatch.setattr(ocweb, "service_file", lambda: Path("/nao/existe.json"))
    host, port, password = ocweb.service_info()
    assert host == "127.0.0.1"
    assert port == 0
    assert password == ""


def test_basic_auth_header():
    import base64

    raw = base64.b64decode(ocweb._basic("abc").split(" ", 1)[1]).decode()
    assert raw == "opencode:abc"


def test_inject_html_adds_theme_badge_and_title():
    html = (
        b"<html><head><title data-sm>OpenCode</title></head>"
        b"<body><div id='root'></div></body></html>"
    )
    out = ocweb._inject_html(html).decode("utf-8")
    assert "UFVAI · OpenCode" in out
    assert "ufvai-ocweb-theme" in out
    assert "ufvai-oc-badge" in out
    assert '<script src="/__ufvai/boot.js"></script>' in out
    assert out.index("ufvai-ocweb-theme") < out.index("</head>")


def test_inject_html_adds_theme_once():
    out = ocweb._inject_html(b"<html><head></head><body></body></html>")
    assert out.count(b"ufvai-ocweb-theme") == 1


def test_ready_false_without_service(monkeypatch):
    monkeypatch.setattr(ocweb, "service_file", lambda: Path("/nao/existe.json"))
    assert ocweb.ready(65530, timeout=0.05) is False


def test_status_without_server(monkeypatch):
    monkeypatch.setattr(ocweb, "service_file", lambda: Path("/nao/existe.json"))
    st = ocweb.status()
    assert st["running"] is False
    assert st["upstream_ready"] is False


def test_wrapper_web_mode_uses_ocweb_ready():
    html = create_wrapper_html(
        "http://localhost:8002", "https://drive.google.com/x", web_mode=True
    )
    assert "/api/ocweb_ready" in html
    assert "{__READY_URL__}" not in html
    assert "http://localhost:8002" in html


def test_wrapper_toggle_terminal_web():
    html = create_wrapper_html(
        "https://8002-x/", "https://drive.google.com/x",
        web_mode=True, ttyd_url="https://8000-x/",
    )
    assert 'id="console-toggle"' in html
    assert "toggleConsole()" in html
    assert "https://8000-x/" in html
    assert '"console.toggle"' in html
    assert "Alternar terminal / versão web" in html
    assert "ufvai-theme" in html
    assert "theme.web_applied" in html


def test_proxy_has_large_accept_backlog():
    assert ocweb._Server.request_queue_size >= 64


def test_sse_event_persists_current_session(monkeypatch, tmp_path):
    target = tmp_path / "current-session"
    active = tmp_path / "active-session"
    monkeypatch.setattr(ocweb, "CURRENT_SESSION_FILE", str(target))
    monkeypatch.setattr(ocweb, "ACTIVE_SESSION_FILE", str(active))
    raw = (
        b'data: {"type":"session.execution.started",'
        b'"data":{"sessionID":"ses_teste123"}}\n\n'
    )
    ocweb._sync_session_from_event(raw)
    assert target.read_text(encoding="utf-8") == "ses_teste123"
    assert json.loads(active.read_text(encoding="utf-8"))["sid"] == "ses_teste123"


def test_current_active_age(monkeypatch, tmp_path):
    active = tmp_path / "active.json"
    monkeypatch.setattr(ocweb, "ACTIVE_SESSION_FILE", str(active))
    active.write_text(json.dumps({"sid": "ses_x", "ts": 0}), encoding="utf-8")
    sid, age = ocweb.current_active()
    assert sid == "ses_x"
    assert age >= 0


def test_boot_js_waits_for_catalog():
    assert "/__ufvai/catalog" in ocweb._BOOT_JS
    assert "fallback=1" in ocweb._BOOT_JS


def test_boot_js_syncs_theme():
    assert "ufvai-theme" in ocweb._BOOT_JS
    assert "opencode-color-scheme" in ocweb._BOOT_JS


def test_catalog_response_falls_back_when_empty(monkeypatch):
    monkeypatch.setattr(
        ocweb, "_global_rows",
        lambda kind, ttl=30.0: [{"id": "global"}] if kind == "model" else [{"id": "prov"}],
    )
    data, status = ocweb._catalog_response("model", b'{"data": []}', 200)
    assert status == 200
    assert json.loads(data)["data"] == [{"id": "global"}]

    data, status = ocweb._catalog_response("provider", b"<html>erro</html>", 500)
    assert status == 200
    assert json.loads(data)["data"] == [{"id": "prov"}]


def test_catalog_response_preserves_non_empty(monkeypatch):
    monkeypatch.setattr(ocweb, "_global_rows", lambda kind, ttl=30.0: [{"id": "global"}])
    raw = b'{"data": [{"id": "real"}]}'
    data, status = ocweb._catalog_response("model", raw, 200)
    assert status == 200
    assert json.loads(data)["data"] == [{"id": "real"}]


def test_brand_new_session_title(monkeypatch):
    raw = json.dumps({"data": {"id": "ses_x", "title": None}}).encode()
    out, sid = ocweb._brand_new_session(raw)
    assert sid == "ses_x"
    assert json.loads(out)["data"]["title"] == "UFVAI"

    raw = json.dumps({"data": {"id": "ses_y", "title": "opencode"}}).encode()
    out, sid = ocweb._brand_new_session(raw)
    assert sid == "ses_y"
    assert json.loads(out)["data"]["title"] == "UFVAI"

    raw = json.dumps({"data": {"id": "ses_z", "title": "Minha pesquisa"}}).encode()
    out, sid = ocweb._brand_new_session(raw)
    assert sid == ""
    assert json.loads(out)["data"]["title"] == "Minha pesquisa"


def test_wrapper_default_keeps_ttyd_ready():
    html = create_wrapper_html("http://localhost:8000", "https://drive.google.com/x")
    assert "/api/ttyd_ready" in html
    assert "{__READY_URL__}" not in html


def test_health_endpoint_reports_ready(monkeypatch, tmp_path):
    """``/__ufvai_ready`` responde JSON com CORS (health-check do boot)."""
    import socket
    import urllib.request

    upstream = socket.socket()
    upstream.bind(("127.0.0.1", 0))
    upstream.listen(1)
    upstream_port = upstream.getsockname()[1]

    service = tmp_path / "service.json"
    service.write_text(
        json.dumps({"url": f"http://127.0.0.1:{upstream_port}", "password": "x"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(ocweb, "service_file", lambda: service)

    assert ocweb.start(0) is True
    port = ocweb.status()["proxy_port"]
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/__ufvai_ready", timeout=5
        ) as response:
            body = json.loads(response.read())
            assert response.status == 200
            assert body["ready"] is True
            assert body["proxy"] == "ufvai-ocweb"
            assert response.headers.get("Access-Control-Allow-Origin") == "*"

        with urllib.request.urlopen(f"http://127.0.0.1:{port}/__ufvai/session", timeout=5) as r:
            assert "sid" in json.loads(r.read())
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/__ufvai/boot.js", timeout=5) as r:
            assert b"/server/" in r.read()
    finally:
        ocweb.stop()
        upstream.close()


def test_wrapper_writes_only_to_isolated_dir(tmp_path):
    """Garante que a suíte não toca no /tmp/pesquisai-wrapper em uso."""
    live = Path("/tmp/pesquisai-wrapper/index.html")
    before = live.read_bytes() if live.exists() else None

    create_wrapper_html("http://localhost:8002", "https://drive.google.com/x", web_mode=True)

    assert (tmp_path / "index.html").exists()
    after = live.read_bytes() if live.exists() else None
    assert after == before, "create_wrapper_html gravou fora do diretório isolado"


def test_install_sync_plugin(tmp_path):
    from pesquisai.tui_sync import install_sync_plugin
    root = install_sync_plugin(str(tmp_path / "plugin"))
    assert (Path(root) / "tui.tsx").exists()
    assert (Path(root) / "package.json").exists()
    assert "ufvai-sync" in (Path(root) / "package.json").read_text(encoding="utf-8")


def test_boot_cell_uses_its_own_web_tree():
    """A célula de boot não pode copiar a árvore sem a interface web."""
    boot = Path(__file__).resolve().parents[1] / "COLAB_BOOT_0.7.11.py"
    text = boot.read_text(encoding="utf-8")
    assert "UFVAI-v0.7.11-web" in text
    assert 'os.path.join(_here, "pesquisai", "ocweb.py")' in text
    assert "_porta_ocupada(8001)" in text
    # não pode sobrar a cópia fixa da árvore antiga
    assert 'SRC = "/content/drive/My Drive/PesquisAI/UFVAI-v0.7.11"\n' not in text

# ── v0.7.11-web9: foco da TUI → web por push (SSE) ────────────────────────

def test_focus_watcher_publishes_changes(monkeypatch, tmp_path):
    """O observador lê FOCUS_FILE e publica a sessão na fila dos assinantes."""
    import queue
    import threading
    import time

    focus = tmp_path / "focus.json"
    monkeypatch.setattr(ocweb, "FOCUS_FILE", str(focus))
    stop = threading.Event()
    monkeypatch.setattr(ocweb, "_FOCUS_STOP", stop)
    sub: queue.Queue = queue.Queue()
    with ocweb._LIVE_LOCK:
        ocweb._LIVE_SUBS.add(sub)
    thread = threading.Thread(target=ocweb._watch_focus, daemon=True)
    thread.start()
    try:
        now = int(time.time() * 1000)
        focus.write_text(json.dumps({"sid": "ses_a", "ts": now}), encoding="utf-8")
        msg = json.loads(sub.get(timeout=4))
        assert msg["sid"] == "ses_a"
        assert msg["source"] == "tui"
    finally:
        stop.set()
        thread.join(timeout=3)
        with ocweb._LIVE_LOCK:
            ocweb._LIVE_SUBS.discard(sub)


def test_web_focus_is_written_atomically(monkeypatch, tmp_path):
    target = tmp_path / "web-focus.json"
    monkeypatch.setattr(ocweb, "WEB_FOCUS_FILE", str(target))
    assert ocweb.write_web_focus("ses_web") is True
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["sid"] == "ses_web"
    assert data["ts"] > 0
    assert ocweb.write_web_focus("") is False


def test_foco_da_tui_por_http_publica_na_hora(monkeypatch, tmp_path):
    """``apply_tui_focus`` grava o arquivo e empurra no SSE sem polling."""
    import queue

    monkeypatch.setattr(ocweb, "FOCUS_FILE", str(tmp_path / "focus.json"))
    monkeypatch.setattr(ocweb, "CURRENT_SESSION_FILE", str(tmp_path / "cur"))
    sub: queue.Queue = queue.Queue()
    with ocweb._LIVE_LOCK:
        ocweb._LIVE_SUBS.add(sub)
    try:
        assert ocweb.apply_tui_focus("ses_http", "session") is True
        msg = json.loads(sub.get(timeout=1))
        assert msg["sid"] == "ses_http" and msg["source"] == "tui"
        data = json.loads((tmp_path / "focus.json").read_text(encoding="utf-8"))
        assert data["sid"] == "ses_http"
        assert data["source"] == "tui"
        assert (tmp_path / "cur").read_text(encoding="utf-8") == "ses_http"
    finally:
        with ocweb._LIVE_LOCK:
            ocweb._LIVE_SUBS.discard(sub)


def test_boot_js_reporta_navegacao_do_usuario_na_hora():
    """pushState/replaceState/popstate publicam o foco imediatamente."""
    js = ocweb._BOOT_JS
    assert "history.pushState=function" in js
    assert "history.replaceState=function" in js
    assert 'addEventListener("popstate"' in js
    assert "reportFocus()" in js


def test_boot_js_follows_focus_by_push():
    """A web segue o foco por EventSource; o polling é só reserva."""
    js = ocweb._BOOT_JS
    assert "/__ufvai/live" in js
    assert "EventSource" in js
    assert "function navTo" in js
    assert "/__ufvai/focus" in js          # web → terminal
    assert js.count("setInterval") >= 2     # reserva + relato de foco


def test_sync_plugin_publishes_router_state():
    from pesquisai import tui_sync

    js = tui_sync.SYNC_PLUGIN_TUI_TS
    assert "context.ui.router.current" in js
    assert "context.ui.router.navigate" in js
    assert "/tmp/ufvai-focus.json" in js
    assert "/tmp/ufvai-web-focus.json" in js
    assert "renameSync" in js              # gravação atômica
    # v0.7.11-web12: caminho rápido por HTTP (sem esperar o polling do arquivo)
    assert "__ufvai/focus" in js
    assert "postFocus" in js
    assert "PUBLISH_MS = 100" in js


def test_live_endpoint_serves_focus_and_pushes(monkeypatch, tmp_path):
    """``/__ufvai/live`` entrega o estado atual e os pushes seguintes."""
    import http.client
    import socket
    import threading
    import time

    focus = tmp_path / "focus.json"
    agora = int(time.time() * 1000)
    focus.write_text(json.dumps({"sid": "ses_um", "ts": agora}), encoding="utf-8")
    monkeypatch.setattr(ocweb, "FOCUS_FILE", str(focus))
    monkeypatch.setattr(ocweb, "WEB_FOCUS_FILE", str(tmp_path / "web.json"))
    upstream = socket.socket()
    upstream.bind(("127.0.0.1", 0))
    upstream.listen(1)
    service = tmp_path / "service.json"
    service.write_text(
        json.dumps({"url": f"http://127.0.0.1:{upstream.getsockname()[1]}", "password": "x"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(ocweb, "service_file", lambda: service)

    assert ocweb.start(0) is True
    port = ocweb.status()["proxy_port"]
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    buffer: list[bytes] = []
    try:
        conn.request("GET", "/__ufvai/live")
        resp = conn.getresponse()
        assert resp.status == 200
        assert "text/event-stream" in resp.getheader("Content-Type", "")

        def _reader() -> None:
            try:
                while True:
                    chunk = resp.read(1)
                    if not chunk:
                        return
                    buffer.append(chunk)
            except Exception:  # noqa: BLE001
                return

        reader = threading.Thread(target=_reader, daemon=True)
        reader.start()

        def _wait(needle: bytes, timeout: float = 6.0) -> bool:
            deadline = time.time() + timeout
            while time.time() < deadline:
                if needle in b"".join(buffer):
                    return True
                time.sleep(0.05)
            return False

        assert _wait(b"ses_um"), b"".join(buffer)[:400]
        focus.write_text(
            json.dumps({"sid": "ses_dois", "ts": int(time.time() * 1000)}),
            encoding="utf-8",
        )
        assert _wait(b"ses_dois"), b"".join(buffer)[:400]

        # web → terminal: grava o foco escolhido no navegador
        body = json.dumps({"sid": "ses_web", "ts": 3}).encode()
        conn2 = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn2.request("POST", "/__ufvai/focus", body=body,
                      headers={"Content-Type": "application/json"})
        assert conn2.getresponse().status == 204
        conn2.close()
        assert json.loads((tmp_path / "web.json").read_text(encoding="utf-8"))["sid"] == "ses_web"
    finally:
        conn.close()
        ocweb.stop()
        upstream.close()


# ── v0.7.11-web10: compressão, agregação de páginas e pré-busca ───────────

def test_accept_encoding_negotiation():
    class Stub:
        def __init__(self, value):
            self.headers = {"Accept-Encoding": value}

    negotiate = ocweb._Handler._accept_encoding
    assert negotiate(Stub("gzip, deflate, br")) == "gzip, deflate"
    assert negotiate(Stub("deflate")) == "deflate"
    assert negotiate(Stub("br")) == "identity"
    assert negotiate(Stub("")) == "identity"


def test_is_message_first_page():
    ok = "/api/session/ses_1/message?limit=200&order=asc"
    assert ocweb._is_message_first_page(ok)
    assert ocweb._is_message_first_page(ok + "&type=user")
    assert not ocweb._is_message_first_page(ok + "&cursor=abc")
    assert not ocweb._is_message_first_page(
        "/api/session/ses_1/message?limit=20&order=asc"
    )
    assert not ocweb._is_message_first_page(
        "/api/session/ses_1/message?limit=200&order=desc"
    )
    assert not ocweb._is_message_first_page("/api/session/ses_1")


def test_aggregate_message_pages_merges_cursor_pages(monkeypatch):
    from urllib.parse import parse_qs, urlparse

    pages = {
        None: {"data": [{"id": "m1"}, {"id": "m2"}], "cursor": {"previous": "p", "next": "c1"}},
        "c1": {"data": [{"id": "m3"}], "cursor": {"previous": "x", "next": "c2"}},
        "c2": {"data": [], "cursor": {"previous": "y", "next": None}},
    }
    chamadas: list[dict] = []

    def fake(path, timeout=30.0, extra_headers=None):
        cursor = parse_qs(urlparse(path).query).get("cursor", [None])[0]
        chamadas.append({"path": path, "headers": extra_headers})
        return 200, json.dumps(pages[cursor]).encode("utf-8")

    monkeypatch.setattr(ocweb, "_get_upstream", fake)
    first = json.dumps(pages[None]).encode("utf-8")
    agregado = ocweb.aggregate_message_pages(
        "/api/session/ses_1/message?limit=200&order=asc",
        first,
        extra_headers={"x-opencode-directory": "x"},
    )
    payload = json.loads(agregado)
    assert [m["id"] for m in payload["data"]] == ["m1", "m2", "m3"]
    assert payload["cursor"]["next"] is None
    assert payload["cursor"]["previous"] == "p"
    # o cursor não pode ser reenviado junto com `order` (o motor devolve 400)
    assert all("order=" not in c["path"] for c in chamadas)
    assert chamadas[0]["headers"] == {"x-opencode-directory": "x"}


def test_prefetch_session_is_single_use(monkeypatch):
    sid = "ses_prefetch"
    raw = json.dumps({"data": [{"id": "m1"}], "cursor": {"next": None}}).encode()
    monkeypatch.setattr(
        ocweb, "_LAST_DIRECTORY", {"value": "/tmp/proj", "header": "%2Ftmp%2Fproj"}
    )
    monkeypatch.setattr(ocweb, "_get_upstream", lambda *a, **k: (200, raw))
    with ocweb._PREFETCH_LOCK:
        ocweb._PREFETCH.clear()
        ocweb._PREFETCH_READY.clear()
    ocweb.prefetch_session(sid)
    path = f"/api/session/{sid}/message?limit=200&order=asc"
    hit = ocweb.take_prefetch(path, "/tmp/proj")
    assert hit is not None and hit[0] == raw
    # uso único: a segunda requisição volta ao motor
    assert ocweb.take_prefetch(path, "/tmp/proj") is None


def test_prefetch_rejects_other_directory(monkeypatch):
    sid = "ses_prefetch_dir"
    raw = json.dumps({"data": [], "cursor": {"next": None}}).encode()
    monkeypatch.setattr(
        ocweb, "_LAST_DIRECTORY", {"value": "/tmp/proj", "header": "%2Ftmp%2Fproj"}
    )
    monkeypatch.setattr(ocweb, "_get_upstream", lambda *a, **k: (200, raw))
    with ocweb._PREFETCH_LOCK:
        ocweb._PREFETCH.clear()
        ocweb._PREFETCH_READY.clear()
    ocweb.prefetch_session(sid)
    path = f"/api/session/{sid}/message?limit=200&order=asc"
    assert ocweb.take_prefetch(path, "/tmp/outro") is None
    assert ocweb.take_prefetch(path, "/tmp/proj") is None  # já foi descartada


def test_boot_js_navega_sem_recarregar():
    js = ocweb._BOOT_JS
    assert "history.pushState" in js          # rota do SPA, sem reload
    assert "PopStateEvent" in js
    # v0.7.11-web9: se a SPA ignorar o popstate, compara o conteúdo de <main>
    # antes/depois e só então recarrega.
    assert "function mainText" in js
    can_nav = js.split("function canNav", 1)[1].split("function navTo", 1)[0]
    # texto do corpo não bloqueia mais a sincronização (o comentário pode
    # citar o termo; o que não pode existir é a checagem no código)
    assert "(Working|Trabalhando)" not in can_nav
    assert "document.body.innerText" not in can_nav


def test_boot_js_usa_chave_da_propria_origem():
    """A rota /server/<key> precisa usar o base64url da origem.

    Com a URL do motor, a SPA não encontra o servidor registrado e a sessão
    abre em branco (regressão observada em 09/11/2026).
    """
    js = ocweb._BOOT_JS
    assert "function originKey" in js
    assert "b64(location.origin)" in js
    assert '"/server/"+originKey()' in js


def test_boot_js_nao_devolve_push_ao_terminal():
    """Push do terminal não volta como foco (evita ping-pong TUI ↔ web)."""
    js = ocweb._BOOT_JS
    assert "function markPush" in js
    assert "ufvai-pushed" in js
    assert "wasPushed" in js


def test_boot_js_reporta_foco_inicial():
    """Ao abrir a web numa sessão, o terminal passa a seguir essa sessão."""
    js = ocweb._BOOT_JS
    bloco = js.split("function reportFocus", 1)[1]
    assert "var first=!_reported;" in bloco
