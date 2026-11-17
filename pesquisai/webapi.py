"""webapi.py — contrato do gateway da versão web do UFVAI (v0.7.11-web17).

Arquitetura **nova** da interface web (escrita do zero, sem a SPA anterior):

    navegador ──► webui_server (:8002) ──► motor OpenCode (API ``/api/*``)

Este módulo é a camada de *tradução*: conhece a API crua do motor e entrega ao
navegador um contrato pequeno, estável e já normalizado. O navegador nunca vê a
senha do motor (a autenticação Basic fica no servidor) e nunca baixa o catálogo
bruto (382 kB com ``settings``/``headers`` de cada modelo).

Nomes de rota usados pelo cliente (``/api/ufvai/*``) — todos devolvem JSON:

=========================================  ==================================
Rota                                       Função
=========================================  ==================================
``GET  /api/ufvai/bootstrap``              estado inicial (agentes, modelos,
                                           sessões, sessão ativa, motor)
``GET  /api/ufvai/models``                 catálogo compacto de modelos
``GET  /api/ufvai/sessions``               lista de sessões
``POST /api/ufvai/sessions``               cria sessão
``GET  /api/ufvai/sessions/{id}/messages`` mensagens normalizadas
``POST /api/ufvai/sessions/{id}/message``  envia prompt
``POST /api/ufvai/sessions/{id}/interrupt`` interrompe a execução
``POST /api/ufvai/sessions/{id}/model``    troca o modelo da sessão
``POST /api/ufvai/sessions/{id}/agent``    troca o agente da sessão
``GET  /api/ufvai/events``                SSE normalizado do motor
=========================================  ==================================
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import shutil
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import quote

__all__ = [
    "engine",
    "engine_json",
    "engine_request",
    "engine_events",
    "catalog",
    "sessions",
    "active_sessions",
    "session",
    "create_session",
    "messages",
    "send_prompt",
    "interrupt",
    "set_model",
    "set_agent",
    "agents",
    "commands",
    "native_commands",
    "locale_info",
    "save_upload",
    "context_usage",
    "session_diff",
    "permission_reply",
    "pending_forms",
    "form_reply",
    "revert_to",
    "save_memory",
    "finalize_session",
    "about",
    "agent_state",
    "normalize_event",
    "provider_available",
]

ENGINE_TIMEOUT = 25.0
EVENT_TIMEOUT = 600.0
CATALOG_TTL = 20.0

# v0.7.11-web23: onde os anexos enviados pelo navegador são gravados. O
# motor aceita data URI (base64), mas um anexo inline NÃO tem caminho em
# disco — o agente não consegue abrir o arquivo. Por isso o gateway grava
# cada anexo aqui e injeta o caminho absoluto no prompt.
UPLOAD_ROOT = Path(os.environ.get("UFVAI_UPLOAD_DIR") or "/tmp/ufvai-uploads")
MAX_UPLOAD_BYTES = 25 * 1024 * 1024

# Idiomas da interface web (mesmos do plugin de TUI ``ufvai.pt``).
WEB_LOCALES = ("pt-BR", "en", "es", "fr", "zh")
_LOCALE_ALIASES = {
    "pt": "pt-BR", "pt_br": "pt-BR", "pt-br": "pt-BR", "br": "pt-BR",
    "en": "en", "en_us": "en", "en-us": "en",
    "es": "es", "es_es": "es", "es-es": "es",
    "fr": "fr", "fr_fr": "fr", "fr-fr": "fr",
    "zh": "zh", "zh_cn": "zh", "zh-cn": "zh",
}

# Provedores que funcionam sem chave do usuário (conta pública do OpenCode).
_BUILTIN_PROVIDERS = ("opencode", "opencode-go")

# Variáveis de ambiente que habilitam um provedor (presença, nunca o valor).
_PROVIDER_ENV: dict[str, tuple[str, ...]] = {
    "google": ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENERATIVE_AI_API_KEY"),
    "openrouter": ("OPENROUTER_API_KEY",),
    "nvidia": ("NVIDIA_API_KEY", "NVIDIA_NIM_API_KEY"),
    "openai": ("OPENAI_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY",),
    "groq": ("GROQ_API_KEY",),
    "mistral": ("MISTRAL_API_KEY",),
    "deepseek": ("DEEPSEEK_API_KEY",),
    "xai": ("XAI_API_KEY",),
    "github-copilot": ("GITHUB_COPILOT_TOKEN",),
    "azure": ("AZURE_API_KEY",),
    "cohere": ("COHERE_API_KEY",),
    "opencode": (),
    "opencode-go": (),
}

_CACHE_LOCK = threading.Lock()
_CATALOG_CACHE: dict[str, Any] = {"ts": 0.0, "data": None}


# ── descoberta do motor ──────────────────────────────────────────────────────

def _service_file() -> Path:
    """``service.json`` do OpenCode (XDG → HOME → /root)."""
    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg:
        candidate = Path(xdg) / "opencode" / "service.json"
        if candidate.exists():
            return candidate
    home = Path(os.path.expanduser("~")) / ".local" / "state" / "opencode" / "service.json"
    if home.exists():
        return home
    return Path("/root/.local/state/opencode/service.json")


_SERVICE: dict[str, Any] = {"key": None, "value": ("127.0.0.1", 0, "")}


def engine() -> tuple[str, int, str]:
    """``(host, porta, senha)`` do motor em execução.

    O ``service.json`` é relido a cada requisição (cache por ``mtime``): o motor
    reinicia durante o boot e troca de porta/senha.
    """
    path = _service_file()
    try:
        st = path.stat()
        key = (str(path), st.st_mtime_ns, st.st_size)
    except OSError:
        return "127.0.0.1", 0, ""
    with _CACHE_LOCK:
        if _SERVICE.get("key") == key and _SERVICE.get("value"):
            return _SERVICE["value"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "127.0.0.1", 0, ""
    url = str(data.get("url") or "")
    port = 0
    if ":" in url:
        try:
            port = int(url.rsplit(":", 1)[1].strip("/"))
        except ValueError:
            port = 0
    value = ("127.0.0.1", port, str(data.get("password") or ""))
    with _CACHE_LOCK:
        _SERVICE["key"] = key
        _SERVICE["value"] = value
    return value


def _auth(password: str) -> str:
    raw = f"opencode:{password}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def engine_request(
    method: str,
    path: str,
    body: Any = None,
    timeout: float = ENGINE_TIMEOUT,
) -> tuple[int, Any]:
    """Chama o motor. Devolve ``(status, json|texto)``; nunca levanta."""
    host, port, password = engine()
    if not port:
        return 0, {"error": "motor indisponível"}
    url = f"http://{host}:{port}{path}"
    payload = None
    headers = {"Authorization": _auth(password), "Accept": "application/json"}
    if body is not None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=payload, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            raw = resp.read()
            status = resp.status
    except urllib.error.HTTPError as exc:  # o motor respondeu com erro
        raw = exc.read() if hasattr(exc, "read") else b""
        status = exc.code
    except (urllib.error.URLError, OSError, ValueError):
        return 0, {"error": "motor indisponível"}
    if not raw:
        return status, {}
    try:
        return status, json.loads(raw.decode("utf-8", errors="replace"))
    except ValueError:
        return status, raw.decode("utf-8", errors="replace")


def engine_json(path: str, timeout: float = ENGINE_TIMEOUT) -> Any:
    """``GET`` no motor devolvendo o JSON (ou ``None`` em falha)."""
    status, data = engine_request("GET", path, timeout=timeout)
    if status != 200:
        return None
    return data


def engine_events(path: str = "/api/event") -> Iterator[dict]:
    """SSE do motor: dicionários ``{id, type, data, ...}``.

    O motor envia comentários (``: heartbeat``) que são ignorados; o stream
    termina quando a conexão cai — o cliente reabre.
    """
    host, port, password = engine()
    if not port:
        return
    request = urllib.request.Request(
        f"http://{host}:{port}{path}",
        headers={"Authorization": _auth(password), "Accept": "text/event-stream"},
    )
    try:
        response = urllib.request.urlopen(request, timeout=EVENT_TIMEOUT)
    except (urllib.error.URLError, OSError, ValueError):
        return
    try:
        for raw in response:
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if not payload:
                continue
            try:
                event = json.loads(payload)
            except ValueError:
                continue
            if isinstance(event, dict):
                yield event
    except (urllib.error.URLError, OSError, ValueError):
        return
    finally:
        try:
            response.close()
        except OSError:
            pass


# ── catálogo de modelos ──────────────────────────────────────────────────────

def provider_available(provider_id: str, used: set | None = None) -> bool:
    """Indica se o provedor tem credencial detectável neste ambiente.

    Três sinais, em ordem: provedor público do OpenCode (funciona sem chave),
    variável de ambiente presente, ou uso recente em uma sessão (prova de que
    a credencial funciona — o motor guarda a chave no banco interno e não
    expõe esse estado pela API).

    A ausência de sinal **não** prova que o provedor está inutilizável; por
    isso o cliente mostra a ressalva "chave não detectada", e não "bloqueado".
    """
    pid = str(provider_id or "").lower()
    if pid in _BUILTIN_PROVIDERS:
        return True
    if used and pid in used:
        return True
    names = _PROVIDER_ENV.get(pid)
    if names is None:
        # provedor desconhecido: sem sinal contra, o motor decide
        return True
    return any(os.environ.get(name) for name in names)


def _providers_in_use() -> set:
    """Provedores usados por sessões recentes (prova de credencial válida)."""
    used: set = set()
    try:
        for row in sessions()[:20]:
            provider = str((row.get("model") or {}).get("providerID") or "")
            if provider:
                used.add(provider.lower())
    except Exception:  # noqa: BLE001 — a lista é um Signals, nunca crítico
        return used
    return used


def _variant_ids(variants: list) -> list:
    """Ids das variantes do modelo (o motor devolve ``[{id, settings}]``)."""
    out: list[str] = []
    for item in variants or []:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict) and item.get("id"):
            out.append(str(item["id"]))
    return out


def _model_cost(model: dict) -> dict:
    """Custo do modelo normalizado (``{input, output, free}``)."""
    costs = model.get("cost") or []
    if not isinstance(costs, list) or not costs:
        return {"input": 0, "output": 0, "free": True}
    first = costs[0] if isinstance(costs[0], dict) else {}
    inp = float(first.get("input") or 0)
    out = float(first.get("output") or 0)
    return {"input": inp, "output": out, "free": inp <= 0 and out <= 0}


def catalog(force: bool = False) -> dict:
    """Catálogo compacto: provedores + modelos utilizáveis.

    O motor devolve ~380 kB (com ``settings``/``headers``/``package`` por
    modelo). Aqui vira um dicionário de poucos kB, com o campo ``available``
    indicando se o provedor tem credencial — é isso que faltava na versão
    anterior (a SPA mostrava ``modelo (unavailable)`` sem explicar o motivo).
    """
    now = time.time()
    with _CACHE_LOCK:
        if not force and _CATALOG_CACHE.get("data") is not None:
            if now - float(_CATALOG_CACHE.get("ts") or 0) < CATALOG_TTL:
                return dict(_CATALOG_CACHE["data"])

    providers_raw = engine_json("/api/provider", timeout=15) or {}
    models_raw = engine_json("/api/model", timeout=25) or {}

    prov_rows = providers_raw.get("data") if isinstance(providers_raw, dict) else providers_raw
    prov_rows = prov_rows if isinstance(prov_rows, list) else []
    names: dict[str, str] = {}
    for row in prov_rows:
        if isinstance(row, dict) and row.get("id"):
            names[str(row["id"])] = str(row.get("name") or row["id"])

    model_rows = models_raw.get("data") if isinstance(models_raw, dict) else models_raw
    model_rows = model_rows if isinstance(model_rows, list) else []

    used = _providers_in_use()
    models: list[dict] = []
    counts: dict[str, int] = {}
    for row in model_rows:
        if not isinstance(row, dict):
            continue
        pid = str(row.get("providerID") or "")
        if not pid or not row.get("modelID"):
            continue
        limit = row.get("limit") or {}
        cost = _model_cost(row)
        models.append(
            {
                "providerID": pid,
                "id": str(row.get("modelID")),
                "name": str(row.get("name") or row.get("modelID")),
                "context": int(limit.get("context") or 0),
                "output": int(limit.get("output") or 0),
                "cost": cost,
                "available": provider_available(pid, used),
                "variants": _variant_ids(row.get("variants") or []),
            }
        )
        counts[pid] = counts.get(pid, 0) + 1

    provider_list = []
    for pid in sorted(counts, key=lambda p: (-counts[p], p)):
        provider_list.append(
            {
                "id": pid,
                "name": names.get(pid, pid),
                "models": counts[pid],
                "available": provider_available(pid, used),
                "inUse": pid in used,
            }
        )

    data = {
        "providers": provider_list,
        "models": models,
        "total": len(models),
        "available": sum(1 for m in models if m["available"]),
        "ts": int(now * 1000),
    }
    with _CACHE_LOCK:
        _CATALOG_CACHE["ts"] = now
        _CATALOG_CACHE["data"] = data
    return dict(data)


# ── sessões ──────────────────────────────────────────────────────────────────

def _session_row(row: dict) -> dict:
    time_info = row.get("time") or {}
    model = row.get("model") or {}
    return {
        "id": str(row.get("id") or ""),
        "title": str(row.get("title") or ""),
        "directory": str((row.get("location") or {}).get("directory") or ""),
        "agent": str(row.get("agent") or ""),
        "model": {
            "id": str(model.get("id") or ""),
            "providerID": str(model.get("providerID") or ""),
            "variant": str(model.get("variant") or ""),
        },
        "created": int(time_info.get("created") or 0),
        "updated": int(time_info.get("updated") or 0),
        "busy": int(time_info.get("busy") or 0),
        "tokens": row.get("tokens") or {},
        "cost": row.get("cost") or 0,
    }


def sessions() -> list[dict]:
    """Sessões do projeto atual, da mais recente para a mais antiga."""
    data = engine_json("/api/session", timeout=15)
    rows = data.get("data") if isinstance(data, dict) else data
    rows = rows if isinstance(rows, list) else []
    out = [_session_row(r) for r in rows if isinstance(r, dict) and r.get("id")]
    out.sort(key=lambda s: s.get("updated") or s.get("created") or 0, reverse=True)
    return out


def active_sessions() -> dict:
    """Sessões que o motor considera em execução.

    v0.7.11-web30: quando o motor está indisponível, devolve ``{"error": …}``
    em vez de ``{}`` — o cliente precisa distinguir "não há nada rodando"
    de "não deu para perguntar" (senão o indicador "trabalhando" morre no
    meio de uma execução).
    """
    data = engine_json("/api/session/active", timeout=8)
    if isinstance(data, dict) and data.get("error"):
        return {"error": str(data["error"])}
    rows = data.get("data") if isinstance(data, dict) else data
    return rows if isinstance(rows, dict) else {}


def session(sid: str) -> dict | None:
    data = engine_json(f"/api/session/{sid}", timeout=10)
    row = data.get("data") if isinstance(data, dict) else data
    if isinstance(row, dict) and row.get("id"):
        return _session_row(row)
    return None


def create_session(
    title: str | None = None,
    agent: str | None = None,
    model: dict | None = None,
    directory: str | None = None,
) -> dict | None:
    """Cria uma sessão no diretório de trabalho do projeto."""
    body: dict[str, Any] = {}
    if title:
        body["title"] = title
    if agent:
        body["agent"] = agent
    if model and model.get("id") and model.get("providerID"):
        body["model"] = {
            "id": str(model["id"]),
            "providerID": str(model["providerID"]),
        }
        if model.get("variant"):
            body["model"]["variant"] = str(model["variant"])
    if directory:
        body["location"] = {"directory": directory}
    status, data = engine_request("POST", "/api/session", body, timeout=20)
    if status not in (200, 201):
        return None
    row = data.get("data") if isinstance(data, dict) else data
    if isinstance(row, dict) and row.get("id"):
        return _session_row(row)
    return None


# ── mensagens ────────────────────────────────────────────────────────────────

def _tool_rows(content: list) -> list[dict]:
    tools = []
    for part in content or []:
        if not isinstance(part, dict) or part.get("type") != "tool":
            continue
        state = part.get("state") or {}
        output = state.get("output")
        if output is None:
            chunks = []
            for item in state.get("content") or []:
                if isinstance(item, dict) and item.get("text"):
                    chunks.append(str(item["text"]))
            output = "".join(chunks) or None
        tools.append(
            {
                "id": str(part.get("id") or ""),
                "name": str(part.get("name") or ""),
                "status": str(state.get("status") or "unknown"),
                "title": str(state.get("title") or ""),
                "input": state.get("input"),
                "output": output,
                "metadata": state.get("metadata") or {},
            }
        )
    return tools


def normalize_message(row: dict) -> dict:
    """Mensagem do motor → contrato do cliente."""
    kind = str(row.get("type") or "")
    time_info = row.get("time") or {}
    content = row.get("content") or []
    texts: list[str] = []
    reasoning: list[str] = []
    for part in content:
        if not isinstance(part, dict):
            continue
        if part.get("type") == "text" and part.get("text"):
            texts.append(str(part["text"]))
        elif part.get("type") == "reasoning" and part.get("text"):
            reasoning.append(str(part["text"]))
    model = row.get("model") or {}
    error = row.get("error")
    # v0.7.11-web27: o motor anexa à mensagem o erro (com status) e a
    # informação de retry (tentativa + atraso) — a interface distingue
    # "servidor sobrecarregado, tentando de novo" de "erro comum".
    retry = row.get("retry") if isinstance(row.get("retry"), dict) else {}
    retry_error = retry.get("error") if isinstance(retry.get("error"), dict) else {}
    return {
        "id": str(row.get("id") or ""),
        "role": "assistant" if kind == "assistant" else ("user" if kind == "user" else "system"),
        "kind": kind,
        "text": str(row.get("text") or "") if kind == "user" else "\n\n".join(texts),
        "reasoning": "\n\n".join(reasoning),
        "tools": _tool_rows(content),
        "agent": str(row.get("agent") or ""),
        "model": {
            "id": str(model.get("id") or ""),
            "providerID": str(model.get("providerID") or ""),
            "variant": str(model.get("variant") or ""),
        },
        "created": int(time_info.get("created") or 0),
        "firstToken": int(time_info.get("firstToken") or 0),
        "streamed": int(time_info.get("streamed") or 0),
        "completed": int(time_info.get("completed") or 0),
        "tokens": row.get("tokens") or {},
        "cost": row.get("cost") or 0,
        "outcome": row.get("outcome"),
        "error": str(error.get("message") if isinstance(error, dict) else error or ""),
        "errorStatus": int(error.get("status") or 0) if isinstance(error, dict) else 0,
        "errorType": str(error.get("type") or "") if isinstance(error, dict) else "",
        "errorReason": _error_reason(error) if isinstance(error, dict) else "error",
        "retry": (
            {
                "attempt": int(retry.get("attempt") or 0),
                "delayMs": int(retry_error.get("retryAfterMs") or 0),
                "status": int(retry_error.get("status") or 0),
                "message": str(retry_error.get("message") or ""),
                "reason": _error_reason(retry_error) if retry_error else "error",
            }
            if retry
            else {}
        ),
    }


def messages(sid: str, limit: int = 200) -> list[dict]:
    """Mensagens da sessão em ordem cronológica (antiga → nova).

    O motor entrega a página mais recente primeiro; com ``order=asc`` as
    páginas vêm em ordem cronológica. Percorremos o cursor até ter o limite
    pedido (o histórico antigo continua acessível pela rolagem do terminal).
    """
    rows: list[dict] = []
    cursor = ""
    for _ in range(12):
        path = f"/api/session/{sid}/message?order=asc"
        if cursor:
            path += "&cursor=" + quote(cursor, safe="")
        data = engine_json(path, timeout=25)
        if not isinstance(data, dict):
            break
        page = data.get("data")
        if not isinstance(page, list) or not page:
            break
        rows.extend([r for r in page if isinstance(r, dict)])
        if limit and len(rows) >= limit:
            break
        nxt = (data.get("cursor") or {}).get("next")
        if not nxt or nxt == cursor:
            break
        cursor = str(nxt)

    rows.sort(key=lambda r: int((r.get("time") or {}).get("created") or 0))
    out = [normalize_message(r) for r in rows]
    out = [m for m in out if m["role"] != "system" or m.get("outcome")]
    if limit and len(out) > limit:
        out = out[-limit:]
    return out


def _ok(status: int) -> bool:
    """2xx = sucesso (o motor usa 204 em operações sem corpo)."""
    return 200 <= int(status) < 300


def _safe_name(name: str) -> str:
    """Nome de arquivo seguro (sem caminho, sem ``..``, sem espaços estranhos)."""
    base = os.path.basename(str(name or "").strip().replace("\\", "/"))
    base = re.sub(r"[^A-Za-z0-9._\-]+", "_", base).strip("._") or "arquivo"
    return base[:120]


def save_upload(sid: str, name: str, mime: str = "", data_b64: str = "") -> dict:
    """Grava um anexo enviado pelo navegador em disco e devolve o caminho.

    O motor aceita anexos **inline** (data URI base64), mas o agente não
    consegue abrir um anexo inline: ele não tem caminho, não tem nome de
    arquivo no disco e não aparece em ``ls``. Aqui o arquivo é gravado em
    ``/tmp/ufvai-uploads/<sessão>/`` e o caminho absoluto é devolvido — o
    gateway o injeta no prompt (ver :func:`send_prompt`).
    """
    if not data_b64:
        return {"ok": False, "error": "arquivo vazio"}
    if "," in data_b64[:80] and data_b64.strip().startswith("data:"):
        data_b64 = data_b64.split(",", 1)[1]
    try:
        raw = base64.b64decode(data_b64, validate=False)
    except Exception:
        return {"ok": False, "error": "conteúdo inválido (base64)"}
    if len(raw) > MAX_UPLOAD_BYTES:
        return {"ok": False, "error": f"arquivo maior que {MAX_UPLOAD_BYTES // 1048576} MB"}
    safe = _safe_name(name)
    target_dir = UPLOAD_ROOT / re.sub(r"[^A-Za-z0-9_-]+", "", str(sid or "sessao"))[:64]
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return {"ok": False, "error": f"não foi possível criar a pasta de anexos: {exc}"}
    target = target_dir / safe
    counter = 1
    while target.exists():
        stem, dot, ext = safe.rpartition(".")
        target = target_dir / (f"{stem or safe}-{counter}" + (dot + ext if dot else ""))
        counter += 1
    try:
        target.write_bytes(raw)
    except OSError as exc:
        return {"ok": False, "error": f"não foi possível gravar o arquivo: {exc}"}
    guessed = mimetypes.guess_type(safe)[0] or mime or "application/octet-stream"
    return {
        "ok": True,
        "name": safe,
        "path": str(target),
        "size": len(raw),
        "mime": guessed,
    }


def _upload_note(uploads: list) -> str:
    """Bloco textual que injeta os caminhos dos anexos no prompt."""
    lines = []
    for item in uploads:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "")
        if not path:
            continue
        size = int(item.get("size") or 0)
        size_txt = f" ({size} bytes)" if size else ""
        lines.append(f"- {path}{size_txt}")
    if not lines:
        return ""
    return (
        "[ARQUIVOS ANEXADOS PELO USUÁRIO — já gravados no disco do agente]\n"
        + "\n".join(lines)
        + "\n\nAbra, leia ou processe cada arquivo pelo caminho absoluto acima.\n\n"
    )


def send_prompt(
    sid: str,
    text: str,
    files: list | None = None,
    agents: list | None = None,
    skills: list | None = None,
    uploads: list | None = None,
) -> dict:
    """Envia um prompt para a sessão.

    ``files`` é a lista de anexos no formato do motor
    (``{uri, source, name}``); o motor aceita **data URI** (base64) — um
    caminho local é recusado com ``Invalid attachment URI``.

    ``uploads`` são os anexos **já gravados em disco** pelo
    :func:`save_upload`: os caminhos absolutos são injetados no texto para
    que o agente saiba onde o arquivo está (v0.7.11-web23).
    """
    body: dict[str, Any] = {"text": text}
    note = _upload_note(uploads or [])
    if note:
        body["text"] = note + text
    if files:
        body["files"] = files
    if agents:
        body["agents"] = agents
    if skills:
        body["skills"] = skills
    status, data = engine_request(
        "POST", f"/api/session/{sid}/prompt", body, timeout=30
    )
    if not _ok(status):
        return {"ok": False, "error": _error_text(data) or f"HTTP {status}"}
    row = data.get("data") if isinstance(data, dict) else data
    return {"ok": True, "id": str((row or {}).get("id") or "")}


def interrupt(sid: str) -> dict:
    """Interrompe a execução em andamento."""
    status, data = engine_request("POST", f"/api/session/{sid}/interrupt", {}, timeout=15)
    if not _ok(status):
        return {"ok": False, "error": _error_text(data) or f"HTTP {status}"}
    return {"ok": True, "interrupted": bool((data or {}).get("interrupted", True))}


def set_model(sid: str, model: dict) -> dict:
    """Troca o modelo da sessão."""
    if not model.get("id") or not model.get("providerID"):
        return {"ok": False, "error": "modelo incompleto"}
    payload = {"id": str(model["id"]), "providerID": str(model["providerID"])}
    if model.get("variant"):
        payload["variant"] = str(model["variant"])
    status, data = engine_request(
        "POST", f"/api/session/{sid}/model", {"model": payload}, timeout=15
    )
    if not _ok(status):
        return {"ok": False, "error": _error_text(data) or f"HTTP {status}"}
    return {"ok": True, "model": payload}


def set_agent(sid: str, agent: str) -> dict:
    """Troca o agente da sessão."""
    status, data = engine_request(
        "POST", f"/api/session/{sid}/agent", {"agent": agent}, timeout=15
    )
    if not _ok(status):
        return {"ok": False, "error": _error_text(data) or f"HTTP {status}"}
    return {"ok": True, "agent": agent}


def _error_text(data: Any) -> str:
    if isinstance(data, dict):
        for key in ("error", "message", "data"):
            value = data.get(key)
            if isinstance(value, str) and value:
                return value
            if isinstance(value, dict):
                nested = value.get("message") or value.get("error")
                if isinstance(nested, str) and nested:
                    return nested
    return ""


# ── agentes e comandos ───────────────────────────────────────────────────────

def agents() -> list[dict]:
    """Agentes disponíveis — **apenas o UFVAI**.

    O motor também expõe agentes internos (``general``, ``explore``,
    ``compaction``, ``title``, ``summary``) que não fazem sentido para o
    usuário: são rotinas internas do OpenCode. A interface mostra só o UFVAI.
    """
    data = engine_json("/api/agent", timeout=15)
    rows = data.get("data") if isinstance(data, dict) else data
    rows = rows if isinstance(rows, list) else []
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        model = row.get("model") or {}
        out.append(
            {
                "id": str(row.get("id") or row.get("name") or ""),
                "name": str(row.get("name") or row.get("id") or ""),
                "description": str(row.get("description") or "")[:200],
                "internal": str(row.get("id") or "").lower()
                in ("general", "explore", "compaction", "title", "summary", "build", "plan"),
                "model": {
                    "id": str(model.get("id") or ""),
                    "providerID": str(model.get("providerID") or ""),
                },
            }
        )
    visible = [a for a in out if not a["internal"]]
    if not visible:
        visible = out[:1]
    return visible


def web_locale() -> str:
    """Idioma da interface web (o mesmo do plugin de TUI ``ufvai.pt``).

    Ordem: ``?lang=`` do pedido → arquivo gravado pelo plugin
    (``~/.config/opencode/ufvai-language.json``) → ``UFVAI_LANG`` →
    ``pt-BR`` (padrão do produto).
    """
    for env in ("UFVAI_LANG", "PESQUISAI_LANG", "PESQUISAI_LOCALE"):
        raw = os.environ.get(env)
        if raw:
            key = raw.strip().lower().replace("-", "_")
            if key in _LOCALE_ALIASES:
                return _LOCALE_ALIASES[key]
    try:
        from .tui_pt import read_saved_locale  # type: ignore

        saved = read_saved_locale()
    except Exception:  # pragma: no cover — o módulo pode não estar no pacote
        saved = None
    if saved:
        key = str(saved).strip().lower().replace("-", "_")
        if key in _LOCALE_ALIASES:
            return _LOCALE_ALIASES[key]
    return "pt-BR"


def locale_info(lang: str | None = None) -> dict:
    """Idioma atual + os disponíveis (para o seletor da interface web)."""
    current = lang or web_locale()
    key = str(current).strip().lower().replace("-", "_")
    current = _LOCALE_ALIASES.get(key, "pt-BR")
    return {
        "lang": current,
        "available": list(WEB_LOCALES),
        "source": "ufvai-language.json",
    }


def native_commands(lang: str | None = None) -> list[dict]:
    """Comandos **nativos** da TUI do OpenCode, traduzidos (plugin ``ufvai.pt``).

    O motor expõe só os comandos de *agente* (``/api/command``: ``pesquisar``,
    ``revisar``, ``dados``…). Os ~37 comandos da barra da TUI (``/new``,
    ``/undo``, ``/themes``, ``/models``…) vivem dentro do binário e não
    aparecem na API — mas o plugin de TUI do UFVAI os traduz e os publica em
    ``pesquisai/tui_pt.py`` (``PT_CATALOG``). Esta função devolve esse
    catálogo já no idioma corrente, para o menu ``/`` da web listar **todos**
    os comandos do OpenCode, e não só os do agente.

    Em inglês (idioma nativo do motor) o slug e o título vêm do arquivo de
    i18n do próprio OpenCode — ver ``pesquisai/web23_native.py``.
    """
    current = locale_info(lang)["lang"]
    try:
        from .tui_pt import GROUPS, PT_CATALOG  # type: ignore
    except Exception:  # pragma: no cover — execução fora do pacote
        try:
            from tui_pt import GROUPS, PT_CATALOG  # type: ignore
        except Exception:
            return []
    catalog = PT_CATALOG.get(current) or PT_CATALOG.get("pt-BR") or {}
    groups = (GROUPS or {}).get(current) or (GROUPS or {}).get("pt-BR") or {}
    try:
        from .web23_native import native_catalog  # type: ignore

        return native_catalog(current, catalog, groups)
    except Exception:  # pragma: no cover
        return []


def commands(lang: str | None = None) -> list[dict]:
    """Comandos do menu ``/``: do agente **e** os nativos da TUI.

    Os comandos do UFVAI (``pesquisar``, ``revisar``, ``dados``…) vêm do
    ``opencode.json``; o motor acrescenta os próprios (``init``, ``review``,
    ``goal``). Os nativos da barra da TUI vêm do catálogo traduzido do plugin
    ``ufvai.pt`` (37 comandos). A interface os mostra agrupados.
    """
    data = engine_json("/api/command", timeout=12)
    rows = data.get("data") if isinstance(data, dict) else data
    rows = rows if isinstance(rows, list) else []
    out: list[dict] = []
    for r in rows:
        if isinstance(r, dict) and r.get("name"):
            out.append(
                {
                    "name": str(r.get("name")),
                    "title": str(r.get("name")),
                    "description": str(r.get("description") or ""),
                    "group": "UFVAI",
                    "aliases": [],
                    "agent": str(r.get("agent") or ""),
                    "source": "motor",
                    "id": str(r.get("name")),
                    "args": False,
                }
            )
    for cmd in native_commands(lang):
        if any(c["name"] == cmd["name"] for c in out):
            continue
        out.append(cmd)
    return out


def skills() -> list[dict]:
    """Habilidades disponíveis (menção ``@skill``)."""
    data = engine_json("/api/skill", timeout=15)
    rows = data.get("data") if isinstance(data, dict) else data
    rows = rows if isinstance(rows, list) else []
    out = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        out.append(
            {
                "id": str(row.get("id")),
                "name": str(row.get("name") or row.get("id")),
                "description": str(row.get("description") or "")[:240],
            }
        )
    return out


def files_list(path: str = "", directory: str = "") -> list[dict]:
    """Listagem de arquivos do projeto (``@`` menu de menções)."""
    query = ""
    if directory:
        query = "?location%5Bdirectory%5D=" + quote(directory, safe="")
    if path:
        query += ("&" if query else "?") + "path=" + quote(path, safe="")
    data = engine_json(f"/api/fs/list{query}", timeout=15)
    rows = data.get("data") if isinstance(data, dict) else data
    rows = rows if isinstance(rows, list) else []
    return [
        {"path": str(r.get("path") or ""), "type": str(r.get("type") or "file")}
        for r in rows
        if isinstance(r, dict)
    ]


def files_find(query: str, directory: str = "", limit: int = 50) -> list[dict]:
    """Busca de arquivos por nome (``@`` menu de menções)."""
    params = ["query=" + quote(query or "", safe=""), "type=file", f"limit={int(limit)}"]
    if directory:
        params.insert(0, "location%5Bdirectory%5D=" + quote(directory, safe=""))
    data = engine_json("/api/fs/find?" + "&".join(params), timeout=15)
    rows = data.get("data") if isinstance(data, dict) else data
    rows = rows if isinstance(rows, list) else []
    return [
        {"path": str(r.get("path") or ""), "type": str(r.get("type") or "file")}
        for r in rows
        if isinstance(r, dict)
    ]


def file_data_uri(path: str, directory: str = "", max_bytes: int = 3_000_000) -> dict | None:
    """Lê um arquivo do projeto e devolve o anexo pronto (``data:`` URI).

    O motor aceita anexos apenas com URI válido (data URI ou http(s)); um
    caminho local é recusado (``Invalid attachment URI``). O arquivo é lido
    **dentro do diretório do projeto** — nada fora dele é servido.
    """
    query = ""
    if directory:
        query = "?location%5Bdirectory%5D=" + quote(directory, safe="")
    data = engine_json(f"/api/fs/read/{quote(path.lstrip('/'), safe='/')}{query}", timeout=20)
    if data is None:
        return None
    if isinstance(data, dict):
        content = data.get("content")
        mime = str(data.get("mime") or data.get("mimeType") or "text/plain")
    else:
        content = data
        mime = "text/plain"
    if content is None:
        return None
    if isinstance(content, str):
        raw = content.encode("utf-8", errors="replace")
    elif isinstance(content, (bytes, bytearray)):
        raw = bytes(content)
    else:
        raw = str(content).encode("utf-8", errors="replace")
    if len(raw) > max_bytes:
        raw = raw[:max_bytes]
    import base64 as _b64

    encoded = _b64.b64encode(raw).decode("ascii")
    return {
        "uri": f"data:{mime};base64,{encoded}",
        "source": {"type": "inline"},
        "name": path.split("/")[-1],
    }


def session_context(sid: str) -> dict:
    """Contexto da sessão (tokens, arquivos, ferramentas — painel de detalhes)."""
    data = engine_json(f"/api/session/{sid}/context", timeout=20)
    return data if isinstance(data, dict) else {}


def context_usage(sid: str) -> dict:
    """Uso da janela de contexto: tokens consumidos × limite do modelo.

    O motor não expõe isso pronto: o limite vem do catálogo (``limit.context``
    do modelo) e o consumido vem da **última** mensagem com tokens — é o
    mesmo critério da SPA. Atenção: o motor devolve tipos diferentes
    (``assistant``, ``compaction``, ``idle``…), e o token mais recente nem
    sempre está numa mensagem de assistente (a compactação também conta).
    """
    data = engine_json(f"/api/session/{sid}/message?order=desc&limit=6", timeout=20)
    rows = data.get("data") if isinstance(data, dict) else data
    rows = rows if isinstance(rows, list) else []
    tokens: dict = {}
    model_info: dict = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_tokens = row.get("tokens")
        if not isinstance(row_tokens, dict) or not row_tokens:
            continue
        tokens = row_tokens
        model_info = row.get("model") or {}
        break
    if not model_info:
        # sem modelo na mensagem: usa o da sessão
        try:
            row = session(sid) or {}
            model_info = row.get("model") or {}
        except Exception:
            model_info = {}
    cache = tokens.get("cache") or {}
    used = (
        int(tokens.get("input") or 0)
        + int(cache.get("read") or 0)
        + int(cache.get("write") or 0)
        + int(tokens.get("output") or 0)
        + int(tokens.get("reasoning") or 0)
    )
    limit = 0
    try:
        cat = catalog()
        for m in cat.get("models") or []:
            if (
                m.get("id") == model_info.get("id")
                and m.get("providerID") == model_info.get("providerID")
            ):
                limit = int(m.get("context") or 0)
                break
    except Exception:
        limit = 0
    percent = round(used * 100.0 / limit, 1) if limit else 0.0
    return {
        "used": used,
        "limit": limit,
        "percent": percent,
        "tokens": tokens,
        "model": {
            "id": str(model_info.get("id") or ""),
            "providerID": str(model_info.get("providerID") or ""),
        },
    }


def session_diff(sid: str) -> dict:
    """Diff dos arquivos alterados na sessão (para marcar adição/supressão)."""
    data = engine_json(f"/api/session/{sid}/diff", timeout=20)
    rows = data.get("data") if isinstance(data, dict) else data
    rows = rows if isinstance(rows, list) else []
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        out.append(
            {
                "file": str(row.get("file") or row.get("path") or ""),
                "additions": int(row.get("additions") or 0),
                "deletions": int(row.get("deletions") or 0),
                "diff": str(row.get("diff") or row.get("patch") or ""),
            }
        )
    return {"files": out}


def pending_permissions(sid: str) -> list[dict]:
    """Pedidos de permissão em aberto da sessão (para a web mostrar as opções)."""
    data = engine_json(f"/api/session/{sid}/permission", timeout=12)
    rows = data.get("data") if isinstance(data, dict) else data
    rows = rows if isinstance(rows, list) else []
    out = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        out.append(
            {
                "id": str(row.get("id")),
                "action": str(row.get("action") or ""),
                "resources": [str(r) for r in (row.get("resources") or [])],
                "message": str(row.get("message") or ""),
                "metadata": row.get("metadata") or {},
            }
        )
    return out


def agent_state() -> dict:
    """Estado do agente para o cabeçalho da interface (v0.7.11-web30).

    ``busy`` = há execução em curso; ``sid`` = a sessão que trabalha.
    """
    ativos = active_sessions()
    if isinstance(ativos, dict) and ativos.get("error"):
        return {"busy": False, "sid": "", "sessions": 0, "error": str(ativos["error"])}
    sids = list(ativos.keys()) if isinstance(ativos, dict) else []
    return {"busy": bool(sids), "sid": sids[0] if sids else "", "sessions": len(sids)}


def about() -> dict:
    """Ficha do UFVAI para a aba “Sobre” (fonte: ``pesquisai/__version__.py``)."""
    try:
        from .__version__ import get_full_metadata, get_version  # type: ignore
    except Exception:  # pragma: no cover — execução fora do pacote
        try:
            from __version__ import get_full_metadata, get_version  # type: ignore
        except Exception:
            return {}
    try:
        data = get_full_metadata()
    except Exception:
        return {}
    data["versionShort"] = get_version()
    return data


def finalize_session(sid: str, mode: str = "archive") -> dict:
    """Finaliza uma sessão.

    ``archive`` (padrão) marca a conversa como encerrada, prefixando o
    título com ``✔`` — ela continua na lista, mas deixa de “pegar” o
    trabalho em curso. ``delete`` remove a sessão do motor (o **autosave no
    Google Drive** continua sendo o arquivo de segurança).
    """
    mode = str(mode or "archive").strip().lower()
    if mode not in ("archive", "delete"):
        return {"ok": False, "error": "modo inválido"}
    if mode == "delete":
        status, data = engine_request("DELETE", f"/api/session/{sid}", None, timeout=20)
        if not _ok(status):
            return {"ok": False, "error": _error_text(data) or f"HTTP {status}"}
        return {"ok": True, "mode": mode, "deleted": True}
    row = session(sid) or {}
    title = str(row.get("title") or sid)
    if not title.startswith("✔"):
        title = f"✔ {title}"
    return rename_session(sid, title)


def permission_reply(sid: str, request_id: str, decision: str) -> dict:
    """Responde a um pedido de permissão do motor.

    ``decision`` é ``once`` (uma vez), ``always`` (sempre) ou ``reject``.
    """
    decision = str(decision or "").strip().lower()
    if decision not in ("once", "always", "reject"):
        return {"ok": False, "error": "decisão inválida"}
    status, data = engine_request(
        "POST",
        f"/api/session/{sid}/permission/{request_id}/reply",
        {"decision": decision},
        timeout=20,
    )
    if not _ok(status):
        return {"ok": False, "error": _error_text(data) or f"HTTP {status}"}
    return {"ok": True, "decision": decision}


def pending_forms(sid: str) -> list[dict]:
    """Formulários em aberto da sessão (v0.7.11-web38).

    A ferramenta ``question`` do agente cria um FORM no motor
    (``GET /api/session/{sid}/form``) com os campos/opções. Sem isto, a
    interface web não mostrava a pergunta e o turno ficava parado.
    """
    data = engine_json(f"/api/session/{sid}/form", timeout=12)
    rows = data.get("data") if isinstance(data, dict) else data
    rows = rows if isinstance(rows, list) else []
    out = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        out.append(
            {
                "id": str(row.get("id")),
                "title": str(row.get("title") or ""),
                "metadata": row.get("metadata") or {},
                "fields": row.get("fields") or [],
            }
        )
    return out


def form_reply(sid: str, form_id: str, answer: dict) -> dict:
    """Responde um formulário pendente (ferramenta ``question``).

    ``answer`` é ``{chave_do_campo: valor}`` (string, número, booleano ou
    lista de strings, conforme o tipo do campo).
    """
    if not isinstance(answer, dict) or not answer:
        return {"ok": False, "error": "resposta vazia"}
    status, data = engine_request(
        "POST",
        f"/api/session/{sid}/form/{form_id}/reply",
        {"answer": answer},
        timeout=20,
    )
    if not _ok(status):
        return {"ok": False, "error": _error_text(data) or f"HTTP {status}"}
    return {"ok": True}


def revert_to(sid: str, message_id: str, files: bool = False) -> dict:
    """Reverte a sessão até (e incluindo) ``message_id``.

    Semântica validada no motor [DADO CONFIRMADO]: ``stage`` + ``commit``
    removem a mensagem-alvo e tudo que veio depois. Serve para **editar e
    reenviar** (reverte à mensagem do usuário e envia o texto editado) e
    **regenerar** (reverte à mesma mensagem e reenvia o texto original).
    ``files=False`` evita reverter alterações no workspace.
    """
    if not message_id:
        return {"ok": False, "error": "mensagem vazia"}
    status, data = engine_request(
        "POST",
        f"/api/session/{sid}/revert/stage",
        {"messageID": message_id, "files": bool(files)},
        timeout=20,
    )
    if not _ok(status):
        return {"ok": False, "error": _error_text(data) or f"HTTP {status}"}
    status, data = engine_request(
        "POST", f"/api/session/{sid}/revert/commit", {}, timeout=20
    )
    if not _ok(status):
        return {"ok": False, "error": _error_text(data) or f"HTTP {status}"}
    return {"ok": True}


def save_memory(text: str, title: str = "", tags: list[str] | None = None) -> dict:
    """Salva um trecho na Minha memória (vault Obsidian).

    Usa o autopilot (``save_finding``), que é no-op quando o vault não está
    disponível — nesse caso devolve erro para a interface avisar.
    """
    body = str(text or "").strip()
    if not body:
        return {"ok": False, "error": "texto vazio"}
    try:
        from .obsidian.autopilot import save_finding  # type: ignore
    except Exception as exc:  # pragma: no cover
        return {"ok": False, "error": f"memória indisponível: {exc}"}
    try:
        path = save_finding(body, source="interface web", tags=tags or None)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}
    if not path:
        return {"ok": False, "error": "vault indisponível"}
    return {"ok": True, "path": str(path), "title": str(title or body.splitlines()[0])[:120]}


def fork_session(sid: str) -> dict:
    """Cria uma cópia (fork) da sessão."""
    status, data = engine_request("POST", f"/api/session/{sid}/fork", {}, timeout=20)
    if not _ok(status):
        return {"ok": False, "error": _error_text(data) or f"HTTP {status}"}
    row = data.get("data") if isinstance(data, dict) else data
    return {"ok": True, "session": _session_row(row) if isinstance(row, dict) else {}}


def compact_session(sid: str) -> dict:
    """Compacta o histórico da sessão."""
    status, data = engine_request("POST", f"/api/session/{sid}/compact", {}, timeout=30)
    if not _ok(status):
        return {"ok": False, "error": _error_text(data) or f"HTTP {status}"}
    return {"ok": True}


def background_session(sid: str) -> dict:
    """Move a execução para segundo plano (Ctrl+B)."""
    status, data = engine_request("POST", f"/api/session/{sid}/background", {}, timeout=15)
    if not _ok(status):
        return {"ok": False, "error": _error_text(data) or f"HTTP {status}"}
    return {"ok": True}


def rename_session(sid: str, title: str) -> dict:
    """Renomeia a sessão."""
    status, data = engine_request(
        "PATCH", f"/api/session/{sid}", {"title": title}, timeout=15
    )
    if not _ok(status):
        return {"ok": False, "error": _error_text(data) or f"HTTP {status}"}
    return {"ok": True, "title": title}


# ── eventos (motor → cliente) ────────────────────────────────────────────────

# Ferramentas que alteram arquivos em disco. O motor não expõe o diff, mas o
# evento ``session.tool.called`` chega ANTES da execução: o gateway tira uma
# "foto" do arquivo nesse instante e, quando a chamada termina, compara com o
# conteúdo atual — daí o cliente poder marcar adição (verde) e supressão
# (vermelho) linha a linha.
_FILE_TOOLS = {"write", "edit", "patch", "multi_edit", "apply_patch"}
_SHADOW: dict[str, dict[str, Any]] = {}
_SHADOW_MAX = 24
_TOOL_NAMES: dict[str, str] = {}


def _infer_tool(name: str, tool_input: Any) -> str:
    """Nome da ferramenta — o motor o manda no ``tool.input.started``.

    Quando falta, deduz pela forma da entrada (o ``tool.called`` do motor
    não repete o nome).
    """
    if str(name or "").strip():
        return str(name)
    if isinstance(tool_input, dict):
        if "oldString" in tool_input or "newString" in tool_input:
            return "edit"
        if "content" in tool_input and ("path" in tool_input or "filePath" in tool_input):
            return "write"
        if "command" in tool_input:
            return "shell"
        if "pattern" in tool_input and "path" in tool_input:
            return "grep"
    return ""


def _tool_path(name: str, tool_input: Any) -> str:
    """Caminho do arquivo alterado pela ferramenta (se houver)."""
    key = str(name or "").lower()
    if key not in _FILE_TOOLS and key not in ("", "write", "edit"):
        return ""
    if not isinstance(tool_input, dict):
        return ""
    for field in ("filePath", "path", "file", "target"):
        value = tool_input.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _read_text(path: str, limit: int = 400_000) -> str:
    try:
        target = Path(path)
        if not target.is_file():
            return ""
        raw = target.read_bytes()[:limit]
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return ""


def _line_diff(before: str, after: str) -> dict[str, Any]:
    """Diff por linhas (LCS) — devolve as linhas adicionadas e removidas."""
    import difflib

    added: list[str] = []
    removed: list[str] = []
    matcher = difflib.SequenceMatcher(
        a=before.splitlines(), b=after.splitlines(), autojunk=False
    )
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("replace", "delete"):
            removed.extend(before.splitlines()[i1:i2][:400])
        if tag in ("replace", "insert"):
            added.extend(after.splitlines()[j1:j2][:400])
    return {"added": added[:400], "removed": removed[:400]}


def _error_reason(error: dict) -> str:
    """Classifica o erro do motor: ``overloaded`` (saturado) ou ``error``.

    O motor distingue a sobrecarga do provedor (HTTP 429/503, “overloaded”,
    “high demand”, “quota”) dos demais erros — a interface precisa mostrar
    a situação de forma diferente (saturação + nova tentativa ≠ falha).
    """
    error = error if isinstance(error, dict) else {}
    message = str(error.get("message") or "")
    status = int(error.get("status") or 0)
    etype = str(error.get("type") or "").lower()
    blob = f"{etype} {message}".lower()
    overload_markers = (
        "overload", "high demand", "temporarily unavailable", "try again later",
        "service unavailable", "capacity", "too many requests", "rate limit",
        "rate_limit", "quota", "resource_exhausted", "429", "503", "529",
    )
    if status in (429, 503, 529) or any(mark in blob for mark in overload_markers):
        return "overloaded"
    return "error"


def normalize_event(event: dict) -> dict | None:
    """Traduz um evento do motor para o contrato do cliente.

    Devolve ``None`` para eventos irrelevantes (outras sessões, telemetria).
    """
    kind = str(event.get("type") or "")
    data = event.get("data") or {}
    if not isinstance(data, dict):
        data = {}
    sid = str(data.get("sessionID") or "")
    message_id = str(data.get("assistantMessageID") or "")

    if kind == "session.execution.started":
        return {"type": "run.started", "sid": sid}
    if kind == "session.execution.succeeded":
        return {"type": "run.finished", "sid": sid}
    if kind == "session.execution.failed":
        return {"type": "run.failed", "sid": sid, "error": str(data.get("error") or "")}
    if kind == "session.step.started":
        model = data.get("model") or {}
        return {
            "type": "step.started",
            "sid": sid,
            "messageID": message_id,
            "agent": str(data.get("agent") or ""),
            "model": {
                "id": str(model.get("id") or ""),
                "providerID": str(model.get("providerID") or ""),
            },
        }
    if kind == "session.step.ended":
        return {
            "type": "step.ended",
            "sid": sid,
            "messageID": message_id,
            "finish": str(data.get("finish") or ""),
            "tokens": data.get("tokens") or {},
            "cost": data.get("cost") or 0,
        }
    if kind == "session.text.started":
        return {"type": "text.started", "sid": sid, "messageID": message_id}
    if kind == "session.text.delta":
        return {"type": "text.delta", "sid": sid, "messageID": message_id, "delta": str(data.get("delta") or "")}
    if kind == "session.text.ended":
        return {"type": "text.ended", "sid": sid, "messageID": message_id, "text": str(data.get("text") or "")}
    if kind == "session.reasoning.started":
        return {"type": "reasoning.started", "sid": sid, "messageID": message_id}
    if kind == "session.reasoning.delta":
        return {
            "type": "reasoning.delta",
            "sid": sid,
            "messageID": message_id,
            "delta": str(data.get("delta") or ""),
        }
    if kind == "session.reasoning.ended":
        return {"type": "reasoning.ended", "sid": sid, "messageID": message_id, "text": str(data.get("text") or "")}
    if kind == "session.tool.input.started":
        # o nome da ferramenta chega aqui (o `tool.called` não o repete)
        call_id = str(data.get("id") or "")
        if call_id:
            _TOOL_NAMES[call_id] = str(data.get("name") or "")
            if len(_TOOL_NAMES) > _SHADOW_MAX * 2:
                for old in list(_TOOL_NAMES)[: len(_TOOL_NAMES) - _SHADOW_MAX * 2]:
                    _TOOL_NAMES.pop(old, None)
        return None
    if kind == "session.tool.called":
        call_id = str(data.get("id") or "")
        tool_input = data.get("input")
        name = _infer_tool(_TOOL_NAMES.get(call_id, ""), tool_input)
        # v0.7.11-web23: foto do arquivo ANTES da alteração
        path = _tool_path(name, tool_input)
        if path and call_id:
            _SHADOW[call_id] = {"path": path, "before": _read_text(path)}
            if len(_SHADOW) > _SHADOW_MAX:
                for old in list(_SHADOW)[: len(_SHADOW) - _SHADOW_MAX]:
                    _SHADOW.pop(old, None)
        return {
            "type": "tool.started",
            "sid": sid,
            "messageID": message_id,
            "callID": call_id,
            "name": name,
            "input": tool_input,
        }
    if kind == "session.tool.progress":
        return {
            "type": "tool.progress",
            "sid": sid,
            "messageID": message_id,
            "callID": str(data.get("id") or ""),
            "metadata": data.get("metadata") or {},
        }
    if kind in ("session.tool.success", "session.tool.error"):
        chunks = []
        for item in data.get("content") or []:
            if isinstance(item, dict) and item.get("text"):
                chunks.append(str(item["text"]))
        call_id = str(data.get("id") or "")
        name = _infer_tool(_TOOL_NAMES.pop(call_id, ""), None)
        # v0.7.11-web23: diff do arquivo alterado (adição/supressão)
        diff = None
        shadow = _SHADOW.pop(call_id, None)
        if shadow and shadow.get("path"):
            after = _read_text(shadow["path"])
            before = str(shadow.get("before") or "")
            if after != before:
                diff = {"file": shadow["path"], **_line_diff(before, after)}
        payload = {
            "type": "tool.finished",
            "sid": sid,
            "messageID": message_id,
            "callID": call_id,
            "name": name,
            "status": "error" if kind.endswith("error") else "completed",
            "output": "".join(chunks) or None,
            "metadata": data.get("metadata") or {},
        }
        if diff:
            payload["diff"] = diff
        return payload
    if kind == "session.retry.scheduled":
        # v0.7.11-web27: o motor agendou uma nova tentativa (cota/saturação).
        # A interface mostra que o servidor está sobrecarregado e que o
        # retry está em curso — nada foi perdido.
        error = data.get("error") or {}
        return {
            "type": "retry.scheduled",
            "sid": sid or str(data.get("sessionID") or ""),
            "messageID": message_id or str(data.get("assistantMessageID") or ""),
            "attempt": int(data.get("attempt") or 0),
            "delayMs": int(error.get("retryAfterMs") or 0),
            "status": int(error.get("status") or 0),
            "errorType": str(error.get("type") or ""),
            "message": str(error.get("message") or ""),
            "reason": _error_reason(error),
        }
    if kind == "form.created":
        # v0.7.11-web38: a ferramenta ``question`` cria um formulário — o
        # cliente precisa buscá-lo e mostrar as opções para o usuário.
        form = data.get("form") or {}
        fsid = str(form.get("sessionID") or sid) if isinstance(form, dict) else sid
        return {
            "type": "form.created",
            "sid": fsid,
            "id": str(form.get("id") or "") if isinstance(form, dict) else "",
        }
    if kind in ("form.replied", "form.cancelled"):
        return {
            "type": kind,
            "sid": sid or str(data.get("sessionID") or ""),
            "id": str(data.get("id") or ""),
        }
    if kind == "permission.asked":
        # v0.7.11-web24: o motor pede licença para agir — a web precisa
        # mostrar as opções (permitir uma vez / sempre / rejeitar).
        return {
            "type": "permission.asked",
            "sid": sid or str(data.get("sessionID") or ""),
            "id": str(data.get("id") or ""),
            "action": str(data.get("action") or ""),
            "resources": [str(r) for r in (data.get("resources") or [])],
            "save": [str(r) for r in (data.get("save") or [])],
            "metadata": data.get("metadata") or {},
            "source": data.get("source") or {},
            "message": str(data.get("message") or ""),
        }
    if kind == "permission.replied":
        return {
            "type": "permission.replied",
            "sid": sid or str(data.get("sessionID") or ""),
            "id": str(data.get("requestID") or ""),
            "decision": str(data.get("reply") or ""),
        }
    if kind == "session.inbox.enqueued":
        payload = item.get("payload") or {}
        return {
            "type": "inbox.enqueued",
            "sid": sid,
            "text": str(payload.get("text") or ""),
        }
    if kind == "session.inbox.delivered":
        return {"type": "inbox.delivered", "sid": sid}
    if kind == "session.usage.updated":
        return {
            "type": "usage",
            "sid": sid,
            "tokens": data.get("tokens") or {},
            "cost": data.get("cost") or 0,
        }
    if kind == "session.updated":
        return {"type": "session.updated", "sid": sid, "title": str(data.get("title") or "")}
    if kind == "session.error" or kind == "message.error":
        error = event.get("error")
        text = error.get("message") if isinstance(error, dict) else error
        payload = {
            "type": "error",
            "sid": sid,
            "error": str(text or "erro desconhecido"),
        }
        if isinstance(error, dict):
            payload["status"] = int(error.get("status") or 0)
            payload["reason"] = _error_reason(error)
            payload["retryAfterMs"] = int(error.get("retryAfterMs") or 0)
        return payload
    return None
