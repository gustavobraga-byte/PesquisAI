"""
autopilot.py — Camada de salvamento AUTÔNOMO do PesquisAI.

Este módulo é a interface que o agente LLM usa para salvar e recuperar
informações do vault do Obsidian **sem precisar que o usuário peça**.

Filosofia:
- O agente **lê** o vault antes de responder (recall)
- O agente **salva** notas automaticamente após concluir uma tarefa
- O agente **loga** a sessão ao final
- Tudo é **no-op** se o vault não estiver disponível (nunca quebra)

Uso típico pelo agente (dentro do OpenCode)::

    from pesquisai.obsidian.autopilot import (
        recall, save, context_brief, end_session,
    )

    # 1. ANTES de responder — recall
    relevant = recall("diabetes prevalência")
    for r in relevant:
        print(f"  {r['path']}: {r['snippet']}")

    # 2. DEPOIS de concluir — save autônomo
    save(
        title="Prevalência de Diabetes no Brasil",
        body="## Resultados\\n\\n- 10,2% (VIGITEL 2023)\\n[DADO CONFIRMADO]",
        tags=["pesquisai/ibge", "pesquisai/datasus"],
        template="research",
    )

    # 3. Ao final — log de sessão
    end_session(summary="Levantamento de prevalência de diabetes")
"""

from __future__ import annotations

import datetime as _dt
import logging
import os
import socket
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("pesquisai.obsidian.autopilot")

# Estado global do autopilot (singleton preguiçoso)
_mem: Optional[Any] = None
_session_started: bool = False
_session_id: Optional[str] = None
_init_attempted: bool = False


def _get_memory() -> Optional[Any]:
    """Retorna a instância de ObsidianMemory (singleton preguiçoso).

    Cria na primeira chamada. Se falhar, retorna None e não tenta de novo.
    """
    global _mem, _init_attempted
    if _init_attempted:
        return _mem
    _init_attempted = True
    try:
        from .memory import ObsidianMemory, ObsidianMemoryStatus
        m = ObsidianMemory.from_env()
        if m.status in (ObsidianMemoryStatus.READY, ObsidianMemoryStatus.READ_ONLY):
            _mem = m
            logger.info("Autopilot: memória ativa (status=%s, root=%s)", m.status.value, m.root)
        else:
            logger.info("Autopilot: memória desativada (status=%s)", m.status.value)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Autopilot: falha ao inicializar memória: %s", exc)
    return _mem


# ════════════════════════════════════════════════════════════════
# API PÚBLICA — funções que o agente chama
# ════════════════════════════════════════════════════════════════

