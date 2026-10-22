# -*- coding: utf-8 -*-
"""Sessoes do OpenCode: listagem, exportacao e restauracao (v0.6.25).

Este modulo concentra as tres operacoes que dependem do motor e que estavam
quebradas na v0.6.25 (diagnostico de 21/10/2026, verificado ao vivo no motor
v2.1.2):

1. `list_sessions()` — lista as sessoes do **servidor** (`opencode api
   session.list`). A listagem antiga (`opencode session list --format json`)
   e escopada por projeto e resolvida pelo CWD do processo; como o wrapper
   roda no diretorio do Drive e as sessoes da TUI vivem no projeto `/root`,
   a listagem voltava VAZIA — o que quebrava o "Historico de Sessoes" e a
   descoberta de sessao do "Salvar backup".

2. `export_session()` — exporta a sessao em JSON (formato v2 do motor).

3. `prepare_import_payload()` — prepara um backup para `session import`.
   O import do motor v2 tem duas limitacoes reais:
     * o payload legado v1 (motor 1.15-1.18) e rejeitado com HTTP 400
       (esquema de mensagens `{info, parts}` em vez de mensagens planas,
       `tokens` com a chave extra `total`, `info` sem `location`);
     * ids de mensagem que ja existem na base provocam HTTP 500
       (violacao de unicidade) — e o caso comum ao restaurar um backup
       recente, cuja sessao de origem continua viva.
   Aqui o payload e convertido (v1 -> v2), saneado (tipos de mensagem e
   `outcome` que o import nao aceita) e recebe **ids novos**.

O arquivo original do Drive nunca e alterado.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "SessionError",
    "list_sessions",
    "export_session",
    "export_session_to_file",
    "export_session_verified",
    "validate_export",
    "write_backup_atomic",
    "detect_format",
    "convert_v1_to_v2",
    "sanitize_v2",
    "prepare_import_payload",
    "import_session",
    "AUTOSAVE_SLOTS",
    "autosave_paths",
    "rotate_autosave",
    "save_autosave",
    "list_autosaves",
    "BACKUP_FILE_RE",
    "AUTOSAVE_FILE_RE",
    "parse_backup_filename",
    "human_size",
    "list_backups",
]


class SessionError(Exception):
    """Falha operacional nas operacoes de sessao."""


# ── utilitarios ──────────────────────────────────────────────────────────

def _run(cmd: List[str], env: Optional[Dict[str, str]] = None,
         timeout: int = 60) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              env=env, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise SessionError(f"Tempo esgotado: {' '.join(cmd[:3])}") from exc
    except OSError as exc:
        raise SessionError(str(exc)) from exc


def _new_session_id() -> str:
    return "ses_" + secrets.token_hex(8)


def _new_message_id() -> str:
    return "msg_" + secrets.token_hex(12)


def _now_ms() -> int:
    return int(time.time() * 1000)


# ── 1. listagem (servidor, nao CWD) ──────────────────────────────────────

def list_sessions(binary: str, env: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    """Lista as sessoes do motor em execucao.

    Usa `opencode api session.list`, que consulta o servidor e portanto
    enxerga todas as sessoes, independentemente do diretorio de trabalho do
    processo. A listagem antiga (CLI escopada por projeto) era a causa do
    historico vazio.
    """
    r = _run([binary, "api", "session.list"], env=env, timeout=60)
    out = (r.stdout or "").strip()
    if not out:
        # Sem servidor no ar: cai para a CLI (funciona quando o CWD e o
        # projeto certo) e devolve lista vazia em vez de quebrar a interface.
        return []
    try:
        data = json.loads(out)
    except ValueError:
        return []
    if isinstance(data, dict):
        sessions = data.get("data")
        if sessions is None:
            sessions = data.get("sessions") or []
    else:
        sessions = data
    return [s for s in (sessions or []) if isinstance(s, dict)]


# ── 2. exportacao ────────────────────────────────────────────────────────

def export_session(binary: str, session_id: str,
                   env: Optional[Dict[str, str]] = None,
                   timeout: int = 120) -> str:
    """Exporta a sessao e devolve o JSON (texto).

    ATENCAO: capturar a saida do motor por **pipe** trunca o payload em
    multiplos de 64 KB (medido: 5 de 6 exports via `capture_output` sairam
    com JSON invalido — 196608, 262144, 393216 bytes). O motor escreve
    direto no arquivo e o resultado e sempre valido. Use
    `export_session_to_file` sempre que a sessao for grande.
    """
    r = _run([binary, "session", "export", session_id], env=env, timeout=timeout)
    if r.returncode == 0 and (r.stdout or "").strip():
        return r.stdout
    # Compatibilidade com motor mais antigo: `opencode export <id>`.
    r2 = _run([binary, "export", session_id], env=env, timeout=timeout)
    if r2.returncode == 0 and (r2.stdout or "").strip():
        return r2.stdout
    raise SessionError((r.stderr or r2.stderr or "Falha ao exportar sessao.")[:400])


def export_session_to_file(binary: str, session_id: str, out_path: str,
                            env: Optional[Dict[str, str]] = None,
                            timeout: int = 180) -> Tuple[Dict[str, Any], str]:
    """Exporta a sessao **direto para um arquivo** e valida o resultado.

    O motor escreve no arquivo (sem pipe no meio) — isso elimina o
    truncamento em blocos de 64 KB que fazia o "Salvar backup" falhar de
    forma intermitente. Devolve (payload, formato).
    """
    cmd = [binary, "session", "export", session_id]
    try:
        with open(out_path, "wb") as fh:
            proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.PIPE,
                                  env=env, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise SessionError(f"Tempo esgotado ao exportar a sessao ({timeout}s).") from exc
    except OSError as exc:
        raise SessionError(str(exc)) from exc

    if proc.returncode != 0:
        err = (proc.stderr or b"").decode("utf-8", "replace").strip()
        raise SessionError((err or "Falha ao exportar a sessao.")[:300])

    size = os.path.getsize(out_path) if os.path.exists(out_path) else 0
    if size == 0:
        raise SessionError("O export devolveu um arquivo vazio.")

    try:
        with open(out_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except ValueError as exc:
        hint = " (tamanho com potencia exata de 2 — truncamento em bloco de 64 KB)" \
            if size and (size & (size - 1)) == 0 else ""
        raise SessionError(
            f"JSON invalido no export ({size} bytes{hint}): {str(exc)[:110]}"
        ) from exc

    if not isinstance(data.get("info"), dict):
        raise SessionError("O export nao contem o cabecalho 'info' da sessao.")
    messages = data.get("messages")
    if not isinstance(messages, list) or not messages:
        raise SessionError("A sessao exportada nao contem mensagens.")
    fmt = detect_format(data)
    if fmt == "desconhecido":
        raise SessionError("Esquema de sessao desconhecido no export.")
    return data, fmt


def validate_export(text: str) -> Tuple[Dict[str, Any], str]:
    """Valida o JSON exportado. Devolve (payload, formato).

    Levanta `SessionError` com o motivo exato (JSON truncado, sem
    mensagens, esquema desconhecido) — e o que permite ao "Salvar backup"
    repetir o export em vez de gravar arquivo corrompido no Drive.
    """
    if not (text or "").strip():
        raise SessionError("O export devolveu saida vazia.")
    try:
        data = json.loads(text)
    except ValueError as exc:
        size = len(text.encode("utf-8"))
        hint = " (tamanho com potencia exata de 2 — truncamento tipico do FUSE)" \
            if size and (size & (size - 1)) == 0 else ""
        raise SessionError(
            f"JSON invalido no export ({size} bytes{hint}): {str(exc)[:120]}"
        ) from exc
    if not isinstance(data, dict):
        raise SessionError("O export nao devolveu um objeto de sessao.")
    if not isinstance(data.get("info"), dict):
        raise SessionError("O export nao contem o cabecalho 'info' da sessao.")
    messages = data.get("messages")
    if not isinstance(messages, list) or not messages:
        raise SessionError("A sessao exportada nao contem mensagens.")
    fmt = detect_format(data)
    if fmt == "desconhecido":
        raise SessionError("Esquema de sessao desconhecido no export.")
    return data, fmt


def export_session_verified(binary: str, session_id: str,
                            env: Optional[Dict[str, str]] = None,
                            attempts: int = 3,
                            timeout: int = 120,
                            out_path: str = "") -> Tuple[str, Dict[str, Any]]:
    """Exporta a sessao e so devolve o JSON depois de valida-lo.

    Prefere a exportacao **direto para arquivo** (sem pipe), que nao sofre
    truncamento; se `out_path` for informado, devolve o texto lido dali.
    Repete enquanto o resultado nao passar em `validate_export`.
    """
    last_error = ""
    for attempt in range(1, attempts + 1):
        try:
            if out_path:
                data, fmt = export_session_to_file(
                    binary, session_id, out_path, env=env, timeout=timeout,
                )
                with open(out_path, "r", encoding="utf-8") as fh:
                    text = fh.read()
            else:
                text = export_session(binary, session_id, env=env, timeout=timeout)
                data, fmt = validate_export(text)
        except SessionError as exc:
            last_error = str(exc)
        else:
            return text, {
                "format": fmt,
                "messages": len(data.get("messages") or []),
                "bytes": len(text.encode("utf-8")),
                "attempts": attempt,
                "title": (data.get("info") or {}).get("title") or "",
            }
        if attempt < attempts:
            time.sleep(0.6 * attempt)
    raise SessionError(last_error or "Falha ao exportar a sessao.")


def write_backup_atomic(tmp_path: str, outpath: str,
                         attempts: int = 3) -> Dict[str, Any]:
    """Copia o backup para o Drive de forma **atomica e verificada**.

    O Google Drive (FUSE) trunca escritas em limites de buffer interno
    (64 KB / 256 KB / 512 KB): o arquivo aparece com o tamanho alvo no
    `stat`, mas o conteudo esta truncado. A correcao:

      1. grava em um arquivo **temporario** no mesmo diretorio (`.tmp-…`);
      2. valida lendo de volta do Drive (tamanho + JSON + estrutura);
      3. so entao renomeia para o nome final (`os.replace` = atomico).

    Se algo falhar, o temporario e removido e o backup anterior (com nome
    final) permanece intacto — nunca fica um arquivo corrompido ocupando o
    nome definitivo.
    """
    import tempfile

    src_size = os.path.getsize(tmp_path)
    directory = os.path.dirname(outpath) or "."
    os.makedirs(directory, exist_ok=True)
    last_error = ""

    for attempt in range(1, attempts + 1):
        fd, tmp_dest = tempfile.mkstemp(prefix=".tmp-backup-", suffix=".json", dir=directory)
        os.close(fd)
        try:
            shutil.copy2(tmp_path, tmp_dest)
            try:
                with open(tmp_dest, "rb") as fh:
                    os.fsync(fh.fileno())
            except OSError:
                pass
            time.sleep(0.4 + attempt * 0.3)
            try:
                os.sync()
            except (AttributeError, OSError):
                pass

            dest_size = os.path.getsize(tmp_dest)
            if dest_size != src_size:
                last_error = f"tamanho divergente (origem={src_size}, drive={dest_size})"
                continue
            with open(tmp_dest, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
            messages = payload.get("messages") if isinstance(payload, dict) else None
            if not isinstance(messages, list) or not messages:
                last_error = "conteudo gravado sem mensagens"
                continue

            os.replace(tmp_dest, outpath)
            return {
                "ok": True,
                "attempts": attempt,
                "size_bytes": dest_size,
                "messages": len(messages),
            }
        except Exception as exc:  # noqa: BLE001 — erro reportado ao usuario
            last_error = str(exc)[:200]
            try:
                os.remove(tmp_dest)
            except OSError:
                pass
            if attempt < attempts:
                time.sleep(0.8 * attempt)
    raise SessionError(last_error or "Falha ao gravar o backup no Drive.")


# ── 3. conversao / saneamento / import ───────────────────────────────────

def detect_format(data: Any) -> str:
    """'v1', 'v2' ou 'desconhecido'."""
    if not isinstance(data, dict):
        return "desconhecido"
    info = data.get("info")
    messages = data.get("messages")
    if not isinstance(info, dict) or not isinstance(messages, list):
        return "desconhecido"
    if not messages:
        if any(k in info for k in ("version", "slug", "directory", "path")):
            return "v1"
        return "v2"
    first = messages[0]
    if not isinstance(first, dict):
        return "desconhecido"
    if "info" in first and "parts" in first and "type" not in first:
        return "v1"
    if "type" in first:
        return "v2"
    return "desconhecido"


def _v2_tokens(tokens: Dict[str, Any]) -> Dict[str, Any]:
    """v1 {total,input,output,reasoning,cache} -> v2 (sem 'total')."""
    out: Dict[str, Any] = {}
    for key in ("input", "output", "reasoning"):
        if isinstance(tokens, dict) and tokens.get(key) is not None:
            out[key] = tokens[key]
    cache = tokens.get("cache") if isinstance(tokens, dict) else None
    if isinstance(cache, dict):
        out["cache"] = {k: v for k, v in cache.items() if k in ("read", "write")}
    return out


def _v1_part_to_v2_content(part: Dict[str, Any], msg_id: str,
                           tools_as_text: bool = True) -> Optional[Dict[str, Any]]:
    """Converte uma parte v1 em parte de `content` v2 (assistente).

    `tools_as_text=True` converte a chamada de ferramenta em **texto**
    (nome + saida). Motivo (verificado por import real em 21/10/2026): o
    validador do import do motor v2 aceita as partes `tool` nativas, mas
    rejeita as convertidas do formato legado — e o esquema exato aceito nao
    foi isolado. A conversao para texto preserva a conversa inteira
    (perguntas, respostas, raciocinio e a saida de cada ferramenta), que e o
    que importa ao restaurar um arquivo antigo.
    """
    ptype = part.get("type")
    if ptype == "text":
        return {
            "type": "text",
            "text": part.get("text") or "",
            "time": {"created": (part.get("time") or {}).get("created", _now_ms())},
        }
    if ptype == "reasoning":
        time_block = part.get("time") or {}
        return {
            "type": "reasoning",
            "text": part.get("text") or "",
            "time": {
                "created": time_block.get("created", _now_ms()),
                "completed": time_block.get("completed", _now_ms()),
            },
        }
    if ptype == "tool":
        state = dict(part.get("state") or {})
        output = state.get("output")
        if not isinstance(output, str):
            output = ""
        name = part.get("tool") or part.get("name") or "tool"
        if tools_as_text:
            return {
                "type": "text",
                "text": f"[ferramenta: {name}]\n{output}"[:20000],
                "time": {"created": (state.get("time") or {}).get("start", _now_ms())},
            }
        if output:
            state["content"] = [{"type": "text", "text": output}]
        state.pop("output", None)
        state.setdefault("status", "completed")
        return {
            "type": "tool",
            "id": part.get("callID") or part.get("id") or f"call_{msg_id}",
            "name": name,
            "executed": state.get("status") == "completed",
            "state": state,
        }
    return None  # step-start / step-finish / compaction


def _v1_step_finish(parts: List[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for part in parts:
        if part.get("type") != "step-finish":
            continue
        if part.get("cost") is not None:
            out["cost"] = part.get("cost")
        if part.get("tokens"):
            out["tokens"] = _v2_tokens(part.get("tokens"))
        if part.get("reason"):
            out["finish"] = part.get("reason")
            out["rawFinish"] = str(part.get("reason")).replace("-", "_")
    return out


def convert_v1_to_v2(data: Dict[str, Any], fallback_directory: str = "",
                     tools_as_text: bool = True) -> Dict[str, Any]:
    """Converte um payload v1 (motor 1.15-1.18) para o esquema v2."""
    old_info = dict(data.get("info") or {})
    session_id = str(old_info.get("id") or "")
    directory = (
        old_info.get("directory")
        or old_info.get("path")
        or (old_info.get("location") or {}).get("directory")
        or fallback_directory
        or ""
    )
    agent = old_info.get("agent") or "UFVAI"
    model = old_info.get("model") if isinstance(old_info.get("model"), dict) else None

    time_block = dict(old_info.get("time") or {})
    time_block.setdefault("created", _now_ms())
    time_block.setdefault("updated", time_block.get("created", _now_ms()))

    new_info: Dict[str, Any] = {
        "id": session_id,
        "agent": agent,
        "title": old_info.get("title") or "Sessao restaurada",
        "time": time_block,
        "location": {"directory": directory},
    }
    for key in ("model", "cost"):
        if old_info.get(key) is not None:
            new_info[key] = old_info[key]
    if old_info.get("tokens") is not None:
        new_info["tokens"] = _v2_tokens(old_info["tokens"])

    new_messages: List[Dict[str, Any]] = []
    for msg in (data.get("messages") or []):
        if not isinstance(msg, dict):
            continue
        info = msg.get("info") or {}
        parts = [p for p in (msg.get("parts") or []) if isinstance(p, dict)]
        role = str(info.get("role") or "user")
        msg_id = str(info.get("id") or f"msg_{session_id[4:16]}")
        mtime = dict(info.get("time") or {"created": _now_ms()})

        if role != "assistant":
            text = "\n".join(
                (p.get("text") or "") for p in parts
                if p.get("type") == "text" and p.get("text")
            )
            new_messages.append({
                "id": msg_id,
                "time": mtime,
                "text": text,
                "files": [],
                "agents": [],
                "type": "user",
            })
            continue

        content = []
        for part in parts:
            converted = _v1_part_to_v2_content(part, msg_id, tools_as_text)
            if converted is not None:
                content.append(converted)

        out_msg: Dict[str, Any] = {
            "id": msg_id,
            "time": mtime,
            "type": "assistant",
            "agent": agent,
            "content": content,
        }
        if model:
            out_msg["model"] = model
        out_msg.update(_v1_step_finish(parts))
        new_messages.append(out_msg)

    return {"info": new_info, "messages": new_messages}


#: Tipos de mensagem que o import do motor v2 aceita.
_IMPORTABLE_MESSAGE_TYPES = ("user", "assistant")

#: Chaves de `info` que o import aceita (as demais sao removidas).
_IMPORTABLE_INFO_KEYS = (
    "id", "projectID", "agent", "model", "cost", "tokens", "time", "title", "location",
)


def sanitize_v2(payload: Dict[str, Any], project_id: str = "",
                fallback_directory: str = "") -> Dict[str, Any]:
    """Remove o que o import do motor v2 rejeita e renova os ids.

    - `info`: mantem apenas as chaves aceitas (remove `outcome`, `slug`,
      `summary`, `version`, `path`, `directory`).
    - `messages`: mantem apenas `user` e `assistant` (o export do motor
      v2.1 tambem emite `agent-switched`, `synthetic`, `idle`,
      `model-switched`, que o import nao aceita → HTTP 500).
    - ids: `info.id` e o id de cada mensagem sao renovados — sem isso o
      import colide com as linhas ja existentes na base (HTTP 500).
    """
    out: Dict[str, Any] = {}

    old_info = dict(payload.get("info") or {})
    new_info: Dict[str, Any] = {}
    for key in _IMPORTABLE_INFO_KEYS:
        if old_info.get(key) is not None:
            new_info[key] = old_info[key]
    if project_id and not new_info.get("projectID"):
        new_info["projectID"] = project_id
    location = new_info.get("location")
    if not (isinstance(location, dict) and location.get("directory")):
        directory = old_info.get("directory") or fallback_directory
        if directory:
            new_info["location"] = {"directory": directory}
    new_info["id"] = _new_session_id()
    out["info"] = new_info

    messages: List[Dict[str, Any]] = []
    for msg in (payload.get("messages") or []):
        if not isinstance(msg, dict):
            continue
        mtype = msg.get("type")
        if mtype not in _IMPORTABLE_MESSAGE_TYPES:
            continue
        new_msg = dict(msg)
        new_msg["id"] = _new_message_id()
        if mtype == "user":
            new_msg.setdefault("files", [])
            new_msg.setdefault("agents", [])
        else:
            content = new_msg.get("content")
            if isinstance(content, str):
                new_msg["content"] = [{"type": "text", "text": content}]
        messages.append(new_msg)
    out["messages"] = messages
    return out


def prepare_import_payload(path: str, project_id: str = "",
                            fallback_directory: str = "") -> Tuple[Dict[str, Any], str]:
    """Le um backup e devolve (payload pronto para o import, formato de origem).

    Levanta `SessionError` quando o arquivo nao pode ser lido ou tem JSON
    invalido (caso dos backups truncados pelo FUSE do Drive).
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except OSError as exc:
        raise SessionError(f"Nao foi possivel ler o backup: {exc}") from exc
    except ValueError as exc:
        size = 0
        try:
            size = os.path.getsize(path)
        except OSError:
            pass
        hint = " (tamanho com potencia exata de 2 — truncamento tipico do FUSE do Drive)" \
            if size and (size & (size - 1)) == 0 else ""
        raise SessionError(
            f"Backup corrompido: JSON invalido ({size} bytes{hint}). "
            f"Causa: {str(exc)[:120]}. Gere um novo backup."
        ) from exc

    fmt = detect_format(data)
    if fmt == "v1":
        payload = convert_v1_to_v2(data, fallback_directory)
    elif fmt == "v2":
        payload = {
            "info": dict(data.get("info") or {}),
            "messages": data.get("messages") or [],
        }
    else:
        raise SessionError("Esquema de sessao desconhecido — o backup nao e compativel.")

    return sanitize_v2(payload, project_id, fallback_directory), fmt


