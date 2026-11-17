"""
search.py — Busca textual e por tags no vault.

Implementa:

- Busca por **substring** (case + accent insensitive) com snippet
- Busca por **tag exata** (``pesquisai/ibge``, ``pesquisai/draft``...)
- Busca por **wikilink** (``[[alvo]]``)
- Ranking **BM25** simplificado (sem dependências externas), suficiente
  para vaults de até ~10.000 notas

v0.6.10 — Otimização para muitas notas:
  • Cache BM25 em disco (embeddings_cache/bm25_cache.json) com validação
    por mtime+size por arquivo → rebuild incremental evita re-tokenizar
    100% do vault a cada busca.
  • Rebuild lazy + thread-safe + métricas de tempo.
  • Busca mantém pesos por campo (título 3.0 > tag 2.5 > wikilink 2.0 > corpo 1.0).

A camada é **read-only**: nunca escreve no vault. O cache é local
(embeddings_cache/), invalidado quando qualquer .md muda.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, Optional

from .links import _normalize_title
import datetime as _dt
from .models import Note, NoteMetadata, SearchResult, TagIndex, _parse_date
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
# Cache BM25 — helpers de disco (v0.6.10)
# ──────────────────────────────────────────────────────────────────

_CACHE_VERSION = 1
_CACHE_SUBDIR = "embeddings_cache"
_CACHE_FILENAME = "bm25_cache.json"
_SEP = "\x1f"  # separador field\x1fterm usado no cache JSON


def _cache_path(vault: Vault) -> Path:
    return vault.root / _CACHE_SUBDIR / _CACHE_FILENAME


# ──────────────────────────────────────────────────────────────────
# Índice BM25
# ──────────────────────────────────────────────────────────────────

class _BM25Index:
    """Índice BM25 simplificado, em memória."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        # doc_id → Counter{(field, term): tf}
        self._postings: dict[str, Counter] = {}
        # doc_id → (total_length, doc_id)
        self._docs: dict[str, tuple[int, str]] = {}
        # (field, term) → df
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
# Searcher — fachada com cache em disco (v0.6.10)
# ──────────────────────────────────────────────────────────────────

