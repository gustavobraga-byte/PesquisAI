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
import string
import subprocess
import time
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Tuple

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
    "id_shape",
    "mint_id_like",
    "session_autosave_dir",
    "session_autosave_path",
    "write_session_autosave",
    "list_session_autosaves",
    "save_all_sessions",
    "infer_project_dir",
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


def _new_session_id(samples: Optional[Iterable[str]] = None) -> str:
    """Novo id de sessao **no formato nativo do motor** (correcao 23/10/2026).

    O id precisa ter o formato que o motor usa, porque o gateway do
    *free tier* do OpenCode valida o cabecalho `x-opencode-session`
    (issue #49433): `ses_` + 12 hex (componente de tempo) + 14 base62.
    Ids fora desse padrao recebem **HTTP 403 FreeTierError** —
    "OpenCode's free tier can only be used from within OpenCode" — e a
    conversa restaurada morre na primeira mensagem (ou na compactacao),
    enquanto uma sessao NOVA funciona (o proprio motor a cria).

    Antes desta correcao o id era `ses_` + 16 hex (`token_hex(8)`), o que
    fazia **toda sessao restaurada** falhar com modelos gratuitos. O
    formato agora e **inferido** dos ids nativos vivos (`samples`, do mais
    novo para o mais antigo) — nunca presumido; sem amostras, usa o padrao
    oficial (12 hex + 14 base62).
    """
    return mint_id_like("ses_", samples, fallback_hex=8)


def _new_message_id(samples: Optional[Iterable[str]] = None) -> str:
    """Novo id de mensagem no formato nativo (ver `_new_session_id`)."""
    return mint_id_like("msg_", samples, fallback_hex=12)


#: Alfabetos dos ids do motor. O formato oficial (opencode `Identifier`) e
#: ``<prefixo>_`` + 12 hex (tempo) + 14 base62; o motor opencode-go usa o
#: mesmo formato. Nao presumimos: `id_shape()` infere a partir dos ids vivos.
_HEX_CHARS = frozenset("0123456789abcdef")
_B62_CHARS = string.ascii_letters + string.digits
_DEFAULT_TAIL_PATTERN = "h" * 12 + "b" * 14

#: Formato NATIVO do id de sessao do motor (medido nos ids vivos):
#: ``ses_`` + 12 caracteres hex + 14 caracteres base62.
#:
#: **E o formato que o gateway do free tier aceita.** Reproduzido em
#: 23/10/2026: uma sessao importada com id no formato legado
#: (``ses_`` + 16 hex — o que a retomada gerava ate a v0.7.3) e recusada
#: por QUALQUER modelo free do OpenCode Zen com
#: "OpenCode's free tier can only be used from within OpenCode"; com o id
#: nativo (26 caracteres) a mesma sessao responde normalmente.
NATIVE_ID_RE = re.compile(r"^ses_[0-9a-f]{12}[0-9A-Za-z]{14}$")
LEGACY_ID_RE = re.compile(r"^ses_[0-9a-f]{16}$")


def is_native_id(value: str) -> bool:
    """True quando o id tem o formato nativo do motor (aceito pelo free tier)."""
    return bool(NATIVE_ID_RE.match(str(value or "")))


def native_ids(samples: Optional[Iterable[str]], prefix: str = "ses_") -> List[str]:
    """Filtra apenas os ids NATIVOS (ignora os legados gerados pela retomada).

    `prefix` permite o mesmo formato para `msg_` (o motor usa o mesmo
    `Identifier` para mensagens).
    """
    rx = NATIVE_ID_RE if prefix == "ses_" else re.compile(
        r"^%s[0-9a-f]{12}[0-9A-Za-z]{14}$" % re.escape(prefix))
    return [s for s in (samples or [])
            if isinstance(s, str) and rx.match(s)]


def id_shape(samples: Optional[Iterable[str]], prefix: str = "ses_",
             ) -> Optional[Tuple[int, str, str]]:
    """Formato dos ids: `(tamanho, padrao, amostra)`.

    `padrao` e uma string de `h` (hex) e `b` (base62) por posicao — p.ex.
    ``"hhhhhhhhhhhhbbbbbbbbbbbbbb"`` (12 hex + 14 base62). A amostra
    devolvida e a primeira (mais recente) com o tamanho majoritario, e
    serve de molde para o componente de tempo.

    Devolve ``None`` quando nao ha amostra utilizavel.

    **23/10/2026 — correcao:** so ids **nativos** devem ser copiados. Um
    id legado (`ses_` + 16 hex) reintroduz o bug do free tier; ids
    antigos nao podem servir de molde.
    """
    tails = [
        value[len(prefix):]
        for value in (samples or [])
        if isinstance(value, str) and value.startswith(prefix)
        and len(value) > len(prefix)
    ]
    if not tails:
        return None
    length = Counter(len(t) for t in tails).most_common(1)[0][0]
    same = [t for t in tails if len(t) == length]
    pattern = []
    for pos in range(length):
        chars = {t[pos] for t in same}
        pattern.append("h" if chars <= _HEX_CHARS else "b")
    return length, "".join(pattern), same[0]