def import_session(binary: str, payload: Dict[str, Any],
                   env: Optional[Dict[str, str]] = None,
                   timeout: int = 180) -> str:
    """Grava o payload em /tmp e chama `opencode session import`.

    Devolve o id da sessao importada. Levanta `SessionError` com a mensagem
    do motor quando o import falha.
    """
    import tempfile

    fd, tmp = tempfile.mkstemp(prefix="ufvai-restore-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
        r = _run([binary, "session", "import", tmp], env=env, timeout=timeout)
        out = ((r.stdout or "") + (r.stderr or "")).strip()
        if r.returncode != 0 or "Imported" not in out:
            first = out.splitlines()[0] if out else "Falha ao importar a sessao."
            raise SessionError(first[:400])
        for line in out.splitlines():
            if "Imported session:" in line:
                return line.split("Imported session:")[-1].strip()
        return str((payload.get("info") or {}).get("id") or "")
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


# ── autosave (v0.7.0) ────────────────────────────────────────────────────

#: Quantidade de autosaves mantidos no Drive (o mais recente + 2 de fallback).
AUTOSAVE_SLOTS = 3

#: v0.7.3 — Quantidade de COPIAS PRESERVADAS de interacoes anteriores.
#: Cada copia e' o ULTIMO autosave de uma interacao distinta (a conversa
#: que terminou quando o usuario entrou numa nova). Vivem nos slots
#: `autosave_4..6`; os slots 1..3 continuam sendo a rotacao da interacao
#: ATUAL. Com isso o autosave de agora NUNCA destroi o backup da sessao
#: anterior — a exigencia do autor: "manter uma copia do ultimo backup das
#: ultimas tres interacoes e depois comecar com o autosave atual".
AUTOSAVE_HISTORY_SLOTS = 3

#: Prefixo dos arquivos de autosave.
AUTOSAVE_PREFIX = "autosave_"


def autosave_paths(directory: str) -> List[str]:
    """Caminhos dos 3 autosaves, do mais recente (1) ao mais antigo (3)."""
    return [
        os.path.join(directory, f"{AUTOSAVE_PREFIX}{i}.json")
        for i in range(1, AUTOSAVE_SLOTS + 1)
    ]


def autosave_history_paths(directory: str) -> List[str]:
    """Slots de HISTORICO (v0.7.3): 4..6.

    Guardam a copia preservada do ULTIMO autosave de cada uma das ultimas
    3 interacoes. Vivem na MESMA pasta (e com o mesmo padrao de nome
    `autosave_<n>.json`) para que o `POST /api/restore` e o calendario do
    "Restaurar" os tratem exatamente como os demais autosaves.
    """
    return [
        os.path.join(directory, f"{AUTOSAVE_PREFIX}{AUTOSAVE_SLOTS + i}.json")
        for i in range(1, AUTOSAVE_HISTORY_SLOTS + 1)
    ]


def rotate_autosave(directory: str) -> None:
    """Rotaciona os autosaves: 3 -> (descarta), 2 -> 3, 1 -> 2.

    Deixa o **slot 1 livre** para o arquivo novo, que e' gravado logo em
    seguida (de forma atomica). Se a gravacao falhar, o autosave anterior
    continua no slot 2 e o fallback (`list_autosaves`) assume.
    """
    paths = autosave_paths(directory)
    try:
        os.remove(paths[2])
    except OSError:
        pass
    for src, dst in ((paths[1], paths[2]), (paths[0], paths[1])):
        if os.path.exists(src):
            try:
                os.replace(src, dst)
            except OSError:
                pass


def content_digest(path: str) -> str:
    """SHA-256 do **(id da sessao + mensagens)** de um export/autosave.

    O digest ignora o resto do cabecalho `info` — nele mora
    `time.updated`/`viewed`, que o motor mexe a cada visualizacao/export.
    Duas rodadas do autosave **sem mensagem nova** produzem, portanto, o
    **mesmo** digest: e' o que permite nao gravar tres copias do mesmo
    arquivo (o que o autor reclamou). Sessoes diferentes tem digest
    diferente (o `id` entra no calculo) — logo, trocar de sessao grava.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return ""
    if not isinstance(data, dict):
        return ""
    info = data.get("info") if isinstance(data.get("info"), dict) else {}
    messages = data.get("messages")
    if not isinstance(messages, list):
        return ""
    # v0.7.3: a chave ESTAVEL do digest e' `info.time.created` (o instante
    # em que a conversa nasceu) e NAO `info.id`. O motor RE-GEROU o id da
    # sessao a cada reinicio do terminal (a MESMA conversa aparece com
    # `time.created` igual e `id` diferente) — usar o id fazia o digest
    # mudar a cada restart e o autosave gravar "versoes distintas" do
    # MESMO conteudo, misturando duas conversas nos 3 slots.
    time_info = info.get("time") if isinstance(info.get("time"), dict) else {}
    stable_key = time_info.get("created") or info.get("id", "")
    blob = json.dumps({"key": stable_key, "messages": messages},
                      sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def logical_session_key(path: str) -> str:
    """Chave ESTAVEL da conversa de um autosave (v0.7.3).

    E' o `info.time.created` do export (o instante em que a conversa
    nasceu). O `info.id` NAO serve: o motor re-gera o id a cada reinicio
    do terminal, entao a MESMA conversa aparece com ids diferentes. Sem
    essa distincao, o "ultimo backup" da conversa anterior era
    sobrescrito pelo autosave da nova — e o fallback misturava as duas.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return ""
    if not isinstance(data, dict):
        return ""
    info = data.get("info") if isinstance(data.get("info"), dict) else {}
    time_info = info.get("time") if isinstance(info.get("time"), dict) else {}
    return str(time_info.get("created") or info.get("id", ""))


