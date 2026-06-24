"""
detector.py — Detecção automática de idioma.

Prioridade de detecção:
  1. Variável de ambiente PESQUISAI_LANG
  2. Variável de ambiente LANG
  3. Header HTTP Accept-Language (se passado)
  4. Fallback: idioma padrão
"""

from __future__ import annotations

import os
import re
from typing import Optional


def detect_language(default: str = "pt_BR") -> str:
    """Detecta o idioma preferido do ambiente.

    Ordem de prioridade:
      1. PESQUISAI_LANG
      2. LANG / LC_ALL
      3. Fallback (default)

    Args:
        default: Idioma padrão se nenhum for detectado.

    Returns:
        Código de idioma normalizado (pt_BR, en_US, es_ES).
    """
    # 1. Variável explícita do PesquisAI
    env_lang = os.environ.get("PESQUISAI_LANG", "").strip()
    if env_lang:
        return _normalize(env_lang, default)

    # 2. Variáveis de sistema
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.environ.get(var, "").strip()
        if val and val != "C" and val != "POSIX":
            return _normalize(val, default)

    return default


def detect_from_accept_language(header: str, default: str = "pt_BR") -> str:
    """Detecta idioma a partir de um cabeçalho HTTP Accept-Language.

    Args:
        header: Valor do cabeçalho (ex: "pt-BR,en-US;q=0.9,es;q=0.8").
        default: Idioma padrão se nenhum for detectado.

    Returns:
        Código de idioma normalizado.
    """
    if not header:
        return default

    # Parse: "pt-BR,en-US;q=0.9"
    candidates: list[tuple[str, float]] = []
    for part in header.split(","):
        part = part.strip()
        if not part:
            continue
        if ";q=" in part:
            tag, q_str = part.split(";q=", 1)
            try:
                q = float(q_str)
            except ValueError:
                q = 1.0
        else:
            tag = part
            q = 1.0
        candidates.append((tag.strip(), q))

    # Ordena por qualidade
    candidates.sort(key=lambda x: -x[1])

    for tag, _ in candidates:
        norm = _normalize(tag, "")
        if norm:
            return norm
    return default


def _normalize(lang: str, default: str) -> str:
    """Normaliza código de idioma para o formato canônico."""
    if not lang:
        return default
    lang = lang.strip().replace("-", "_")
    # Remove modificadores (ex: pt_BR.UTF-8 → pt_BR)
    if "." in lang:
        lang = lang.split(".", 1)[0]
    if "@" in lang:
        lang = lang.split("@", 1)[0]
    # Mapeamento
    if lang.lower().startswith("pt"):
        return "pt_BR"
    if lang.lower().startswith("en"):
        return "en_US"
    if lang.lower().startswith("es"):
        return "es_ES"
    if lang.lower().startswith("fr"):
        return "fr_FR"
    if lang in ("pt_BR", "en_US", "es_ES", "fr_FR"):
        return lang
    return default
