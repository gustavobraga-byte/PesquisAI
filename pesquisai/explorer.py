"""web26_explorer.py — mini navigateur de arquivos do agente (v0.7.11-web26).

Painel lateral na interface web que navega pela **pasta do agente** (o
diretório do projeto, no Google Drive) e mostra um visualizador mínimo:

* **texto** (``.md``, ``.txt``, ``.csv``, ``.json``, código-fonte…) — lido e
  exibido no painel;
* **imagem** (``.png``, ``.jpg``, ``.gif``, ``.webp``, ``.svg``…) — servida
  inline pelo gateway;
* **suite Office** (``.docx``, ``.xlsx``, ``.pptx``, ``.odt``, ``.ods``…) —
  o texto é extraído do próprio pacote (ZIP + XML, só biblioteca padrão) e
  mostrado de forma resumida, com o link para a versão completa no Drive.

Mais o **download** do arquivo e o **link para editar no Google Drive**.

Regras de segurança (as mesmas do Drive Guard do motor):
* todo caminho é resolvido e precisa ficar **dentro** de uma raiz permitida
  (o diretório do agente) — nada fora é servido;
* a leitura de arquivo é limitada em tamanho;
* nada é escrito — o painel é somente leitura.
"""

from __future__ import annotations

import html
import os
import re
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import quote

__all__ = [
    "allowed_roots",
    "safe_path",
    "listing",
    "search",
    "resolve",
    "preview",
    "read_bytes",
    "drive_link",
    "DRIVE_HOME",
    "DRIVE_SEARCH",
]

#: Página inicial do Drive usada nos links.
DRIVE_HOME = "https://drive.google.com/drive/u/0/my-drive"

#: v0.7.11-web28: a **busca** no Drive é em ``/search?q=`` — o link antigo
#: (``/my-drive?q=``) ignorava o parâetro e caía na tela inicial do Drive.
DRIVE_SEARCH = "https://drive.google.com/drive/u/0/search"

TEXT_SUFFIXES = {
    ".md", ".markdown", ".txt", ".csv", ".tsv", ".json", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".conf", ".log", ".txt",
    ".py", ".js", ".ts", ".tsx", ".jsx", ".sh", ".bash", ".zsh", ".css",
    ".scss", ".html", ".htm", ".xml", ".sql", ".r", ".jl", ".tex", ".bib",
    ".tex", ".ipynb", ".env", ".gitignore", ".dockerfile", ".makefile",
}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".ico", ".avif"}
OFFICE_SUFFIXES = {
    ".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp", ".doc", ".xls", ".ppt",
}
PDF_SUFFIXES = {".pdf"}

MAX_TEXT_BYTES = 200_000
MAX_BINARY_BYTES = 25 * 1024 * 1024
#: v0.7.11-web28: limite do HTML gerado a partir do .docx.
MAX_HTML_BYTES = 2_000_000


def _engine_sessions() -> list[dict]:
    try:
        from .webapi import engine_json  # type: ignore

        data = engine_json("/api/session", timeout=10)
    except Exception:  # pragma: no cover — motor fora do ar
        return []
    rows = data.get("data") if isinstance(data, dict) else data
    return [r for r in (rows or []) if isinstance(r, dict)]


def allowed_roots() -> list[Path]:
    """Diretórios em que o agente pode estar (o do projeto em execução)."""
    roots: list[Path] = []
    for row in _engine_sessions():
        directory = (row.get("location") or {}).get("directory")
        if directory:
            try:
                roots.append(Path(str(directory)).resolve())
            except OSError:
                continue
    if not roots:
        try:
            roots.append(Path.cwd().resolve())
        except OSError:
            roots.append(Path("/"))
    # mantém a ordem e remove duplicatas
    uniq: list[Path] = []
    for root in roots:
        if root not in uniq:
            uniq.append(root)
    # v0.7.11-web28: com várias sessões, o motor devolve diretórios
    # diferentes (às vezes ``/root``). A pasta do PROJETO no Google Drive tem
    # a preferência — antes a primeira sessão da lista era usada e o
    # explorador abria no lugar errado (sem os arquivos do projeto).
    uniq.sort(key=lambda p: 0 if str(p).startswith("/content/drive") else 1)
    return uniq


def safe_path(relative: str, roots: list[Path] | None = None) -> Path | None:
    """Resolve um caminho **dentro** de uma raiz permitida (ou ``None``)."""
    rel = str(relative or "").strip().lstrip("/")
    for root in (roots if roots is not None else allowed_roots()):
        try:
            base = root.resolve()
        except OSError:
            continue
        target = (base / rel) if rel else base
        try:
            resolved = target.resolve()
        except OSError:
            resolved = target
        try:
            resolved.relative_to(base)
        except ValueError:
            continue
        return resolved
    return None


