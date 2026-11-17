#!/usr/bin/env python3
"""web23_native.py — catálogo dos comandos nativos da TUI do OpenCode.

O motor expõe só os comandos de *agente* (``/api/command``: ``pesquisar``,
``revisar``, ``dados``…). Os ~37 comandos da barra da TUI (``/new``,
``/undo``, ``/themes``, ``/models``…) vivem dentro do binário e não aparecem
na API — mas o plugin de TUI do UFVAI (``pesquisai/tui_pt.py``) os traduz e
os publica em ``PT_CATALOG``.

Este módulo junta as duas fontes para a interface web:

1. **Título nativo (inglês)** — de ``pesquisai/assets/i18n/pt-BR.json``: a
   seção ``commands`` traz, para cada id nativo, o dicionário
   ``{"<título nativo em inglês>": "<tradução pt-BR>"}``. A **chave** é o
   título nativo — é dela que sai o rótulo em inglês.
2. **Slug nativo (inglês)** — o próprio nome que o OpenCode registra
   (``slash_commands`` do mesmo arquivo). O par id → slug está na lista
   ``NATIVE_SLUGS`` de ``tests/test_comandos_pt.py`` (extraída do keymap
   real) e é conferido aqui contra o ``slash_commands`` do arquivo oficial.
3. **Grupo** — ``GROUPS`` do plugin (rótulo localizado) ou o nome nativo em
   inglês.

Nada aqui é inventado: tudo sai do arquivo de i18n do próprio OpenCode ou do
catálogo do plugin ``ufvai.pt``.
"""

from __future__ import annotations

import json
from pathlib import Path

__all__ = [
    "native_catalog",
    "native_slug",
    "NATIVE_SLUGS",
]

# id nativo -> slug nativo (inglês). Fonte: ``NATIVE_SLUGS`` em
# ``tests/test_comandos_pt.py`` (extraído do keymap real do OpenCode).
# Conferido contra ``slash_commands`` de ``assets/i18n/pt-BR.json``.
NATIVE_SLUGS: dict[str, str] = {
    "session.new": "new",
    "session.clear": "clear",
    "session.list": "sessions",
    "open.menu": "open",
    "session.rename": "rename",
    "session.timeline": "timeline",
    "session.fork": "fork",
    "session.compact": "compact",
    "session.undo": "undo",
    "session.redo": "redo",
    "messages.copy": "copy",
    "session.export": "export",
    "session.terminal": "terminal",
    "session.aside": "btw",
    "session.move": "worktrees",
    "session.cd": "cd",
    "prompt.editor": "editor",
    "prompt.skills": "skills",
    "model.list": "models",
    "agent.list": "agents",
    "mcp.list": "mcps",
    "variant.list": "variants",
    "provider.connect": "connect",
    "opencode.highlights": "highlights",
    "opencode.settings": "settings",
    "opencode.status": "status",
    "opencode.update": "update",
    "server.pair": "pair",
    "location.reload": "reload",
    "opencode.debug": "debug",
    "theme.switch": "themes",
    "help.show": "help",
    "app.exit": "exit",
    "diff.open": "diff",
    "stats.open": "stats",
    "plugins.list": "plugins",
    "service.restart": "restart",
}

# Comandos da TUI que a interface web sabe executar (os demais só existem
# no terminal). O valor é a ação correspondente no cliente.
WEB_ACTIONS: dict[str, str] = {
    "session.new": "new-session",
    "session.rename": "rename-session",
    "session.fork": "fork-session",
    "session.compact": "compact-session",
    "session.background": "background-session",
    "session.terminal": "toggle-terminal",
    "session.export": "copy-session-link",
    "model.list": "open-models",
    "variant.list": "open-variants",
    "agent.list": "open-agents",
    "prompt.skills": "open-skills",
    "opencode.settings": "open-settings",
    "theme.switch": "toggle-theme",
    "help.show": "open-shortcuts",
}

# Nomes canônicos dos grupos (inglês) — são as chaves de ``GROUPS`` no
# plugin ``ufvai.pt``.
GROUP_NAMES: dict[str, str] = {
    "session": "Session",
    "agent": "Agent",
    "system": "System",
    "integration": "Integration",
    "vcs": "VCS",
    "prompt": "Prompt",
}