def preserve_autosave_history(directory: str) -> Optional[Dict[str, Any]]:
    """Preserva o ULTIMO autosave da interacao que terminou (v0.7.3).

    Chamado quando o autosave detecta que a conversa mudou (nova
    interacao). Copia o slot 1 (o ultimo backup da conversa anterior)
    para um slot de historico (4..6), preservando o mtime original — o
    calendario do "Restaurar" continua mostrando a data real do backup.
    No maximo 3 copias: as 3 interacoes mais recentes.
    """
    live = autosave_paths(directory)
    if not live or not os.path.exists(live[0]):
        return None
    key = logical_session_key(live[0])
    if not key:
        return None
    history = autosave_history_paths(directory)
    # ja preservado? (mesma interacao) -> nao duplica
    for hpath in history:
        if os.path.exists(hpath) and logical_session_key(hpath) == key:
            return None
    # alvo: o slot de historico mais antigo (rotacao)
    target: Optional[str] = None
    target_mtime: Optional[float] = None
    for hpath in history:
        if not os.path.exists(hpath):
            target = hpath
            break
        try:
            mtime = os.path.getmtime(hpath)
        except OSError:
            mtime = 0.0
        if target_mtime is None or mtime < target_mtime:
            target, target_mtime = hpath, mtime
    if not target:
        return None
    tmp = target + ".tmp-preserve"
    try:
        shutil.copy2(live[0], tmp)
        os.replace(tmp, target)
    except OSError:
        try:
            os.remove(tmp)
        except OSError:
            pass
        return None
    return {"path": target, "key": key}


