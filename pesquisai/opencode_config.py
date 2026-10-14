"""
opencode_config.py — Configuração do OpenCode V2 gerada pelo UFVAI.

Concentra a lógica de arquivos do motor (sem efeitos colaterais no import):

- leitura de JSON/JSONC com proteção contra sobrescrita (se o arquivo do
  usuário não puder ser lido, NÃO reescrevemos — evita perda de dados);
- escrita atômica de JSON;
- `cli.json` (V2: tema + modo do terminal);
- `opencode.json` (V2: `default_agent`);
- tema UFVAI no formato V1 com as 50 chaves exigidas pelo conversor do V2
  (o V2 converte o formato V1 internamente, via `ce()` no binário);
- agente Markdown (`agents/<nome>.md`) no frontmatter aceito pela V2.

Referências (documentação oficial OpenCode V2, consultada em 2026-10-13):
  - https://opencode.ai/v2/docs/cli/config/
  - https://opencode.ai/v2/docs/config/
  - https://opencode.ai/v2/docs/agents/
  - https://opencode.ai/v2/docs/cli/theme/
"""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any

CLI_SCHEMA_URL = "https://opencode.ai/v2/cli.json"
CONFIG_SCHEMA_URL = "https://opencode.ai/config.json"
THEME_SCHEMA_URL = "https://opencode.ai/theme.json"

UFVAI_THEME_NAME = "pesquisai"
UFVAI_THEME_MODES = ("dark", "light")


# ─────────────────────────────────────────────────────────────────
# JSON / JSONC
# ─────────────────────────────────────────────────────────────────

def strip_jsonc(text: str) -> str:
    """Remove comentários // e /* */ e vírgulas finais, respeitando strings."""
    out: list[str] = []
    i, n = 0, len(text)
    in_str = False
    while i < n:
        ch = text[i]
        if in_str:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            end = text.find("*/", i + 2)
            i = n if end == -1 else end + 2
            continue
        out.append(ch)
        i += 1
    cleaned = "".join(out)
    # vírgula final antes de } ou ] (fora de strings: regex simples basta aqui)
    import re
    return re.sub(r",(\s*[}\]])", r"\1", cleaned)


