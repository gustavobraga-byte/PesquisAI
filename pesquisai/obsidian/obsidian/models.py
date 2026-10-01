"""
models.py — Dataclasses do módulo ``pesquisai.obsidian``.

Mantém uma representação em memória das notas, dos metadados, dos
resultados de busca e dos logs de sessão. Nenhuma das classes faz I/O —
a I/O é responsabilidade de :mod:`pesquisai.obsidian.vault`.

Design:

- ``Note`` é imutável do ponto de vista do ``Vault``: para alterar,
  cria-se uma nova instância e chama-se ``vault.write(new_note)``.
- ``NoteMetadata`` é o subconjunto de campos que aparecem no frontmatter
  YAML e que são expostos ao Dataview.
- ``SearchResult`` carrega o trecho onde houve o match, o que permite
  destacar o hit no Obsidian e em uma UI web.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

# ── Tags reconhecidas (taxonomia oficial) ────────────────────────
# Estas constantes alimentam o autocompletar e a validação de tags.
OFFICIAL_TAGS: frozenset[str] = frozenset({
    # Fonte de dados
    "pesquisai/ibge",
    "pesquisai/datasus",
    "pesquisai/agrobr",
    "pesquisai/dados-brasil",
    "pesquisai/capes",
    "pesquisai/sucupira",
    # Tipo de nota
    "pesquisai/daily",
    "pesquisai/research",
    "pesquisai/literature",
    "pesquisai/session",
    "pesquisai/methodology",
    "pesquisai/datasource",
    "pesquisai/hypothesis",
    "pesquisai/reference",
    "pesquisai/moc",
    "pesquisai/inbox",
    # Estado
    "pesquisai/draft",
    "pesquisai/review",
    "pesquisai/published",
    "pesquisai/archived",
    # Área do conhecimento (vazio por design — usuário define)
})

# ── Regex usadas em todo o módulo ────────────────────────────────
WIKILINK_RE = re.compile(r"\[\[([^\]\|#]+)(?:#[^\]\|]+)?(?:\|[^\]]+)?\]\]")
TAG_RE = re.compile(r"(?:^|\s)#([a-zA-Z0-9_\-/]+)")
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


# ──────────────────────────────────────────────────────────────────
# Dataclasses
# ──────────────────────────────────────────────────────────────────

@dataclass(slots=True, frozen=True)
class NoteMetadata:
    """Subconjunto de campos do frontmatter YAML (Dataview-friendly)."""

    title: str
    created: _dt.date
    updated: _dt.date
    tags: tuple[str, ...] = ()
    author: str = ""
    created_by: str = ""  # "pesquisai" para notas geradas pelo agente
    source: str = ""      # URL / DOI / caminho de origem
    project: str = ""     # ID do projeto (MOC)
    status: str = "draft"
    citekey: str = ""     # chave de citação (Zotero/Mendeley)
    doi: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Dataview prefere listas, não tuplas
        d["tags"] = list(self.tags)
        # Datas como ISO
        d["created"] = self.created.isoformat()
        d["updated"] = self.updated.isoformat()
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NoteMetadata":
        tags = data.get("tags", ())
        if isinstance(tags, str):
            tags = tuple(t.strip() for t in tags.split(",") if t.strip())
        elif isinstance(tags, list):
            tags = tuple(tags)
        return cls(
            title=str(data.get("title", "")).strip() or "Sem título",
            created=_parse_date(data.get("created")) or _dt.date.today(),
            updated=_parse_date(data.get("updated")) or _dt.date.today(),
            tags=tags,
            author=str(data.get("author", "")).strip(),
            created_by=str(data.get("created_by", "")).strip(),
            source=str(data.get("source", "")).strip(),
            project=str(data.get("project", "")).strip(),
            status=str(data.get("status", "draft")).strip() or "draft",
            citekey=str(data.get("citekey", "")).strip(),
            doi=str(data.get("doi", "")).strip(),
        )


@dataclass(slots=True)
class Note:
    """Uma nota do vault, com metadados + corpo Markdown."""

    path: str                              # caminho relativo dentro do vault
    metadata: NoteMetadata
    body: str = ""
    wikilinks: tuple[str, ...] = field(default_factory=tuple)
    tags: tuple[str, ...] = field(default_factory=tuple)

    # ── Propriedades derivadas (não serializadas) ────────────────
    @property
    def title(self) -> str:
        return self.metadata.title

    @property
    def content_hash(self) -> str:
        """SHA-256 do ``body`` + metadados (para detectar mudanças)."""
        h = hashlib.sha256()
        h.update(self.metadata.title.encode("utf-8"))
        h.update(b"|")
        h.update(self.body.encode("utf-8"))
        h.update(b"|")
        h.update(",".join(sorted(self.tags)).encode("utf-8"))
        return h.hexdigest()

    @property
    def is_pesquisai_generated(self) -> bool:
        return self.metadata.created_by.lower() == "pesquisai"

    # ── Serialização ─────────────────────────────────────────────
    def to_markdown(self) -> str:
        """Serializa para Markdown com frontmatter YAML."""
        lines = ["---"]
        d = self.metadata.to_dict()
        for key, value in d.items():
            if value is None or value == "" or value == []:
                continue
            if isinstance(value, list):
                if not value:
                    continue
                lines.append(f"{key}:")
                for item in value:
                    lines.append(f"  - {yaml_escape(str(item))}")
            else:
                lines.append(f"{key}: {yaml_escape(str(value))}")
        lines.append("---")
        lines.append("")
        if self.body:
            lines.append(self.body.rstrip())
            lines.append("")
        return "\n".join(lines)

    @classmethod
    def from_markdown(cls, path: str, text: str) -> "Note":
        """Desserializa uma nota Markdown. Aceita frontmatter opcional."""
        m = FRONTMATTER_RE.match(text)
        if not m:
            return cls(
                path=path,
                metadata=NoteMetadata(
                    title=Path(path).stem,
                    created=_dt.date.today(),
                    updated=_dt.date.today(),
                ),
                body=text.strip(),
                wikilinks=extract_wikilinks(text),
                tags=extract_tags(text),
            )

        yaml_text, body = m.group(1), m.group(2)
        meta = _yaml_load(yaml_text)
        metadata = NoteMetadata.from_dict(meta)
        # Tags: união das tags do frontmatter com tags no corpo
        body_tags = extract_tags(body)
        all_tags = tuple(sorted(set(metadata.tags) | set(body_tags)))
        return cls(
            path=path,
            metadata=metadata,
            body=body.strip(),
            wikilinks=extract_wikilinks(body),
            tags=all_tags,
        )

    @classmethod
    def empty(
        cls,
        path: str,
        title: str,
        *,
        tags: tuple[str, ...] = (),
        template: str = "",
    ) -> "Note":
        today = _dt.date.today()
        return cls(
            path=path,
            metadata=NoteMetadata(
                title=title,
                created=today,
                updated=today,
                tags=tags,
                created_by="pesquisai",
                status="draft",
            ),
            body=template.strip(),
            wikilinks=extract_wikilinks(template),
            tags=tags,
        )


@dataclass(slots=True, frozen=True)
class SearchResult:
    """Resultado de busca no vault."""

    note: Note
    score: float
    snippet: str
    matched_field: str  # "title" | "body" | "tag" | "wikilink"

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.note.path,
            "title": self.note.title,
            "score": self.score,
            "snippet": self.snippet,
            "matched_field": self.matched_field,
            "tags": list(self.note.tags),
        }


@dataclass(slots=True)
class SessionLog:
    """Registro de uma sessão do PesquisAI (entrada para o log)."""

    session_id: str
    started_at: _dt.datetime
    ended_at: _dt.datetime
    user_requests: tuple[str, ...] = ()
    skills_used: tuple[str, ...] = ()
    notes_created: tuple[str, ...] = ()
    notes_updated: tuple[str, ...] = ()
    files_generated: tuple[str, ...] = ()
    summary: str = ""
    tokens_in: int = 0
    tokens_out: int = 0

    def to_markdown(self) -> str:
        lines = [
            "## Sessão",
            "",
            f"- **Início:** {self.started_at.isoformat(timespec='seconds')}",
            f"- **Fim:** {self.ended_at.isoformat(timespec='seconds')}",
            f"- **Duração:** {(self.ended_at - self.started_at).total_seconds():.0f}s",
            f"- **Skills usadas:** {', '.join(self.skills_used) or '_(nenhuma)_'}",
            f"- **Tokens:** in {self.tokens_in} · out {self.tokens_out}",
            "",
        ]
        if self.notes_created:
            lines.append("### 📝 Notas criadas")
            for n in self.notes_created:
                lines.append(f"- [[{n}]]")
            lines.append("")
        if self.notes_updated:
            lines.append("### ✏️  Notas atualizadas")
            for n in self.notes_updated:
                lines.append(f"- [[{n}]]")
            lines.append("")
        if self.files_generated:
            lines.append("### 📎 Arquivos gerados")
            for f in self.files_generated:
                lines.append(f"- `{f}`")
            lines.append("")
        if self.summary:
            lines.extend(["### Resumo", "", self.summary.strip(), ""])
        if self.user_requests:
            lines.extend(["### Interações", ""])
            for r in self.user_requests:
                lines.append(f"> {r}")
            lines.append("")
        return "\n".join(lines)


@dataclass(slots=True, frozen=True)
class TagIndex:
    """Índice de tags → caminhos de notas (alimenta Dataview)."""

    tag_to_notes: dict[str, tuple[str, ...]] = field(default_factory=dict)
    note_to_tags: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def notes_with_tag(self, tag: str) -> tuple[str, ...]:
        return self.tag_to_notes.get(tag, ())

    def tags_of(self, note_path: str) -> tuple[str, ...]:
        return self.note_to_tags.get(note_path, ())

    def all_tags(self) -> tuple[str, ...]:
        return tuple(sorted(self.tag_to_notes.keys()))


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────

def _parse_date(value: Any) -> Optional[_dt.date]:
    if not value:
        return None
    if isinstance(value, _dt.date):
        return value
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y"):
            try:
                return _dt.datetime.strptime(value, fmt).date()
            except ValueError:
                continue
    return None


def extract_wikilinks(text: str) -> tuple[str, ...]:
    """Extrai targets de wikilinks ``[[nota]]`` e ``[[nota#heading]]``.

    Aceita também o alias ``|apelido``, removendo-o. Retorna tupla
    ordenada e deduplicada para igualdade estrutural.
    """
    targets: set[str] = set()
    for m in WIKILINK_RE.finditer(text):
        target = m.group(1).strip()
        # Remove heading anchor e alias
        target = target.split("|", 1)[0].split("#", 1)[0].strip()
        if target:
            targets.add(target)
    return tuple(sorted(targets))


def extract_tags(text: str) -> tuple[str, ...]:
    """Extrai tags ``#tag/subtag`` de um texto (não dentro de code blocks)."""
    # Simplificação: ignora tags em code fences (3 backticks seguidos)
    cleaned = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    cleaned = re.sub(r"`[^`]+`", "", cleaned)
    tags: set[str] = set()
    for m in TAG_RE.finditer(cleaned):
        tags.add(m.group(1))
    return tuple(sorted(tags))


def yaml_escape(value: str) -> str:
    """Escapa uma string para uso seguro em YAML simples (sem pyyaml)."""
    if not value:
        return '""'
    # Se tem caracteres especiais, usa aspas duplas
    special = set('":#%@&*!|>%\'`{}[]')
    if any(c in special for c in value) or value[0] in "- " or "\n" in value:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def _yaml_load(yaml_text: str) -> dict[str, Any]:
    """Parser YAML minimalista, com fallback para pyyaml se disponível.

    Suporta:

    - ``chave: valor``
    - ``chave: "valor com aspas"``
    - listas com ``- item``
    - datas ISO ``YYYY-MM-DD``

    Para casos complexos (listas inline, âncoras, multi-linha), usa
    ``pyyaml`` se estiver disponível.
    """
    try:
        import yaml  # type: ignore

        return yaml.safe_load(yaml_text) or {}
    except ImportError:
        pass

    # Fallback manual
    result: dict[str, Any] = {}
    current_key: Optional[str] = None
    current_list: Optional[list[str]] = None
    for raw_line in yaml_text.splitlines():
        line = raw_line.rstrip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("  - ") and current_list is not None:
            current_list.append(_yaml_unquote(line[4:].strip()))
            continue
        if ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if not value:
                # Pode ser lista nos próximos lines
                current_list = []
                result[key] = current_list
                current_key = key
            else:
                current_list = None
                result[key] = _yaml_unquote(value)
                current_key = key
    return result


def _yaml_unquote(value: str) -> Any:
    if not value:
        return ""
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    # Tenta int / float / bool / data
    if value.lower() in ("true", "yes", "on"):
        return True
    if value.lower() in ("false", "no", "off"):
        return False
    if value.lower() in ("null", "~", ""):
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value