def recall(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Busca notas relevantes no vault ANTES de responder.

    O agente deve chamar esta função no início de cada resposta para
    verificar se já existe informação sobre o tema.

    Args:
        query: texto da busca (ex.: "prevalência diabetes Brasil")
        limit: número máximo de resultados

    Returns:
        Lista de dicts com ``path``, ``title``, ``snippet``, ``score``.
        Lista vazia se o vault não estiver disponível.

    Exemplo::

        results = recall("PNAE capacidade estatal")
        if results:
            print("Já tenho notas sobre isso:")
            for r in results:
                print(f"  {r['title']} (score={r['score']:.2f})")
    """
    mem = _get_memory()
    if mem is None or not mem.enabled:
        return []
    results = mem.search(query, limit=limit)
    return [
        {
            "path": r.note.path,
            "title": r.note.metadata.title,
            "snippet": r.snippet,
            "score": round(r.score, 2),
            "tags": list(r.note.tags),
            "wikilinks": list(r.note.wikilinks),
        }
        for r in results
    ]


def save(
    title: str,
    body: str,
    *,
    tags: Optional[list[str]] = None,
    template: str = "inbox",
    path: Optional[str] = None,
    project: str = "",
) -> Optional[str]:
    """Salva uma nota no vault AUTONOMAMENTE.

    O agente deve chamar esta função **após concluir uma tarefa**
    (coleta de dados, análise, redação de seção, etc.) — não espera
    o usuário pedir.

    Args:
        title: título da nota.
        body: conteúdo Markdown da nota.
        tags: tags da taxonomia ``pesquisai/*`` (ex.: ``["pesquisai/ibge"]``).
        template: template oficial (default: ``"inbox"`` para captura rápida).
        path: caminho relativo no vault. Se None, gera automaticamente
            a partir do template + slug do título.
        project: ID do projeto (para linkar ao MOC).

    Returns:
        O caminho da nota criada, ou ``None`` se falhou.

    Exemplo::

        save(
            title="Prevalência de Diabetes no Brasil",
            body="## Resultados\\n\\n- 10,2% (VIGITEL 2023)\\n\\n[DADO CONFIRMADO]",
            tags=["pesquisai/ibge", "pesquisai/datasus"],
            template="research",
            project="diabetes",
        )
    """
    mem = _get_memory()
    if mem is None or not mem.writable:
        logger.debug("save() ignorado: memória não disponível para escrita")
        return None

    # Gera path automaticamente se não fornecido
    if path is None:
        slug = _slugify(title)
        subdir = _template_to_subdir(template)
        today = _dt.date.today().isoformat()
        if template == "daily":
            path = f"daily/{today}.md"
        elif template == "session":
            sid = _ensure_session()
            path = f"sessions/{today}-{sid}.md"
        else:
            path = f"{subdir}/{slug}.md"

    # Garante que path não colide com nota humana existente
    if mem.vault and mem.vault.exists(path):
        existing = mem.get(path)
        if existing and not existing.is_pesquisai_generated:
            # Nota humana existe — cria com sufixo
            path = path.replace(".md", "-pesquisai.md")

    context = {
        "title": title,
        "date": _dt.date.today().isoformat(),
        "project": project,
    }
    note = mem.create_note(
        path,
        title=title,
        template=template,
        tags=tuple(tags or ()),
        context=context,
    )
    if note is None:
        return None

    # Anexa o body fornecido (o template pode ter placeholders)
    if body and body.strip():
        updated = mem.update_note(note, append=body)
        if updated:
            return updated.path
    return note.path


def save_finding(
    finding: str,
    *,
    source: str = "",
    tags: Optional[list[str]] = None,
    project: str = "",
) -> Optional[str]:
    """Salva um achado rápido (capture-and-forget).

    Versão simplificada de :func:`save` para quando o agente quer apenas
    registrar algo rapidamente sem montar uma nota estruturada.

    Args:
        finding: texto do achado (1-3 frases).
        source: fonte do achado (ex.: "IBGE PNAD 2023").
        tags: tags ``pesquisai/*``.
        project: ID do projeto.

    Returns:
        Caminho da nota criada, ou ``None``.
    """
    timestamp = _dt.datetime.now().strftime("%H:%M:%S")
    title = f"Achado {timestamp}"
    body = finding.strip()
    if source:
        body += f"\n\n**Fonte:** {source}"
    return save(
        title=title,
        body=body,
        tags=tags or ["pesquisai/inbox"],
        template="inbox",
        project=project,
    )


def context_brief(max_chars: int = 3000) -> str:
    """Retorna um resumo do vault para injetar no prompt do agente.

    Inclui:
    - Notas recentes (3 últimas dailies)
    - Projetos ativos (MOCs)
    - Estatísticas do vault

    Retorna string vazia se o vault não estiver disponível.
    """
    mem = _get_memory()
    if mem is None or not mem.enabled:
        return ""
    return mem.context_brief(max_chars=max_chars)


def start_session() -> str:
    """Inicia uma sessão de log automático.

    Retorna o session_id. Se já iniciada, retorna o ID existente.
    """
    global _session_started, _session_id
    if _session_started and _session_id:
        return _session_id
    mem = _get_memory()
    if mem is None or not mem.writable:
        return ""
    _session_id = mem.start_session()
    _session_started = True
    logger.info("Autopilot: sessão iniciada (%s)", _session_id)
    return _session_id


def end_session(summary: str = "") -> Optional[str]:
    """Encerra a sessão e grava o log automaticamente.

    O agente deve chamar esta função ao final de uma conversa ou
    quando o usuário disser "tchau", "obrigado", "pode parar", etc.

    Args:
        summary: resumo da sessão (1-3 frases).

    Returns:
        Caminho da nota de sessão, ou ``None``.
    """
    global _session_started, _session_id
    if not _session_started:
        return None
    mem = _get_memory()
    if mem is None or not mem.writable:
        _session_started = False
        _session_id = None
        return None
    note = mem.end_session(summary=summary)
    _session_started = False
    _session_id = None
    logger.info("Autopilot: sessão encerrada (nota=%s)", note.path if note else "N/A")
    return note.path if note else None


def log_request(text: str) -> None:
    """Registra um pedido do usuário na sessão atual."""
    mem = _get_memory()
    if mem is None:
        return
    _ensure_session()
    if mem._session is not None:
        mem.log_request(text)


def log_skill(skill_id: str) -> None:
    """Registra o uso de uma skill na sessão atual."""
    mem = _get_memory()
    if mem is None:
        return
    _ensure_session()
    if mem._session is not None:
        mem.use_skill(skill_id)


def log_file(path: str) -> None:
    """Registra um arquivo gerado na sessão atual."""
    mem = _get_memory()
    if mem is None:
        return
    _ensure_session()
    if mem._session is not None:
        mem.log_file(path)


def stats() -> dict[str, Any]:
    """Retorna estatísticas do vault para diagnóstico."""
    mem = _get_memory()
    if mem is None or not mem.enabled:
        return {"enabled": False}
    return mem.stats()


def is_active() -> bool:
    """Retorna True se o autopilot está ativo (vault disponível)."""
    mem = _get_memory()
    return mem is not None and mem.enabled


# ════════════════════════════════════════════════════════════════
# Inicialização automática (chamada pelo setup.py / main.py)
# ════════════════════════════════════════════════════════════════

def auto_init(vault_path: Optional[str] = None) -> dict[str, Any]:
    """Inicializa o vault automaticamente na pasta do Drive.

    Esta função é chamada pelo ``setup.py`` (ou ``main.py``) na inicialização do
    PesquisAI. Ela:

    1. Define ``PESQUISAI_OBSIDIAN_VAULT`` se não estiver definida
    2. Cria a estrutura de pastas do vault se não existir
    3. Cria a daily note de hoje se não existir
    4. Inicia a sessão de log automático

    Args:
        vault_path: caminho do vault. Se None, usa o padrão do Drive.

    Returns:
        Dict com status da inicialização.
    """
    from .discovery import ensure_drive_path, _is_in_drive, DRIVE_PATH_PREFIXES  # type: ignore

    result: dict[str, Any] = {
        "enabled": False,
        "vault_path": "",
        "created": False,
        "daily_created": False,
        "session_started": False,
        "error": "",
    }

    # 1. Determinar caminho
    if vault_path is None:
        vault_path = os.environ.get("PESQUISAI_OBSIDIAN_VAULT", "").strip()
        if not vault_path:
            # Padrão: <DRIVE>/PesquisAI/vault
            drive_path = os.environ.get("PESQUISAI_DRIVE_PATH", "/content/drive/My Drive/PesquisAI")
            vault_path = os.path.join(drive_path, "vault")

    # 2. Validar que está no Drive (no Colab)
    if not _is_in_drive(vault_path):
        # Tenta o caminho padrão do Drive
        default = "/content/drive/My Drive/PesquisAI/vault"
        if _is_in_drive(default) or Path(default).parent.parent.exists():
            vault_path = default
        else:
            result["error"] = f"Caminho {vault_path} não está no Google Drive"
            logger.info("Autopilot auto_init: %s", result["error"])
            return result

    # 3. Definir variável de ambiente
    os.environ["PESQUISAI_OBSIDIAN_VAULT"] = vault_path

    # 4. Criar vault se não existir
    try:
        if not Path(vault_path).is_dir():
            ensure_drive_path(vault_path)
            result["created"] = True
            logger.info("Autopilot: vault criado em %s", vault_path)
    except Exception as exc:  # noqa: BLE001
        result["error"] = f"Falha ao criar vault: {exc}"
        logger.warning("Autopilot auto_init: %s", result["error"])
        return result

    # 5. Criar estrutura de pastas
    for sub in ["daily", "research", "literature", "sessions", "moc",
                "inbox", "hypothesis", "methodology", "reference", "datasource",
                ".obsidian", ".trash", ".backups"]:
        (Path(vault_path) / sub).mkdir(parents=True, exist_ok=True)

    # 6. Criar daily note de hoje se não existir
    today = _dt.date.today().isoformat()
    daily_path = Path(vault_path) / "daily" / f"{today}.md"
    if not daily_path.exists():
        try:
            _create_daily_note(daily_path, today)
            result["daily_created"] = True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Autopilot: falha ao criar daily: %s", exc)

    # 7. Criar MOC raiz se não existir
    moc_path = Path(vault_path) / "moc" / "index.md"
    if not moc_path.exists():
        try:
            _create_root_moc(moc_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Autopilot: falha ao criar MOC raiz: %s", exc)

    # 8. Resetar singleton para que _get_memory() re-detecte
    global _mem, _init_attempted
    _mem = None
    _init_attempted = False

    # 9. Iniciar sessão automática
    mem = _get_memory()
    if mem is not None and mem.writable:
        start_session()
        result["session_started"] = True

    result["enabled"] = is_active()
    result["vault_path"] = vault_path
    logger.info("Autopilot auto_init concluído: %s", result)
    return result


# ════════════════════════════════════════════════════════════════
# Helpers internos
# ════════════════════════════════════════════════════════════════

def _slugify(text: str) -> str:
    """Converte um título em slug (lowercase, sem acentos, hífens)."""
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", text)
    no_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    slug = no_accents.lower().strip()
    slug = slug.replace(" ", "-").replace("_", "-")
    import re
    slug = re.sub(r"[^a-z0-9\-]", "", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "nota"


def _template_to_subdir(template: str) -> str:
    """Mapeia nome do template para subpasta do vault."""
    mapping = {
        "daily": "daily",
        "daily-note": "daily",
        "research": "research",
        "research-note": "research",
        "literature": "literature",
        "literature-note": "literature",
        "session": "sessions",
        "session-log": "sessions",
        "methodology": "methodology",
        "methodology-note": "methodology",
        "datasource": "datasource",
        "data-source": "datasource",
        "data-source-note": "datasource",
        "hypothesis": "hypothesis",
        "hypothesis-note": "hypothesis",
        "reference": "reference",
        "reference-note": "reference",
        "moc": "moc",
        "project-moc": "moc",
        "inbox": "inbox",
        "inbox-note": "inbox",
    }
    return mapping.get(template, "inbox")


def _ensure_session() -> str:
    """Garante que há uma sessão ativa. Se não, inicia uma."""
    if not _session_started:
        return start_session()
    return _session_id or ""


def _create_daily_note(path: Path, date_str: str) -> None:
    """Cria uma daily note mínima."""
    content = f"""---
title: "{date_str}"
created: {date_str}
updated: {date_str}
tags:
  - pesquisai/daily
  - pesquisai/draft
author: ""
created_by: pesquisai
status: draft
source: ""
project: ""
---

# {date_str}

> **Vault:** PesquisAI v0.5.1+
> **Auto-criada pelo autopilot**

## 🎯 Foco do dia

- [ ]

## 📥 Inbox

-

## 💡 Insights

-

## 📌 Próximos passos

- [ ]
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _create_root_moc(path: Path) -> None:
    """Cria o MOC raiz do vault."""
    today = _dt.date.today().isoformat()
    content = f"""---
title: "📚 MOC raiz — Índice do Vault"
created: {today}
updated: {today}
tags:
  - pesquisai/moc
author: ""
created_by: pesquisai
status: published
---

# 📚 MOC raiz

> **Vault:** PesquisAI v0.5.1+ (autopilot)

## Projetos ativos

```dataview
LIST
FROM "moc"
WHERE file.name != "index"
SORT file.ctime DESC
```

## Daily notes recentes

```dataview
LIST
FROM "daily"
SORT file.name DESC
LIMIT 7
```

## Pesquisas em andamento

```dataview
LIST
FROM "research"
SORT file.mtime DESC
```

## Literatura revisada

```dataview
LIST
FROM "literature"
SORT file.mtime DESC
LIMIT 20
```
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