def _mime_of(path: Path) -> str:
    import mimetypes

    mime, _ = mimetypes.guess_type(str(path))
    return mime or "application/octet-stream"


def _kind_of(path: Path) -> str:
    suffix = path.suffix.lower()
    if path.is_dir():
        return "directory"
    if suffix in IMAGE_SUFFIXES:
        return "image"
    if suffix in OFFICE_SUFFIXES:
        return "office"
    if suffix in PDF_SUFFIXES:
        return "pdf"
    if suffix in TEXT_SUFFIXES or not suffix:
        return "text"
    return "binary"


def drive_link(name: str) -> str:
    """Link para **pesquisar** o arquivo no Google Drive.

    A montagem FUSE do Drive não expõe o *file id*, então o link vai para a
    **busca** (``/drive/u/0/search?q=``) pelo nome exato — abre o arquivo em
    uma etapa. Antes apontava para ``/my-drive?q=``, que ignorava a consulta.
    """
    return f"{DRIVE_SEARCH}?q={quote(str(name or ''), safe='')}"


def listing(relative: str = "") -> dict[str, Any]:
    """Conteúdo de uma pasta do agente."""
    roots = allowed_roots()
    target = safe_path(relative, roots)
    if target is None:
        return {"error": "caminho fora da pasta do agente", "path": relative, "items": []}
    if not target.exists():
        return {"error": "pasta não encontrada", "path": relative, "items": []}
    if not target.is_dir():
        return {"error": "não é uma pasta", "path": relative, "items": []}
    items: list[dict] = []
    try:
        entries = sorted(os.scandir(target), key=lambda e: (not e.is_dir(), e.name.lower()))
    except OSError as exc:
        return {"error": f"não foi possível ler a pasta: {exc}", "path": relative, "items": []}
    parent = ""
    rel = str(relative or "").strip("/")
    if rel:
        parent = rel.rsplit("/", 1)[0] if "/" in rel else ""
    for entry in entries:
        if entry.name.startswith(".") or entry.name == "__pycache__":
            continue
        path = Path(entry.path)
        is_dir = entry.is_dir()
        try:
            stat = entry.stat()
            size = 0 if is_dir else int(stat.st_size)
            modified = int(stat.st_mtime * 1000)
        except OSError:
            size, modified = 0, 0
        item_rel = f"{rel}/{entry.name}" if rel else entry.name
        items.append(
            {
                "name": entry.name,
                "path": item_rel,
                "type": "directory" if is_dir else "file",
                "size": size,
                "modified": modified,
                "mime": "" if is_dir else _mime_of(path),
                "kind": _kind_of(path),
                "driveUrl": drive_link(entry.name),
            }
        )
    return {
        "path": rel,
        "parent": parent,
        "root": str(target),
        "items": items,
        "driveHome": DRIVE_HOME,
        "error": "",
    }


#: Pastas que a busca **não** entra (ruído e peso).
SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", "site-packages",
    ".ipynb_checkpoints", ".next", ".cache", ".tox", ".idea", ".vscode",
}

MAX_SEARCH_RESULTS = 300
MAX_SEARCH_DEPTH = 5
#: v0.7.11-web28: teto de pastas visitadas — a busca recursiva num Drive
#: grande é lenta (3 s); sem o teto, a interface parece travada.
MAX_SEARCH_DIRS = 4000


#: Cache do índice da árvore (v0.7.11-web28): a busca recursiva no Drive
#: (FUSE) levava 3–6 s; com o índice em cache, a 2ª busca é imediata.
_INDEX: dict[str, Any] = {"ts": 0.0, "base": "", "items": []}
INDEX_TTL = 120.0


def _tree_index(base: Path) -> list[tuple[str, str, bool]]:
    """Índice da árvore: ``[(caminho relativo, nome, é_pasta)]``."""
    import time
    from concurrent.futures import ThreadPoolExecutor

    agora = time.time()
    chave = str(base)
    if _INDEX.get("base") == chave and (agora - float(_INDEX.get("ts") or 0)) < INDEX_TTL:
        return _INDEX.get("items") or []

    itens: list[tuple[str, str, bool]] = []

    def worker(args: tuple) -> tuple[list[tuple[str, str, bool]], list[tuple]]:
        dir_path, prefix = args
        achados: list[tuple[str, str, bool]] = []
        subpastas: list[tuple] = []
        try:
            entries = list(os.scandir(dir_path))
        except OSError:
            return achados, subpastas
        for entry in entries:
            name = entry.name
            if name.startswith(".") or name == "__pycache__":
                continue
            try:
                is_dir = entry.is_dir()
            except OSError:
                continue
            rel = f"{prefix}/{name}" if prefix else name
            achados.append((rel, name, is_dir))
            if is_dir and name not in SKIP_DIRS:
                subpastas.append((Path(entry.path), rel))
        return achados, subpastas

    with ThreadPoolExecutor(max_workers=8) as pool:
        nivel: list[tuple] = [(base, "")]
        visitadas = 0
        while nivel and visitadas < MAX_SEARCH_DIRS:
            visitadas += len(nivel)
            proximo: list[tuple] = []
            for achados, subpastas in pool.map(worker, nivel):
                itens.extend(achados)
                proximo.extend(subpastas)
            nivel = proximo
    _INDEX.update({"ts": agora, "base": chave, "items": itens})
    return itens