def mint_id_like(prefix: str, samples: Optional[Iterable[str]] = None,
                 fallback_hex: int = 8,
                 taken: Optional[Iterable[str]] = None) -> str:
    """Gera um id novo **no formato nativo do motor**.

    - Com amostras NATIVAS: copia os 12 primeiros caracteres (o componente
      de tempo — que o gateway usa para checar plausibilidade) da amostra
      mais recente e sorteia os 14 restantes no alfabeto base62.
    - Sem amostra nativa: monta o formato oficial (12 hex + 14 base62).
    - `taken`: ids que nao podem ser repetidos (garante unicidade).

    **Nunca** devolve o formato legado (`ses_` + 16 hex): ids assim sao
    recusados pelo gateway do free tier (ver `NATIVE_ID_RE`).
    """
    native = native_ids(samples, prefix)
    if native:
        template = native[0][len(prefix):]
        length = len(template)
        hex_part = template[:12] if length >= 12 else template
        tail_len = max(0, length - len(hex_part))
        for _ in range(8):
            chars = list(hex_part) + [
                secrets.choice(_B62_CHARS) for _ in range(tail_len)
            ]
            candidate = prefix + "".join(chars)
            if not taken or candidate not in set(taken):
                return candidate
        # colisao com um id ja usado: sorteia so a parte aleatoria
        chars = list(hex_part) + [secrets.choice(_B62_CHARS) for _ in range(tail_len)]
        return prefix + "".join(chars)

    # Sem referencia nativa: formato oficial do OpenCode (12 hex + 14 base62).
    tail = secrets.token_hex(6) + "".join(
        secrets.choice(_B62_CHARS) for _ in _DEFAULT_TAIL_PATTERN[12:]
    )
    return _unique(prefix + tail, prefix, taken, fallback_hex)


def _plausible_hex12() -> str:
    """12 hex com aparencia de tempo (ms nos bits altos), como o motor."""
    return format((int(time.time() * 1000) << 12) & 0xFFFFFFFFFFFF, "012x")


