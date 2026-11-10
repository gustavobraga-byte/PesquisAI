"""Testes v0.7.11 — Google no seletor de gratuitos + "Outro provedor" no onboarding."""
from __future__ import annotations

import pytest

from pesquisai import free_models as fm
from pesquisai import onboarding as ob


# ── Google no seletor "Modelo gratuito padrão" ───────────────

def test_google_is_free_model():
    assert fm.is_free_model("google/gemini-flash-lite-latest") is True
    assert fm.is_free_model("google/gemini-3-flash") is True
    assert fm.is_free_model("google/") is False


def test_filter_free_models_includes_google():
    lines = [
        "google/gemini-3-flash",
        "nvidia/llama-3.1-70b",
        "openrouter/free",
        "openrouter/meta-llama/llama-3:free",
        "openai/gpt-4o",          # pago, não entra
    ]
    items = fm.filter_free_models(lines)
    ids = [m["id"] for m in items]
    assert "google/gemini-3-flash" in ids
    assert "nvidia/llama-3.1-70b" in ids
    assert "openrouter/free" in ids
    assert "openai/gpt-4o" not in ids
    # Google vem primeiro na ordenação declarada
    assert ids[0].startswith("google/")


def test_merge_default_model_accepts_google():
    merged = fm.merge_default_model({"default_agent": "UFVAI"}, "google/gemini-3-flash")
    assert merged["model"] == "google/gemini-3-flash"
    assert merged["default_agent"] == "UFVAI"


def test_merge_default_model_rejects_paid():
    with pytest.raises(ValueError):
        fm.merge_default_model({}, "openai/gpt-4o")


def test_key_links_has_google():
    assert "google" in fm.KEY_LINKS
    assert "aistudio.google.com" in fm.KEY_LINKS["google"]


# ── "Outro provedor" no onboarding ───────────────────────────

def test_other_providers_are_supported():
    for pid in ("openai", "anthropic", "groq", "mistral", "deepseek",
                "together", "fireworks", "xai", "cohere"):
        assert ob.is_supported(pid), pid
        assert ob.get_provider(pid)["label"]


def test_mistral_without_prefix_is_accepted():
    ok, msg = ob.validate_key_format("mistral", "a" * 30)
    assert ok is True, msg


def test_openai_prefix_is_accepted():
    ok, msg = ob.validate_key_format("openai", "sk-" + "a" * 30)
    assert ok is True, msg


def test_sk_prefix_is_ambiguous():
    # "sk-" pode ser OpenAI ou DeepSeek: não adivinha.
    assert ob.detect_provider("sk-" + "a" * 30) == ""
    assert ob.detect_provider("sk-ant-" + "a" * 30) == "anthropic"
    assert ob.detect_provider("gsk_" + "a" * 30) == "groq"


def test_providers_public_has_main_and_other():
    items = ob.providers_public()
    main = [p for p in items if not p.get("other")]
    other = [p for p in items if p.get("other")]
    assert len(main) == 4
    assert len(other) >= 9
    assert "google" in [p["id"] for p in main]
    assert "openai" in [p["id"] for p in other]
    # "outro" não troca o modelo padrão sozinho
    assert all(p["model"] == "" for p in other)


def test_has_any_key_accepts_other_env():
    assert ob.has_any_key({}, {"OPENAI_API_KEY": "sk-" + "a" * 30}) is True
    assert ob.has_any_key({}, {"MISTRAL_API_KEY": "a" * 30}) is True


def test_default_model_for_other_is_empty():
    assert ob.default_model_for("openai") == ""
    assert ob.default_model_for("mistral") == ""
