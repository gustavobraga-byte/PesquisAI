"""tests/test_v0710_onboarding.py — onboarding de primeiro uso (v0.7.10).

Cobre as funções puras de `pesquisai/onboarding.py` e o contrato mínimo da
interface/endpoints, sem subir servidor e sem tocar no Drive.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pesquisai import onboarding as ob  # noqa: E402

ROOT = Path(__file__).parent.parent
UI = (ROOT / "pesquisai" / "launch_app_responsive_v041.py").read_text(encoding="utf-8")
APP = (ROOT / "pesquisai" / "launch_app.py").read_text(encoding="utf-8")


# ── normalização e detecção ────────────────────────────────────────────────

def test_normalize_key_limpa_espacos_aspas_e_quebras():
    assert ob.normalize_key('  "AIzaSyABC"\n') == "AIzaSyABC"
    assert ob.normalize_key("\u00a0nvapi-123\u200b") == "nvapi-123"
    assert ob.normalize_key(None) == ""


def test_detect_provider_google():
    assert ob.detect_provider("AIzaSyD-1234567890abcdef") == "google"


def test_detect_provider_nvidia_e_openrouter():
    assert ob.detect_provider("nvapi-abcdefghijklmnop") == "nvidia"
    assert ob.detect_provider("sk-or-v1-abcdefghijklmnop") == "openrouter"


def test_detect_provider_ambiguo_nao_chuta():
    # `sk-` genérico pode ser OpenAI, DeepSeek ou OpenCode Go: não adivinhar.
    assert ob.detect_provider("sk-abcdefghijklmnop") == ""
    assert ob.detect_provider("") == ""


# ── validação de formato ───────────────────────────────────────────────────

def test_validate_key_format_aceita_prefixos_corretos():
    ok, msg = ob.validate_key_format("google", "AIza" + "x" * 30)
    assert ok and msg == ""
    ok, _ = ob.validate_key_format("nvidia", "nvapi-" + "x" * 30)
    assert ok
    ok, _ = ob.validate_key_format("openrouter", "sk-or-" + "x" * 30)
    assert ok


def test_validate_key_format_recusa_prefixo_errado_e_curta():
    ok, msg = ob.validate_key_format("google", "sk-or-xxxxxxxxxxxxxxxxxxxxxxxx")
    assert not ok and "AIza" in msg
    ok, msg = ob.validate_key_format("google", "AIza")
    assert not ok and "incompleta" in msg
    ok, msg = ob.validate_key_format("google", "")
    assert not ok and "Cole a chave" in msg


def test_validate_key_format_recusa_provedor_desconhecido():
    ok, _ = ob.validate_key_format("acme", "AIza" + "x" * 30)
    assert not ok


def test_mask_key_nunca_devolve_a_chave_inteira():
    key = "AIzaSyD-1234567890abcdef"
    masked = ob.mask_key(key)
    assert key not in masked
    assert masked.startswith("AIzaSy") and masked.endswith("cdef")
    assert ob.mask_key("curta") == "cur…"
    assert ob.mask_key("") == ""


# ── condição da tela ───────────────────────────────────────────────────────

def test_needs_onboarding_sem_chave():
    assert ob.needs_onboarding({}, {}) is True


def test_needs_onboarding_com_chave_no_store():
    assert ob.needs_onboarding({"google": "AIza" + "x" * 30}, {}) is False


def test_needs_onboarding_ignora_metadados_env():
    # _env_* são metadados; sozinhos não configuram provedor.
    assert ob.needs_onboarding({"_env_google": "GOOGLE_GENERATIVE_AI_API_KEY"}, {}) is True


def test_needs_onboarding_com_variavel_de_ambiente():
    env = {"GOOGLE_GENERATIVE_AI_API_KEY": "AIza" + "x" * 30}
    assert ob.needs_onboarding({}, env) is False


def test_needs_onboarding_com_provedor_fora_do_onboarding():
    # Quem já configurou Anthropic não deve ver a tela de primeiro uso.
    assert ob.needs_onboarding({}, {"ANTHROPIC_API_KEY": "sk-ant-1234567890"}) is False


def test_needs_onboarding_respeita_kill_switch(monkeypatch):
    monkeypatch.setenv("UFVAI_SKIP_ONBOARDING", "1")
    assert ob.needs_onboarding({}, {}) is False


def test_store_keys_descarta_metadados_e_vazios():
    store = {"google": "k", "_env_google": "VAR", "nvidia": "", "openrouter": "  "}
    assert ob.store_keys(store) == {"google": "k"}


# ── modelo padrão do Google ────────────────────────────────────────────────

def test_google_model_padrao_e_o_gemini_35_flash():
    assert ob.google_model() == "google/gemini-3.5-flash"


def test_google_model_respeita_override(monkeypatch):
    monkeypatch.setenv("UFVAI_GOOGLE_MODEL", "gemini-3-pro")
    assert ob.google_model() == "google/gemini-3-pro"
    monkeypatch.setenv("UFVAI_GOOGLE_MODEL", "google/gemini-x")
    assert ob.google_model() == "google/gemini-x"


def test_google_model_from_catalog_escolhe_o_primeiro_disponivel():
    linhas = ["openrouter/free", "google/gemini-3-flash", "nvidia/llama"]
    assert ob.google_model_from_catalog(linhas) == "google/gemini-3-flash"
    assert ob.google_model_from_catalog([]) == "google/gemini-3.5-flash"


def test_default_model_for():
    assert ob.default_model_for("google") == "google/gemini-3.5-flash"
    assert ob.default_model_for("openrouter") == "openrouter/free"
    assert ob.default_model_for("nvidia") == ""
    assert ob.default_model_for("desconhecido") == ""


def test_merge_model_preserva_o_resto_da_configuracao():
    antes = {"model": "x", "agent": {"UFVAI": {}}, "provider": {"a": 1}}
    depois = ob.merge_model(antes, "google/gemini-3.5-flash")
    assert depois["model"] == "google/gemini-3.5-flash"
    assert depois["agent"] == antes["agent"]
    assert depois["provider"] == antes["provider"]
    assert antes["model"] == "x"  # não muta


def test_merge_model_recusa_vazio():
    with pytest.raises(ValueError):
        ob.merge_model({}, "  ")


# ── contrato da interface e dos endpoints ──────────────────────────────────

def test_endpoints_existem_no_wrapper():
    assert '"/api/onboarding"' in APP
    assert '"/api/onboarding/key"' in APP
    assert "save_encrypted_keys(DRIVE_BACKUP_DIR" in APP
    assert "_ensure_google_default_model" in APP
    assert "_apply_opencode_env_change_async()" in APP


def test_endpoint_nao_loga_a_chave():
    trecho = APP.split('if p == "/api/onboarding/key":', 1)[1][:3000]
    assert "masked" in trecho
    # não há logger/print recebendo a variável `key`
    for linha in trecho.splitlines():
        if "logger." in linha or "print(" in linha:
            assert "key" not in linha.replace("_ok_fmt", "").replace("api_key", ""), linha


def test_ui_tem_as_tres_etapas():
    for el in ("onboard-overlay", "ob-step0", "ob-step1", "ob-step2", "ob-done"):
        assert el in UI
    assert "Para usar o UFVAI você precisa de um provedor de IA" in UI
    assert "Já tenho um provedor de IA" in UI
    assert "não sei o que é isso" in UI


def test_ui_oferece_google_nvidia_openrouter_e_pago():
    for pid in ("google", "nvidia", "openrouter", "opencode_go"):
        assert pid in UI
    assert "recomendado" in UI
    assert "PAGO" in UI or "paga" in UI or "pago" in UI


def test_ui_do_google_tem_link_e_campo_de_colar():
    assert "aistudio.google.com/api-keys" in ob.PROVIDERS["google"]["url"]
    assert "GOOGLE_GENERATIVE_AI_API_KEY" in ob.PROVIDERS["google"]["env"]
    assert "Copiar" in UI
    assert "ob-key" in UI


def test_ui_espera_termos_antes_de_aparecer():
    # a tela precisa aguardar terms-overlay e welcome-overlay
    assert "terms-overlay" in UI
    assert "welcome-overlay" in UI
    assert "ufvai_ob_skip" in UI