def save_autosave(binary: str, session_id: str, directory: str,
                  env: Optional[Dict[str, str]] = None,
                  attempts: int = 3) -> Dict[str, Any]:
    """Grava um autosave da sessao no Drive, mantendo os 3 ultimos.

    Usa o mesmo pipeline robusto do "Salvar backup": export direto para
    arquivo (sem pipe), validacao, escrita atomica e rotacao com fallback.

    **Um autosave por ciclo (v0.7.1):** se o conteudo exportado (id da
    sessao + mensagens) for identico ao do slot 1 (o autosave mais
    recente), o arquivo **nao e' gravado de novo** e a rotacao nao
    acontece. Sem isso, cada ciclo gravava uma copia do *mesmo* conteudo
    e os 3 slots viravam tres copias do mesmo arquivo (o que o autor
    reclamou). O slot 1 passa a ser sempre o conteudo mais recente
    **distinto**; slots 2 e 3 ficam como fallback.

    **Ordem da rotacao (corrigida na v0.7.0):** a rotacao acontece ANTES
    da gravacao — o slot 1 (mais recente) e' esvaziado pelo deslocamento
    (1 -> 2, 2 -> 3, o 3 antigo e' descartado) e so entao o arquivo novo
    entra no slot 1. Antes, a rotacao vinha DEPOIS da gravacao e levava o
    arquivo recem-gravado do slot 1 para o slot 2, deixando o **slot 1
    sempre vazio** (e o "mais recente" fora do lugar documentado).
    """
    os.makedirs(directory, exist_ok=True)
    tmp_export = os.path.join("/tmp", f"{AUTOSAVE_PREFIX}export.json")
    data, fmt = export_session_to_file(binary, session_id, tmp_export, env=env)
    paths = autosave_paths(directory)
    saved_at = time.time()
    meta = {
        "path": paths[0],
        "size_bytes": os.path.getsize(tmp_export) if os.path.exists(tmp_export) else 0,
        "messages": len(data.get("messages") or []),
        "title": (data.get("info") or {}).get("title") or "",
        "session_id": session_id,
        "format": fmt,
        "saved_at": saved_at,
        "saved_at_iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(saved_at)),
        "saved_at_local": time.strftime("%d/%m/%Y %H:%M:%S", time.localtime(saved_at)),
    }
    # v0.7.1: nao grava copia do mesmo conteudo (3 slots = 3 versoes
    # distintas, nao 3 copias do mesmo arquivo)
    new_digest = content_digest(tmp_export)
    if new_digest and os.path.exists(paths[0]):
        if new_digest == content_digest(paths[0]):
            meta.update({"ok": True, "skipped": True,
                         "reason": "conteudo_identico",
                         "slots": AUTOSAVE_SLOTS})
            return meta
    # v0.7.3: se a CONVERSA mudou (nova interacao), preserva o ultimo
    # autosave da conversa anterior antes de rotacionar — o autosave de
    # agora nao pode destruir o backup da sessao anterior. A copia vai
    # para os slots de historico (4..6).
    new_key = logical_session_key(tmp_export)
    if new_key and os.path.exists(paths[0]):
        old_key = logical_session_key(paths[0])
        if old_key and old_key != new_key:
            preserve_autosave_history(directory)
    # 1. rotaciona (o slot 1 fica livre; se a gravacao falhar, o anterior
    #    continua no slot 2 e o fallback assume)
    rotate_autosave(directory)
    # 2. grava o novo no slot 1 (escrita atomica: temp + validacao + replace)
    info = write_backup_atomic(tmp_export, paths[0], attempts=attempts)
    meta.update({"ok": True, "skipped": False,
                 "size_bytes": info.get("size_bytes", meta["size_bytes"]),
                 "messages": info.get("messages", meta["messages"]),
                 "attempts": info.get("attempts", 1),
                 "slots": AUTOSAVE_SLOTS})
    return meta


