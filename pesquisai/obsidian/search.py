"""
search.py — Busca textual e por tags no vault.

Implementa:

- Busca por **substring** (case + accent insensitive) com snippet
- Busca por **tag exata** (``pesquisai/ibge``, ``pesquisai/draft``...)
- Busca por **wikilink** (``[[alvo]]``)
- Ranking **BM25** simplificado (sem dependências externas), suficiente
  para vaults de até ~10.000 notas

A camada é **read-only**: nunca escreve no vault. O cache é local
(módulo), invalidado a cada ``invalidate()`` ou ``rebuild()``.
"""

from __future__ import annotations

import logging
import math
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, Optional

from .links import _normalize_title
from .models import Note, SearchResult, TagIndex
from .vault import Vault

logger = logging.getLogger("pesquisai.obsidian.search")


# ── Stopwords (PT + EN básico) ──────────────────────────────────
_STOPWORDS: frozenset[str] = frozenset({
    # PT
    "a", "o", "as", "os", "um", "uma", "uns", "umas", "de", "da", "do",
    "das", "dos", "em", "na", "no", "nas", "nos", "para", "pra", "por",
    "pelo", "pela", "com", "sem", "e", "ou", "mas", "que", "se", "é",
    "são", "foi", "ser", "ter", "tem", "têm", "ao", "à", "aos", "às",
    "como", "mais", "menos", "também", "já", "ainda", "muito", "pouco",
    "entre", "sobre", "sob", "até", "após", "desde",
    # EN
    "the", "a", "an", "and", "or", "but", "of", "in", "on", "at", "to",
    "for", "with", "without", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "this", "that", "these",
    "those", "i", "you", "he", "she", "it", "we", "they",
})


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(c)
    )


def _normalize_text(text: str) -> str:
    return _strip_accents(text).lower()


def _tokenize(text: str) -> list[str]:
    """Tokeniza, removendo stopwords e acentos."""
    text = _normalize_text(text)
    # Mantém palavras com hífen (ex.: covid-19)
    tokens = re.findall(r"[a-z0-9][a-z0-9_\-]+", text)
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 1]


def _snippet(text: str, query: str, *, context: int = 80) -> str:
    """Retorna um trecho ao redor do primeiro match do query."""
    text_l = _normalize_text(text)
    q_l = _normalize_text(query)
    pos = text_l.find(q_l)
    if pos < 0:
        return text[: 2 * context].strip() + ("…" if len(text) > 2 * context else "")
    start = max(0, pos - context)
    end = min(len(text), pos + len(query) + context)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return prefix + text[start:end].strip() + suffix


# ──────────────────────────────────────────────────────────────────
# Cache BM25
# ──────────────────────────────────────────────────────────────────

