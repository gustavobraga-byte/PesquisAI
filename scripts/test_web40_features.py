#!/usr/bin/env python3
"""test_web40_features.py — valida os recursos da v0.7.11-web40 (estático).

Cobre: editar/regenerar, ações por mensagem, timestamps/TTFT, duração de
tool calls, LaTeX/Mermaid, realce ampliado + linhas, fila, favoritos e
preferência Enter/Ctrl+Enter.

Roda: python3 scripts/test_web40_features.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "pesquisai" / "webui" / "app.js").read_text(encoding="utf-8")
HTML = (ROOT / "pesquisai" / "webui" / "index.html").read_text(encoding="utf-8")
API = (ROOT / "pesquisai" / "webapi.py").read_text(encoding="utf-8")
SRV = (ROOT / "pesquisai" / "webui_server.py").read_text(encoding="utf-8")
I18N = json.loads((ROOT / "pesquisai" / "webui" / "i18n.json").read_text(encoding="utf-8"))

ok = total = 0


def check(name, cond):
    global ok, total
    total += 1
    print(("✓" if cond else "✗") + "  " + name)
    if cond:
        ok += 1


# HTML
for ident in ["ask-modal", "ask-ok", "ask-cancel", "fav-btn", "fav-menu"]:
    check(f'index.html tem #{ident}', f'id="{ident}"' in HTML)

# app.js — funções
for fn in ["function messageActions", "function messageMeta", "function editMessage",
           "function regenerate", "function queueMessage", "function flushQueue",
           "function renderFavMenu", "function loadFavorites", "function ensureKatex",
           "function ensureMermaid", "function codeBlockHtml", "function decorateRich",
           "function askConfirm"]:
    check(f"app.js tem {fn}", fn in APP)

# app.js — integrações
check("ações por mensagem no render", "messageActions(message, true)" in APP
      and "messageActions(message, false)" in APP)
check("meta (timestamp/TTFT) no render", "messageMeta(message)" in APP)
check("edit/regenerate chamam revert", "/revert" in APP and "messageID: message.id" in APP
      and "messageID: user.id" in APP)
check("tool duration no evento", "slot.toolStarted[ev.callID] = Date.now()" in APP
      and "ms / 1000" in APP and "setBlockStatus(block" in APP)
check("LaTeX inline/block", "math-block" in APP and "class=\"math\"" in APP)
check("Mermaid", ".mermaid" in APP and "mermaid.esm" in APP)
check("realce ampliado", all(x in APP for x in ["sql:", "r:", "jl:", "cpp:", "java:", "go:", "rust:"]))
check("números de linha", "class=\"ln\"" in APP and "class=\"cl\"" in APP)
check("fila no send", "queueMessage(text)" in APP and "flushQueue" in APP)
check("preferência ctrlEnter", "state.prefs.ctrlEnter" in APP and "sendOnCtrl" in APP)
check("favoritos em localStorage", "ufvai_prompt_favorites" in APP)

# backend
check("webapi.revert_to", "def revert_to(" in API and "revert/stage" in API)
check("webapi.save_memory", "def save_memory(" in API and "save_finding" in API)
check("webapi expõe firstToken", '"firstToken"' in API)
check("gateway rota revert", 'action == "revert"' in SRV and "revert_to" in SRV)
check("gateway rota memory", 'action == "memory"' in SRV and "save_memory" in SRV)

# i18n
needed = ["msg.copyMd", "msg.quote", "msg.usePrompt", "msg.saveMemory", "msg.edit",
          "msg.regenerate", "queue.badge", "fav.title", "settings.ctrlEnter", "key.ok"]
locales = I18N.get("locales", {})
check("5 idiomas", set(locales) == {"pt-BR", "en", "es", "fr", "zh"})
for loc in locales:
    faltando = [k for k in needed if k not in locales[loc]]
    check(f"{loc}: chaves web40", not faltando)

print(f"\n{ok}/{total} verificações passaram")
sys.exit(0 if ok == total else 1)