def search(relative: str = "", query: str = "", max_depth: int = MAX_SEARCH_DEPTH) -> dict[str, Any]:
    """Busca **recursiva** por nome, dentro da pasta do agente.

    v0.7.11-web28: o filtro do explorador. Devolve os arquivos e pastas cujo
    nome contém o termo (sem distinção de maiúsculas), com o caminho
    completo relativo — para que o clique abra o item certo.

    Usa o **índice em cache** da árvore (ver :func:`_tree_index`): o Drive é
    um FUSE e varrer tudo a cada tecla digitada deixava a interface lenta.
    """
    roots = allowed_roots()
    base = safe_path(relative, roots)
    if base is None:
        return {"error": "caminho fora da pasta do agente", "path": relative, "items": []}
    if not base.is_dir():
        return {"error": "não é uma pasta", "path": relative, "items": []}
    needle = str(query or "").strip().lower()
    if not needle:
        return {"error": "", "path": str(relative or ""), "items": [], "query": ""}

    rel_base = str(relative or "").strip("/")
    indice = _tree_index(base)
    found: list[dict[str, Any]] = []
    for rel, name, is_dir in indice:
        if needle not in name.lower():
            continue
        depth = rel.count("/")
        if depth > max_depth:
            continue
        parent = rel.rsplit("/", 1)[0] if "/" in rel else ""
        path = Path(base) / rel
        try:
            stat = path.stat()
            size = 0 if is_dir else int(stat.st_size)
            modified = int(stat.st_mtime * 1000)
        except OSError:
            size, modified = 0, 0
        found.append(
            {
                "name": name,
                "path": rel,
                "parent": parent,
                "type": "directory" if is_dir else "file",
                "size": size,
                "modified": modified,
                "mime": "" if is_dir else _mime_of(path),
                "kind": _kind_of(path),
                "driveUrl": drive_link(name),
                "depth": depth,
            }
        )
        if len(found) >= MAX_SEARCH_RESULTS:
            break
    found.sort(key=lambda i: (i.get("depth", 0), i.get("path", "")))
    return {
        "path": rel_base,
        "parent": "",
        "root": str(base),
        "items": found,
        "query": query,
        "truncated": len(found) >= MAX_SEARCH_RESULTS,
        "driveHome": DRIVE_HOME,
        "error": "",
    }


def read_bytes(relative: str, max_bytes: int = MAX_BINARY_BYTES) -> tuple[bytes | None, str]:
    """Lê o arquivo (bytes crus + caminho absoluto) dentro da raiz permitida."""
    target = safe_path(relative)
    if target is None or not target.is_file():
        return None, ""
    try:
        size = target.stat().st_size
    except OSError:
        return None, ""
    try:
        with open(target, "rb") as handle:
            data = handle.read(min(size, max_bytes) + 1)
    except OSError:
        return None, ""
    if len(data) > max_bytes:
        data = data[:max_bytes]
    return data, str(target)


# ── extração de texto da suíte Office (só biblioteca padrão) ───────────────

def _docx_text(data: bytes) -> str:
    with zipfile.ZipFile(_BytesIO(data)) as zf:
        try:
            xml = zf.read("word/document.xml").decode("utf-8", "replace")
        except KeyError:
            return ""
    # um parágrafo por linha: as quebras vivem em </w:p>, não nos <w:t>
    paragraphs: list[str] = []
    for block in re.findall(r"<w:p\b.*?</w:p>", xml, re.S):
        texts = re.findall(r"<w:t[^>]*>(.*?)</w:t>", block, re.S)
        if texts:
            paragraphs.append(html.unescape("".join(texts)))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(paragraphs))


