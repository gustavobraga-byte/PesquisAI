#!/usr/bin/env python3
"""gera `pesquisai/webui/i18n.json` — dicionário da interface web do UFVAI.

Cinco idiomas, como o plugin de TUI ``ufvai.pt`` (pt-BR, en, es, fr, zh).
O wrapper e a fonte de verdade do idioma: ao trocar o idioma la, a web recebe
``postMessage {type:'ufvai-lang'}`` e troca os textos sem recarregar.

Uso:  python3 scripts/gen_webui_i18n.py
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "pesquisai" / "webui" / "i18n.json"

# ordem de traducao: pt-BR (canonico) -> en -> es -> fr -> zh
KEYS: list[str] = [
    "app.title", "app.tagline", "app.description",
    "sidebar.sessions", "sidebar.newSession", "sidebar.search", "sidebar.close",
    "sidebar.engine", "sidebar.connected", "sidebar.reconnecting", "sidebar.engineDead",
    "top.sessions", "top.actions", "top.settings", "top.refresh", "top.model",
    "top.agent", "top.variant", "top.usage", "top.context", "top.copyLink",
    "empty.hint",
    "composer.placeholder", "composer.attach", "composer.send", "composer.stop",
    "composer.remove", "composer.attached", "composer.uploading", "composer.uploadFail",
    "composer.tooBig", "composer.filesSaved",
    "status.working", "status.interrupting", "status.queued",
    # v0.7.11-web30: interrupção pedida pelo usuário + "nada em execução"
    "status.stopped", "status.noneRunning",
    "palette.commands", "palette.skills", "palette.files", "palette.hint",
    "palette.noResults", "palette.terminalOnly", "composer.placeholderShort",
    # v0.7.11-web30: comando da web — parar a execução
    "palette.stopCommand", "palette.stopDesc",
    "modal.model", "modal.searchModel", "modal.settings", "modal.session",
    "modal.close", "modal.variant",
    "tool.reasoning", "tool.copy", "tool.copied", "tool.copyFail", "tool.expandAll",
    "tool.collapseAll", "tool.call", "tool.calls", "tool.running", "tool.done",
    "tool.error", "tool.file", "tool.added", "tool.removed", "tool.noChanges",
    "session.rename", "session.renamePrompt", "session.fork", "session.compact",
    "session.background", "session.context", "session.copy", "session.new",
    "session.duplicate", "session.clear", "session.done", "session.copyResponse",
    "settings.tab.general", "settings.tab.model", "settings.tab.agent",
    "settings.tab.commands", "settings.tab.skills", "settings.tab.session",
    "settings.tab.shortcuts", "settings.tab.about", "settings.tab.autosave",
    "settings.autosaveNote", "settings.autosaveEnabled", "settings.autosaveInterval",
    "settings.autosaveScope", "settings.autosaveSessions", "settings.autosaveState",
    "settings.autosaveConnected", "settings.autosaveStandalone", "settings.autosaveSaved",
    "settings.scopeActive", "settings.scopeAll", "settings.scopeSelected", "settings.minutes",
    "retry.overloaded", "retry.detail", "retry.waiting", "error.title",
    "retry.attempt", "retry.attemptNoDelay",
    "session.finalize", "session.finalizeAsk", "session.finalizeArchive",
    "session.finalizeDelete", "session.finalizeDone",
    "explorer.title", "explorer.up", "explorer.refresh", "explorer.loading",
    "explorer.empty", "explorer.download", "explorer.drive", "explorer.truncated",
    "explorer.search", "explorer.clearSearch", "explorer.resize",
    "explorer.noResults", "explorer.results", "explorer.closePreview",
    "explorer.notFound", "explorer.resizePreview",
    "answer.openFile", "answer.openFolder",
    "about.version", "about.codename", "about.release", "about.author", "about.email",
    "about.institution", "about.registry", "about.license", "about.languages", "about.agencies",
    "settings.expandReasoning", "settings.expandTools", "settings.expandAll",
    "settings.theme", "settings.language", "settings.model", "settings.variant",
    "settings.agent", "settings.shortcutHint",
    "settings.aboutBody", "settings.copyShortcut",
    "settings.appearance", "settings.themeNote", "settings.display",
    "settings.displayNote", "settings.expandAllNote", "settings.engine",
    "settings.version", "settings.directory", "settings.modelsCount",
    "settings.providers", "settings.providerOk", "settings.providerNoKey",
    "settings.modelSession", "settings.current", "settings.default",
    "settings.chooseModel", "settings.providersTitle", "settings.agentNote",
    "settings.commandsNote", "settings.skillsNone", "settings.sessionCurrent",
    "settings.title", "settings.id", "settings.created", "settings.updated",
    "settings.tokens", "settings.tokensDetail", "settings.cost",
    "settings.showContext", "settings.duplicateSession", "settings.compact",
    "settings.aboutTitle", "settings.aboutText", "settings.languageNote",
    "settings.shortcuts", "settings.modelRow", "settings.variantRow",
    "key.send", "key.newline", "key.commands", "key.mention", "key.palette", "key.cancel",
    "key.expandAll", "key.interrupt", "key.background", "key.toggleSidebar",
    "key.attach", "key.copy", "key.close",
    "permission.title", "permission.once", "permission.always", "permission.reject",
    "permission.done", "permission.action", "permission.resource",
    "warn.gatewayOld", "warn.gatewayOldBody",
    "warn.disconnected", "warn.dead", "warn.deadBody", "warn.deadAction",
    "warn.reconnect", "warn.noSession", "warn.sendFailed", "warn.copyFailed",
    "toolname.shell", "toolname.write", "toolname.edit", "toolname.read",
    "toolname.list", "toolname.grep", "toolname.glob", "toolname.todo",
    "toolname.web", "toolname.task", "toolname.skill", "toolname.patch",
    "toolname.other",
]

# nomes proprios do motor (nao traduzidos de proposito)
TOOL_NAMES = {
    "toolname.shell": "Shell",
    "toolname.write": "Write",
    "toolname.edit": "Edit",
    "toolname.read": "Read",
    "toolname.list": "List",
    "toolname.grep": "Grep",
    "toolname.glob": "Glob",
    "toolname.todo": "Todo",
    "toolname.web": "Web",
    "toolname.task": "Task",
    "toolname.skill": "Skill",
    "toolname.patch": "Patch",
}

# chaves acrescentadas depois da traducao inicial (ficam aqui para o
# gerador nao depender de um arquivo externo)
EXTRA_FILE = Path(__file__).resolve().parent / "_webui_i18n_extra.json"


def _extra() -> dict[str, dict[str, str]]:
    """Chaves acrescentadas depois da traducao inicial (ficam em JSON)."""
    if not EXTRA_FILE.exists():
        return {}
    try:
        return json.loads(EXTRA_FILE.read_text(encoding="utf-8"))
    except ValueError:
        return {}


def _table(data: dict[str, str]) -> dict[str, str]:
    """Valida a completude do dicionario de um idioma."""
    missing = [k for k in KEYS if k not in data]
    if missing:
        raise SystemExit(f"faltam chaves: {missing}")
    extra = [k for k in data if k not in KEYS]
    if extra:
        raise SystemExit(f"chaves desconhecidas: {extra}")
    return {k: data[k] for k in KEYS}


def _load_existing() -> dict[str, dict[str, str]]:
    """Dicionarios ja validos de uma execucao anterior (base das traducoes)."""
    if not OUT.exists():
        return {}
    try:
        data = json.loads(OUT.read_text(encoding="utf-8"))
    except ValueError:
        return {}
    return data.get("locales") or {}


def main() -> None:
    base = _load_existing()
    extra = _extra()
    tables: dict[str, dict[str, str]] = {}
    for locale in ("pt-BR", "en", "es", "fr", "zh"):
        merged = dict(base.get(locale) or {})
        merged.update(extra.get(locale) or {})
        merged.update(extra.get(locale) or {})
        merged.update(TOOL_NAMES)
        tables[locale] = _table(merged)
    payload = {
        "version": "0.7.11-web23",
        "default": "pt-BR",
        "locales": tables,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{OUT} - {len(KEYS)} chaves x {len(tables)} idiomas")


if __name__ == "__main__":
    main()
