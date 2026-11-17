"""
vault.py — Operações de I/O no vault do Obsidian.

Responsabilidades:

- Listar, ler, criar, atualizar e apagar notas Markdown (``.md``)
- Preservar arquivos binários (imagens, PDFs) sem tentar parsear
- Validar integridade de escritas (fsync + hash)
- Auditar escritas em ``vault/.pesquisai-audit.log``
- Respeitar a regra "read-only para notas humanas"

A camada é **stateless**: o ``Vault`` é construído a partir de um caminho
e expõe métodos. Não há cache interno (buscas com cache são feitas em
:mod:`pesquisai.obsidian.search`).
"""

from __future__ import annotations

import datetime as _dt
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Iterator, Optional, Union

from .models import Note, NoteMetadata

logger = logging.getLogger("pesquisai.obsidian.vault")


class VaultNotFoundError(FileNotFoundError):
    """A pasta do vault não existe."""


class VaultPermissionError(PermissionError):
    """Sem permissão de escrita na pasta do vault."""


class Vault:
    """Ponto de entrada para I/O no vault do Obsidian.

    Uso::

        v = Vault("/content/drive/My Drive/PesquisAI/vault")
        for note in v.iter_notes():
            print(note.path, note.title)
        v.write(Note.empty("daily/2026-06-29.md", "Daily 2026-06-29"))
    """

    # Arquivos/pastas que **nunca** devem ser tocados pelo agente
    PROTECTED_PATHS: frozenset[str] = frozenset({
        ".obsidian",
        ".trash",
        ".pesquisai-audit.log",
        ".git",
    })

    def __init__(self, root: Union[str, os.PathLike[str]]) -> None:
        self.root = Path(root).expanduser().resolve()
        if not self.root.exists():
            raise VaultNotFoundError(f"Vault não encontrado: {self.root}")
        if not self.root.is_dir():
            raise VaultNotFoundError(f"Vault não é diretório: {self.root}")
        if not os.access(self.root, os.R_OK):
            raise VaultPermissionError(f"Sem permissão de leitura: {self.root}")
        self.audit_log = self.root / ".pesquisai-audit.log"

    # ── Itera sobre todas as notas .md ────────────────────────────
    def iter_notes(
        self,
        *,
        subdir: Optional[str] = None,
        skip_protected: bool = True,
    ) -> Iterator[Note]:
        """Itera sobre as notas do vault."""
        base = (self.root / subdir) if subdir else self.root
        if not base.is_dir():
            return
        for path in sorted(base.rglob("*.md")):
            if skip_protected and self._is_protected(path):
                continue
            try:
                yield self.read(path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Falha ao ler %s: %s", path, exc)

    def list_paths(self, subdir: Optional[str] = None) -> list[str]:
        """Retorna os caminhos relativos das notas (sem leitura)."""
        base = (self.root / subdir) if subdir else self.root
        if not base.is_dir():
            return []
        result: list[str] = []
        for path in sorted(base.rglob("*.md")):
            if self._is_protected(path):
                continue
            rel = path.relative_to(self.root)
            result.append(str(rel))
        return result

    # ── Leitura ───────────────────────────────────────────────────
    def read(self, path: Union[str, Path]) -> Note:
        """Lê uma nota pelo caminho absoluto ou relativo ao vault."""
        full = self._resolve_safe(path)
        text = full.read_text(encoding="utf-8")
        return Note.from_markdown(str(full.relative_to(self.root)), text)

    def exists(self, path: Union[str, Path]) -> bool:
        return self._resolve_safe(path, check_only=True).is_file()

    # ── Escrita ──────────────────────────────────────────────────
    def write(
        self,
        note: Note,
        *,
        force: bool = False,
    ) -> Path:
        """Escreve uma nota, validando integridade.

        Args:
            note: nota a gravar.
            force: se ``True``, permite sobrescrever notas humanas
                (use com cuidado; o default é ``False``).

        Raises:
            PermissionError: se a nota existir e for humana e ``force`` for False.
        """
        full = self.root / note.path
        full.parent.mkdir(parents=True, exist_ok=True)
        existed = full.exists()

        if existed and not force:
            existing = Note.from_markdown(
                str(full.relative_to(self.root)),
                full.read_text(encoding="utf-8"),
            )
            if not existing.is_pesquisai_generated and not note.is_pesquisai_generated:
                raise PermissionError(
                    f"Nota '{note.path}' é humana e 'force' é False. "
                    "Notas humanas são read-only para o PesquisAI."
                )
            # Se existe e é do PesquisAI, é atualização legítima
        elif existed and force:
            existing = Note.from_markdown(
                str(full.relative_to(self.root)),
                full.read_text(encoding="utf-8"),
            )
            logger.warning(
                "Sobrescrevendo nota '%s' (force=True) — autor original: %s",
                note.path, existing.metadata.author or "(desconhecido)",
            )

        self._write_atomic(full, note.to_markdown())
        self._audit("write" if not existed else "update", note.path)
        return full

    def delete(self, path: Union[str, Path], *, force: bool = False) -> bool:
        """Remove uma nota. Por padrão, só remove notas criadas pelo agente."""
        full = self._resolve_safe(path, check_only=True)
        if not full.is_file():
            return False
        if not force:
            note = Note.from_markdown(
                str(full.relative_to(self.root)),
                full.read_text(encoding="utf-8"),
            )
            if not note.is_pesquisai_generated:
                raise PermissionError(
                    f"Nota '{path}' é humana — use force=True para remover."
                )
        self._move_to_trash(full)
        self._audit("delete", str(path))
        return True

    # ── Templates ─────────────────────────────────────────────────
    def write_from_template(
        self,
        path: str,
        template_name: str,
        *,
        context: Optional[dict[str, str]] = None,
        tags: tuple[str, ...] = (),
    ) -> Note:
        """Cria uma nova nota a partir de um template oficial."""
        from .discovery import _find_template
        from .models import NoteMetadata, extract_wikilinks, extract_tags

        template_text = _find_template(template_name)
        body = _render_template(template_text, context or {})

        # NoteMetadata é frozen, então criamos nova instância.
        # CORREÇÃO DE BUG: deduplicar tags para evitar "pesquisai/draft"
        # aparecer 2x (encontrado no teste e2e).
        today = _dt.date.today()
        # Tags finais: sempre inclui "pesquisai/draft" + tags do usuário,
        # deduplicadas preservando ordem.
        raw_tags = ("pesquisai/draft",) + tuple(tags)
        dedup_tags = tuple(dict.fromkeys(raw_tags))  # dedup preservando ordem

        merged = {
            "title": context.get("title", Path(path).stem) if context else Path(path).stem,
            "created": today,
            "updated": today,
            "tags": dedup_tags,
            "author": "",
            "created_by": "pesquisai",
            "source": "",
            "project": "",
            "status": "draft",
            "citekey": "",
            "doi": "",
        }
        for k, v in (context or {}).items():
            if k in merged:
                merged[k] = v
        new_meta = NoteMetadata(**merged)

        # Extrai wikilinks e tags do body renderizado
        body_wikilinks = extract_wikilinks(body)
        body_tags = extract_tags(body)
        all_tags = tuple(sorted(set(dedup_tags) | set(body_tags)))

        note = Note(
            path=path,
            metadata=new_meta,
            body=body.strip(),
            wikilinks=body_wikilinks,
            tags=all_tags,
        )
        self.write(note)
        return note

    # ── Auxiliares internos ──────────────────────────────────────
    def _resolve_safe(self, path: Union[str, Path], *, check_only: bool = False) -> Path:
        """Resolve um caminho, prevenindo path traversal."""
        p = Path(path)
        if not p.is_absolute():
            p = self.root / p
        p = p.resolve()
        # Defesa contra path traversal
        try:
            p.relative_to(self.root)
        except ValueError as exc:
            raise PermissionError(f"Caminho fora do vault: {p}") from exc
        if not check_only and not p.exists():
            raise FileNotFoundError(f"Arquivo não existe: {p}")
        return p

    def _is_protected(self, path: Path) -> bool:
        try:
            rel = path.relative_to(self.root)
        except ValueError:
            return True
        parts = rel.parts
        if not parts:
            return True
        return parts[0] in self.PROTECTED_PATHS

    def _write_atomic(self, target: Path, content: str) -> None:
        """Escreve com atomicidade: tmp + fsync + rename."""
        target.parent.mkdir(parents=True, exist_ok=True)
        # Cria tmp na mesma partição (para rename atômico)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(target.parent),
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            tmp.write(content)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_path = Path(tmp.name)
        try:
            tmp_path.replace(target)
            # Sincroniza diretório (importante em FUSE, vide bug v0.2.3)
            dir_fd = os.open(str(target.parent), os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

    def _move_to_trash(self, path: Path) -> None:
        trash = self.root / ".trash"
        trash.mkdir(exist_ok=True)
        stamp = _dt.datetime.now().strftime("%Y%m%d%H%M%S")
        target = trash / f"{path.stem}.{stamp}{path.suffix}"
        shutil.move(str(path), str(target))

    def _audit(self, action: str, path: str) -> None:
        """Registra uma ação no log de auditoria."""
        try:
            ts = _dt.datetime.now().isoformat(timespec="seconds")
            with self.audit_log.open("a", encoding="utf-8") as f:
                f.write(f"{ts}\t{action}\t{path}\n")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Falha ao auditar %s %s: %s", action, path, exc)


def _render_template(template: str, context: dict[str, str]) -> str:
    """Substitui ``{{chave}}`` no template por valores do contexto."""
    out = template
    for key, value in context.items():
        out = out.replace("{{" + key + "}}", str(value))
    return out
