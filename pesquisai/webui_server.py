"""webui_server.py — servidor da **nova** versão web do UFVAI (v0.7.11-web17).

Substitui a pilha antiga (SPA do OpenCode injetada + ``boot.js`` + watchdog de
recarregamento) por três peças simples e explícitas:

1. **Cliente novo** (``pesquisai/webui/``) — HTML/CSS/JS escritos do zero, sem
   dependências externas e sem build.
2. **Contrato** (``pesquisai/webapi.py``) — tradução da API do motor para um
   formato pequeno e estável.
3. **Este servidor** — serve o cliente, expõe o contrato em ``/api/ufvai/*`` e
   reencaminha o stream de eventos do motor (SSE) já normalizado.

O navegador nunca recebe a senha do motor: a autenticação Basic é feita aqui.
"""

from __future__ import annotations

import importlib
import json
import os
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse

from . import explorer, webapi
from .constants import FOCUS_FILE, WEB_FOCUS_FILE

WEBUI_DIR = Path(__file__).resolve().parent / "webui"
DEFAULT_PORT = 8002
STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".json": "application/json; charset=utf-8",
    ".ico": "image/x-icon",
    ".png": "image/png",
    ".woff2": "font/woff2",
}

_SERVER: ThreadingHTTPServer | None = None
_THREAD: threading.Thread | None = None
_LOCK = threading.Lock()

# Foco compartilhado entre TUI e web (mesmo formato de arquivo do plugin TUI).
_FOCUS: dict[str, Any] = {"seq": int(time.time() * 1000), "sid": "", "source": "", "ts": 0}
_FOCUS_LOCK = threading.Lock()
_FOCUS_SUBS: set = set()


# ── foco (TUI ↔ web) ─────────────────────────────────────────────────────────

def _read_json_file(path: str) -> dict:
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _write_json_file(path: str, payload: dict) -> bool:
    tmp = f"{path}.{os.getpid()}.{threading.get_ident()}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        os.replace(tmp, path)
        return True
    except OSError:
        return False


def focus_state() -> dict:
    """Foco atual (TUI tem prioridade; web é a reserva)."""
    with _FOCUS_LOCK:
        snap = dict(_FOCUS)
    tui = _read_json_file(FOCUS_FILE)
    if tui.get("sid") and int(tui.get("ts") or 0) >= int(snap.get("ts") or 0):
        snap["sid"] = str(tui.get("sid"))
        snap["source"] = "tui"
        snap["ts"] = int(tui.get("ts") or 0)
    return snap


def set_focus(sid: str, source: str) -> dict:
    """Registra uma troca de sessão e propaga aos assinantes."""
    sid = str(sid or "").strip()
    if not sid:
        return {}
    with _FOCUS_LOCK:
        _FOCUS["seq"] = int(_FOCUS["seq"]) + 1
        _FOCUS["sid"] = sid
        _FOCUS["source"] = source
        _FOCUS["ts"] = int(time.time() * 1000)
        snap = dict(_FOCUS)
    if source == "web":
        _write_json_file(
            WEB_FOCUS_FILE,
            {"sid": sid, "seq": snap["seq"], "ts": snap["ts"], "source": "web"},
        )
    else:
        _write_json_file(
            FOCUS_FILE,
            {"sid": sid, "ts": snap["ts"], "route": "session", "source": "tui"},
        )
    return snap


# ── rotas ────────────────────────────────────────────────────────────────────