def _xlsx_text(data: bytes) -> str:
    with zipfile.ZipFile(_BytesIO(data)) as zf:
        shared: list[str] = []
        try:
            sxml = zf.read("xl/sharedStrings.xml").decode("utf-8", "replace")
            for si in re.findall(r"<si>(.*?)</si>", sxml, re.S):
                shared.append(html.unescape("".join(re.findall(r"<t[^>]*>(.*?)</t>", si, re.S))))
        except KeyError:
            shared = []
        names = sorted(n for n in zf.namelist() if n.startswith("xl/worksheets/sheet"))
        out: list[str] = []
        for name in names:
            try:
                sheet = zf.read(name).decode("utf-8", "replace")
            except KeyError:
                continue
            out.append(f"— {name.split('/')[-1]} —")
            for row in re.findall(r"<row[^>]*>(.*?)</row>", sheet, re.S):
                cells: list[str] = []
                for cell in re.findall(r"<c\b([^>]*)>(.*?)</c>", row, re.S):
                    attrs, body = cell
                    value = ""
                    if 't="s"' in attrs:
                        m = re.search(r"<v>(\d+)</v>", body)
                        if m:
                            idx = int(m.group(1))
                            value = shared[idx] if idx < len(shared) else ""
                    else:
                        m = re.search(r"<v>(.*?)</v>", body, re.S)
                        value = m.group(1) if m else ""
                        m2 = re.search(r"<is>.*?<t[^>]*>(.*?)</t>", body, re.S)
                        if m2:
                            value = html.unescape(m2.group(1))
                    cells.append(value)
                if any(cells):
                    out.append(" | ".join(cells))
    return "\n".join(out)


def _pptx_text(data: bytes) -> str:
    with zipfile.ZipFile(_BytesIO(data)) as zf:
        names = sorted(n for n in zf.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n))
        out: list[str] = []
        for name in names:
            try:
                xml = zf.read(name).decode("utf-8", "replace")
            except KeyError:
                continue
            texts = re.findall(r"<a:t[^>]*>(.*?)</a:t>", xml, re.S)
            if texts:
                out.append(f"— {name.split('/')[-1]} —")
                out.append(html.unescape(" ".join(texts)))
    return "\n".join(out)


def _odf_text(data: bytes) -> str:
    with zipfile.ZipFile(_BytesIO(data)) as zf:
        try:
            xml = zf.read("content.xml").decode("utf-8", "replace")
        except KeyError:
            return ""
    xml = re.sub(r"</text:p>", "\n", xml)
    xml = re.sub(r"</table:table-row>", "\n", xml)
    texts = re.findall(r"<text:p[^>]*>(.*?)</text:p>", xml, re.S)
    joined = "\n".join(html.unescape("".join(re.findall(r"<[^>]+>|([^<]+)", t))) for t in texts)
    return re.sub(r"\n{3,}", "\n\n", joined)


def _BytesIO(data: bytes):  # noqa: N802 — helper local
    import io

    return io.BytesIO(data)


# ── DOCX → HTML (modo leitura, com a formatação do Word) ───────────────────
#
# v0.7.11-web28: o `.docx` era extraído como **texto puro** (parágrafos em
# linhas) — a formatação do Word (títulos, negrito, itálico, listas, tabelas,
# links e imagens) se perdia. Aqui o pacote OOXML é convertido em HTML
# simples, só com a biblioteca padrão.

_TAG_RE = re.compile(r"<[^>]+>")


def _xml_attr(tag: str, name: str) -> str:
    m = re.search(rf'{name}="([^"]*)"', tag)
    return m.group(1) if m else ""


def _docx_numbering(zf: zipfile.ZipFile) -> dict[str, dict[int, str]]:
    """Mapa ``numId → {nível: 'bullet'|'decimal'}`` (de ``numbering.xml``)."""
    out: dict[str, dict[int, str]] = {}
    try:
        xml = zf.read("word/numbering.xml").decode("utf-8", "replace")
    except KeyError:
        return out
    abstracts: dict[str, dict[int, str]] = {}
    for block in re.findall(r"<w:abstractNum\b.*?</w:abstractNum>", xml, re.S):
        aid = ""
        levels: dict[int, str] = {}
        for lvl in re.findall(r"<w:lvl\b[^>]*>.*?</w:lvl>", block, re.S):
            ilvl = int(_xml_attr(lvl[: lvl.find(">") + 1], "w:ilvl") or 0)
            fmt = ""
            m = re.search(r"<w:numFmt\b[^>]*w:val=\"([^\"]*)\"", lvl)
            if m:
                fmt = m.group(1)
            levels[ilvl] = "bullet" if fmt == "bullet" else "decimal"
        aid = _xml_attr(block[: block.find(">") + 1], "w:abstractNumId")
        if aid:
            abstracts[aid] = levels
    for num in re.findall(r"<w:num\b.*?</w:num>", xml, re.S):
        num_id = _xml_attr(num[: num.find(">") + 1], "w:numId")
        aid = ""
        m = re.search(r"<w:abstractNumId\b[^>]*w:val=\"([^\"]*)\"", num)
        if m:
            aid = m.group(1)
        if num_id:
            out[num_id] = abstracts.get(aid, {})
    return out