def list_autosaves(directory: str) -> List[Dict[str, Any]]:
    """Autosaves validos no Drive, do mais recente para o mais antigo.

    Cada arquivo e lido e validado: um autosave truncado (FUSE) e
    descartado, e o proximo da fila vira o candidato. E o fallback
    exigido: se o ultimo falhar, o anterior assume.
    """
    found: List[Dict[str, Any]] = []
    # v0.7.3: slots 1..3 (rotacao da interacao atual) + 4..6 (copias
    # preservadas das ultimas 3 interacoes) — o fallback da retomada
    # alcanca as conversas anteriores.
    live_paths = autosave_paths(directory)
    history_paths = autosave_history_paths(directory)
    for path in live_paths + history_paths:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            continue  # corrompido/truncado: ignora e segue para o proximo
        if not isinstance(data, dict):
            continue
        info = data.get("info")
        messages = data.get("messages")
        if not isinstance(info, dict) or not isinstance(messages, list) or not messages:
            continue
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            mtime = time.time()
        found.append({
            "path": path,
            # v0.7.1: o nome DEVIA vir prefixado com "autosave/" — e' o
            # mesmo formato usado por `list_backups()`. Sem o prefixo, o
            # POST /api/restore tratava o autosave como se fosse backup de
            # sessao e respondia "Este arquivo nao e um backup de sessao":
            # a retomada na ENTRADA falhava (o botao "Restaurar", que usa
            # list_backups, funcionava).
            "file": "autosave/" + os.path.basename(path),
            "name": os.path.basename(path),
            # v0.7.3: True = copia preservada de uma interacao anterior.
            "history": path in history_paths,
            "session_id": info.get("id", ""),
            "title": info.get("title", ""),
            "messages": len(messages),
            "saved_at": mtime,
            "saved_at_iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(mtime)),
            "saved_at_local": time.strftime("%d/%m/%Y %H:%M:%S", time.localtime(mtime)),
        })
    found.sort(key=lambda item: item["saved_at"], reverse=True)
    return found


