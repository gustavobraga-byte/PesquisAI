"""
tui_branding.py — **textos da tela de NOVA SESSÃO** no idioma do app (v0.6.25).

⚠️ DECISÃO DO AUTOR (21/10/2026): o logo e as sugestões de prompt do motor passaram a
ser substituídos por patch. Isto **revoga** a decisão de 18/10/2026 ("não se faz patch
no binário do motor") — registrada em `tui_prompt.py`, que mantém a restauração dos
patches antigos (backup `<binário>.orig-ufvai`).

## O que este módulo troca

Na tela de **nova sessão** do OpenCode V2 aparecem alguns textos do motor que, no
UFVAI, devem seguir o **idioma do app** (o idioma escolhido na interface / pelo
comando `/idioma`):

| Texto do motor                          | Ocorrência                                  |
|-----------------------------------------|---------------------------------------------|
| `Ask anything… "`                       | placeholder do prompt (nova sessão)          |
| `Run a command… "`                      | placeholder do prompt (modo shell)           |
| `Ask anything, / for commands, @ for context` | dica longa do prompt                  |
| `Fix a TODO in the codebase`            | sugestão do placeholder                      |
| `What is the tech stack of this project?` | sugestão do placeholder                   |
| `Fix broken tests`                      | sugestão do placeholder                      |
| `agents` / `commands`                   | **NÃO** são trocados — são nomes de comando do keymap (o caso `commands`
|                                          | quebrou o SQLite em 18/10). O rodapé `shift+tab agents · ctrl+p commands`
|                                          | permanece em inglês.                         |

Cada literal é substituído por um **mesmo comprimento de BYTE**: o bytecode do Bun
referencia literais por deslocamento no texto-fonte embutido; qualquer alteração de
tamanho deslocaria todos os offsets seguintes e corromperia o binário. O módulo
**recusa** o patch se algum par não for byte-exato (verificado na importação).

## As DUAS tabelas de strings (descoberta de 21/10/2026)

O binário guarda os textos da TUI em **dois** lugares:

| Tabela | Região (v2.1.1) | Quem usa |
|--------|-----------------|----------|
| UTF-8 (texto-fonte embutido) | ~96,2 MB | *source maps*/erros — **não** é o que a tela mostra |
| **UTF-16LE** (strings do bytecode) | ~96,3 MB | **é o que a TUI renderiza** |

Por isso um patch só na tabela UTF-8 **não** muda a tela (verificado em execução: o
placeholder continuava `Ask anything…`). `_TEXT_U16` guarda os pares UTF-16LE, também
com o **mesmo número de code units** — sem exceção.

## Por que o LOGO não é trocado aqui

A arte do logo (`opencode` em blocos) **não é** um literal simples: em todo o binário
(213 MB) há apenas **13 bytes** de caracteres meio-cheio (`E2 96 80/84/88`), todos da
biblioteca de fontes ASCII (cfonts/iconv). A arte existe **somente** como texto de
escape (`\u2588\u2580\u2580\u2588…`) no texto-fonte embutido — e o motor executa a
cópia **comprimida** do bytecode, não esse texto. Prova empírica: o patch das
sugestões (que vive na tabela de literais **não comprimida**) passou a valer na tela,
enquanto a alteração da arte no texto-fonte **não** teve efeito. Trocar a arte
exigiria recompilar o bytecode do motor — risco de corromper o motor.

A marca **UFVAI** na nova sessão é entregue pela **API pública de plugins** (slot
`prompt.footer.status` do plugin `ufvai-pt`).

## Garantias

- **Só literais de exibição** — nada que toque nome de tabela/coluna ou contrato
  interno (o caso `commands` → `SQLiteError: table project has no column named
  commands`).
- **Backup** do binário original em `<binário>.orig-ufvai-brand`; a troca é sempre
  feita a partir dessa cópia **pristina**, então trocar de idioma é determinístico.
- **Fail-open** — qualquer falha não impede o boot; **idempotente**.
- **Desligável** — `UFVAI_TUI_BRANDING=0` restaura o binário original.

Autor: Gustavo Bastos Braga · UFV · Universidade Federal de Viçosa
"""

from __future__ import annotations

import os
import shutil
import tempfile
from typing import Optional

__all__ = [
    "BACKUP_SUFFIX",
    "LOCALIZED_TEXTS",
    "SUPPORTED_LOCALES",
    "apply_branding",
    "restore",
    "status",
]

BACKUP_SUFFIX = ".orig-ufvai-brand"

# ── Textos da nova sessão por idioma (todos byte-exatos) ─────────────────────
# Chave = literal do motor (bytes) · valor = texto no idioma do app (bytes).
_BASE: dict[str, list[tuple[bytes, bytes]]] = [
    (b"Ask anything", b"Escreva algo"),
    (b"Ask anything, / for commands, @ for context",
     "Escreva algo, / comandos, @ para o contexto".encode("utf-8")),
    (b"Fix a TODO in the codebase", "Monte um plano de pesquisa".encode("utf-8")),
    (b"What is the tech stack of this project?",
     "Qual a base de dados da minha pesquisa?".encode("utf-8")),
    (b"Fix broken tests", "Revise o artigo.".encode("utf-8")),
]

