#!/usr/bin/env python3
"""test_web39_features.py — valida os recursos da v0.7.11-web39 (estático).

Cobre: seleção em massa de sessões, busca na conversa (Ctrl+F), arrastar/colar,
aviso de contexto, contador de novas mensagens, histórico de prompts e ARIA.

Roda: python3 scripts/test_web39_features.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "pesquisai" / "webui" / "app.js").read_text(encoding="utf-8")
HTML = (ROOT / "pesquisai" / "webui" / "index.html").read_text(encoding="utf-8")
I18N = json.loads((ROOT / "pesquisai" / "webui" / "i18n.json").read_text(encoding="utf-8"))

ok = total = 0


def check(name, cond):
    global ok, total
    total += 1
    print(("✓" if cond else "✗") + "  " + name)
    if cond:
        ok += 1


# ── HTML: novos elementos ──────────────────────────────────────────────
for ident in ["bulk-toggle", "bulk-bar", "bulk-all", "bulk-archive", "bulk-delete",
              "find-bar", "find-input", "find-prev", "find-next", "find-close",
              "context-warning", "context-compact", "context-dismiss"]:
    check(f'index.html tem #{ident}', f'id="{ident}"' in HTML)

# ── HTML: acessibilidade ───────────────────────────────────────────────
check('status com aria-live', 'id="status-text" role="status" aria-live="polite"' in HTML)
check('toast com aria-live', 'id="toast" hidden role="status" aria-live="polite"' in HTML)
check('modais com role="dialog"', HTML.count('role="dialog"') >= 5)
check('modais com aria-modal', HTML.count('aria-modal="true"') >= 5)

# ── app.js: funções e integrações ──────────────────────────────────────
for fn in ["function toggleBulkMode", "function toggleBulk", "function updateBulkBar",
           "function askBulk", "function bulkFinalize", "function runConfirm",
           "function openFind", "function closeFind", "function runFind",
           "function stepFind", "function maybeWarnContext"]:
    check(f"app.js tem {fn}", fn in APP)

check("renderSessions em modo bulk", "bulk-mode" in APP and "s-check" in APP)
check("confirmação usa runConfirm", "runConfirm('archive')" in APP and "runConfirm('delete')" in APP)
check("Ctrl+F abre a busca", "event.key === 'f'" in APP and "openFind()" in APP)
check("atalho ? abre ajuda", "event.key === '?'" in APP and "openSettings('atalhos')" in APP)
check("arrastar/soltar anexa", "threadBox.addEventListener('drop'" in APP and "attachLocalFiles(files)" in APP)
check("colar anexa", "addEventListener('paste'" in APP and "attachLocalFiles(files)" in APP)
check("contador de novas mensagens", "MutationObserver" in APP and "newSinceScroll" in APP)
check("histórico de prompts", "ufvai_prompt_history" in APP and "ArrowUp" in APP)
check("aviso de contexto em 80%", "pct >= 80" in APP and "maybeWarnContext()" in APP)
check("focus trap nos modais", "prende o foco no modal visível" in APP)

# ── i18n: chaves nos 5 idiomas ────────────────────────────────────────
needed = ["bulk.select", "bulk.all", "bulk.archive", "bulk.delete", "bulk.cancel",
          "bulk.title", "bulk.confirm", "bulk.done", "find.placeholder",
          "ctx.warning", "ctx.compact"]
locales = I18N.get("locales", {})
check("5 idiomas", set(locales) == {"pt-BR", "en", "es", "fr", "zh"})
for loc in locales:
    faltando = [k for k in needed if k not in locales[loc]]
    check(f"{loc}: todas as chaves novas", not faltando)

print(f"\n{ok}/{total} verificações passaram")
sys.exit(0 if ok == total else 1)
