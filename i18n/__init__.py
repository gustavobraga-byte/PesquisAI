"""
i18n — Suporte multilíngue para o PesquisAI.

Idiomas suportados: pt_BR (padrão), en_US, es_ES.
Detecção automática via cabeçalho HTTP Accept-Language, variável
de ambiente LANG, ou argumento explícito.

Uso:
    from pesquisai.i18n import t, set_language, get_language

    set_language("en_US")
    print(t("ui.backup"))  # "Save backup"

    # Detecção automática
    set_language(detect_from_env())
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .translator import Translator, SUPPORTED_LANGUAGES
from .detector import detect_language, detect_from_accept_language


_DEFAULT_LANG: str = "pt_BR"
_current_lang: str = _DEFAULT_LANG
_translator: Optional[Translator] = None

# Caminho para os arquivos de tradução
TRANSLATIONS_DIR: Path = Path(__file__).parent / "translations"


def _get_translator() -> Translator:
    """Retorna o tradutor singleton."""
    global _translator
    if _translator is None:
        _translator = Translator(TRANSLATIONS_DIR, default_lang=_DEFAULT_LANG)
    return _translator


def set_language(lang: str) -> None:
    """Define o idioma atual. Aceita 'pt_BR', 'en_US', 'es_ES'."""
    global _current_lang
    if not lang:
        raise ValueError("Idioma não pode ser vazio")
    lang_norm = _normalize_lang(lang)
    # Verifica se a entrada original era suportada (em qualquer formato)
    original_normalized = lang.strip().replace("-", "_").split(".")[0].split("@")[0]
    if lang_norm not in SUPPORTED_LANGUAGES:
        raise ValueError(
            f"Idioma '{lang}' não suportado. "
            f"Idiomas disponíveis: {', '.join(SUPPORTED_LANGUAGES)}"
        )
    if not (
        original_normalized.lower().startswith(("pt", "en", "es", "fr"))
        or original_normalized in SUPPORTED_LANGUAGES
    ):
        raise ValueError(
            f"Idioma '{lang}' não suportado. "
            f"Idiomas disponíveis: {', '.join(SUPPORTED_LANGUAGES)}"
        )
    _current_lang = lang_norm


def get_language() -> str:
    """Retorna o idioma atual."""
    return _current_lang


def t(key: str, **kwargs) -> str:
    """Traduz uma chave para o idioma atual.

    Args:
        key: Chave de tradução em notação de ponto (ex: "ui.backup").
        **kwargs: Variáveis de interpolação.

    Returns:
        String traduzida, ou a própria chave se não houver tradução.
    """
    translator = _get_translator()
    return translator.translate(key, _current_lang, **kwargs)


def t_for(lang: str, key: str, **kwargs) -> str:
    """Traduz uma chave para um idioma específico (não muda o idioma atual)."""
    translator = _get_translator()
    lang = _normalize_lang(lang)
    return translator.translate(key, lang, **kwargs)


def detect() -> str:
    """Detecta o idioma preferido do ambiente (LANG, HTTP headers, fallback pt_BR)."""
    return detect_language(_DEFAULT_LANG)


def available_languages() -> list[dict[str, str]]:
    """Retorna lista de idiomas disponíveis com metadados."""
    return [
        {"code": "pt_BR", "name": "Português (Brasil)", "flag": "🇧🇷"},
        {"code": "en_US", "name": "English (United States)", "flag": "🇺🇸"},
        {"code": "es_ES", "name": "Español (España)", "flag": "🇪🇸"},
        {"code": "fr_FR", "name": "Français (France)", "flag": "🇫🇷"},
    ]


def _normalize_lang(lang: str) -> str:
    """Normaliza código de idioma para o formato canônico."""
    if not lang:
        return _DEFAULT_LANG
    lang = lang.strip().replace("-", "_")
    # pt-BR, pt_BR, pt → pt_BR
    if lang.lower().startswith("pt"):
        return "pt_BR"
    if lang.lower().startswith("en"):
        return "en_US"
    if lang.lower().startswith("es"):
        return "es_ES"
    if lang.lower().startswith("fr"):
        return "fr_FR"
    if lang in SUPPORTED_LANGUAGES:
        return lang
    return _DEFAULT_LANG


__all__ = [
    "t", "t_for", "set_language", "get_language", "detect",
    "available_languages", "SUPPORTED_LANGUAGES", "TRANSLATIONS_DIR",
    "Translator",
]
