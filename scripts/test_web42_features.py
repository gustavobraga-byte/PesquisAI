#!/usr/bin/env python3
"""test_web42_features.py — robustez dos formulários da `question` (v0.7.11-web42).

Valida que a interface busca o formulário periodicamente (não depende só do
evento `form.created`), sem re-renderizar à toa e com diagnóstico no console.

Roda: python3 scripts/test_web42_features.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "pesquisai" / "webui" / "app.js").read_text(encoding="utf-8")

ok = total = 0


def check(name, cond):
    global ok, total
    total += 1
    print(("✓" if cond else "✗") + "  " + name)
    if cond:
        ok += 1


check("estado guarda os formulários", "forms: []," in APP and "state.forms = rows" in APP)
check("assinatura evita re-render", "formsSig" in APP and "if (sig === state.formsSig) return;" in APP)
check("polling de 3 s", "loadForms(); }, 3000);" in APP)
check("gatilho no run.started", "setTimeout(loadForms, 600)" in APP)
check("gatilho no tool.started (question)", "ev.name === 'question') setTimeout(loadForms, 400)" in APP)
check("log do form.created", "console.info('[ufvai] form.created'" in APP)
check("log de pendentes", "formulário(s) pendente(s)" in APP)
check("loadForms exposto", "loadForms,   // v0.7.11-web42" in APP)

print(f"\n{ok}/{total} verificações passaram")
sys.exit(0 if ok == total else 1)