def _bootstrap() -> dict:
    """Estado inicial do cliente: agentes, modelos, sessões, motor."""
    agents = webapi.agents()
    catalog = webapi.catalog()
    sess = webapi.sessions()
    active = webapi.active_sessions()
    directory = sess[0]["directory"] if sess else ""
    current = None
    for row in sess:
        if row["id"] in active:
            current = row
            break
    default_agent = ""
    for agent in agents:
        if agent["id"].upper() == "UFVAI":
            default_agent = agent["id"]
            break
    if not default_agent and agents:
        default_agent = agents[0]["id"]
    version = ""
    info = webapi.engine_json("/api/info", timeout=8)
    if isinstance(info, dict):
        version = str(info.get("version") or "")
    return {
        "engine": {"version": version, "ready": bool(webapi.engine()[1])},
        "directory": directory,
        "agents": agents,
        "commands": webapi.commands(),
        "sessions": sess,
        "active": active,
        "current": current,
        "defaultAgent": default_agent,
        "models": {
            "providers": catalog.get("providers", []),
            "models": catalog.get("models", []),
            "total": catalog.get("total", 0),
            "available": catalog.get("available", 0),
        },
        "serverTime": int(time.time() * 1000),
    }


def _handle_api(method: str, path: str, query: dict, body: dict) -> tuple[int, Any]:
    """Roteia ``/api/ufvai/*``. Devolve ``(status, payload)``."""
    parts = [p for p in path.split("/") if p]

    # /api/ufvai/<recurso>
    if len(parts) < 3 or parts[0] != "api" or parts[1] != "ufvai":
        return 404, {"error": "rota desconhecida"}
    resource = parts[2]

    if resource == "bootstrap" and method == "GET":
        return 200, _bootstrap()
    if resource == "models" and method == "GET":
        force = query.get("force", ["0"])[0] in ("1", "true")
        return 200, webapi.catalog(force=force)
    if resource == "sessions" and method == "GET" and len(parts) == 3:
        return 200, {"sessions": webapi.sessions(), "active": webapi.active_sessions()}
    if resource == "sessions" and method == "POST" and len(parts) == 3:
        row = webapi.create_session(
            title=body.get("title"),
            agent=body.get("agent"),
            model=body.get("model"),
            directory=body.get("directory"),
        )
        if not row:
            return 502, {"error": "não foi possível criar a sessão"}
        return 200, {"session": row}
    if resource == "focus" and method == "GET":
        return 200, focus_state()
    if resource == "focus" and method == "POST":
        return 200, {"focus": set_focus(str(body.get("sid") or ""), "web")}
    if resource == "commands" and method == "GET":
        lang = str(query.get("lang", [""])[0] or "")
        return 200, {
            "commands": webapi.commands(lang or None),
            "skills": webapi.skills(),
        }
    if resource == "explorer" and method == "GET" and len(parts) == 3:
        rel = str(query.get("path", [""])[0] or "")
        # v0.7.11-web28: com "q" o gateway devolve a BUSCA recursiva
        # (o filtro do explorador); sem "q", a listagem da pasta.
        needle = str(query.get("q", [""])[0] or "").strip()
        if needle:
            return 200, explorer.search(rel, needle)
        # v0.7.11-web44: ordenação escolhida no explorador
        # (name | name-desc | mtime | mtime-asc).
        order = str(query.get("sort", [""])[0] or "name").strip()
        return 200, explorer.listing(rel, sort=order)
    if resource == "explorer" and method == "GET" and len(parts) == 4 and parts[3] == "preview":
        rel = str(query.get("path", [""])[0] or "")
        return 200, explorer.preview(rel)
    if resource == "explorer" and method == "GET" and len(parts) == 4 and parts[3] == "resolve":
        # v0.7.11-web28: resolve a referência de arquivo citada na resposta
        name = str(query.get("name", [""])[0] or "")
        return 200, explorer.resolve(name)
    if resource == "explorer" and method == "POST" and len(parts) == 4 and parts[3] == "rename":
        # v0.7.11-web43: renomear arquivo/pasta do explorador (com validação
        # de raiz e de nome em explorer.rename).
        return 200, explorer.rename(
            str(body.get("path") or ""),
            str(body.get("name") or ""),
        )
    if resource == "explorer" and method == "POST" and len(parts) == 4 and parts[3] == "delete":
        # v0.7.11-web44: excluir arquivo/pasta do explorador (confirmação no
        # navegador; validação de raiz em explorer.delete).
        return 200, explorer.delete(str(body.get("path") or ""))
    if resource == "about" and method == "GET":
        return 200, webapi.about()
    if resource == "agent-state" and method == "GET":
        # v0.7.11-web30: estado do agente (ativo/ocioso) — o cabeçalho do
        # wrapper pergunta aqui (o wrapper pode estar numa versão antiga,
        # então o gateway é a fonte confiável).
        return 200, webapi.agent_state()
    if resource == "locale" and method == "GET":
        lang = str(query.get("lang", [""])[0] or "")
        return 200, webapi.locale_info(lang or None)
    if resource == "upload" and method == "POST":
        # v0.7.11-web23: anexo do navegador -> gravado em /tmp, com o
        # caminho absoluto devolvido (o agente precisa abrir o arquivo).
        result = webapi.save_upload(
            sid=str(body.get("sid") or ""),
            name=str(body.get("name") or ""),
            mime=str(body.get("mime") or ""),
            data_b64=str(body.get("data") or ""),
        )
        return (200 if result.get("ok") else 400), result
    if resource == "files" and method == "GET":
        directory = str(query.get("directory", [""])[0] or "")
        path = str(query.get("path", [""])[0] or "")
        search = str(query.get("query", [""])[0] or "")
        rows = (
            webapi.files_find(search, directory=directory)
            if search
            else webapi.files_list(path=path, directory=directory)
        )
        return 200, {"files": rows}
    if resource == "file" and method == "POST":
        # anexa um arquivo do projeto (data URI) ao próximo prompt
        path = str(body.get("path") or "")
        directory = str(body.get("directory") or "")
        if not path:
            return 400, {"error": "caminho vazio"}
        attachment = webapi.file_data_uri(path, directory=directory)
        if not attachment:
            return 404, {"error": "arquivo não encontrado ou ilegível"}
        return 200, {"file": attachment}

    # /api/ufvai/sessions/{sid}
    if resource == "sessions" and len(parts) == 4:
        sid = unquote(parts[3])
        row = webapi.session(sid)
        return (200 if row else 404), (row or {"error": "sessão inexistente"})

    # /api/ufvai/sessions/{sid}/<ação>
    if resource == "sessions" and len(parts) >= 5:
        sid = unquote(parts[3])
        action = parts[4]
        if action == "messages" and method == "GET":
            limit = int(query.get("limit", ["120"])[0] or 120)
            return 200, {"messages": webapi.messages(sid, limit=limit)}
        if action == "message" and method == "POST":
            text = str(body.get("text") or "").strip()
            files = body.get("files") or []
            if not text and not files:
                return 400, {"error": "mensagem vazia"}
            result = webapi.send_prompt(
                sid,
                text,
                files=files if isinstance(files, list) else None,
                agents=body.get("agents") if isinstance(body.get("agents"), list) else None,
                skills=body.get("skills") if isinstance(body.get("skills"), list) else None,
                uploads=body.get("uploads") if isinstance(body.get("uploads"), list) else None,
            )
            return (200 if result.get("ok") else 502), result
        if action == "context" and method == "GET":
            return 200, webapi.session_context(sid)
        if action == "usage" and method == "GET":
            return 200, webapi.context_usage(sid)
        if action == "diff" and method == "GET":
            return 200, webapi.session_diff(sid)
        if action == "finalize" and method == "POST":
            # {mode: 'archive' | 'delete'}
            result = webapi.finalize_session(sid, str(body.get("mode") or "archive"))
            return (200 if result.get("ok") else 502), result
        if action == "permission" and method == "GET":
            # pedidos de permissão pendentes da sessão
            return 200, {"permissions": webapi.pending_permissions(sid)}
        if action == "permission" and method == "POST":
            # {requestID, decision: once|always|reject}
            request_id = str(body.get("requestID") or body.get("id") or "")
            decision = str(body.get("decision") or "")
            if not request_id:
                return 400, {"error": "pedido de permissão vazio"}
            result = webapi.permission_reply(sid, request_id, decision)
            return (200 if result.get("ok") else 502), result
        if action == "form" and method == "GET":
            # v0.7.11-web38: formulários da ferramenta "question"
            return 200, {"forms": webapi.pending_forms(sid)}
        if action == "form" and method == "POST":
            # {formID, answer: {campo: valor}}
            form_id = str(body.get("formID") or body.get("id") or "")
            answer = body.get("answer") if isinstance(body.get("answer"), dict) else {}
            if not form_id:
                return 400, {"error": "formulário vazio"}
            result = webapi.form_reply(sid, form_id, answer)
            return (200 if result.get("ok") else 502), result
        if action == "revert" and method == "POST":
            # {messageID, files} — editar/regenerar (v0.7.11-web40)
            message_id = str(body.get("messageID") or body.get("id") or "")
            if not message_id:
                return 400, {"error": "mensagem vazia"}
            result = webapi.revert_to(sid, message_id, bool(body.get("files")))
            return (200 if result.get("ok") else 502), result
        if action == "memory" and method == "POST":
            # {text, title, tags} — salvar na Minha memória
            text = str(body.get("text") or "")
            title = str(body.get("title") or "")
            tags = body.get("tags") if isinstance(body.get("tags"), list) else None
            result = webapi.save_memory(text, title, tags)
            return (200 if result.get("ok") else 400), result
        if action == "fork" and method == "POST":
            result = webapi.fork_session(sid)
            return (200 if result.get("ok") else 502), result
        if action == "compact" and method == "POST":
            result = webapi.compact_session(sid)
            return (200 if result.get("ok") else 502), result
        if action == "background" and method == "POST":
            result = webapi.background_session(sid)
            return (200 if result.get("ok") else 502), result
        if action == "rename" and method == "POST":
            title = str(body.get("title") or "").strip()
            if not title:
                return 400, {"error": "título vazio"}
            result = webapi.rename_session(sid, title)
            return (200 if result.get("ok") else 502), result
        if action == "interrupt" and method == "POST":
            result = webapi.interrupt(sid)
            return (200 if result.get("ok") else 502), result
        if action == "model" and method == "POST":
            model = body.get("model") or {}
            result = webapi.set_model(sid, model)
            return (200 if result.get("ok") else 502), result
        if action == "agent" and method == "POST":
            agent = str(body.get("agent") or "").strip()
            if not agent:
                return 400, {"error": "agente vazio"}
            result = webapi.set_agent(sid, agent)
            return (200 if result.get("ok") else 502), result
        if action == "session" and method == "GET":
            row = webapi.session(sid)
            return (200 if row else 404), (row or {"error": "sessão inexistente"})

    return 404, {"error": "rota desconhecida"}


