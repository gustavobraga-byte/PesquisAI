"""
links.py — Resolução de wikilinks e construção de backlinks.

No Obsidian, ``[[Nome da Nota]]`` aponta para uma nota cujo **filename**
(ou título) é "Nome da Nota". O PesquisAI precisa:

- **Detectar** wikilinks em qualquer nota (já feito em
  :func:`models.extract_wikilinks`).
- **Resolver** um wikilink para o caminho real do arquivo, mesmo que o
  alvo use capitalização diferente ou esteja em outra pasta.
- **Construir** o índice de backlinks: para cada nota A que contém
  ``[[B]]``, registrar A como backlink de B.

A resolução é **case-insensitive** e **accent-insensitive** para tolerar
diferenças de digitação humana.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Optional

from .models import Note
from .vault import Vault

logger = logging.getLogger("pesquisai.obsidian.links")


def _strip_accents(text: str) -> str:
    """Remove acentos para comparação tolerant."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _normalize_title(title: str) -> str:
    return _strip_accents(title).lower().strip()


def _normalize_path(path: str) -> str:
    return _strip_accents(path).lower().strip()


class LinkIndex:
    """Índice reverso: ``target → notas que apontam para ele``.

    Construído uma vez por ``Vault.iter_notes()`` e consultado em O(1).
    """

    def __init__(self) -> None:
        # target_normalized → set[note_path]
        self._target_to_sources: dict[str, set[str]] = defaultdict(set)
        # source_path → set[target_normalized]
        self._source_to_targets: dict[str, set[str]] = defaultdict(set)
        # alias → caminho canônico (case/accent-insensitive)
        self._aliases: dict[str, str] = {}

    # ── Construção ────────────────────────────────────────────────
    @classmethod
    def from_vault(cls, vault: Vault) -> "LinkIndex":
        idx = cls()
        for note in vault.iter_notes():
            idx.add_note(note)
        return idx

    def add_note(self, note: Note) -> None:
        """Indexa os wikilinks de uma nota."""
        # Indexa o título como alias do path (case + accent insensitive)
        self._aliases[_normalize_path(note.path)] = note.path
        self._aliases[_normalize_title(note.metadata.title)] = note.path
        # Garante que a nota aparece como source mesmo sem wikilinks
        # (importante para backlinks() funcionar e stats() contar)
        self._source_to_targets.setdefault(note.path, set())
        for target in note.wikilinks:
            t_norm = _normalize_title(target)
            self._target_to_sources[t_norm].add(note.path)
            self._source_to_targets[note.path].add(t_norm)

    def remove_note(self, note_path: str) -> None:
        """Remove uma nota do índice."""
        for t in list(self._source_to_targets.get(note_path, set())):
            self._target_to_sources.get(t, set()).discard(note_path)
        self._source_to_targets.pop(note_path, None)
        # Não removemos aliases — são idempotentes

    # ── Consultas ─────────────────────────────────────────────────
    def resolve(self, target: str) -> Optional[str]:
        """Resolve um wikilink (com case/accent-insensitive) para o path."""
        t_norm = _normalize_title(target)
        # Tenta resolver via aliases
        if t_norm in self._aliases:
            return self._aliases[t_norm]
        # Procura nos paths conhecidos (case-insensitive contains)
        for k, v in self._aliases.items():
            if k == t_norm:
                return v
        # Tenta match pelo stem do path (sem extensão .md)
        # - k = "research/diabetes.md" -> stem = "research/diabetes"
        # - t_norm = "diabetes" -> match se stem termina com "/diabetes"
        for k, v in self._aliases.items():
            stem = k[:-3] if k.endswith(".md") else k
            if stem.endswith("/" + t_norm) or stem == t_norm:
                return v
        return None

    def backlinks(self, target_path: str) -> tuple[str, ...]:
        """Retorna os paths de notas que contêm ``[[target_path]]``."""
        # Se target_path é um path, normaliza
        candidates = {_normalize_path(target_path), _normalize_title(Path(target_path).stem)}
        sources: set[str] = set()
        for c in candidates:
            sources.update(self._target_to_sources.get(c, set()))
        return tuple(sorted(sources))

    def outgoing(self, source_path: str) -> tuple[str, ...]:
        """Retorna os targets (normalizados) de uma nota."""
        return tuple(sorted(self._source_to_targets.get(source_path, set())))

    def orphans(self) -> tuple[str, ...]:
        """Notas que **não** têm backlinks (candidatas a deletar/mover)."""
        all_paths: set[str] = set()
        for sources in self._target_to_sources.values():
            all_paths.update(sources)
        # Caminhos que são alvo de algum wikilink
        linked_paths: set[str] = set()
        for t, sources in self._target_to_sources.items():
            if sources:
                # Pode ser alias — converte
                for src in sources:
                    linked_paths.add(src)
        # Heurística: nota é "orphana" se nunca é fonte nem alvo
        # (em grafo pequeno, isto captura notas sem contexto)
        orphans = set()
        for sources in self._source_to_targets.keys():
            if sources not in linked_paths:
                orphans.add(sources)
        return tuple(sorted(orphans))

    def stats(self) -> dict[str, int]:
        return {
            "notes": len(self._source_to_targets),
            "targets": len(self._target_to_sources),
            "edges": sum(len(s) for s in self._source_to_targets.values()),
        }


# ── Construção de wikilinks em texto novo ───────────────────────

def make_wikilink(target: str, *, alias: Optional[str] = None) -> str:
    """Cria a string ``[[target]]`` ou ``[[target|alias]]``."""
    if alias:
        return f"[[{target}|{alias}]]"
    return f"[[{target}]]"


def replace_in_text(
    text: str,
    replacements: dict[str, str],
) -> str:
    """Substitui strings por wikilinks no texto.

    Args:
        text: texto original.
        replacements: mapa ``termo → nota alvo``. A substituição é feita
            por word-boundary para evitar matches parciais.
    """
    out = text
    for term, target in replacements.items():
        # Word boundary, case-insensitive
        pattern = re.compile(r"\b" + re.escape(term) + r"\b", flags=re.IGNORECASE)
        out = pattern.sub(make_wikilink(target), out)
    return out


def find_mentionable_terms(notes: Iterable[Note]) -> dict[str, tuple[str, ...]]:
    """Para cada nota, retorna os termos (palavras-chave) que poderiam
    virar wikilink em outras notas.

    Útil para o agente sugerir conexões ao redigir uma nota nova.
    """
    result: dict[str, tuple[str, ...]] = {}
    for note in notes:
        # Heurística: títulos viram termos canônicos
        title = note.metadata.title.strip()
        if title and len(title) >= 3:
            result[note.path] = (title,)
    return result