def _unique(candidate: str, prefix: str, taken: Optional[Iterable[str]],
            fallback_hex: int) -> str:
    if not taken:
        return candidate
    used = set(taken)
    while candidate in used:
        candidate = prefix + secrets.token_hex(fallback_hex)
    return candidate


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
                fallback_directory: str = "",
                id_samples: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    """Remove o que o import do motor v2 rejeita e renova os ids.

    - `info`: mantem apenas as chaves aceitas (remove `outcome`, `slug`,
      `summary`, `version`, `path`, `directory`).
    - `messages`: mantem apenas `user` e `assistant` (o export do motor
      v2.1 tambem emite `agent-switched`, `synthetic`, `idle`,
      `model-switched`, que o import nao aceita → HTTP 500).
    - ids: `info.id` e o id de cada mensagem sao renovados — sem isso o
      import colide com as linhas ja existentes na base (HTTP 500).

    `id_samples` (23/10/2026): ids de sessoes **nativas** do motor em
    execucao (do mais novo para o mais antigo). O id novo imita esse
    formato — obrigatorio para o free tier do OpenCode, que valida o
    cabecalho `x-opencode-session` (issue #49433). Sem amostras, usa o
    padrao oficial (12 hex + 14 base62).
    """
    out: Dict[str, Any] = {}
    samples = [s for s in (id_samples or []) if isinstance(s, str)]

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
    new_info["id"] = _new_session_id(samples)
    out["info"] = new_info

    # Ids de mensagem: mesmo formato do id de sessao recem-criado (o motor
    # usa o mesmo `Identifier` para `msg_`). A amostra e o proprio id novo.
    msg_samples = [new_info["id"].replace("ses_", "msg_", 1)] + samples

    messages: List[Dict[str, Any]] = []
    for msg in (payload.get("messages") or []):
        if not isinstance(msg, dict):
            continue
        mtype = msg.get("type")
        if mtype not in _IMPORTABLE_MESSAGE_TYPES:
            continue
        new_msg = dict(msg)
        new_msg["id"] = _new_message_id(msg_samples)
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
                            fallback_directory: str = "",
                            id_samples: Optional[Iterable[str]] = None,
                            ) -> Tuple[Dict[str, Any], str]:
    """Le um backup e devolve (payload pronto para o import, formato de origem).

    Levanta `SessionError` quando o arquivo nao pode ser lido ou tem JSON
    invalido (caso dos backups truncados pelo FUSE do Drive).

    `id_samples` — ids das sessoes nativas vivas, para o id importado nascer
    no formato do motor (ver `sanitize_v2`).
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

    return sanitize_v2(payload, project_id, fallback_directory,
                       id_samples=id_samples), fmt


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


# ── v0.7.4 — um autosave POR SESSAO (varias conversas) ───────────────────

#: Pasta (dentro de `backups/autosave/`) que guarda **um arquivo por
#: conversa**: `sessions/<session_id>.json`.
#:
#: Por que: com **varias sessoes** abertas (o TUI tem abas), o autosave
#: antigo gravava **so uma** — a do terminal — e as outras conversas
#: ficavam sem backup. Agora cada conversa viva que tenha conteudo novo
#: recebe o seu proprio arquivo, e o "Restaurar" lista todos.
AUTOSAVE_SESSIONS_SUBDIR = "sessions"

#: Quantas conversas sao salvas por ciclo (protege o Drive de escrever
#: dezenas de arquivos de ~1 MB a cada minuto).
MAX_SESSIONS_PER_CYCLE = 6

#: Conversas mais velhas que isso (em segundos) deixam de ser salvas.
SESSION_AUTOSAVE_MAX_AGE_S = 6 * 3600


def session_autosave_dir(directory: str) -> str:
    """Pasta dos autosaves por sessao."""
    return os.path.join(directory, AUTOSAVE_SESSIONS_SUBDIR)


def session_autosave_path(directory: str, session_id: str) -> str:
    """Caminho do autosave de uma sessao (`sessions/<id>.json`)."""
    safe = re.sub(r"[^A-Za-z0-9_-]", "", str(session_id or ""))
    if not safe:
        return ""
    return os.path.join(session_autosave_dir(directory), safe + ".json")


def write_session_autosave(source_path: str, session_id: str,
                            directory: str) -> Dict[str, Any]:
    """Copia um export ja pronto para o arquivo da sessao.

    Não reescreve quando o conteúdo é **idêntico** (mesmo digest) — evita
    escrever ~1 MB no Drive a cada minuto sem mudança.
    """
    target = session_autosave_path(directory, session_id)
    if not target or not os.path.exists(source_path):
        return {"ok": False, "session_id": session_id}
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        digest = content_digest(source_path)
        if digest and os.path.exists(target):
            if digest == content_digest(target):
                return {"ok": True, "skipped": True, "session_id": session_id,
                        "path": target}
        tmp = target + ".tmp"
        shutil.copy2(source_path, tmp)
        os.replace(tmp, target)
        return {"ok": True, "skipped": False, "session_id": session_id,
                "path": target,
                "size_bytes": os.path.getsize(target)}
    except OSError:
        return {"ok": False, "session_id": session_id}


def _files_signature(paths: List[str]) -> Tuple[Tuple[str, int, int], ...]:
    """Assinatura (caminho, mtime_ns, tamanho) — invalida caches de listagem."""
    sig: List[Tuple[str, int, int]] = []
    for path in paths:
        try:
            st = os.stat(path)
            sig.append((path, int(st.st_mtime_ns), int(st.st_size)))
        except OSError:
            sig.append((path, 0, 0))
    return tuple(sig)


#: Cache (em processo) das listagens de autosave. Sem ele, cada abertura da
#: interface (e cada "Restaurar") relia e reparseava ate 21 MB de JSON no
#: Drive — ~1,5 s por chamada, bloqueando a pergunta de retomada.
_LIST_CACHE: Dict[str, Tuple[Tuple[Tuple[str, int, int], ...], float, List[Dict[str, Any]]]] = {}
_LIST_CACHE_TTL_S = 25.0

#: Cache (em processo) do CABECALHO de cada autosave, chaveado por
#: ``(caminho, mtime_ns, tamanho)``.
#:
#: Por que existe: o autosave rotaciona a cada minuto, e a listagem inteira
#: era invalidada quando UM slot mudava — na pratica a pergunta de retomada
#: reparseava os 21 MB do Drive a cada abertura (0,4-1,0 s). Com o cache por
#: arquivo, so o slot que mudou e' relido; os grandes ficam prontos.
_FILE_CACHE: Dict[Tuple[str, int, int], Dict[str, Any]] = {}
_FILE_CACHE_MAX = 200


def _read_autosave_cached(path: str) -> Optional[Dict[str, Any]]:
    """Cabecalho de um autosave: ``info``, ``messages`` (nº), ``mtime``, ``size``.

    Devolve ``None`` quando o arquivo esta corrompido/truncado (FUSE) ou nao
    tem o formato de sessao — o chamador simplesmente segue para o proximo.
    """
    try:
        st = os.stat(path)
    except OSError:
        return None
    key = (path, int(st.st_mtime_ns), int(st.st_size))
    hit = _FILE_CACHE.get(key)
    if hit is not None:
        return dict(hit)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    info = data.get("info")
    messages = data.get("messages")
    if not isinstance(info, dict) or not isinstance(messages, list) or not messages:
        return None
    desc = {
        "info": info,
        "messages": len(messages),
        "mtime": st.st_mtime,
        "size": int(st.st_size),
    }
    if len(_FILE_CACHE) >= _FILE_CACHE_MAX:
        # descarta a quarta parte mais antiga (dict preserva a ordem de insercao)
        for old_key in list(_FILE_CACHE)[: max(1, len(_FILE_CACHE) // 4)]:
            _FILE_CACHE.pop(old_key, None)
    _FILE_CACHE[key] = dict(desc)
    return desc


def clear_list_caches() -> None:
    """Zera os caches de listagem (testes / apos gravar um autosave)."""
    _LIST_CACHE.clear()
    _FILE_CACHE.clear()


def list_session_autosaves(directory: str) -> List[Dict[str, Any]]:
    """Autosaves por sessao (um arquivo por conversa), prontos para a lista.

    O `file` sai no mesmo formato aceito pelo `/api/restore`:
    `autosave/sessions/<session_id>.json`.
    """
    base = session_autosave_dir(directory)
    if not os.path.isdir(base):
        return []
    try:
        names = sorted(os.listdir(base))
    except OSError:
        return []
    paths = [os.path.join(base, n) for n in names
             if n.endswith(".json") and not n.startswith(".")]
    sig = _files_signature(paths)
    cached = _LIST_CACHE.get(base)
    now = time.time()
    if cached and cached[0] == sig and (now - cached[1]) < _LIST_CACHE_TTL_S:
        return [dict(item) for item in cached[2]]
    found: List[Dict[str, Any]] = []
    for name, path in zip([n for n in names if n.endswith(".json") and not n.startswith(".")], paths):
        desc = _read_autosave_cached(path)
        if desc is None:
            continue
        info = desc["info"]
        mtime = desc["mtime"]
        size = desc["size"]
        stamp = datetime.datetime.fromtimestamp(mtime)
        found.append({
            "path": path,
            "file": "autosave/" + AUTOSAVE_SESSIONS_SUBDIR + "/" + name,
            "name": name,
            "kind": "autosave-session",
            "title": info.get("title") or "",
            "session_id": info.get("id") or name[:-5],
            "messages": desc["messages"],
            "date": stamp.strftime("%Y-%m-%d"),
            "time": stamp.strftime("%H:%M:%S"),
            "datetime": stamp.strftime("%Y-%m-%dT%H:%M:%S"),
            "timestamp": mtime,
            "size": size,
            "size_h": human_size(size),
            "valid": True,
        })
    found.sort(key=lambda item: item["timestamp"], reverse=True)
    _LIST_CACHE[base] = (sig, now, [dict(item) for item in found])
    return found


def infer_project_dir(sessions: List[Dict[str, Any]]) -> str:
    """Pasta do projeto: onde vive a conversa com conteudo real.

    Ignora as sessoes de preflight (que vivem em `/root` e nao tem
    conversa) e devolve o diretorio da conversa mais atualizada com
    mensagens.
    """
    best = ""
    best_ts = 0.0
    for sess in (sessions or []):
        if not isinstance(sess, dict):
            continue
        tokens = sess.get("tokens") or {}
        try:
            has_content = int(tokens.get("input") or 0) > 0
        except (TypeError, ValueError):
            has_content = False
        if not has_content:
            continue
        location = (sess.get("location") or {}).get("directory") or ""
        if not location:
            continue
        try:
            ts = float((sess.get("time") or {}).get("updated") or 0)
        except (TypeError, ValueError):
            ts = 0.0
        if ts >= best_ts:
            best_ts = ts
            best = location
    return best


def save_all_sessions(binary: str, sessions: List[Dict[str, Any]],
                      directory: str,
                      env: Optional[Dict[str, str]] = None,
                      project_dir: str = "",
                      max_sessions: int = MAX_SESSIONS_PER_CYCLE,
                      max_age_s: int = SESSION_AUTOSAVE_MAX_AGE_S) -> Dict[str, Any]:
    """Salva **todas** as conversas vivas que tenham conteudo novo.

    Só exporta o que mudou: se o arquivo da sessão já é mais novo que a
    última atualização da conversa, ela é pulada (sem export, sem escrita
    no Drive). O resultado traz `saved`, `skipped` e `sessions` (o que foi
    gravado).
    """
    now = time.time()
    saved: List[str] = []
    skipped: List[str] = []
    failed: List[str] = []
    candidates: List[Dict[str, Any]] = []
    # O "projeto" e' deduzido das proprias conversas (a pasta onde vive a
    # conversa do autor) — mais robusto que o CWD do processo.
    effective_dir = project_dir or infer_project_dir(sessions)
    dirs_seen = set()
    for sess in (sessions or []):
        if not isinstance(sess, dict):
            continue
        sid = str(sess.get("id") or "")
        if not sid:
            continue
        location = (sess.get("location") or {}).get("directory") or ""
        if location:
            dirs_seen.add(location)
        if effective_dir and location and location != effective_dir:
            continue                      # conversa de outro projeto
        try:
            updated = float((sess.get("time") or {}).get("updated") or 0) / 1000.0
        except (TypeError, ValueError):
            updated = 0.0
        if updated and (now - updated) > max_age_s:
            continue                      # conversa parada ha muito tempo
        candidates.append(sess)
    # Se o filtro de projeto nao casou com nenhuma conversa (CWD diferente
    # do projeto), nao descarta nada: salva todas.
    if effective_dir and dirs_seen and effective_dir not in dirs_seen:
        effective_dir = ""
        candidates = [sess for sess in (sessions or []) if isinstance(sess, dict)]
    candidates.sort(key=lambda s: float((s.get("time") or {}).get("updated") or 0),
                    reverse=True)
    for sess in candidates[:max(0, int(max_sessions))]:
        sid = str(sess.get("id") or "")
        target = session_autosave_path(directory, sid)
        try:
            updated = float((sess.get("time") or {}).get("updated") or 0) / 1000.0
        except (TypeError, ValueError):
            updated = 0.0
        if target and os.path.exists(target):
            try:
                if os.path.getmtime(target) >= updated - 2:
                    skipped.append(sid)    # nada novo nesta conversa
                    continue
            except OSError:
                pass
        tmp_export = os.path.join("/tmp", f"ufvai-sess-{sid}.json")
        try:
            export_session_to_file(binary, sid, tmp_export, env=env)
        except (SessionError, OSError):
            failed.append(sid)
            continue
        res = write_session_autosave(tmp_export, sid, directory)
        if res.get("ok"):
            if res.get("skipped"):
                skipped.append(sid)
            else:
                saved.append(sid)
        else:
            failed.append(sid)
    return {"ok": True, "saved": saved, "skipped": skipped, "failed": failed,
            "total": len(saved)}


# ── ajuste ao contexto do modelo (correcao 23/10/2026) ───────────────────

#: Orcamento de contexto (em tokens) que TODA sessao restaurada deve caber.
#:
#: Por que existe: os autosaves reais do UFVAI tem ~1,1 MB (≈300 mil
#: tokens). Os modelos *free* do OpenCode Zen tem 200 mil de contexto
#: (`deepseek-v4.1-flash-free`, `glm-5.3-flash-free`, ...). Ao abrir a
#: sessao restaurada o motor ve o contexto estourado e dispara a
#: **compactacao automatica** antes de responder — e esse caminho
#: interno e' recusado pelo gateway do free tier com
#: "OpenCode's free tier can only be used from within OpenCode"
#: (issues #49587, #49592, #49433). Resultado: QUALQUER sessao restaurada
#: falha com modelo gratuito, enquanto uma sessao NOVA funciona (contexto
#: vazio, sem compactacao).
#:
#: A compactacao MANUAL (`POST /api/session/<id>/compact`) nao passa por
#: esse caminho e funciona — por isso ela e' a primeira tentativa aqui.
FREE_TIER_SAFE_TOKENS = 130_000

#: Fracao do contexto do modelo usada como orcamento. So se compacta
#: quando a sessao restaurada **nao cabe** no modelo — ou seja, quando o
#: motor teria de compactar sozinho (caminho automatico, que e' o que o
#: gateway do free tier recusa). Com folga para o system prompt, as
#: ferramentas e a proxima resposta.
CONTEXT_BUDGET_RATIO = 0.85

#: Ajuste 23/10/2026 (sem bump) — LIMITE PARA COMPACTAR.
#:
#: A compactacao MANUAL resolve bem uma sessao **pouco** acima do
#: orcamento (segundos). Para um autosave gigante (os reais chegam a
#: 9,5 MB / ~2,6 milhoes de tokens), compactar custa dezenas de segundos
#: e o resultado e' um resumo — enquanto aparar as mensagens mais antigas
#: leva milissegundos e preserva a conversa recente. Acima desta razao
#: sobre o orcamento, o restore APARA antes de importar (import unico).
COMPACT_MAX_RATIO = 1.25

#: Tempo maximo esperando a compactacao manual. Antes: 120 s (o usuario
#: ficava ~2 min olhando "Restaurando…" quando a compactacao travava).
#: Depois disso, aparar e reimportar e' sempre mais rapido.
COMPACT_WAIT_S = 30.0

#: Intervalo entre consultas de status da compactacao (era 3 s).
COMPACT_POLL_S = 1.0

#: Cache (em processo) do contexto dos modelos — evita um
#: `opencode api get /api/model` por restore (~0,5 s cada).
_MODEL_CACHE: Dict[Tuple[str, str, str], Tuple[float, int]] = {}
_MODEL_CACHE_TTL_S = 900.0

#: Cache (em processo) das amostras de id nativos — evita um
#: `opencode session list` por restore (~0,4 s cada).
_ID_SHAPE_CACHE: Dict[str, Tuple[float, List[str]]] = {}
_ID_SHAPE_TTL_S = 900.0


def native_id_samples_cached(binary: str,
                            env: Optional[Dict[str, str]] = None,
                            ) -> List[str]:
    """Ids nativos vivos (amostras), com cache em processo (v0.7.5+).

    O restore usava `list_sessions()` so para colher amostras de id — um
    processo `opencode session list` a cada restauracao (~0,4 s). O
    componente de tempo dos ids nao precisa ser fresco: so precisa ser
    plausivel para o gateway.
    """
    key = str(binary or "opencode")
    hit = _ID_SHAPE_CACHE.get(key)
    now = time.time()
    if hit and (now - hit[0]) < _ID_SHAPE_TTL_S:
        return list(hit[1])
    samples: List[str] = []
    try:
        samples = [
            str(s.get("id") or "")
            for s in list_sessions(binary, env=env)
            if str(s.get("id") or "")
        ]
    except Exception:
        samples = []
    _ID_SHAPE_CACHE[key] = (time.time(), list(samples))
    return list(samples)


def clear_restore_caches() -> None:
    """Zera os caches de metadados do motor (testes / troca de binario)."""
    _MODEL_CACHE.clear()
    _ID_SHAPE_CACHE.clear()
    try:
        _LIST_CACHE.clear()
        _FILE_CACHE.clear()
    except NameError:  # definidos mais abaixo no modulo
        pass


def estimate_tokens(payload: Dict[str, Any]) -> int:
    """Estimativa de tokens do payload (heuristica ~3,5 caracteres/token).

    Soma o JSON de cada mensagem (texto, ferramentas, resultados). Nao
    precisa ser exato: serve para decidir se a sessao cabe no contexto do
    modelo antes de o motor tentar compactar.
    """
    total = 0
    for msg in (payload.get("messages") or []):
        try:
            total += len(json.dumps(msg, ensure_ascii=False))
        except (TypeError, ValueError):
            continue
    return int(total / 3.5)


def model_context_limit(binary: str, model: Dict[str, Any],
                        env: Optional[Dict[str, str]] = None,
                        use_cache: bool = True) -> int:
    """Contexto (em tokens) do modelo da sessao; 0 quando desconhecido."""
    pid = str((model or {}).get("providerID") or "")
    mid = str((model or {}).get("id") or "")
    if not pid or not mid:
        return 0
    key = (str(binary or "opencode"), pid, mid)
    if use_cache:
        hit = _MODEL_CACHE.get(key)
        if hit and (time.time() - hit[0]) < _MODEL_CACHE_TTL_S:
            return hit[1]
    try:
        r = _run([binary, "api", "get", "/api/model"], env=env, timeout=60)
        data = json.loads(r.stdout or "[]")
    except (SessionError, ValueError, OSError):
        return 0
    items = data.get("data") if isinstance(data, dict) else data
    for item in (items or []):
        if not isinstance(item, dict):
            continue
        if item.get("providerID") == pid and item.get("id") == mid:
            try:
                limit = int((item.get("limit") or {}).get("context") or 0)
            except (TypeError, ValueError):
                return 0
            _MODEL_CACHE[key] = (time.time(), limit)
            return limit
    return 0


def context_budget(binary: str, model: Dict[str, Any],
                   env: Optional[Dict[str, str]] = None) -> int:
    """Orcamento seguro para a sessao restaurada.

    `min(55% do contexto do modelo, FREE_TIER_SAFE_TOKENS)`. Sem contexto
    conhecido, usa o teto dos modelos gratuitos. O teto fixo garante que a
    sessao continue funcionando se o usuario trocar para um modelo free de
    200 mil tokens depois de restaurar.
    """
    limit = model_context_limit(binary, model, env)
    if limit <= 0:
        # Modelo desconhecido: usa o menor contexto comum dos modelos
        # gratuitos (200 mil) como referencia.
        return FREE_TIER_SAFE_TOKENS
    return int(limit * CONTEXT_BUDGET_RATIO)


def trim_payload(payload: Dict[str, Any], budget: int) -> Tuple[Dict[str, Any], int]:
    """Apara as mensagens MAIS ANTIGAS ate o payload caber em `budget`.

    Devolve `(payload_novo, quantas_mensagens_foram_descartadas)`. Mantem
    sempre a ultima mensagem do usuario (o contexto imediato da conversa).
    """
    messages = list(payload.get("messages") or [])
    if not messages or budget <= 0:
        return dict(payload), 0
    kept: List[Dict[str, Any]] = []
    used = 0
    for msg in reversed(messages):
        try:
            size = int(len(json.dumps(msg, ensure_ascii=False)) / 3.5) + 1
        except (TypeError, ValueError):
            size = 1
        if kept and used + size > budget:
            break
        kept.append(msg)
        used += size
    kept.reverse()
    dropped = len(messages) - len(kept)
    out = dict(payload)
    out["messages"] = kept
    return out, dropped


def _compaction_status(binary: str, session_id: str,
                       env: Optional[Dict[str, str]] = None) -> str:
    """Status da compactacao MAIS RECENTE da sessao ("", "running", ...)."""
    try:
        r = _run([binary, "api", "get", f"/api/session/{session_id}/message"],
                 env=env, timeout=60)
        data = json.loads(r.stdout or "{}")
    except (SessionError, ValueError, OSError):
        return ""
    items = data.get("data") if isinstance(data, dict) else data
    for msg in (items or []):
        if isinstance(msg, dict) and msg.get("type") == "compaction":
            return str(msg.get("status") or "running")
    return ""


def compact_session(binary: str, session_id: str,
                    env: Optional[Dict[str, str]] = None,
                    wait_s: float = COMPACT_WAIT_S,
                    interval: float = COMPACT_POLL_S) -> bool:
    """Roda a compactacao MANUAL da sessao e espera terminar.

    A compactacao manual nao sofre o bloqueio do free tier (o caminho
    automatico e' que e' recusado). Devolve True quando o motor reporta
    `completed`.

    Ajuste 23/10/2026: espera de 30 s (era 120 s) e consulta de 1 s (era
    3 s). A compactacao de uma sessao que cabe logo no orcamento termina
    em poucos segundos; se em 30 s nao terminou, aparar e' mais rapido do
    que continuar esperando.
    """
    try:
        r = _run([binary, "api", "post", f"/api/session/{session_id}/compact",
                  "-d", "{}"], env=env, timeout=90)
    except SessionError:
        return False
    if r.returncode != 0:
        return False
    deadline = time.time() + max(5.0, float(wait_s))
    while time.time() < deadline:
        status = _compaction_status(binary, session_id, env)
        if status == "completed":
            return True
        if status == "failed":
            return False
        time.sleep(max(0.2, float(interval)))
    return False


def delete_session(binary: str, session_id: str,
                   env: Optional[Dict[str, str]] = None) -> bool:
    """Apaga uma sessao (best-effort) — usada ao descartar um import aparado."""
    try:
        r = _run([binary, "session", "delete", session_id], env=env, timeout=60)
        return r.returncode == 0
    except SessionError:
        return False


def plan_restore(payload: Dict[str, Any], binary: str,
                 env: Optional[Dict[str, str]] = None,
                 ratio: float = COMPACT_MAX_RATIO) -> Dict[str, Any]:
    """Decide o caminho do restore **antes** de importar.

    Tres caminhos, do mais barato para o mais caro:

    - ``none``    — cabe no orcamento: importar direto;
    - ``compact`` — ate 25% acima: importar e compactar (manual);
    - ``trim``    — muito acima: **aparar antes** e importar UMA vez.

    Antes, TODO restore importava o payload inteiro e so depois decidia;
    com um autosave de 9,5 MB (~2,6 milhoes de tokens) isso significava
    importar tudo, esperar a compactacao e, se falhasse, importar de novo
    o aparado. Agora o caso comum (conversa longa) apara primeiro.
    """
    model = dict(payload.get("info") or {}).get("model") or {}
    budget = context_budget(binary, model, env)
    before = estimate_tokens(payload)
    plan: Dict[str, Any] = {
        "action": "none",
        "tokens_before": before,
        "budget": budget,
    }
    if budget <= 0 or before <= budget:
        return plan
    limit = int(budget * max(1.0, float(ratio)))
    plan["compact_limit"] = limit
    plan["action"] = "compact" if before <= limit else "trim"
    return plan


def prepare_payload_for_restore(payload: Dict[str, Any], binary: str,
                                env: Optional[Dict[str, str]] = None,
                                ratio: float = COMPACT_MAX_RATIO,
                                ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Aplica o plano ANTES do import. Devolve ``(payload, plano)``.

    No caminho ``trim`` o payload ja sai aparado — o import grava apenas o
    que sera usado. O plano volta com ``action="trimmed"`` e
    ``messages_dropped`` para a interface informar o usuario.
    """
    plan = plan_restore(payload, binary, env=env, ratio=ratio)
    if plan["action"] != "trim":
        return payload, plan
    trimmed, dropped = trim_payload(payload, int(plan["budget"]))
    plan.update({
        "action": "trimmed",
        "messages_dropped": dropped,
        "tokens_after": estimate_tokens(trimmed),
    })
    return trimmed, plan