def load_json_config(path: str) -> tuple[bool, dict[str, Any]]:
    """Carrega JSON/JSONC de um arquivo.

    Returns:
        (pode_gravar, dados). ``pode_gravar`` é False quando o arquivo existe
        mas não pode ser interpretado — nesse caso o chamador NÃO deve gravar
        por cima (evita apagar configuração do usuário).
    """
    if not os.path.exists(path):
        return True, {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = fh.read()
    except OSError:
        return False, {}
    if not raw.strip():
        return True, {}
    for candidate in (raw, strip_jsonc(raw)):
        try:
            data = json.loads(candidate)
        except (ValueError, TypeError):
            continue
        if isinstance(data, dict):
            return True, data
        return False, {}
    return False, {}


def write_json_atomic(path: str, data: dict[str, Any]) -> None:
    """Grava JSON de forma atômica (arquivo temporário + os.replace)."""
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


# ─────────────────────────────────────────────────────────────────
# cli.json (cliente de terminal — V2)
# ─────────────────────────────────────────────────────────────────

def merge_cli_theme(existing: dict[str, Any], theme_name: str, mode: str) -> dict[str, Any]:
    """Aplica tema e modo em cli.json preservando as demais configurações.

    A V2 rejeita chaves desconhecidas em cli.json, por isso só mexemos em
    ``theme`` e ``$schema``.
    """
    if mode not in UFVAI_THEME_MODES:
        mode = "dark"
    merged = dict(existing)
    theme = merged.get("theme")
    # Cópia também do theme: `dict(existing)` é rasa e escrever em theme
    # mutaria o dicionário do chamador (ex.: o config recarregado do disco).
    theme = dict(theme) if isinstance(theme, dict) else {}
    theme["name"] = theme_name
    theme["mode"] = mode
    merged["theme"] = theme
    merged["$schema"] = CLI_SCHEMA_URL
    return merged


def mode_from_ui_theme(ui_theme: str) -> str:
    """'pesquisai-light' → 'light'; qualquer outro valor → 'dark'."""
    return "light" if ui_theme == "pesquisai-light" else "dark"


def ui_theme_from_cli(cli: dict[str, Any]) -> str:
    """Converte o cli.json do V2 no nome de tema usado pela interface web."""
    theme = cli.get("theme")
    mode = theme.get("mode") if isinstance(theme, dict) else None
    return "pesquisai-light" if mode == "light" else "pesquisai"


# ─────────────────────────────────────────────────────────────────
# opencode.json (configuração global — V2)
# ─────────────────────────────────────────────────────────────────

def merge_default_agent(existing: dict[str, Any], agent_name: str) -> dict[str, Any]:
    """Define ``default_agent`` preservando o restante da configuração."""
    merged = dict(existing)
    merged["default_agent"] = agent_name
    merged.setdefault("$schema", CONFIG_SCHEMA_URL)
    return merged


# ─────────────────────────────────────────────────────────────────
# Agente Markdown (agents/<nome>.md)
# ─────────────────────────────────────────────────────────────────

def strip_frontmatter(text: str) -> str:
    """Remove um bloco inicial de frontmatter YAML (---) do texto."""
    if not text.startswith("---"):
        return text
    lines = text.splitlines(keepends=True)
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            return "".join(lines[idx + 1:]).lstrip("\n")
    return text


def build_agent_markdown(description: str, color: str, body: str) -> str:
    """Monta o agente com frontmatter aceito pela V2.

    Campos usados: ``description``, ``mode`` (primary, explícito) e ``color``
    (hex de 6 dígitos). ``name`` NÃO é usado: a V2 define o ID pelo caminho do
    arquivo — verificado em 13/10/2026 na V2.0.28: um ``name: UFVAI`` no
    frontmatter é **ignorado** e o agente continua aparecendo como ``ufvai``.
    Para o agente se chamar "UFVAI", o arquivo precisa ser ``agents/UFVAI.md``.
    """
    # Aspas duplas (formato JSON é YAML válido): a descrição tem ": " e "#",
    # que quebrariam um escalar YAML sem aspas.
    safe_description = json.dumps(description.replace("\n", " ").strip(), ensure_ascii=False)
    return (
        "---\n"
        f"description: {safe_description}\n"
        "mode: primary\n"
        f'color: "{color}"\n'
        "---\n\n"
        f"{body.strip()}\n"
    )


# ─────────────────────────────────────────────────────────────────
# Tema UFVAI (formato V1 com as 50 chaves do tema embutido)
# ─────────────────────────────────────────────────────────────────

# Paleta UFVAI (mesmos valores históricos do tema do terminal)
_DARK: dict[str, str] = {
    "bg0": "#141c24", "bg1": "#1a232c", "bg2": "#1f2831", "bg3": "#26313c",
    "bg4": "#2f3d4a", "fg0": "#e8e6e0", "fg1": "#a8b2ba", "fg2": "#6b7684",
    "blue": "#d4b56a", "blueDim": "#8a6d33", "green": "#5dba7e",
    "greenDark": "#1d4a2e", "amber": "#D1A705", "red": "#e07a70",
    "redDark": "#571512", "cyan": "#7fa8bd", "purple": "#c98a76",
    "synKeyword": "#7fa8bd", "synString": "#5dba7e", "synComment": "#6b7684",
    "synNumber": "#D1A705", "synFunction": "#d4b56a", "synType": "#c98a76",
    "synOp": "#a8b2ba",
}

_LIGHT: dict[str, str] = {
    "bg0": "#faf9f6", "bg1": "#ffffff", "bg2": "#f1efe9", "bg3": "#e5e1d6",
    "bg4": "#d9d3c4", "fg0": "#1f2831", "fg1": "#4a5560", "fg2": "#857f72",
    "blue": "#8a6d33", "blueDim": "#d4b56a", "green": "#2e7d32",
    "greenDark": "#a5d6a7", "amber": "#a67c00", "red": "#c0392b",
    "redDark": "#ef9a9a", "cyan": "#4a7c8c", "purple": "#9a5a48",
    "synKeyword": "#4a7c8c", "synString": "#2e7d32", "synComment": "#857f72",
    "synNumber": "#a67c00", "synFunction": "#8a6d33", "synType": "#9a5a48",
    "synOp": "#4a5560",
}

# Cada chave do tema embutido do V2 aponta para um papel da paleta.
# As 50 chaves são exigidas pelo conversor (ausência gera erro e fallback).
_THEME_ROLES: dict[str, str] = {
    "primary": "blue", "secondary": "cyan", "accent": "purple",
    "error": "red", "warning": "amber", "success": "green", "info": "cyan",
    "text": "fg0", "textMuted": "fg1",
    "background": "bg0", "backgroundPanel": "bg1", "backgroundElement": "bg2",
    "border": "bg3", "borderActive": "bg4", "borderSubtle": "bg2",
    "diffAdded": "green", "diffAddedBg": "greenDark",
    "diffRemoved": "red", "diffRemovedBg": "redDark",
    "diffContext": "fg1", "diffContextBg": "bg1", "diffHunkHeader": "fg2",
    "diffHighlightAdded": "greenDark", "diffHighlightRemoved": "redDark",
    "diffLineNumber": "fg2", "diffAddedLineNumberBg": "greenDark",
    "diffRemovedLineNumberBg": "redDark",
    "syntaxComment": "synComment", "syntaxKeyword": "synKeyword",
    "syntaxFunction": "synFunction", "syntaxVariable": "fg0",
    "syntaxString": "synString", "syntaxNumber": "synNumber",
    "syntaxType": "synType", "syntaxOperator": "synOp",
    "syntaxPunctuation": "fg2",
    "markdownText": "fg0", "markdownHeading": "blue", "markdownLink": "cyan",
    "markdownLinkText": "cyan", "markdownCode": "green",
    "markdownCodeBlock": "fg0", "markdownBlockQuote": "fg2",
    "markdownEmph": "fg1", "markdownStrong": "fg0",
    "markdownHorizontalRule": "bg4", "markdownListItem": "blue",
    "markdownListEnumeration": "blue", "markdownImage": "cyan",
    "markdownImageText": "fg1",
}


def build_ufvai_theme() -> dict[str, Any]:
    """Retorna o tema UFVAI completo (dark + light) no formato V1 aceito pelo V2."""
    defs: dict[str, str] = {}
    for role, value in _DARK.items():
        defs[f"d_{role}"] = value
    for role, value in _LIGHT.items():
        defs[f"l_{role}"] = value
    theme: dict[str, Any] = {
        key: {"dark": f"d_{role}", "light": f"l_{role}"}
        for key, role in _THEME_ROLES.items()
    }
    return {"$schema": THEME_SCHEMA_URL, "defs": defs, "theme": theme}


def theme_key_count() -> int:
    """Quantidade de chaves do tema (deve ser 50, igual ao tema embutido)."""
    return len(_THEME_ROLES)