def _docx_rels(zf: zipfile.ZipFile) -> dict[str, dict[str, str]]:
    """Mapa ``rId → {tipo, alvo}`` (de ``word/_rels/document.xml.rels``)."""
    out: dict[str, dict[str, str]] = {}
    try:
        xml = zf.read("word/_rels/document.xml.rels").decode("utf-8", "replace")
    except KeyError:
        return out
    for rel in re.findall(r"<Relationship\b[^>]*/>", xml):
        rid = _xml_attr(rel, "Id")
        target = _xml_attr(rel, "Target")
        rtype = _xml_attr(rel, "Type").rsplit("/", 1)[-1]
        if rid:
            out[rid] = {"type": rtype, "target": target}
    return out


def _docx_images(zf: zipfile.ZipFile, rels: dict[str, dict[str, str]]) -> dict[str, str]:
    """Mapa ``rId → data URI`` das imagens embutidas.

    v0.7.11-web28: com limite de tamanho e de quantidade — um .docx com
    fotos grandes geraria um HTML de vários MB (travando a pré-visualização).
    """
    import base64
    import mimetypes

    out: dict[str, str] = {}
    total = 0
    for rid, info in rels.items():
        if info.get("type") != "image":
            continue
        if len(out) >= 12 or total >= 3 * 1024 * 1024:
            break
        target = info.get("target") or ""
        name = target.split("/")[-1]
        path = f"word/{target}" if not target.startswith("word/") else target
        try:
            raw = zf.read(path)
        except KeyError:
            continue
        if len(raw) > 900 * 1024:      # imagem muito grande: fora
            continue
        mime = mimetypes.guess_type(name)[0] or "image/png"
        out[rid] = f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"
        total += len(raw)
    return out


def _docx_run_html(run: str, rels: dict[str, dict[str, str]],
                   images: dict[str, str]) -> str:
    """Um ``<w:r>`` → HTML (negrito, itálico, sublinhado, link, imagem)."""
    props = ""
    rpr = re.search(r"<w:rPr\b.*?</w:rPr>", run, re.S)
    if rpr:
        props = rpr.group(0)
    text = "".join(html.unescape(t) for t in re.findall(r"<w:t[^>]*>(.*?)</w:t>", run, re.S))
    if not text:
        # imagem embutida
        for rid in re.findall(r'r:embed="([^"]+)"', run):
            src = images.get(rid)
            if src:
                return f'<img src="{src}" alt="">'
        return ""
    out = html.escape(text)
    if "<w:b/>" in props or '<w:b ' in props:
        out = f"<strong>{out}</strong>"
    if "<w:i/>" in props or '<w:i ' in props:
        out = f"<em>{out}</em>"
    if "<w:u/>" in props or "<w:u " in props:
        out = f"<u>{out}</u>"
    return out


def _docx_paragraph_html(block: str, rels: dict[str, dict[str, str]],
                         images: dict[str, str],
                         numbering: dict[str, dict[int, str]]) -> tuple[str, str, int]:
    """Um ``<w:p>`` → (html, tipo, nível).

    ``tipo``: ``p`` | ``h1..h6`` | ``title`` | ``quote`` | ``li`` | ``img``.
    """
    ppr = ""
    m = re.search(r"<w:pPr\b.*?</w:pPr>", block, re.S)
    if m:
        ppr = m.group(0)
    style = ""
    ms = re.search(r"<w:pStyle\b[^>]*w:val=\"([^\"]*)\"", ppr)
    if ms:
        style = ms.group(1).lower()

    # numeração (lista)
    num_id = ""
    ilvl = 0
    mn = re.search(r"<w:numId\b[^>]*w:val=\"([^\"]*)\"", ppr)
    if mn:
        num_id = mn.group(1)
    mi = re.search(r"<w:ilvl\b[^>]*w:val=\"([^\"]*)\"", ppr)
    if mi:
        try:
            ilvl = int(mi.group(1))
        except ValueError:
            ilvl = 0
    list_fmt = "decimal"
    if num_id:
        levels = numbering.get(num_id) or {}
        list_fmt = levels.get(ilvl, "decimal")

    # conteúdo: runs + hyperlinks
    partes: list[str] = []
    for hm in re.finditer(r"<w:hyperlink\b([^>]*)>(.*?)</w:hyperlink>", block, re.S):
        rid = _xml_attr(hm.group(1), "r:id")
        url = (rels.get(rid) or {}).get("target") or ""
        inner = "".join(
            _docx_run_html(r, rels, images) for r in re.findall(r"<w:r\b.*?</w:r>", hm.group(2), re.S)
        )
        if url.startswith("http"):
            partes.append(f'<a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener">{inner}</a>')
        else:
            partes.append(inner)
    # runs fora de hyperlinks
    fora = re.sub(r"<w:hyperlink\b.*?</w:hyperlink>", "", block, flags=re.S)
    for rm in re.finditer(r"<w:r\b.*?</w:r>", fora, re.S):
        partes.append(_docx_run_html(rm.group(0), rels, images))
    conteudo = "".join(partes)

    tipo = "p"
    if style in ("title",):
        tipo = "title"
    elif re.match(r"^heading(\d)$", style):
        tipo = "h" + style[-1]
    elif style == "quote":
        tipo = "quote"
    elif num_id:
        tipo = "li"
    return conteudo, tipo, ilvl, list_fmt