_LOCALIZED: dict[str, list[tuple[bytes, bytes]]] = {
    "pt-BR": _BASE,
    "es": [
        (b"Ask anything", "Escribe algo".encode("utf-8")),
        (b"Ask anything, / for commands, @ for context",
         "Escribe algo, / comandos, @ para contexto  ".encode("utf-8")),
        (b"Fix a TODO in the codebase", "Diseña un plan de trabajo".encode("utf-8")),
        (b"What is the tech stack of this project?",
         "¿Qué datos necesito para la pesquisa?".encode("utf-8")),
        (b"Fix broken tests", "Revisa el texto.".encode("utf-8")),
    ],
    "fr": [
        (b"Ask anything", "Écrivez ici".encode("utf-8")),
        (b"Ask anything, / for commands, @ for context",
         "Écrivez ici, / commandes, @ pour contexte ".encode("utf-8")),
        (b"Fix a TODO in the codebase", "Plan de recherche complet.".encode("utf-8")),
        (b"What is the tech stack of this project?",
         "Quelles données pour cette recherche ?".encode("utf-8")),
        (b"Fix broken tests", "Relis l'article.".encode("utf-8")),
    ],
    "zh": [
        (b"Ask anything", "输入问题".encode("utf-8")),
        (b"Ask anything, / for commands, @ for context",
         "输入问题, / 命令, @ 上下文内容  ".encode("utf-8")),
        (b"Fix a TODO in the codebase", "制定一份研究计划  ".encode("utf-8")),
        (b"What is the tech stack of this project?",
         "为这项研究选择合适的数据源".encode("utf-8")),
        (b"Fix broken tests", "请审阅此稿.".encode("utf-8")),
    ],
    # inglês = original do motor (sem patch de texto)
    "en": [],
}

# ── Tabela UTF-16LE (é esta que a TUI RENDERIZA) ───────────────────────────
# Descoberta de 21/10/2026: o binário guarda as strings da TUI em **dois**
# lugares — a tabela UTF-8 (texto-fonte, ~96,2 MB) e a tabela **UTF-16LE**
# (strings do bytecode, ~96,3 MB). A TUI renderiza a UTF-16: por isso o patch
# só na UTF-8 não mudava a tela. Os pares abaixo têm o MESMO número de code
# units (o deslocamento do bytecode não pode mudar).
_TEXT_U16: dict[str, list[tuple[str, str]]] = {
    # "Ask anything… \"" tem 15 code units; "Run a command… \"" tem 16.
    "pt-BR": [
        ('Ask anything\u2026 "', 'Escreva algo\u2026 "'),
        ('Run a command\u2026 "', 'Rodar comando\u2026 "'),
    ],
    "es": [
        ('Ask anything\u2026 "', 'Escribe algo\u2026 "'),
        ('Run a command\u2026 "', 'Corre comando\u2026 "'),
    ],
    "fr": [
        ('Ask anything\u2026 "', '\u00c9crivez ici\u2026  "'),
        ('Run a command\u2026 "', 'Tapez une cmd\u2026 "'),
    ],
    "zh": [
        ('Ask anything\u2026 "', '请在此输入你要研究的问题\u2026 "'),
        ('Run a command\u2026 "', '输入你要运行的命令内容吧。\u2026 "'),
    ],
    "en": [],
}

LOCALIZED_TEXTS: dict[str, list[tuple[bytes, bytes]]] = _LOCALIZED
SUPPORTED_LOCALES: tuple[str, ...] = ("pt-BR", "en", "es", "fr", "zh")


def _validate() -> None:
    """Falha cedo (import) se algum par não for byte-exato."""
    for locale, pairs in LOCALIZED_TEXTS.items():
        for old, new in pairs:
            if len(old) != len(new):
                raise ValueError(
                    f"tui_branding: par não byte-exato em {locale}: "
                    f"{old!r} ({len(old)} B) → {new!r} ({len(new)} B)"
                )
    for locale, pairs in _TEXT_U16.items():
        for old, new in pairs:
            if len(old.encode("utf-16-le")) != len(new.encode("utf-16-le")):
                raise ValueError(
                    f"tui_branding: par UTF-16 não equivalente em {locale}: "
                    f"{old!r} → {new!r}"
                )


_validate()


def _locale_file() -> str:
    return os.path.expanduser("~/.config/opencode/ufvai-language.json")


def detect_locale(default: str = "pt-BR") -> str:
    """Idioma do app: arquivo gravado pelo `/idioma` → env → padrão."""
    try:
        import json

        with open(_locale_file(), encoding="utf-8") as handle:
            locale = json.load(handle).get("locale")
        if locale in SUPPORTED_LOCALES:
            return locale
    except (OSError, ValueError):
        pass
    for var in ("UFVAI_LANG", "PESQUISAI_LOCALE", "PESQUISAI_LANG"):
        raw = (os.environ.get(var) or "").strip().lower().replace("_", "-")
        for candidate in SUPPORTED_LOCALES:
            if raw == candidate.lower() or raw.startswith(candidate.lower()[:2]):
                return candidate
    return default