# ─────────────────────────────────────────────────────────────────────────
# v0.7.0 — Listagem de backups por data (calendario + filtro por data)
# ─────────────────────────────────────────────────────────────────────────
#
# O modal "Restaurar" listava TODOS os arquivos .json da pasta `backups/`,
# o que misturava backups de sessao com arquivos que NAO sao backup
# (`keys_store.json`, `keys.json`, `aakeys.json`, `ufvai_consentimento*.json`)
# e quebrava o backup mais recente do motor (v2) — todos os outros sao v1
# (motor 1.15-1.18).
#
# Aqui a listagem e filtrada pelo padrao de nome do backup e enriched com
# data/hora, tamanho e integridade, para que a interface possa montar um
# CALENDARIO e um FILTRO por data.

#: Nome dos backups gerados pelo "Salvar backup":
#: ``backup_ses_<id>_<HH-MM-SS>_<DD-MM-YYYY>.json``
BACKUP_FILE_RE = re.compile(
    r"^backup_ses_(?P<sid>[0-9A-Za-z]{3,40})_"
    r"(?P<hh>\d{2})-(?P<mi>\d{2})-(?P<ss>\d{2})_"
    r"(?P<dd>\d{2})-(?P<mm>\d{2})-(?P<yyyy>\d{4})\.json$"
)