# ── handler HTTP ─────────────────────────────────────────────────────────────

class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "UFVAI-web/0.7.11"

    def log_message(self, *_args):  # silencioso
        return

    # -- utilidades --
    def _json(self, status: int, payload: Any, cors: bool = False) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        if cors:
            # v0.7.11-web30: o cabeçalho do wrapper (porta 8001) pergunta
            # o estado do agente ao gateway (outra origem) — sem este
            # cabeçalho o navegador bloqueia a leitura.
            self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def _static(self, name: str) -> None:
        target = (WEBUI_DIR / name).resolve()
        try:
            target.relative_to(WEBUI_DIR.resolve())
        except ValueError:
            self._json(403, {"error": "caminho bloqueado"})
            return
        if not target.exists() or not target.is_file():
            self._json(404, {"error": "não encontrado"})
            return
        data = target.read_bytes()
        ctype = STATIC_TYPES.get(target.suffix.lower(), "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        # v0.7.11-web20: sem cache — o cliente muda a cada iteração e um
        # index.html antigo no navegador quebrava o JavaScript.
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            return {}
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8", errors="replace"))
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}

    def _download(self, query: dict) -> None:
        """Baixa (ou exibe inline) um arquivo da pasta do agente."""
        rel = str(query.get("path", [""])[0] or "")
        inline = str(query.get("inline", ["0"])[0] or "").lower() in ("1", "true")
        data, _abs_path = explorer.read_bytes(rel)
        if data is None:
            self._json(404, {"error": "arquivo não encontrado"})
            return
        target = explorer.safe_path(rel)
        name = target.name if target else "arquivo"
        mime = "application/octet-stream"
        if target is not None:
            import mimetypes

            mime = mimetypes.guess_type(str(target))[0] or mime
        disposition = "inline" if inline else "attachment"
        try:
            safe_name = name.encode("ascii", "ignore").decode() or "arquivo"
            ascii_name = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in name) or "arquivo"
        except Exception:  # noqa: BLE001
            safe_name = ascii_name = "arquivo"
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header(
            "Content-Disposition",
            f"{disposition}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name)}",
        )
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    # -- rotas --
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = parse_qs(parsed.query)

        if path in ("/", "/index.html", "/web", "/web/"):
            self._static("index.html")
            return
        if path == "/health":
            self._json(200, status())
            return
        if path == "/api/ufvai/events":
            self._events(query)
            return
        if path == "/api/ufvai/explorer/download":
            # v0.7.11-web26: download (ou exibição inline) de um arquivo da
            # pasta do agente — resposta binária, não JSON.
            self._download(query)
            return
        if path == "/__ufvai/focus/stream":
            self._focus_stream()
            return
        if path == "/api/ufvai/focus" and query.get("stream", ["0"])[0] in ("1", "true"):
            self._focus_stream()
            return
        if path.startswith("/api/ufvai/"):
            try:
                status_code, payload = _handle_api("GET", path, query, {})
            except Exception as exc:  # noqa: BLE001
                status_code, payload = 500, {"error": str(exc)}
            # v0.7.11-web30: a rota de estado do agente é consultada pelo
            # cabeçalho do wrapper (outra origem) → precisa de CORS.
            self._json(status_code, payload, cors="agent-state" in path)
            return
        if path.startswith("/__ufvai/"):
            # compatibilidade com o plugin de sincronia do TUI
            if path == "/__ufvai/focus":
                self._json(200, focus_state())
                return
            self._json(404, {"error": "rota desconhecida"})
            return
        # estaticos do cliente (com subpastas, ex.: assets/logo.svg — o
        # guarda de travessia fica em _static)
        self._static(path.strip("/"))
        return

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        body = self._read_body()
        if path == "/__ufvai/focus":
            set_focus(str(body.get("sid") or ""), "tui")
            self._json(200, {"ok": True})
            return
        if path.startswith("/api/ufvai/"):
            try:
                status_code, payload = _handle_api("POST", path, {}, body)
            except Exception as exc:  # noqa: BLE001
                status_code, payload = 500, {"error": str(exc)}
            self._json(status_code, payload)
            return
        self._json(404, {"error": "não encontrado"})

    # -- SSE --
    def _events(self, query: dict) -> None:
        """Stream de eventos do motor, normalizado e filtrado por sessão."""
        sid = str((query.get("sid") or [""])[0] or "")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        last_ping = time.time()
        try:
            while True:
                for event in webapi.engine_events():
                    normalized = webapi.normalize_event(event)
                    if not normalized:
                        continue
                    event_sid = str(normalized.get("sid") or "")
                    if sid and event_sid and event_sid != sid:
                        continue
                    payload = json.dumps(normalized, ensure_ascii=False)
                    self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                    self.wfile.flush()
                # o motor caiu ou reiniciou: reconecta
                time.sleep(1.0)
                if time.time() - last_ping > 10:
                    last_ping = time.time()
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

    def _focus_stream(self) -> None:
        """Stream de trocas de sessão (TUI → web)."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        last_seq = -1
        last_ping = time.time()
        try:
            while True:
                snap = focus_state()
                seq = int(snap.get("seq") or 0)
                if seq != last_seq:
                    last_seq = seq
                    payload = json.dumps(snap, ensure_ascii=False)
                    self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                    self.wfile.flush()
                if time.time() - last_ping > 10:
                    last_ping = time.time()
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                time.sleep(0.4)
        except (BrokenPipeError, ConnectionResetError, OSError):
            return


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 128


# ── ciclo de vida ────────────────────────────────────────────────────────────

def start(port: int = DEFAULT_PORT) -> bool:
    """Sobe o servidor da nova web (idempotente)."""
    global _SERVER, _THREAD
    with _LOCK:
        if _SERVER is not None:
            return True
        try:
            server = _Server(("0.0.0.0", int(port)), _Handler)
        except OSError:
            return False
        thread = threading.Thread(
            target=server.serve_forever, name="ufvai-webui", daemon=True
        )
        thread.start()
        _SERVER, _THREAD = server, thread
        _inicia_recarregador()
        return True


# ── recarregador de módulos (v0.7.11-web30) ─────────────────────────────────

#: Módulos recarregáveis quando o código-fonte muda no disco.
_RELOADAVEIS = ("webapi", "explorer")
_RELOAD_MTIME: dict[str, float] = {}


def _inicia_recarregador() -> None:
    """Recarrega ``webapi``/``explorer`` quando a fonte muda no disco.

    **Por que isso importa**

    O servidor do boot (porta 8002) sobe **dentro do processo do OpenCode**,
    no início da instância: o código Python ficava congelado até o próximo
    reinício do Colab. Os arquivos estáticos (HTML/CSS/JS) são lidos a cada
    requisição — por isso a interface atualizava — mas o *contrato* (rotas,
    explorador, resolução de pastas) continuava velho. Os sintomas eram
    confusos: o cliente novo com o servidor velho.

    ``importlib.reload`` reexecuta o módulo **no lugar** — as referências já
    existentes passam a ver o código novo, sem reiniciar o processo.
    """
    global _RELOAD_MTIME
    for nome in _RELOADAVEIS:
        modulo = sys.modules.get(f"{__package__}.{nome}")
        arquivo = getattr(modulo, "__file__", None)
        if not arquivo:
            continue
        try:
            _RELOAD_MTIME[nome] = os.path.getmtime(arquivo)
        except OSError:
            _RELOAD_MTIME[nome] = 0.0

    def _loop() -> None:
        while True:
            time.sleep(15.0)
            for nome in _RELOADAVEIS:
                modulo = sys.modules.get(f"{__package__}.{nome}")
                arquivo = getattr(modulo, "__file__", None)
                if not arquivo:
                    continue
                try:
                    mtime = os.path.getmtime(arquivo)
                except OSError:
                    continue
                if abs(mtime - _RELOAD_MTIME.get(nome, 0.0)) < 1e-6:
                    continue
                _RELOAD_MTIME[nome] = mtime
                try:
                    importlib.reload(modulo)
                    print(f"[webui] módulo '{nome}' recarregado ({arquivo})", flush=True)
                except Exception as exc:  # noqa: BLE001
                    print(f"[webui] falha ao recarregar '{nome}': {exc}", flush=True)

    threading.Thread(target=_loop, name="ufvai-webui-reload", daemon=True).start()


def stop() -> None:
    global _SERVER, _THREAD
    with _LOCK:
        server, _SERVER = _SERVER, None
        _THREAD = None
    if server is not None:
        try:
            server.shutdown()
            server.server_close()
        except OSError:
            pass


def status() -> dict:
    host, port, _ = webapi.engine()
    server = _SERVER
    return {
        "running": bool(server),
        "port": int(server.server_address[1]) if server else 0,
        "engine": f"http://{host}:{port}" if port else "",
        "engine_ready": bool(port),
        "ui": "webui-v1",
    }


def ready(port: int = DEFAULT_PORT, timeout: float = 0.4) -> bool:
    """Servidor no ar **e** motor respondendo."""
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=timeout):
            pass
    except OSError:
        return False
    _, upstream, _ = webapi.engine()
    if not upstream:
        return False
    try:
        with socket.create_connection(("127.0.0.1", int(upstream)), timeout=timeout):
            return True
    except OSError:
        return False


if __name__ == "__main__":  # pragma: no cover
    import sys

    port = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    start(port)
    print(f"UFVAI web (webui-v1) em http://0.0.0.0:{port}", flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop()
