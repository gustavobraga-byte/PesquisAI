"""
memory.py — API pública do "segundo cérebro" do PesquisAI.

O :class:`ObsidianMemory` é o ponto de entrada que o agente usa. Ele
encapsula:

- Inicialização a partir de variáveis de ambiente / convenções
- Carregamento preguiçoso de vault + índice BM25
- Operações de leitura (search, get, by_tag, ...)
- Operações de escrita controladas (log_session, create_note,
  update_note)
- Logs de auditoria (.pesquisai-audit.log)
- Sincronização opcional (push para Drive / git)

Modos de operação:

============================  ===========================================
Estado                        Comportamento
============================  ===========================================
``DISABLED``                  Módulo inativo (variável não definida)
``NO_VAULT``                  Variável definida, mas pasta não existe
``READY``                     Tudo OK — agente lê e escreve
``READ_ONLY``                 Falta permissão de escrita
``ERROR``                     Erro inesperado (ver ``last_error``)
============================  ===========================================
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import os
import socket
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Union

from .discovery import get_default_vault_path, is_available
from .links import LinkIndex
from .models import Note, SearchResult, SessionLog, TagIndex
from .search import Searcher
from .sync import SyncReport, sync_drive, sync_git
from .vault import Vault, VaultNotFoundError, VaultPermissionError

logger = logging.getLogger("pesquisai.obsidian.memory")


class ObsidianMemoryStatus(str, Enum):
    """Estado atual do módulo."""

    DISABLED = "disabled"        # PESQUISAI_OBSIDIAN_VAULT não definida
    NO_VAULT = "no_vault"        # variável definida, mas pasta não existe
    READY = "ready"              # tudo OK
    READ_ONLY = "read_only"      # sem permissão de escrita
    ERROR = "error"              # erro na inicialização


@dataclass(slots=True)
class _SessionContext:
    """Estado interno de uma sessão do agente."""

    session_id: str
    started_at: _dt.datetime
    user_requests: list[str] = None  # type: ignore[assignment]
    skills_used: list[str] = None    # type: ignore[assignment]
    notes_created: list[str] = None  # type: ignore[assignment]
    notes_updated: list[str] = None  # type: ignore[assignment]
    files_generated: list[str] = None  # type: ignore[assignment]
    tokens_in: int = 0
    tokens_out: int = 0

    def __post_init__(self) -> None:
        self.user_requests = self.user_requests or []
        self.skills_used = self.skills_used or []
        self.notes_created = self.notes_created or []
        self.notes_updated = self.notes_updated or []
        self.files_generated = self.files_generated or []


class ObsidianMemory:
    """API principal de "segundo cérebro" do PesquisAI.

    Uso típico::

        from pesquisai.obsidian import ObsidianMemory

        mem = ObsidianMemory.from_env()
        if mem.status != ObsidianMemoryStatus.READY:
            ... # módulo desativado, trabalha sem memória

        # No início da sessão: carrega contexto
        context_notes = mem.recent_daily_notes(limit=3)
        for n in context_notes:
            mem.add_to_context(n)

        # Durante a sessão: registra o que vai fazendo
        mem.start_session()
        mem.log_request("Qual a prevalência de diabetes?")
        mem.use_skill("ibge-br")
        note = mem.create_note(
            "research/diabetes-prevalencia.md",
            title="Prevalência de Diabetes no Brasil",
            template="research-note",
        )
        # ... preenche a nota ...
        mem.update_note(note)

        # No fim: grava log de sessão
        mem.end_session(summary="...")
        mem.sync_drive()
    """

    def __init__(self, vault_path: Optional[Union[str, Path]] = None) -> None:
        self.status: ObsidianMemoryStatus = ObsidianMemoryStatus.DISABLED
        self.last_error: Optional[str] = None
        self._vault: Optional[Vault] = None
        self._searcher: Optional[Searcher] = None
        self._link_index: Optional[LinkIndex] = None
        self._session: Optional[_SessionContext] = None
        self._context: list[str] = []  # notas carregadas no contexto atual

        if vault_path is None:
            vault_path = get_default_vault_path()
        if vault_path is None:
            self.status = ObsidianMemoryStatus.DISABLED
            logger.debug("PESQUISAI_OBSIDIAN_VAULT não definida — módulo desativado")
            return

        try:
            self._vault = Vault(vault_path)
        except VaultNotFoundError:
            self.status = ObsidianMemoryStatus.NO_VAULT
            logger.info("Vault %s não encontrado — módulo desativado", vault_path)
            return
        except VaultPermissionError as exc:
            self.status = ObsidianMemoryStatus.READ_ONLY
            self.last_error = str(exc)
            logger.warning("Vault read-only: %s", exc)
            return
        except Exception as exc:  # noqa: BLE001
            self.status = ObsidianMemoryStatus.ERROR
            self.last_error = repr(exc)
            logger.error("Erro ao abrir vault: %s", exc)
            return

        if not os.access(self._vault.root, os.W_OK):
            self.status = ObsidianMemoryStatus.READ_ONLY
            self.last_error = "Sem permissão de escrita"
        else:
            self.status = ObsidianMemoryStatus.READY

        self._searcher = Searcher(self._vault)
        logger.info(
            "ObsidianMemory pronto em %s (status=%s)",
            self._vault.root, self.status.value,
        )

    # ── Fábricas ──────────────────────────────────────────────────
    @classmethod
    def from_env(cls) -> "ObsidianMemory":
        """Construtor padrão a partir de variáveis de ambiente."""
        return cls()

    @classmethod
    def at(cls, path: Union[str, Path]) -> "ObsidianMemory":
        """Construtor com path explícito."""
        return cls(path)

    @property
    def enabled(self) -> bool:
        return self.status in (
            ObsidianMemoryStatus.READY,
            ObsidianMemoryStatus.READ_ONLY,
        )

    @property
    def writable(self) -> bool:
        return self.status == ObsidianMemoryStatus.READY

    @property
    def vault(self) -> Optional[Vault]:
        return self._vault

    @property
    def root(self) -> Optional[Path]:
        return self._vault.root if self._vault else None

    # ── Inicialização preguiçosa ──────────────────────────────────
    def _ensure_searcher(self) -> Searcher:
        assert self._searcher is not None
        return self._searcher

    def _ensure_links(self) -> LinkIndex:
        if self._link_index is None:
            assert self._vault is not None
            self._link_index = LinkIndex.from_vault(self._vault)
        return self._link_index

    # ══════════════════════════════════════════════════════════════
    # LEITURA
    # ══════════════════════════════════════════════════════════════

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        tags: Optional[list[str]] = None,
    ) -> list[SearchResult]:
        """Busca textual com BM25, opcionalmente filtrada por tags."""
        if not self.enabled:
            return []
        return self._ensure_searcher().search(query, limit=limit, tags=tags)

    def by_tag(self, tag: str) -> list[Note]:
        """Notas com uma tag específica."""
        if not self.enabled:
            return []
        return self._ensure_searcher().by_tag(tag)

    def get(self, path: str) -> Optional[Note]:
        """Acesso direto por path."""
        if not self.enabled:
            return None
        return self._ensure_searcher().note(path)

    def recent_daily_notes(self, limit: int = 3) -> list[Note]:
        """Retorna as últimas ``limit`` daily notes (padrão ``daily/AAAA-MM-DD.md``)."""
        if not self.enabled:
            return []
        all_daily = self._ensure_searcher().by_path_prefix("daily/")
        all_daily.sort(key=lambda n: n.path, reverse=True)
        return all_daily[:limit]

    def backlinks(self, target_path: str) -> tuple[str, ...]:
        """Notas que referenciam ``target_path``."""
        if not self.enabled:
            return ()
        return self._ensure_links().backlinks(target_path)

    def tags_summary(self) -> dict[str, int]:
        """Mapa tag → contagem de notas."""
        if not self.enabled:
            return {}
        idx = self._ensure_searcher()
        idx._ensure_built()  # type: ignore[attr-defined]
        tag_index = idx._tag_index  # type: ignore[attr-defined]
        return {tag: len(notes) for tag, notes in tag_index.tag_to_notes.items()}

    def stats(self) -> dict[str, Union[str, int, bool]]:
        """Estatísticas do vault (para o /api/health)."""
        if not self.enabled:
            return {"enabled": False, "status": self.status.value}
        s = self._ensure_searcher()
        s._ensure_built()  # type: ignore[attr-defined]
        link_stats = self._ensure_links().stats()
        return {
            "enabled": True,
            "status": self.status.value,
            "root": str(self.root),
            "writable": self.writable,
            "notes": s.stats()["notes"],
            "tags": s.stats()["tags"],
            "avg_note_length": s.stats()["avg_note_length"],
            "links": link_stats,
        }

    def add_to_context(self, note: Note) -> None:
        """Carrega uma nota no contexto desta sessão (para o agente usar)."""
        self._context.append(note.path)

    @property
    def context_notes(self) -> list[str]:
        return list(self._context)

    # ══════════════════════════════════════════════════════════════
    # ESCRITA
    # ══════════════════════════════════════════════════════════════

    def start_session(self) -> str:
        """Inicia uma nova sessão. Retorna o session_id."""
        sid = f"{socket.gethostname()}-{_dt.datetime.now().strftime('%Y%m%d%H%M%S')}"
        self._session = _SessionContext(
            session_id=sid,
            started_at=_dt.datetime.now(),
        )
        return sid

    def log_request(self, text: str) -> None:
        if self._session is not None:
            self._session.user_requests.append(text)

    def use_skill(self, skill_id: str) -> None:
        if self._session is not None:
            self._session.skills_used.append(skill_id)

    def create_note(
        self,
        path: str,
        *,
        title: Optional[str] = None,
        template: str = "inbox",
        tags: tuple[str, ...] = (),
        context: Optional[dict[str, str]] = None,
    ) -> Optional[Note]:
        """Cria uma nova nota a partir de um template.

        Args:
            path: caminho relativo dentro do vault (ex.: ``research/minha-nota.md``).
            title: título da nota (default: nome do arquivo).
            template: nome do template (sem extensão). Padrão: ``inbox``.
            tags: tags extras a adicionar.
            context: variáveis para renderizar o template (``{{chave}}``).

        Returns:
            A :class:`Note` criada, ou ``None`` se o módulo não está pronto.
        """
        if not self.writable:
            logger.warning("create_note ignorado: módulo read-only")
            return None
        assert self._vault is not None
        title = title or Path(path).stem
        note = self._vault.write_from_template(
            path, template,
            context={**(context or {}), "title": title},
            tags=("pesquisai/draft",) + tuple(tags),
        )
        if self._session is not None:
            self._session.notes_created.append(path)
        return note

    def update_note(
        self,
        note: Note,
        *,
        append: Optional[str] = None,
        replace_body: Optional[str] = None,
    ) -> Optional[Note]:
        """Atualiza uma nota existente (do PesquisAI).

        Args:
            note: a nota com as alterações.
            append: texto a **anexar** ao final do corpo.
            replace_body: novo corpo (substitui o anterior).

        Returns:
            A nota atualizada, ou ``None`` se falhou.
        """
        if not self.writable:
            return None
        assert self._vault is not None
        from dataclasses import replace as _dc_replace
        from .models import extract_wikilinks, extract_tags

        # Reconstrói corpo
        if append is not None:
            new_body = (note.body.rstrip() + "\n\n" + append.strip()).strip()
        elif replace_body is not None:
            new_body = replace_body
        else:
            new_body = note.body

        # NoteMetadata é frozen=True — usar dataclasses.replace para
        # atualizar o timestamp (corrige bug encontrado no teste e2e).
        new_meta = _dc_replace(note.metadata, updated=_dt.date.today())

        # Recomputa wikilinks e tags do novo corpo
        new_wikilinks = extract_wikilinks(new_body)
        body_tags = extract_tags(new_body)
        all_tags = tuple(sorted(set(new_meta.tags) | set(body_tags)))

        new_note = Note(
            path=note.path,
            metadata=new_meta,
            body=new_body,
            wikilinks=new_wikilinks,
            tags=all_tags,
        )
        self._vault.write(new_note)
        # Atualiza índice
        if self._searcher is not None:
            self._searcher.invalidate()
        if self._session is not None and note.path not in self._session.notes_updated:
            self._session.notes_updated.append(note.path)
        return new_note

    def log_file(self, path: str) -> None:
        """Registra um arquivo gerado (linkado na nota de sessão)."""
        if self._session is not None:
            self._session.files_generated.append(path)

    def end_session(
        self,
        *,
        summary: str = "",
        tokens_in: int = 0,
        tokens_out: int = 0,
    ) -> Optional[Note]:
        """Encerra a sessão atual e grava a nota de log.

        Cria (ou atualiza) ``sessions/AAAA-MM-DD-<session_id>.md`` com
        a timeline da sessão.
        """
        if not self.writable or self._session is None:
            return None
        assert self._vault is not None
        self._session.tokens_in = tokens_in
        self._session.tokens_out = tokens_out

        log = SessionLog(
            session_id=self._session.session_id,
            started_at=self._session.started_at,
            ended_at=_dt.datetime.now(),
            user_requests=tuple(self._session.user_requests),
            skills_used=tuple(self._session.skills_used),
            notes_created=tuple(self._session.notes_created),
            notes_updated=tuple(self._session.notes_updated),
            files_generated=tuple(self._session.files_generated),
            summary=summary,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
        )
        # Cria/atualiza nota de sessão
        today = _dt.date.today().isoformat()
        path = f"sessions/{today}-{self._session.session_id}.md"
        existing = self._vault.exists(path)
        if existing:
            note = self._vault.read(path)
            new_body = note.body.rstrip() + "\n\n---\n\n" + log.to_markdown()
            self.update_note(note, replace_body=new_body)
        else:
            note = Note.empty(
                path=path,
                title=f"Sessão {today}",
                tags=("pesquisai/session", "pesquisai/draft"),
                template=log.to_markdown(),
            )
            self._vault.write(note)
        # Limpa estado
        self._session = None
        # Invalida índice
        if self._searcher is not None:
            self._searcher.invalidate()
        return note

    # ══════════════════════════════════════════════════════════════
    # SINCRONIZAÇÃO
    # ══════════════════════════════════════════════════════════════

    def sync_drive(
        self,
        mirror: Union[str, Path],
        *,
        direction: str = "push",
    ) -> SyncReport:
        """Sincroniza com uma pasta espelho no Drive."""
        if not self.enabled:
            return SyncReport(
                started_at=_dt.datetime.now(),
                ended_at=_dt.datetime.now(),
                errors=("módulo desativado",),
            )
        assert self._vault is not None
        return sync_drive(self._vault, mirror, direction=direction)

    def sync_git(
        self,
        *,
        remote: Optional[str] = None,
        branch: str = "main",
        commit_message: Optional[str] = None,
    ) -> SyncReport:
        """Sincroniza via git."""
        if not self.enabled:
            return SyncReport(
                started_at=_dt.datetime.now(),
                ended_at=_dt.datetime.now(),
                errors=("módulo desativado",),
            )
        assert self._vault is not None
        return sync_git(
            self._vault,
            remote=remote,
            branch=branch,
            commit_message=commit_message,
        )

    # ══════════════════════════════════════════════════════════════
    # PROMPT HELPER — para o agente incluir no contexto
    # ══════════════════════════════════════════════════════════════

    def context_brief(self, *, max_chars: int = 4000) -> str:
        """Gera um resumo das notas em contexto para o prompt do agente.

        Formato::

            ## 🧠 Memória (PesquisAI / Obsidian)

            ### Notas carregadas
            - [[research/diabetes]] — Prevalência de Diabetes no Brasil
            - [[literature/santos-2024]] — Santos (2024): ...

            ### Estatísticas do vault
            138 notas · 47 tags · 234 backlinks

        Use::

            prompt = system_prompt + mem.context_brief() + user_message
        """
        if not self.enabled or not self._context:
            return ""
        assert self._searcher is not None
        parts: list[str] = ["## 🧠 Memória (PesquisAI / Obsidian)", ""]
        parts.append("### Notas carregadas no contexto")
        for path in self._context:
            note = self._searcher.note(path)
            if note is None:
                continue
            line = f"- `[[{note.path}]]` — {note.metadata.title}"
            if len(note.body) > 100:
                snippet = note.body[:200].replace("\n", " ").strip()
                line += f"\n  > {snippet}…"
            parts.append(line)
        parts.append("")
        stats = self.stats()
        parts.append(
            f"### Estatísticas do vault\n"
            f"{stats.get('notes', 0)} notas · {stats.get('tags', 0)} tags · "
            f"{stats.get('links', {}).get('edges', 0)} wikilinks"
        )
        out = "\n".join(parts)
        return out[:max_chars]
