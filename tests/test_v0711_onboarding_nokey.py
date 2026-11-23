#!/usr/bin/env python3
"""Testes do onboarding 'não adicionar chave' (web46)."""
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pesquisai import onboarding as ob  # noqa: E402

ok = total = 0
def check(name, cond):
    global ok, total
    total += 1
    print(("OK  " if cond else "FAIL") + "  " + name)
    if cond: ok += 1


def main():
    check("sem chave -> precisa onboarding", ob.needs_onboarding({}) is True)
    check("skip meta -> nao precisa", ob.needs_onboarding({ob.SKIP_KEY_META: "1"}) is False)
    check("skip_key_selected True", ob.skip_key_selected({ob.SKIP_KEY_META: "1"}) is True)
    check("skip_key_selected False", ob.skip_key_selected({}) is False)
    check("store_keys ignora skip", "google" in ob.store_keys({ob.SKIP_KEY_META: "1", "google": "K"})
          and ob.SKIP_KEY_META not in ob.store_keys({ob.SKIP_KEY_META: "1", "google": "K"}))
    check("ENV UFVAI_SKIP_ONBOARDING", _with_env())

    st = ob.onboarding_state({ob.SKIP_KEY_META: "1"})
    check("state.skip_key", st.get("skip_key") is True)
    check("state.needs False", st.get("needs") is False)
    fm = st.get("free_models") or {}
    check("free_models.known", fm.get("known") is True)
    check("free_models.count > 0", int(fm.get("count") or 0) > 0)

    # HTML do wrapper
    spec = importlib.util.spec_from_file_location(
        "wrap", str(ROOT / "pesquisai" / "launch_app_responsive_v041.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    html = mod.create_wrapper_html("http://t", "http://d")
    for needle in ("id=\"ob-nokey\"", "ob-step3", "ob-nokey-confirm",
                   "/api/onboarding/skip", "modelos gratuitos, se disponíveis no momento",
                   "var STEPS = [\"ob-step0\", \"ob-step1\", \"ob-step2\", \"ob-step3\"]"):
        check("HTML: " + needle[:32], needle in html)

    print(f"\nRESULTADO: {ok}/{total}")
    return 0 if ok == total else 1


def _with_env():
    old = os.environ.get("UFVAI_SKIP_ONBOARDING")
    os.environ["UFVAI_SKIP_ONBOARDING"] = "1"
    try:
        return ob.needs_onboarding({}) is False
    finally:
        if old is None: os.environ.pop("UFVAI_SKIP_ONBOARDING", None)
        else: os.environ["UFVAI_SKIP_ONBOARDING"] = old


if __name__ == "__main__":
    raise SystemExit(main())
