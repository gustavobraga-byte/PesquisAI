# tests/test_sem_i18n.py — v0.6.24 (ajuste 18/10/2026, SEM bump)
"""Garante a REMOÇÃO do plugin opencode-i18n da versão.

Contexto (defeito relatado pelo autor): com o plugin ``opencode-i18n-v2`` e o
plugin autoral ``ufvai-pt`` ativos, a paleta de comandos (ctrl+p) recebia DUAS
camadas de espelho para os mesmos ids — os comandos apareciam duplicados — e o
plugin de terceiros injetava entradas próprias com título em chinês
("界面语言"), além de exigir pacotes de idioma em chinês.

O que estes testes travam:
- ``strip_i18n_plugin`` remove o plugin das listas em formato string e dict,
  preservando os demais plugins do usuário;
- ``merge_opencode_config`` NUNCA volta a instalar o plugin;
- ``cleanup_i18n_leftovers`` apaga diretório/estado do plugin antigo;
- o módulo ``opencode_i18n`` não existe mais no pacote.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pesquisai.opencode_config import (  # noqa: E402
    cleanup_i18n_leftovers,
    merge_opencode_config,
    strip_i18n_plugin,
)


# ── strip_i18n_plugin ───────────────────────────────────────────────────────
def test_strip_remove_plugin_string():
    cfg = {"plugins": ["outro-plugin", "opencode-i18n-v2"]}
    out = strip_i18n_plugin(cfg)
    assert out["plugins"] == ["outro-plugin"]


def test_strip_remove_plugin_dict_e_pacote_path():
    cfg = {
        "plugins": [
            {"package": "opencode-i18n-v2", "options": {}},
            {"package": "./local"},
            "opencode-i18n",
        ]
    }
    out = strip_i18n_plugin(cfg)
    assert out["plugins"] == [{"package": "./local"}]


def test_strip_preserva_config_sem_plugins():
    assert strip_i18n_plugin({"default_agent": "UFVAI"}) == {"default_agent": "UFVAI"}


def test_strip_nao_muta_entrada():
    cfg = {"plugins": ["opencode-i18n-v2", "x"]}
    strip_i18n_plugin(cfg)
    assert cfg["plugins"] == ["opencode-i18n-v2", "x"]


def test_merge_opencode_config_nunca_reinstala_i18n():
    cfg = {
        "plugins": ["opencode-i18n-v2", {"package": "meu-plugin"}],
        "commands": {},
    }
    out = merge_opencode_config(cfg, "UFVAI")
    assert out["default_agent"] == "UFVAI"
    assert out["plugins"] == [{"package": "meu-plugin"}]
    assert all(
        not (
            (isinstance(p, str) and "opencode-i18n" in p)
            or (isinstance(p, dict) and "opencode-i18n" in str(p.get("package", "")))
        )
        for p in out["plugins"]
    )


# ── cleanup_i18n_leftovers ──────────────────────────────────────────────────
def test_cleanup_remove_diretorio_e_estado(tmp_path, monkeypatch):
    home = tmp_path / "home"
    config = home / ".config" / "opencode" / "i18n"
    state = home / ".local" / "state" / "opencode"
    config.mkdir(parents=True)
    (config / "config.json").write_text("{}", encoding="utf-8")
    state.mkdir(parents=True)
    (state / "i18n-state.json").write_text("{}", encoding="utf-8")
    (state / "pesquisai-browser-locale.json").write_text("{}", encoding="utf-8")

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(home / ".local" / "state"))

    removed = cleanup_i18n_leftovers()
    assert str(config) in removed
    assert not config.exists()
    assert not (state / "i18n-state.json").exists()
    assert not (state / "pesquisai-browser-locale.json").exists()


def test_cleanup_fail_open_sem_nada(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / ".local" / "state"))
    assert cleanup_i18n_leftovers() == []


# ── módulo removido ─────────────────────────────────────────────────────────
def test_modulo_opencode_i18n_nao_existe_mais():
    for name in list(sys.modules):
        if name.startswith("pesquisai.opencode_i18n"):
            del sys.modules[name]
    try:
        importlib.import_module("pesquisai.opencode_i18n")
    except ModuleNotFoundError:
        return
    raise AssertionError("pesquisai.opencode_i18n ainda existe no pacote")


def test_assets_i18n_removido():
    assert not (REPO_ROOT / "pesquisai" / "assets" / "i18n").exists()