#: Prefixo minimo para um arquivo da pasta `backups/` ser considerado
#: backup de sessao (o nome completo e conferido por BACKUP_FILE_RE).
BACKUP_PREFIX = "backup_"

#: Autosaves: ``autosave_<slot>.json`` (pasta ``backups/autosave/``).
AUTOSAVE_FILE_RE = re.compile(r"^autosave_(?P<slot>[1-9][0-9]*)\.json$")


def parse_backup_filename(fname: str) -> Optional[Dict[str, Any]]:
    """Data/hora e id de sessao a partir do nome de um backup.

    Retorna ``None`` quando o nome nao segue o padrao do "Salvar backup".
    """
    match = BACKUP_FILE_RE.match(fname or "")
    if not match:
        return None
    try:
        stamp = datetime.datetime(
            int(match["yyyy"]), int(match["mm"]), int(match["dd"]),
            int(match["hh"]), int(match["mi"]), int(match["ss"]),
        )
    except ValueError:
        return None  # data inexistente (ex.: 31/02)
    return {
        "session_id": match["sid"],
        "datetime": stamp,
        "date": stamp.strftime("%Y-%m-%d"),
        "time": stamp.strftime("%H:%M:%S"),
        "timestamp": stamp.timestamp(),
    }


def human_size(num_bytes: int) -> str:
    """Tamanho em KB/MB/GB, com separador de milhar pt-BR."""
    try:
        value = float(num_bytes or 0)
    except (TypeError, ValueError):
        return "0 B"
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:,.1f}".replace(".", ",") + f" {unit}"
        value /= 1024
    return f"{value:,.1f} GB"


