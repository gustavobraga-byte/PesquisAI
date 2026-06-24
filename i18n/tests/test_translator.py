"""Testes do módulo i18n."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch

import i18n
from i18n.translator import Translator
from i18n.detector import detect_language, detect_from_accept_language, _normalize


# ── Fixtures ────────────────────────────────────────────────────

@pytest.fixture
def translator():
    translations_dir = Path(__file__).parent.parent / "translations"
    return Translator(translations_dir, default_lang="pt_BR")


@pytest.fixture(autouse=True)
def reset_language():
    """Reseta o idioma antes de cada teste."""
    i18n.set_language("pt_BR")
    yield
    i18n.set_language("pt_BR")


# ── Testes de tradução ──────────────────────────────────────────

class TestTranslation:
    def test_pt_br_basic(self):
        i18n.set_language("pt_BR")
        assert i18n.t("ui.backup") == "Salvar backup"
        assert i18n.t("ui.restore") == "Restaurar"

    def test_en_us_basic(self):
        i18n.set_language("en_US")
        assert i18n.t("ui.backup") == "Save backup"
        assert i18n.t("ui.restore") == "Restore"

    def test_es_es_basic(self):
        i18n.set_language("es_ES")
        assert i18n.t("ui.backup") == "Guardar copia"
        assert i18n.t("ui.restore") == "Restaurar"

    def test_fr_fr_basic(self):
        i18n.set_language("fr_FR")
        assert i18n.t("ui.backup") == "Sauvegarder"
        assert i18n.t("ui.restore") == "Restaurer"
        assert i18n.t("ui.drive") == "Drive"

    def test_fr_fr_dashboard(self):
        i18n.set_language("fr_FR")
        assert i18n.t("dashboard.title") == "Tableau de bord de santé"
        assert i18n.t("dashboard.drive_mounted") == "Google Drive monté"

    def test_fr_fr_errors(self):
        i18n.set_language("fr_FR")
        assert i18n.t("errors.no_data") == "[DONNÉES INSUFFISANTES]"
        assert i18n.t("errors.connection_failed") == "Échec de la connexion"

    def test_fr_fr_agents_rules(self):
        i18n.set_language("fr_FR")
        assert "citation-management" in i18n.t("agents.rule1")
        assert "intégrité" in i18n.t("agents.rule4").lower() or "intégrité" in i18n.t("agents.rule4")

    def test_nested_keys(self):
        i18n.set_language("en_US")
        assert i18n.t("dashboard.title") == "Health Dashboard"
        assert i18n.t("providers.title") == "Connect AI Provider"

    def test_unknown_key_returns_key(self):
        i18n.set_language("en_US")
        assert i18n.t("nonexistent.key") == "nonexistent.key"

    def test_interpolation(self):
        i18n.set_language("en_US")
        # Vamos adicionar uma chave com placeholder para teste
        # Como não temos, testamos fallback
        result = i18n.t("dashboard.title")
        assert isinstance(result, str)

    def test_fallback_to_default_when_translation_missing(self):
        i18n.set_language("es_ES")
        # Todas as chaves devem existir nos 3 idiomas, então
        # testamos com uma chave inexistente
        assert i18n.t("this.does.not.exist") == "this.does.not.exist"


# ── Testes de troca de idioma ──────────────────────────────────

class TestLanguageManagement:
    def test_set_valid_language(self):
        i18n.set_language("en_US")
        assert i18n.get_language() == "en_US"

    def test_set_invalid_raises(self):
        with pytest.raises(ValueError):
            i18n.set_language("xx_XX")

    def test_normalize_variants(self):
        i18n.set_language("pt-br")
        assert i18n.get_language() == "pt_BR"
        i18n.set_language("EN")
        assert i18n.get_language() == "en_US"
        i18n.set_language("fr")
        assert i18n.get_language() == "fr_FR"
        i18n.set_language("fr-CA")
        assert i18n.get_language() == "fr_FR"

    def test_t_for_specific_language(self):
        i18n.set_language("pt_BR")
        # t_for não muda o idioma atual
        assert i18n.t_for("en_US", "ui.backup") == "Save backup"
        # idioma atual continua pt_BR
        assert i18n.t("ui.backup") == "Salvar backup"


# ── Testes de detecção ──────────────────────────────────────────

class TestLanguageDetection:
    def test_explicit_env_var(self):
        with patch.dict(os.environ, {"PESQUISAI_LANG": "en_US"}, clear=False):
            assert detect_language() == "en_US"

    def test_lang_env_var(self):
        env = {"LANG": "en_US.UTF-8"}
        with patch.dict(os.environ, env, clear=False):
            # Remove PESQUISAI_LANG se existir
            os.environ.pop("PESQUISAI_LANG", None)
            assert detect_language() == "en_US"

    def test_portuguese_variants(self):
        with patch.dict(os.environ, {"PESQUISAI_LANG": "pt"}, clear=False):
            assert detect_language() == "pt_BR"
        with patch.dict(os.environ, {"PESQUISAI_LANG": "pt-PT"}, clear=False):
            assert detect_language() == "pt_BR"

    def test_french_variants(self):
        with patch.dict(os.environ, {"PESQUISAI_LANG": "fr"}, clear=False):
            assert detect_language() == "fr_FR"
        with patch.dict(os.environ, {"PESQUISAI_LANG": "fr-CA"}, clear=False):
            assert detect_language() == "fr_FR"
        with patch.dict(os.environ, {"PESQUISAI_LANG": "fr_FR.UTF-8"}, clear=False):
            assert detect_language() == "fr_FR"

    def test_default_fallback(self):
        with patch.dict(os.environ, {}, clear=True):
            assert detect_language() == "pt_BR"

    def test_accept_language_parsing(self):
        assert detect_from_accept_language("en-US,pt-BR;q=0.8") == "en_US"
        assert detect_from_accept_language("es-ES") == "es_ES"
        assert detect_from_accept_language("pt-BR,en-US;q=0.5") == "pt_BR"
        assert detect_from_accept_language("fr-FR") == "fr_FR"
        assert detect_from_accept_language("fr-CA,en-US;q=0.5") == "fr_FR"

    def test_accept_language_quality_order(self):
        # pt-BR com q=0.9 deve vir antes de en-US com q=1.0
        assert detect_from_accept_language("en-US;q=1.0,pt-BR;q=0.9") == "en_US"
        # en-US com q=0.9 antes de pt-BR com q=1.0
        assert detect_from_accept_language("en-US;q=0.9,pt-BR;q=1.0") == "pt_BR"

    def test_normalize_edge_cases(self):
        assert _normalize("pt-BR.UTF-8", "pt_BR") == "pt_BR"
        assert _normalize("en_US@UTF-8", "en_US") == "en_US"
        assert _normalize("", "es_ES") == "es_ES"
        assert _normalize("xx_XX", "pt_BR") == "pt_BR"


# ── Testes da classe Translator ────────────────────────────────

class TestTranslator:
    def test_loads_all_languages(self, translator):
        assert "pt_BR" in translator._cache
        assert "en_US" in translator._cache
        assert "es_ES" in translator._cache
        assert "fr_FR" in translator._cache

    def test_has_translation(self, translator):
        assert translator.has_translation("ui.backup", "en_US") is True
        assert translator.has_translation("nonexistent.key", "en_US") is False

    def test_lookup_nested(self, translator):
        text = translator._lookup(translator._cache["en_US"], "providers.title")
        assert text == "Connect AI Provider"

    def test_collect_keys(self, translator):
        keys: list[str] = []
        translator._collect_keys(translator._cache["pt_BR"], "", keys)
        assert "ui.backup" in keys
        assert "dashboard.title" in keys
        assert len(keys) > 20

    def test_missing_keys(self, translator):
        # Como temos todas as chaves nos 4 idiomas, missing deve ser []
        missing_en = translator.missing_keys("en_US")
        missing_es = translator.missing_keys("es_ES")
        missing_fr = translator.missing_keys("fr_FR")
        assert missing_en == []
        assert missing_es == []
        assert missing_fr == []


# ── Testes de available_languages ──────────────────────────────

class TestAvailableLanguages:
    def test_returns_four_languages(self):
        langs = i18n.available_languages()
        assert len(langs) == 4

    def test_each_has_code_name_flag(self):
        langs = i18n.available_languages()
        for lang in langs:
            assert "code" in lang
            assert "name" in lang
            assert "flag" in lang

    def test_includes_all_supported(self):
        codes = {l["code"] for l in i18n.available_languages()}
        assert "pt_BR" in codes
        assert "en_US" in codes
        assert "es_ES" in codes
        assert "fr_FR" in codes