def docx_html(data: bytes) -> str:
    """Converte um ``.docx`` em HTML (modo leitura, com a formatação)."""
    try:
        zf = zipfile.ZipFile(_BytesIO(data))
    except (zipfile.BadZipFile, OSError):
        return ""
    rels = _docx_rels(zf)
    images = _docx_images(zf, rels)
    numbering = _docx_numbering(zf)
    try:
        xml = zf.read("word/document.xml").decode("utf-8", "replace")
    except KeyError:
        return ""

    out: list[str] = []
    lista_aberta = False
    tipo_lista = "ul"

    def fechar_lista() -> None:
        nonlocal lista_aberta
        if lista_aberta:
            out.append(f"</{tipo_lista}>")
            lista_aberta = False

    # percorre o corpo: parágrafos e tabelas
    corpo = re.search(r"<w:body\b.*?</w:body>", xml, re.S)
    corpo_txt = corpo.group(0) if corpo else xml
    blocos = re.findall(
        r"<w:p\b.*?</w:p>|<w:tbl>.*?</w:tbl>", corpo_txt, re.S
    )
    for bloco in blocos:
        if bloco.startswith("<w:tbl"):
            fechar_lista()
            out.append(_docx_table_html(bloco, rels, images))
            continue
        conteudo, tipo, ilvl, fmt = _docx_paragraph_html(bloco, rels, images, numbering)
        if tipo == "li":
            alvo = "ul" if fmt == "bullet" else "ol"
            if lista_aberta and alvo != tipo_lista:
                fechar_lista()
            if not lista_aberta:
                out.append(f"<{alvo}>")
                lista_aberta = True
                tipo_lista = alvo
            out.append(f"<li>{conteudo}</li>")
            continue
        fechar_lista()
        if not conteudo.strip():
            continue
        if tipo == "title":
            out.append(f"<h1>{conteudo}</h1>")
        elif tipo.startswith("h") and tipo[1:].isdigit():
            out.append(f"<{tipo}>{conteudo}</{tipo}>")
        elif tipo == "quote":
            out.append(f"<blockquote>{conteudo}</blockquote>")
        else:
            out.append(f"<p>{conteudo}</p>")
    fechar_lista()
    return "\n".join(out)


def _docx_table_html(block: str, rels: dict[str, dict[str, str]],
                     images: dict[str, str]) -> str:
    """Uma ``<w:tbl>`` → ``<table>``."""
    linhas: list[str] = []
    for row in re.findall(r"<w:tr\b.*?</w:tr>", block, re.S):
        celulas: list[str] = []
        for cell in re.findall(r"<w:tc\b.*?</w:tc>", row, re.S):
            paragrafos = []
            for p in re.findall(r"<w:p\b.*?</w:p>", cell, re.S):
                conteudo, _t, _l, _f = _docx_paragraph_html(p, rels, images, {})
                if conteudo.strip():
                    paragrafos.append(f"<p>{conteudo}</p>")
            celulas.append("".join(paragrafos) or "<p></p>")
        if celulas:
            linhas.append("<tr>" + "".join(f"<td>{c}</td>" for c in celulas) + "</tr>")
    if not linhas:
        return ""
    return "<table><tbody>" + "".join(linhas) + "</tbody></table>"


def _col_index(ref: str) -> int:
    """``"B3"`` → 1 (índice da coluna, base 0)."""
    m = re.match(r"([A-Z]+)", str(ref or ""))
    if not m:
        return 0
    idx = 0
    for ch in m.group(1):
        idx = idx * 26 + (ord(ch) - 64)
    return idx - 1


def _xlsx_shared(zf: zipfile.ZipFile) -> list[str]:
    """Textos compartilhados (``xl/sharedStrings.xml``)."""
    try:
        xml = zf.read("xl/sharedStrings.xml").decode("utf-8", "replace")
    except KeyError:
        return []
    out: list[str] = []
    for si in re.findall(r"<si\b.*?</si>", xml, re.S):
        textos = re.findall(r"<t[^>]*>(.*?)</t>", si, re.S)
        out.append(html.unescape("".join(textos)))
    return out


