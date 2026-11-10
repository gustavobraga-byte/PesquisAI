"""Testes do UFVAI Retry (v0.7.10) — plugin de retry para cota/429."""

from __future__ import annotations

import json
import pathlib

from pesquisai import opencode_config as oc
from pesquisai import retry_plugin as rp


def test_plugin_fonte_tem_o_hook_e_a_janela_de_62s():
    src = pathlib.Path(rp.PLUGIN_SRC_DIR)
    js = (src / "index.js").read_text(encoding="utf-8")
    assert 'ctx.session.hook("retry"' in js
    assert "429" in js and "503" in js
    assert "62_000" in js
    assert "switchModel" in js and "switchAfter" in js
    assert "google/gemini-3.1-flash-lite" in js
    assert (src / "package.json").is_file()
    assert json.loads((src / "package.json").read_text(encoding="utf-8"))["type"] == "module"


def test_install_copia_e_registra_sem_duplicar(tmp_path):
    cfg = tmp_path / "opencode.json"
    cfg.write_text(json.dumps({"model": "x", "plugins": ["/a"]}), encoding="utf-8")
    dest = tmp_path / "plugins" / "ufvai-retry"

    first = rp.ensure_retry_plugin(cfg_path=str(cfg), dest=str(dest))
    assert first["ok"] is True
    assert (dest / "index.js").is_file()

    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert data["plugins"] == ["/a", str(dest)]
    assert data["model"] == "x"  # preserva o resto

    second = rp.ensure_retry_plugin(cfg_path=str(cfg), dest=str(dest))
    assert second["written"] == []  # idempotente
    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert data["plugins"].count(str(dest)) == 1


def test_merge_plugin_preserva_configuracao_do_usuario():
    cfg = {"plugins": ["/a"], "agents": {"UFVAI": {"model": "m"}}, "permissions": []}
    out = oc.merge_plugin(cfg, "/b")
    assert out["plugins"] == ["/a", "/b"]
    assert out["agents"] == cfg["agents"]
    assert out["permissions"] == cfg["permissions"]
    assert cfg["plugins"] == ["/a"]  # não muta


def test_config_ilegivel_nao_e_sobrescrito(tmp_path):
    cfg = tmp_path / "opencode.json"
    cfg.write_text("{ isto não é json", encoding="utf-8")
    before = cfg.read_text(encoding="utf-8")
    r = rp.ensure_retry_plugin(cfg_path=str(cfg), dest=str(tmp_path / "p"))
    assert r["ok"] is False
    assert cfg.read_text(encoding="utf-8") == before


def test_fallback_apos_5_tentativas(tmp_path):
    """Executa o plugin de verdade no Node: 5ª falha → troca para o 3.1."""
    import shutil
    import subprocess

    node = shutil.which("node")
    if not node:
        import pytest
        pytest.skip("node indisponível")

    script = tmp_path / "t.mjs"
    plugin = pathlib.Path(rp.PLUGIN_SRC_DIR) / "index.js"
    script.write_text(
        f"""
import plugin from {plugin.as_uri()!r};
let hook;
const calls = [];
const ctx = {{
  options: {{}},
  session: {{
    hook: async (_name, cb) => {{ hook = cb; }},
    switchModel: async (arg) => {{ calls.push(arg); }},
  }},
}};
await plugin.setup(ctx);
const base = {{
  sessionID: "s1",
  model: {{ providerID: "google", id: "gemini-flash-lite-latest" }},
  error: {{ status: 429, message: "quota exceeded" }},
}};
const a = {{ ...base, attempt: 2, decision: {{}} }};
await hook(a);
const b = {{ ...base, attempt: 5, decision: {{}} }};
await hook(b);
const c = {{ ...base, attempt: 6, model: {{ providerID: "google", id: "gemini-3.1-flash-lite" }}, decision: {{}} }};
await hook(c);
const d = {{ ...base, attempt: 2, error: {{ status: 429, message: "Too many requests" }}, decision: {{}} }};
await hook(d);
const e = {{ ...base, attempt: 2, error: {{ status: 503, message: "Service overloaded" }}, decision: {{}} }};
await hook(e);
const f = {{ ...base, attempt: 2, error: {{ status: 503, message: "This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later." }}, decision: {{}} }};
await hook(f);
console.log(JSON.stringify({{
  calls,
  a: a.decision,
  b: b.decision,
  c: c.decision,
  d: d.decision,
  e: e.decision,
  f: f.decision,
}}));
""",
        encoding="utf-8",
    )
    out = subprocess.run(
        [node, str(script)], capture_output=True, text=True, timeout=30, check=True
    )
    import json as _json

    data = _json.loads(out.stdout)
    assert data["a"]["retry"] is True and data["a"]["delay"] >= 5000   # espera, sem trocar
    assert data["calls"] == [{"sessionID": "s1", "model": {"providerID": "google", "id": "gemini-3.1-flash-lite"}}]
    assert data["b"]["retry"] is True and data["b"]["delay"] == 1500    # 5ª falha → fallback
    assert data["c"]["retry"] is True and data["c"]["delay"] >= 5000    # já no fallback: espera normal
    assert data["d"] == {}                                              # 429 genérico: motor decide
    assert data["e"] == {"retry": True, "delay": 5000}                  # overload: espera curta
    assert data["f"] == {"retry": True, "delay": 5000}                  # "high demand": 5 s
