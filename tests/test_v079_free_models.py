"""tests/test_v079_free_models.py — v0.7.9: gratuitos, modelo padrão e instruções de chave."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pesquisai import free_models as fm  # noqa: E402


def test_is_free_model_aceita_openrouter_free_e_nvidia():
    assert fm.is_free_model("openrouter/free")
    assert fm.is_free_model("openrouter/nvidia/nemotron-3.5-lightning:free")
    assert fm.is_free_model("nvidia/nvidia/nemotron-3.5-lightning-30b-a3b")


def test_is_free_model_rejeita_pagos_e_vazios():
    assert not fm.is_free_model("openrouter/anthropic/claude-opus-5")  # pago
    assert not fm.is_free_model("opencode-go/kimi-k3")                 # OpenCode Go é pago
    assert not fm.is_free_model("opencode/crouton-alpha-free")         # Zen fora do escopo do seletor
    assert not fm.is_free_model("")
    assert not fm.is_free_model("nvidia/")


def test_filter_free_models_dedup_ordena_e_marca_provedor():
    saida = [
        "google/gemini-2.5-flash",
        "openrouter/google/gemma-4-31b-it:free",
        "openrouter/free",
        "openrouter/free",            # duplicado
        "nvidia/nvidia/nemotron-3.5-lightning-30b-a3b",
        "opencode-go/kimi-k3",        # pago
        "   ",
        "linha com espaço:free",      # lixo
    ]
    itens = fm.filter_free_models(saida)
    assert [i["provider"] for i in itens] == ["nvidia", "openrouter", "openrouter"]
    assert {i["id"] for i in itens} == {
        "nvidia/nvidia/nemotron-3.5-lightning-30b-a3b",
        "openrouter/free",
        "openrouter/google/gemma-4-31b-it:free",
    }


def test_merge_default_model_preserva_config_e_define_model():
    antes = {"$schema": "x", "default_agent": "UFVAI", "plugins": ["p"]}
    depois = fm.merge_default_model(antes, "openrouter/free")
    assert depois["model"] == "openrouter/free"
    assert depois["default_agent"] == "UFVAI"
    assert depois["plugins"] == ["p"]
    assert "model" not in antes  # não muta o original


def test_merge_default_model_recusa_modelo_pago():
    with pytest.raises(ValueError):
        fm.merge_default_model({}, "opencode-go/kimi-k3")


def test_links_de_chave_e_pagamento():
    assert fm.KEY_LINKS["openrouter"] == "https://openrouter.ai/keys"
    assert fm.KEY_LINKS["nvidia"] == "https://build.nvidia.com/"
    assert fm.KEY_LINKS["opencode_go"] == "https://opencode.ai/go"
    assert fm.CHAVES_DOC_URL.endswith("/docs/CHAVES_API.md")