def fit_to_context(binary: str, session_id: str, payload: Dict[str, Any],
                   env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Faz a sessao restaurada CABER no contexto dos modelos gratuitos.

    Ordem: (1) nada a fazer, se ja cabe; (2) compactacao MANUAL (preserva
    um resumo da conversa); (3) reimportar o payload aparado (ultimas
    mensagens que cabem) e apagar o import grande.

    Sem isso, o motor dispara a compactacao AUTOMATICA ao abrir a sessao —
    caminho que o gateway do free tier recusa — e o usuario ve
    `✗ Compaction · OpenCode's free tier can only be used from within
    OpenCode` em qualquer sessao restaurada.
    """
    model = dict(payload.get("info") or {}).get("model") or {}
    budget = context_budget(binary, model, env)
    before = estimate_tokens(payload)
    result: Dict[str, Any] = {
        "session_id": session_id,
        "action": "none",
        "tokens_before": before,
        "budget": budget,
    }
    if budget <= 0 or before <= budget:
        return result

    if compact_session(binary, session_id, env):
        result["action"] = "compacted"
        result["tokens_after"] = 0  # o motor nao informa o novo total aqui
        return result

    trimmed, dropped = trim_payload(payload, budget)
    try:
        new_id = import_session(binary, trimmed, env)
    except SessionError as exc:
        result["action"] = "failed"
        result["error"] = str(exc)[:200]
        return result
    delete_session(binary, session_id, env)
    result.update({
        "session_id": new_id,
        "action": "trimmed",
        "messages_dropped": dropped,
        "tokens_after": estimate_tokens(trimmed),
    })
    return result


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
    all_paths = live_paths + history_paths
    # Ajuste 23/10/2026: cache por (mtime, tamanho). Reler 21 MB de JSON do
    # Drive a cada abertura custava ~1,5 s e atrasava a pergunta de retomada.
    sig = _files_signature(all_paths)
    cached = _LIST_CACHE.get(directory)
    now = time.time()
    if cached and cached[0] == sig and (now - cached[1]) < _LIST_CACHE_TTL_S:
        return [dict(item) for item in cached[2]]
    for path in all_paths:
        if not os.path.exists(path):
            continue
        desc = _read_autosave_cached(path)
        if desc is None:
            continue  # corrompido/truncado: ignora e segue para o proximo
        info = desc["info"]
        mtime = desc["mtime"]
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
            "messages": desc["messages"],
            "saved_at": mtime,
            "saved_at_iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(mtime)),
            "saved_at_local": time.strftime("%d/%m/%Y %H:%M:%S", time.localtime(mtime)),
        })
    found.sort(key=lambda item: item["saved_at"], reverse=True)
    _LIST_CACHE[directory] = (sig, now, [dict(item) for item in found])
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
