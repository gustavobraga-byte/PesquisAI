#!/usr/bin/env python3
"""test_web41_features.py — valida os recursos da v0.7.11-web41 (estático).

Cobre: cache de Markdown, debounce, pausa de timers em aba oculta,
containment/content-visibility, sessões agrupadas/fixadas, exportação de
conversa e sanitização de URLs.

Roda: python3 scripts/test_web41_features.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "pesquisai" / "webui" / "app.js").read_text(encoding="utf-8")
CSS = (ROOT / "pesquisai" / "webui" / "app.css").read_text(encoding="utf-8")
THEME = (ROOT / "pesquisai" / "webui" / "theme34.css").read_text(encoding="utf-8")
I18N = json.loads((ROOT / "pesquisai" / "webui" / "i18n.json").read_text(encoding="utf-8"))

ok = total = 0


def check(name, cond):
    global ok, total
    total += 1
    print(("✓" if cond else "✗") + "  " + name)
    if cond:
        ok += 1


# performance
check("cache de Markdown", "__mdCache" in APP and "__mdCache.get(__key)" in APP)
check("debounce helper", "function debounce(" in APP)
check("debounce na busca de sessão", "debounce(renderSessions, 150)" in APP)
check("debounce na busca de modelo", "debounce((e) => renderModelList" in APP)
check("debounce na busca da conversa", "debounce(() => runFind" in APP)
check("isVisible helper", "const isVisible = () => !document.hidden" in APP)
check("timers guardados", APP.count("if (isVisible())") >= 4)
check("CSS containment", ".msg { contain: layout paint style; }" in CSS)
check("content-visibility", "content-visibility: auto" in CSS)
check("blur desligado no mobile", "@media (max-width: 900px)" in THEME
      and "backdrop-filter: none !important" in THEME)

# organização de sessões
check("state.pinned", "pinned: new Set()" in APP)
check("sessionGroup", "function sessionGroup(" in APP)
check("loadPinned", "function loadPinned(" in APP and "ufvai_pinned_sessions" in APP)
check("togglePin", "function togglePin(" in APP)
check("grupo no renderSessions", "sessions.${g}" in APP and "session-group" in APP)
check("pin no renderSessions", "s-pin" in APP)

# exportação
check("conversationMarkdown", "function conversationMarkdown(" in APP)
check("downloadText", "function downloadText(" in APP and "URL.createObjectURL" in APP)
check("exportConversation", "function exportConversation(" in APP)
check("copyConversation", "function copyConversation(" in APP)
check("menu exporta/copia", "session.exportMd" in APP and "session.copyAll" in APP)

# segurança
check("safeUrl", "const safeUrl =" in APP and "/^(https?:|mailto:" in APP)
check("inline usa safeUrl", APP.count("safeUrl(") >= 2)

# i18n
needed = ["sessions.today", "sessions.yesterday", "sessions.week", "sessions.older",
          "sessions.pin", "sessions.unpin", "session.exportMd", "session.exported",
          "session.copyAll", "session.copied"]
locales = I18N.get("locales", {})
check("5 idiomas", set(locales) == {"pt-BR", "en", "es", "fr", "zh"})
for loc in locales:
    faltando = [k for k in needed if k not in locales[loc]]
    check(f"{loc}: chaves web41", not faltando)

print(f"\n{ok}/{total} verificações passaram")
sys.exit(0 if ok == total else 1)