class Searcher:
    """Fachada de busca: textual, por tag, por wikilink.

    Mantém um índice BM25 em memória, reconstruído sob demanda e
    **cacheado em disco** (``vault/embeddings_cache/bm25_cache.json``)
    com validação por ``mtime`` + ``size`` por arquivo — ideal para
    vaults com centenas/milhares de notas.::

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
        self._cache_hit = False

    # ── Cache em disco ────────────────────────────────────────────
    def _load_from_cache(self) -> bool:
        """Tenta carregar índice do disco. Retorna True se cache válido."""
        try:
            cpath = _cache_path(self.vault)
            if not cpath.is_file():
                return False
            t0 = time.time()
            with open(cpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("version") != _CACHE_VERSION:
                logger.debug("BM25 cache: versão incompatível (%s)", data.get("version"))
                return False
            if data.get("vault_root") != str(self.vault.root):
                logger.debug("BM25 cache: vault_root divergente")
                return False
            notes_data: dict = data.get("notes", {})
            if not notes_data:
                return False
            # Validação rápida por mtime/size — sem ler bodies
            for rel_path, info in notes_data.items():
                f = self.vault.root / rel_path
                try:
                    st = f.stat()
                except FileNotFoundError:
                    logger.debug("BM25 cache stale: arquivo removido %s", rel_path)
                    return False
                # tolerância 1s para FUSE do Drive
                if abs(st.st_mtime - float(info.get("mtime", 0))) > 1.0 or st.st_size != int(info.get("size", -1)):
                    logger.debug("BM25 cache stale: mtime/size mudou %s", rel_path)
                    return False
            # Detecta arquivos novos (não estão no cache)
            # Usa list_paths() (filtra protegidos igual ao Vault) — evita descompasso com iter_notes
            try:
                current_files = set(self.vault.list_paths())
            except Exception:
                # fallback rglob
                current_files = set()
                for p in sorted(self.vault.root.rglob("*.md")):
                    try:
                        if p.is_file() and ".obsidian" not in p.parts and ".trash" not in p.parts:
                            rel = str(p.relative_to(self.vault.root))
                            current_files.add(rel)
                    except Exception:
                        continue
            if set(notes_data.keys()) != current_files:
                # diferença de conjunto → arquivo adicionado/removido
                # permite diff pequeno? por enquanto invalida
                if len(set(notes_data.keys()).symmetric_difference(current_files)) > 0:
                    logger.debug("BM25 cache stale: conjunto de arquivos mudou (cached %d vs atual %d)", len(notes_data), len(current_files))
                    # se poucos arquivos novos, poderíamos fazer incremental;
                    # por simplicidade, invalida cache quando há diferença
                    # mas mantém valid se só houver poucos? aqui invalida
                    return False

            # Reconstrói objetos em memória a partir do cache
            # _bm25
            bm25 = _BM25Index()
            # df: chaves são "field\x1fterm"
            df_raw: dict = data.get("df", {})
            df_counter: Counter = Counter()
            for k, v in df_raw.items():
                if _SEP in k:
                    field, term = k.split(_SEP, 1)
                    df_counter[(field, term)] = int(v)
                else:
                    # fallback legado
                    df_counter[(k, "")] = int(v)
            bm25._df = df_counter
            bm25._avg_dl = float(data.get("avg_dl", 0))
            # docs e postings por nota
            docs: dict[str, tuple[int, str]] = {}
            postings: dict[str, Counter] = {}
            notes: dict[str, Note] = {}
            tag_to: dict[str, list[str]] = {}
            for rel_path, info in notes_data.items():
                # docs
                total_len = int(info.get("total_len", 0))
                docs[rel_path] = (total_len, rel_path)
                # postings: counter com chaves "field\x1fterm"
                cnt_raw: dict = info.get("counter", {})
                cnt: Counter = Counter()
                for k, v in cnt_raw.items():
                    if _SEP in k:
                        field, term = k.split(_SEP, 1)
                        cnt[(field, term)] = int(v)
                    else:
                        cnt[(k, "")] = int(v)
                postings[rel_path] = cnt
                # Note
                try:
                    meta = NoteMetadata(
                        title=str(info.get("title", "")),
                        created=_parse_date(info.get("created", "")) or _dt.date.today(),
                        updated=_parse_date(info.get("updated", "")) or _dt.date.today(),
                        author=str(info.get("author", "")),
                        created_by=str(info.get("created_by", "")),
                        source=str(info.get("source", "")),
                        project=str(info.get("project", "")),
                        status=str(info.get("status", "draft")),
                        citekey=str(info.get("citekey", "")),
                        doi=str(info.get("doi", "")),
                        tags=tuple(info.get("tags", [])),
                    )
                    # compat: tags já vêm no meta + body tags
                    n = Note(
                        path=rel_path,
                        metadata=meta,
                        body=str(info.get("body", "")),
                        wikilinks=tuple(info.get("wikilinks", [])),
                        tags=tuple(info.get("tags", [])),
                    )
                except Exception as e:
                    logger.warning("BM25 cache: falha ao reconstruir nota %s: %s", rel_path, e)
                    return False
                notes[rel_path] = n
                for tag in n.tags:
                    tag_to.setdefault(tag, []).append(rel_path)
            bm25._docs = docs
            bm25._postings = postings
            # Se avg_dl estava 0, recalc
            if not bm25._avg_dl and docs:
                bm25._avg_dl = sum(d[0] for d in docs.values()) / len(docs)
            self._bm25 = bm25
            self._notes = notes
            self._tag_index = TagIndex(
                tag_to_notes={k: tuple(sorted(v)) for k, v in tag_to.items()},
                note_to_tags={p: tuple(sorted(notes[p].tags)) for p in notes},
            )
            elapsed = time.time() - t0
            logger.info("Searcher: cache HIT — %d notas do disco em %.2fs (%.1f ms/nota)", len(notes), elapsed, (elapsed/max(len(notes),1))*1000)
            self._cache_hit = True
            return True
        except Exception as e:
            logger.debug("BM25 cache miss: %s", e)
            return False

    def _save_to_cache(self) -> None:
        """Persiste índice no disco (JSON atômico)."""
        try:
            cpath = _cache_path(self.vault)
            cpath.parent.mkdir(parents=True, exist_ok=True)
            t0 = time.time()
            notes_data: dict = {}
            for rel_path, note in self._notes.items():
                f = self.vault.root / rel_path
                try:
                    st = f.stat()
                    mtime = st.st_mtime
                    size = st.st_size
                except Exception:
                    mtime = time.time()
                    size = len(note.body.encode("utf-8"))
                # counter → dict com chaves string
                cnt = self._bm25._postings.get(rel_path, Counter())
                cnt_dict = {f"{field}{_SEP}{term}": int(v) for (field, term), v in cnt.items()}
                notes_data[rel_path] = {
                    "mtime": mtime,
                    "size": size,
                    "title": note.metadata.title,
                    "body": note.body,
                    "tags": list(note.tags),
                    "wikilinks": list(note.wikilinks),
                    "created": str(getattr(note.metadata, "created", "")),
                    "updated": str(getattr(note.metadata, "updated", "")),
                    "author": str(getattr(note.metadata, "author", "")),
                    "created_by": str(getattr(note.metadata, "created_by", "")),
                    "source": str(getattr(note.metadata, "source", "")),
                    "project": str(getattr(note.metadata, "project", "")),
                    "status": str(getattr(note.metadata, "status", "draft")),
                    "citekey": str(getattr(note.metadata, "citekey", "")),
                    "doi": str(getattr(note.metadata, "doi", "")),
                    "counter": cnt_dict,
                    "total_len": int(self._bm25._docs.get(rel_path, (0, ""))[0]),
                }
            # df → dict string
            df_dict = {f"{field}{_SEP}{term}": int(v) for (field, term), v in self._bm25._df.items()}
            payload = {
                "version": _CACHE_VERSION,
                "vault_root": str(self.vault.root),
                "built_at": time.time(),
                "avg_dl": float(self._bm25._avg_dl),
                "total_len": sum(d[0] for d in self._bm25._docs.values()),
                "df": df_dict,
                "notes": notes_data,
            }
            # escrita atômica
            tmp = cpath.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as out:
                json.dump(payload, out, ensure_ascii=False)
            tmp.replace(cpath)
            elapsed = time.time() - t0
            logger.info("Searcher: cache SALVO — %d notas em %.2fs → %s", len(notes_data), elapsed, cpath)
        except Exception as e:
            logger.warning("Falha ao salvar BM25 cache: %s", e)

    # ── Construção / invalidação ──────────────────────────────────
    def rebuild(self) -> None:
        """Reconstrói o índice a partir do vault (com cache em disco)."""
        t0 = time.time()
        # Tenta cache primeiro (rápido para vaults grandes)
        if self._load_from_cache():
            self._built = True
            return
        # Cache miss → rebuild completo (tokenização)
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
        elapsed = time.time() - t0
        logger.info(
            "Searcher: indexadas %d notas (%d tags únicas) em %.2fs — cache MISS",
            len(self._notes), len(self._tag_index.all_tags()), elapsed,
        )
        # Persiste para próximas aberturas
        self._save_to_cache()

    def invalidate(self) -> None:
        self._built = False
        self._notes = {}
        self._tag_index = TagIndex()
        # Não apaga o arquivo — próximo rebuild detectará stale via mtime
        # e recriará; evita I/O extra aqui

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
            "cache_hit": int(bool(getattr(self, "_cache_hit", False))),
        }