class _BM25Index:
    """Índice BM25 simplificado, em memória."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        # doc_id → [(field, term, tf)]
        self._postings: dict[str, Counter] = {}
        # doc_id → (total_length, doc_id)
        self._docs: dict[str, tuple[int, str]] = {}
        # term → df
        self._df: Counter = Counter()
        self._avg_dl: float = 0.0

    def index(self, note: Note) -> None:
        fields = {
            "title": _tokenize(note.metadata.title),
            "body": _tokenize(note.body),
            "tag": list(note.tags),
            "wikilink": list(note.wikilinks),
        }
        counter: Counter = Counter()
        total_len = 0
        for field_name, tokens in fields.items():
            for tok in tokens:
                counter[(field_name, tok)] += 1
                total_len += 1
        doc_id = note.path
        self._docs[doc_id] = (total_len, note.path)
        self._postings[doc_id] = counter
        # Atualiza DF por (field, term)
        seen: set[tuple[str, str]] = set()
        for (field_name, tok) in counter.keys():
            if (field_name, tok) not in seen:
                self._df[(field_name, tok)] += 1
                seen.add((field_name, tok))
        # Recalcula média
        if self._docs:
            self._avg_dl = sum(d[0] for d in self._docs.values()) / len(self._docs)

    def search(self, query: str, *, limit: int = 10) -> list[tuple[str, float, str]]:
        """Retorna ``[(note_path, score, matched_field)]`` ordenado por score."""
        if not self._docs or not query.strip():
            return []
        tokens = _tokenize(query)
        if not tokens:
            tokens = [_normalize_text(query)]  # tenta match exato
        scores: dict[str, float] = defaultdict(float)
        matched_field: dict[str, str] = {}
        n_docs = len(self._docs)
        for tok in tokens:
            for (field_name, term), df in self._df.items():
                if term != tok:
                    continue
                idf = math.log(((n_docs - df + 0.5) / (df + 0.5)) + 1)
                weight = {
                    "title": 3.0,
                    "tag": 2.5,
                    "wikilink": 2.0,
                    "body": 1.0,
                }.get(field_name, 1.0)
                for doc_id, counter in self._postings.items():
                    tf = counter.get((field_name, term), 0)
                    if tf == 0:
                        continue
                    dl, _ = self._docs[doc_id]
                    denom = tf + self.k1 * (1 - self.b + self.b * dl / max(self._avg_dl, 1))
                    score = idf * (tf * (self.k1 + 1)) / denom * weight
                    scores[doc_id] += score
                    if score > 0 and doc_id not in matched_field:
                        matched_field[doc_id] = field_name
        ranked = sorted(scores.items(), key=lambda kv: -kv[1])[:limit]
        return [(doc_id, score, matched_field.get(doc_id, "body")) for doc_id, score in ranked]


# ──────────────────────────────────────────────────────────────────
# Searcher
# ──────────────────────────────────────────────────────────────────

class Searcher:
    """Fachada de busca: textual, por tag, por wikilink.

    Mantém um índice BM25 em memória, reconstruído sob demanda::

        s = Searcher(vault)
        s.rebuild()  # opcional (lazy na primeira busca)
        results = s.search("PNAD contínua", limit=10)
        for r in results:
            print(r.score, r.note.path, r.snippet)
    """

    def __init__(self, vault: Vault) -> None:
        self.vault = vault
        self._bm25 = _BM25Index()
        self._notes: dict[str, Note] = {}
        self._tag_index = TagIndex()
        self._built = False

    # ── Construção / invalidação ──────────────────────────────────
    def rebuild(self) -> None:
        """Reconstrói o índice a partir do vault."""
        self._bm25 = _BM25Index()
        self._notes = {}
        tag_to: dict[str, list[str]] = {}
        note_to_tags: dict[str, list[str]] = []
        for note in self.vault.iter_notes():
            self._notes[note.path] = note
            self._bm25.index(note)
            for tag in note.tags:
                tag_to.setdefault(tag, []).append(note.path)
            note_to_tags.append((note.path, list(note.tags)))
        self._tag_index = TagIndex(
            tag_to_notes={k: tuple(sorted(v)) for k, v in tag_to.items()},
            note_to_tags={p: tuple(sorted(t)) for p, t in note_to_tags},
        )
        self._built = True
        logger.info(
            "Searcher: indexadas %d notas (%d tags únicas)",
            len(self._notes), len(self._tag_index.all_tags()),
        )

    def invalidate(self) -> None:
        self._built = False
        self._notes = {}
        self._tag_index = TagIndex()

    def _ensure_built(self) -> None:
        if not self._built:
            self.rebuild()

    # ── Buscas ────────────────────────────────────────────────────
    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        tags: Optional[Iterable[str]] = None,
    ) -> list[SearchResult]:
        """Busca textual com BM25, opcionalmente filtrada por tags."""
        self._ensure_built()
        if not query.strip():
            return []
        ranked = self._bm25.search(query, limit=max(limit * 4, 40))
        results: list[SearchResult] = []
        for doc_id, score, matched_field in ranked:
            note = self._notes.get(doc_id)
            if note is None:
                continue
            if tags and not all(t in note.tags for t in tags):
                continue
            if matched_field == "title":
                snippet = note.metadata.title
            elif matched_field == "tag":
                snippet = ", ".join(note.tags)
            elif matched_field == "wikilink":
                snippet = "[[" + "]], [[".join(note.wikilinks[:3]) + "]]"
            else:
                snippet = _snippet(note.body, query)
            results.append(SearchResult(
                note=note,
                score=score,
                snippet=snippet,
                matched_field=matched_field,
            ))
            if len(results) >= limit:
                break
        return results

    def by_tag(self, tag: str) -> list[Note]:
        """Retorna todas as notas com uma tag específica."""
        self._ensure_built()
        paths = self._tag_index.notes_with_tag(tag)
        return [self._notes[p] for p in paths if p in self._notes]

    def by_path_prefix(self, prefix: str) -> list[Note]:
        """Notas cujo path começa com ``prefix`` (ex.: ``daily/``)."""
        self._ensure_built()
        return [
            n for p, n in self._notes.items()
            if p.startswith(prefix)
        ]

    def note(self, path: str) -> Optional[Note]:
        """Acesso direto por path."""
        self._ensure_built()
        return self._notes.get(path)

    # ── Estatísticas ──────────────────────────────────────────────
    def stats(self) -> dict[str, int]:
        self._ensure_built()
        return {
            "notes": len(self._notes),
            "tags": len(self._tag_index.all_tags()),
            "avg_note_length": int(
                sum(len(n.body) for n in self._notes.values())
                / max(len(self._notes), 1)
            ),
        }