def _xlsx_sheets(zf: zipfile.ZipFile) -> list[tuple[str, str]]:
    """``[(nome da aba, caminho da xml)]`` — de ``workbook.xml`` + rels."""
    try:
        wb = zf.read("xl/workbook.xml").decode("utf-8", "replace")
        rels_xml = zf.read("xl/_rels/workbook.xml.rels").decode("utf-8", "replace")
    except KeyError:
        return []
    rels: dict[str, str] = {}
    for rel in re.findall(r"<Relationship\b[^>]*/>", rels_xml):
        rid = _xml_attr(rel, "Id")
        target = _xml_attr(rel, "Target")
        if rid:
            rels[rid] = target
    out: list[tuple[str, str]] = []
    for sheet in re.findall(r"<sheet\b[^>]*/>", wb):
        nome = _xml_attr(sheet, "name")
        rid = _xml_attr(sheet, "r:id")
        alvo = rels.get(rid, "")
        if not alvo:
            continue
        caminho = alvo[1:] if alvo.startswith("/") else f"xl/{alvo}"
        caminho = caminho.replace("xl/xl/", "xl/")
        out.append((html.unescape(nome), caminho))
    return out


def _xlsx_sheet_html(zf: zipfile.ZipFile, caminho: str, compartilhados: list[str]) -> str:
    """Uma planilha → ``<table>``."""
    try:
        xml = zf.read(caminho).decode("utf-8", "replace")
    except KeyError:
        return ""
    linhas: list[list[str]] = []
    for row in re.findall(r"<row\b.*?</row>", xml, re.S):
        celulas: list[str] = []
        for cell in re.findall(r"<c\b([^>]*)>(.*?)</c>|<c\b([^>]*)/>", row, re.S):
            attrs = cell[0] or cell[2] or ""
            corpo = cell[1] or ""
            tipo = _xml_attr(attrs, "t")
            valor = ""
            if tipo == "s":
                m = re.search(r"<v>(.*?)</v>", corpo, re.S)
                if m:
                    try:
                        valor = compartilhados[int(m.group(1))]
                    except (ValueError, IndexError):
                        valor = ""
            elif tipo == "inlineStr":
                textos = re.findall(r"<t[^>]*>(.*?)</t>", corpo, re.S)
                valor = html.unescape("".join(textos))
            elif tipo == "str":
                m = re.search(r"<v>(.*?)</v>", corpo, re.S)
                valor = html.unescape(m.group(1)) if m else ""
            else:
                m = re.search(r"<v>(.*?)</v>", corpo, re.S)
                valor = html.unescape(m.group(1)) if m else ""
            col = _col_index(_xml_attr(attrs, "r"))
            while len(celulas) < col:
                celulas.append("")
            celulas.append(valor)
        if any(c.strip() for c in celulas):
            linhas.append(celulas)
    if not linhas:
        return ""
    corpo = []
    for celulas in linhas:
        corpo.append("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in celulas) + "</tr>")
    return "<table><tbody>" + "".join(corpo) + "</tbody></table>"


def xlsx_html(data: bytes) -> str:
    """Converte um ``.xlsx`` em HTML — **cada aba vira uma tabela**."""
    try:
        zf = zipfile.ZipFile(_BytesIO(data))
    except (zipfile.BadZipFile, OSError):
        return ""
    compartilhados = _xlsx_shared(zf)
    abas = _xlsx_sheets(zf)
    if not abas:
        return ""
    out: list[str] = []
    for nome, caminho in abas:
        tabela = _xlsx_sheet_html(zf, caminho, compartilhados)
        if not tabela:
            continue
        out.append(f"<h3>{html.escape(nome)}</h3>")
        out.append(tabela)
    return "\n".join(out)


def office_text(path: Path) -> str:
    """Texto extraído de um arquivo da suíte Office (best-effort)."""
    try:
        data = path.read_bytes()
    except OSError:
        return ""
    suffix = path.suffix.lower()
    try:
        if suffix == ".docx":
            return _docx_text(data)
        if suffix == ".xlsx":
            return _xlsx_text(data)
        if suffix == ".pptx":
            return _pptx_text(data)
        if suffix in (".odt", ".ods", ".odp"):
            return _odf_text(data)
    except (zipfile.BadZipFile, OSError, ValueError):
        return ""
    return ""


def resolve(name: str) -> dict[str, Any]:
    """Resolve uma referência de arquivo **ou pasta** citada numa resposta.

    v0.7.11-web28: quando a resposta menciona um arquivo (pelo nome ou pelo
    caminho), o clique tem de **abrir o arquivo no explorador**. Aceita:

    * caminho absoluto dentro da raiz permitida (ex.: ``/content/drive/.../a.pdf``);
    * caminho relativo à raiz (``docs/relatorio.pdf``);
    * apenas o **nome** do arquivo (``relatorio.pdf``) — procurado na árvore
      (o mais raso primeiro).

    v0.7.11-web30: também aceita **pastas** — pelo caminho
    (``outputs-projeto/artigos``) ou só pelo nome (``artigos``). O clique
    abre a pasta no explorador.
    """
    raw = str(name or "").strip().strip("`'\"")
    if not raw:
        return {"ok": False, "error": "referência vazia"}
    roots = allowed_roots()

    # 1) caminho absoluto ou relativo, dentro da raiz
    candidate = safe_path(raw, roots)
    if candidate and candidate.is_file():
        rel = _relative(candidate, roots)
        return {"ok": True, "path": rel, "name": candidate.name, "kind": _kind_of(candidate)}
    if candidate and candidate.is_dir():
        return {"ok": True, "path": _relative(candidate, roots), "name": candidate.name,
                "kind": "directory", "dir": True}

    # 2) só o nome: procura na árvore (o mais raso primeiro) — ARQUIVOS e
    #    PASTAS (v0.7.11-web30: o caminho de uma pasta também é clicável)
    base = os.path.basename(raw.rstrip("/"))
    if not base:
        return {"ok": False, "error": "arquivo não encontrado", "name": raw}
    achados: list[tuple[int, int, str, Path]] = []
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
            depth = dirpath[len(str(root)):].count(os.sep)
            if depth > 4:
                dirnames[:] = []
                continue
            for nome in filenames:
                if nome.lower() == base.lower():
                    achados.append((depth, 0, os.path.join(dirpath, nome), Path(dirpath) / nome))
            for nome in dirnames:
                if nome.lower() == base.lower():
                    achados.append((depth, 1, os.path.join(dirpath, nome), Path(dirpath) / nome))
    if not achados:
        return {"ok": False, "error": "arquivo não encontrado na pasta do agente", "name": raw}
    achados.sort(key=lambda x: (x[0], x[1], x[2]))
    _depth, _e_pasta, caminho, _p = achados[0]
    alvo = Path(caminho)
    return {
        "ok": True,
        "path": _relative(alvo, roots),
        "name": os.path.basename(caminho),
        "kind": "directory" if _e_pasta else _kind_of(alvo),
        "dir": bool(_e_pasta),
    }


def _relative(path: Path, roots: list[Path] | None = None) -> str:
    """Caminho relativo à raiz permitida (para a URL do explorador)."""
    for root in (roots if roots is not None else allowed_roots()):
        try:
            return str(path.resolve().relative_to(root.resolve()))
        except (ValueError, OSError):
            continue
    return path.name


def preview(relative: str) -> dict[str, Any]:
    """Prévia de um arquivo para o painel (texto, imagem ou Office)."""
    target = safe_path(relative)
    if target is None:
        return {"error": "caminho fora da pasta do agente"}
    if not target.is_file():
        return {"error": "arquivo não encontrado"}
    kind = _kind_of(target)
    name = target.name
    info: dict[str, Any] = {
        "name": name,
        "path": str(relative),
        "kind": kind,
        "mime": _mime_of(target),
        "driveUrl": drive_link(name),
        "downloadUrl": f"api/ufvai/explorer/download?path={quote(str(relative), safe='')}",
        "text": "",
        "truncated": False,
        "error": "",
    }
    try:
        info["size"] = int(target.stat().st_size)
    except OSError:
        info["size"] = 0
    if kind == "image":
        info["inlineUrl"] = (
            f"api/ufvai/explorer/download?path={quote(str(relative), safe='')}&inline=1"
        )
        return info
    if kind == "office":
        text = office_text(target)
        if not text:
            info["error"] = (
                "não foi possível extrair o texto (formato legado ou protegido); "
                "abra no Google Drive"
            )
        info["text"] = text[:MAX_TEXT_BYTES]
        info["truncated"] = len(text) > MAX_TEXT_BYTES
        # v0.7.11-web28: o .docx/.xlsx sai em HTML — com a formatação do
        # Word/Excel (títulos, negrito, listas, tabelas, links, imagens), em
        # modo leitura.
        suffix = target.suffix.lower()
        if suffix in (".docx", ".xlsx"):
            try:
                raw = target.read_bytes()
            except OSError:
                raw = b""
            html_out = docx_html(raw) if suffix == ".docx" else xlsx_html(raw)
            info["html"] = html_out[:MAX_HTML_BYTES]
        return info
    if kind == "pdf":
        # v0.7.11-web28: o PDF é exibido **dentro** da web (o navegador
        # renderiza o `application/pdf` inline) — antes só havia o link
        # para o Drive.
        info["inlineUrl"] = (
            f"api/ufvai/explorer/download?path={quote(str(relative), safe='')}&inline=1"
        )
        return info
    if kind == "binary":
        info["error"] = "arquivo binário — baixe ou abra no Google Drive"
        return info
    # texto
    try:
        raw = target.read_bytes()[: MAX_TEXT_BYTES + 1]
    except OSError as exc:
        info["error"] = f"não foi possível ler: {exc}"
        return info
    info["truncated"] = len(raw) > MAX_TEXT_BYTES
    raw = raw[:MAX_TEXT_BYTES]
    try:
        info["text"] = raw.decode("utf-8")
    except UnicodeDecodeError:
        info["text"] = raw.decode("latin-1", "replace")
    return info