def status(binary: str) -> str:
    """`branded` | `clean` | `backup-only` | `missing`.

    ``backup-only`` = existe backup pristine, mas o binário não tem as marcas
    (ex.: restaurado, ou patch desligado). As marcas são checadas **antes** do
    backup; do contrário todo binário com backup seria reportado como
    ``backup-only`` — inclusive o já patchado.
    """
    if not os.path.exists(binary):
        return "missing"
    try:
        with open(binary, "rb") as handle:
            data = handle.read()
    except OSError:
        return "missing"
    for old, new in LOCALIZED_TEXTS.get("pt-BR", []):
        if new in data and old not in data:
            return "branded"
    for old_txt, new_txt in _TEXT_U16.get("pt-BR", []):
        if new_txt.encode("utf-16-le") in data and old_txt.encode("utf-16-le") not in data:
            return "branded"
    if os.path.exists(binary + BACKUP_SUFFIX):
        return "backup-only"
    return "clean"


def restore(binary: str) -> bool:
    """Restaura o binário original a partir do backup. Fail-open."""
    backup = binary + BACKUP_SUFFIX
    if not os.path.exists(backup):
        return False
    directory = os.path.dirname(binary) or "."
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".opencode-brand-restore-")
        os.close(fd)
        shutil.copyfile(backup, tmp)
        os.chmod(tmp, 0o755)
        os.replace(tmp, binary)
        tmp = None
    except OSError:
        return False
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
    return True


def _write_atomic(path: str, payload: bytes) -> bool:
    directory = os.path.dirname(path) or "."
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".opencode-brand-")
        os.close(fd)
        with open(tmp, "wb") as handle:
            handle.write(payload)
        os.chmod(tmp, 0o755)
        os.replace(tmp, path)
        tmp = None
        return True
    except OSError:
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        return False


def _is_branded(data: bytes, locale: str) -> bool:
    """True se **todos** os pares do idioma já estão aplicados em ``data``."""
    pairs8 = LOCALIZED_TEXTS.get(locale, [])
    pairs16 = _TEXT_U16.get(locale, [])
    if not pairs8 and not pairs16:
        return False
    for old, new in pairs8:
        if new not in data or old in data:
            return False
    for old_txt, new_txt in pairs16:
        if new_txt.encode("utf-16-le") not in data or old_txt.encode("utf-16-le") in data:
            return False
    return True


def apply_branding(binary: str, locale: Optional[str] = None) -> str:
    """Aplica os textos da nova sessão no idioma ``locale`` (padrão: o do app).

    A troca é sempre feita a partir da cópia **pristina** (backup), de modo que
    trocar de idioma seja determinístico e nunca acumule patches.

    Returns:
        "applied" | "already" | "disabled" | "not-found" | "failed"
    """
    if not os.path.exists(binary):
        return "not-found"
    if os.environ.get("UFVAI_TUI_BRANDING", "1").strip() in {"0", "false", "no", "off"}:
        restore(binary)
        return "disabled"

    locale = locale or detect_locale()
    pairs = LOCALIZED_TEXTS.get(locale, [])
    backup = binary + BACKUP_SUFFIX

    # base pristine: o backup se existir, senão o binário atual
    try:
        if os.path.exists(backup):
            with open(backup, "rb") as handle:
                base = handle.read()
        else:
            with open(binary, "rb") as handle:
                base = handle.read()
    except OSError:
        return "failed"

    patched = base
    if pairs:
        # do literal MAIS LONGO para o mais curto: senão `Ask anything` (12 B)
        # consome o prefixo da dica longa e o par de 43 B nunca casa.
        for old, new in sorted(pairs, key=lambda pair: len(pair[0]), reverse=True):
            if len(old) != len(new):
                return "failed"
            patched = patched.replace(old, new)
    # tabela UTF-16LE — é a que a TUI renderiza (ver _TEXT_U16)
    for old_txt, new_txt in _TEXT_U16.get(locale, []):
        old16 = old_txt.encode("utf-16-le")
        new16 = new_txt.encode("utf-16-le")
        if len(old16) != len(new16):
            return "failed"
        patched = patched.replace(old16, new16)
    if len(patched) != len(base):
        return "failed"

    # idempotência: se o binário já tem todos os pares deste idioma, não reescreve
    if os.path.exists(backup):
        try:
            with open(binary, "rb") as handle:
                current = handle.read()
        except OSError:
            current = b""
        if _is_branded(current, locale):
            return "already"

    if not os.path.exists(backup):
        try:
            shutil.copyfile(binary, backup)
            os.chmod(backup, 0o755)
        except OSError:
            return "failed"

    if not _write_atomic(binary, patched):
        return "failed"
    return "applied"