_I18N_FILE = Path(__file__).resolve().parent / "assets" / "i18n" / "pt-BR.json"
_CACHE: dict[str, dict] = {}


def _i18n() -> dict:
    """Arquivo de i18n do OpenCode (títulos nativos + slugs nativos)."""
    if _CACHE:
        return _CACHE
    try:
        data = json.loads(_I18N_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    _CACHE.update(data if isinstance(data, dict) else {})
    return _CACHE


def native_title(command_id: str) -> str:
    """Título nativo em inglês do comando (fonte: i18n do OpenCode).

    Cadeia de resolução:
      1. ``commands[id].titles`` — a **chave** é o título nativo;
      2. via ``slash_commands`` — a descrição pt-BR do slug aponta para o
         comando equivalente (ex.: ``/clear`` é a mesma coisa que ``/new``);
      3. o próprio id (identidade real do comando).
    """
    data = _i18n()
    commands = data.get("commands") or {}
    entry = commands.get(command_id) or {}
    titles = entry.get("titles") or {}
    for key in titles:
        return str(key)

    # 2) pelo slug: a descrição pt-BR do comando traduzido
    slug = native_slug(command_id)
    desc_pt = (data.get("slash_commands") or {}).get(f"/{slug}")
    if desc_pt:
        for other_id, other in commands.items():
            other_titles = (other or {}).get("titles") or {}
            if desc_pt in other_titles.values():
                for key in other_titles:
                    return str(key)
    # 3) sem título no arquivo: usa o id (identidade real do comando)
    return str(command_id)


def native_group(command_id: str) -> str:
    """Grupo nativo em inglês do comando."""
    key = str(command_id).split(".")[0]
    return GROUP_NAMES.get(key, key.capitalize())


def native_slug(command_id: str) -> str:
    """Slug nativo em inglês do comando (``/new``, ``/undo``…)."""
    slug = NATIVE_SLUGS.get(command_id)
    if slug:
        return slug
    return str(command_id).split(".")[-1]


def _known_slugs() -> set[str]:
    slugs = _i18n().get("slash_commands") or {}
    return {str(k).lstrip("/") for k in slugs}


def native_catalog(lang: str, catalog: dict, groups: dict) -> list[dict]:
    """Catálogo dos comandos nativos da TUI, no idioma pedido.

    ``catalog`` é o ``PT_CATALOG`` do plugin (``ufvai.pt``) e ``groups`` o
    ``GROUPS`` — já localizados. Em inglês (o idioma nativo do motor) o
    slug e o título vêm do arquivo de i18n do próprio OpenCode.
    """
    english = str(lang).lower() == "en"
    known = _known_slugs()
    out: list[dict] = []
    for command_id, spec in (catalog or {}).items():
        if not isinstance(spec, dict):
            continue
        slug = str(spec.get("slug") or command_id.split(".")[-1])
        raw_group = str(spec.get("group") or command_id.split(".")[0])
        if english:
            # em inglês os rótulos são os nativos do motor
            group = GROUP_NAMES.get(raw_group) or native_group(command_id)
        else:
            group = str(
                (groups or {}).get(raw_group)
                or (groups or {}).get(raw_group.capitalize())
                or GROUP_NAMES.get(raw_group)
                or native_group(command_id)
            )
        title = str(spec.get("title") or slug)
        native = native_slug(command_id)
        out.append(
            {
                "name": native if english else slug,
                "title": native_title(command_id) if english else title,
                "description": str(spec.get("description") or ""),
                "group": group,
                "aliases": [str(a) for a in (spec.get("aliases") or [])],
                "agent": "",
                "source": "ufvai-pt",
                "id": str(command_id),
                "args": bool(spec.get("args")),
                "native": native,
                "nativeTitle": native_title(command_id),
                "known": (not known) or (native in known),
                "action": WEB_ACTIONS.get(str(command_id), ""),
                "scope": "web" if WEB_ACTIONS.get(str(command_id)) else "tui",
            }
        )
    return out
