"""
translator.py — Mecanismo de tradução baseado em JSON.

Carrega arquivos de tradução de `translations/<lang>.json` e expõe
a função `translate(key, lang)` com fallback em pt_BR.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


SUPPORTED_LANGUAGES: list[str] = ["pt_BR", "en_US", "es_ES", "fr_FR"]


class Translator:
    """Carregador e resolvedor de traduções."""

    def __init__(self, translations_dir: Path, default_lang: str = "pt_BR") -> None:
        self.translations_dir = Path(translations_dir)
        self.default_lang = default_lang
        self._cache: dict[str, dict] = {}
        self._load_all()

    def _load_all(self) -> None:
        """Carrega todos os arquivos de tradução."""
        for lang in SUPPORTED_LANGUAGES:
            path = self.translations_dir / f"{lang}.json"
            if path.exists():
                try:
                    with open(path, encoding="utf-8") as f:
                        self._cache[lang] = json.load(f)
                except (json.JSONDecodeError, OSError):
                    self._cache[lang] = {}
            else:
                self._cache[lang] = {}

    def translate(self, key: str, lang: str, **kwargs) -> str:
        """Resolve uma chave no idioma, com fallback para pt_BR.

        Args:
            key: Chave em notação de ponto (ex: "ui.backup").
            lang: Código do idioma (pt_BR, en_US, es_ES).
            **kwargs: Variáveis de interpolação (ex: nome="Maria").

        Returns:
            String traduzida, ou a chave se não houver tradução.
        """
        translations = self._cache.get(lang, {})
        text = self._lookup(translations, key)

        # Fallback para o idioma padrão
        if text is None and lang != self.default_lang:
            default_translations = self._cache.get(self.default_lang, {})
            text = self._lookup(default_translations, key)

        # Se nem no padrão existir, retorna a própria chave
        if text is None:
            return key

        # Interpolação de variáveis
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, IndexError):
                # Se faltar variável, retorna o template original
                pass
        return text

    def _lookup(self, translations: dict, key: str) -> Optional[str]:
        """Busca uma chave em notação de ponto."""
        parts = key.split(".")
        current: dict = translations
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current if isinstance(current, str) else None

    def has_translation(self, key: str, lang: str) -> bool:
        """Verifica se existe tradução para uma chave em um idioma."""
        return self._lookup(self._cache.get(lang, {}), key) is not None

    def missing_keys(self, lang: str) -> list[str]:
        """Retorna chaves presentes em pt_BR mas ausentes no idioma."""
        if lang == self.default_lang:
            return []
        default = self._cache.get(self.default_lang, {})
        target = self._cache.get(lang, {})
        result: list[str] = []
        self._collect_keys(default, "", result)
        missing = []
        for key in result:
            if self._lookup(target, key) is None:
                missing.append(key)
        return missing

    def _collect_keys(self, d: dict, prefix: str, result: list[str]) -> None:
        """Coleta todas as chaves de um dict aninhado em notação de ponto."""
        for k, v in d.items():
            new_key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                self._collect_keys(v, new_key, result)
            elif isinstance(v, str):
                result.append(new_key)