def _json_intact(path: str) -> bool:
    """Heuristica barata de integridade do JSON.

    O FUSE do Google Drive trunca arquivos grandes em multiplos de 64 KB
    (ou 256 KB) e o resultado fica sem a chave de fechamento. Verificar
    apenas os 2 ultimos bytes detecta o truncamento **sem ler o arquivo
    inteiro** (44 backups x ate 1,9 MB = leitura cara e lenta no Drive).
    """
    try:
        size = os.path.getsize(path)
        if size <= 0:
            return False
        with open(path, "rb") as fh:
            fh.seek(max(0, size - 2))
            tail = fh.read(2)
        return tail.rstrip().endswith(b"}")
    except OSError:
        return False


def _peek_title(path: str, limit: int = 4096) -> str:
    """Titulo da sessao, lido do inicio do arquivo (leitura parcial)."""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            head = fh.read(limit)
    except OSError:
        return ""
    match = re.search(r'"title"\s*:\s*"((?:[^"\\]|\\.){0,200})"', head)
    return match.group(1) if match else ""


def list_backups(directory: str,
                 autosave_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """Backups de sessao do Drive, prontos para o calendario e o filtro.

    So entram arquivos que **sao** backup de sessao:

    * na pasta `backups/`: os que comecam por ``backup_`` e terminam em
      ``.json`` (o padrao do "Salvar backup") — os demais (``keys_store.json``,
      ``keys.json``, ``ufvai_consentimento*.json`` …) ficam de fora;
    * na pasta `backups/autosave/`: os ``autosave_<slot>.json``.

    Cada item traz os dados que a interface precisa:

    ``file``      nome (com prefixo ``autosave/`` para os autosaves);
    ``kind``      ``backup`` | ``autosave``;
    ``date``      ``YYYY-MM-DD`` (chave do calendario);
    ``time``      ``HH:MM:SS``;
    ``datetime``  ``YYYY-MM-DDTHH:MM:SS``;
    ``timestamp`` epoch (ordem cronologica);
    ``size`` / ``size_h`` bytes e tamanho legivel;
    ``title``     titulo da sessao (leitura parcial do inicio do arquivo);
    ``valid``     ``False`` quando o arquivo esta truncado/corrompido.
    """
    items: List[Dict[str, Any]] = []

    try:
        names = sorted(os.listdir(directory))
    except OSError:
        names = []

    for name in names:
        if name.startswith(".") or not name.endswith(".json"):
            continue
        if not name.startswith(BACKUP_PREFIX):
            continue  # nao e backup de sessao (chaves, consentimentos…)
        path = os.path.join(directory, name)
        try:
            if not os.path.isfile(path):
                continue
            size = os.path.getsize(path)
            mtime = os.path.getmtime(path)
        except OSError:
            continue

        meta = parse_backup_filename(name)
        if meta is None:
            # nome fora do padrao (backup antigo): usa a data do arquivo
            stamp = datetime.datetime.fromtimestamp(mtime)
            meta = {
                "session_id": "",
                "datetime": stamp,
                "date": stamp.strftime("%Y-%m-%d"),
                "time": stamp.strftime("%H:%M:%S"),
                "timestamp": mtime,
            }

        items.append({
            "file": name,
            "kind": "backup",
            "session_id": meta["session_id"],
            "date": meta["date"],
            "time": meta["time"],
            "datetime": meta["datetime"].strftime("%Y-%m-%dT%H:%M:%S"),
            "timestamp": meta["timestamp"],
            "size": size,
            "size_h": human_size(size),
            "title": _peek_title(path),
            "valid": _json_intact(path),
        })

    if autosave_dir:
        try:
            autosave_names = sorted(os.listdir(autosave_dir))
        except OSError:
            autosave_names = []
        for name in autosave_names:
            match = AUTOSAVE_FILE_RE.match(name)
            if not match:
                continue
            path = os.path.join(autosave_dir, name)
            try:
                if not os.path.isfile(path):
                    continue
                size = os.path.getsize(path)
                mtime = os.path.getmtime(path)
            except OSError:
                continue
            stamp = datetime.datetime.fromtimestamp(mtime)
            items.append({
                "file": "autosave/" + name,
                "kind": "autosave",
                "session_id": "",
                "date": stamp.strftime("%Y-%m-%d"),
                "time": stamp.strftime("%H:%M:%S"),
                "datetime": stamp.strftime("%Y-%m-%dT%H:%M:%S"),
                "timestamp": mtime,
                "size": size,
                "size_h": human_size(size),
                "title": _peek_title(path),
                "valid": _json_intact(path),
            })

    items.sort(key=lambda item: item["timestamp"], reverse=True)
    return items
