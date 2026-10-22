# pesquisai/opencode_i18n.py — v0.6.23
# -*- coding: utf-8 -*-
"""Integração de i18n do TUI do OpenCode V2 (plugin ``opencode-i18n-v2``).

O UFVAI é BR-first: o padrão é pt-BR, mas o idioma é DETECTADO na ordem:
  1. ``PESQUISAI_LOCALE`` (env) — override explícito;
  2. língua do NAVEGADOR (header ``Accept-Language`` gravado pela UI web
     via :func:`record_browser_locale`);
  3. ``LANG``/``LC_ALL`` do ambiente;
  4. fallback: ``pt-BR``.

O que este módulo faz no boot:
  - garante o plugin ``opencode-i18n-v2`` na lista ``plugins`` (feita pela
    cadeia ``merge_opencode_config`` → :func:`merge_i18n_plugin`);
  - implanta o locale ``pt-BR.json`` (empacotado em
    ``pesquisai/assets/i18n/``) em ``~/.config/opencode/i18n/locales/``;
  - escreve o índice ``~/.config/opencode/i18n/config.json``
    (lista de idiomas + padrão) respeitando o arquivo já existente;
  - grava o estado (``~/.local/state/opencode/i18n-state.json``) com
    ``enabled`` + ``locale`` detectado — quando a detecção resulta em
    inglês, a localização fica desligada (o inglês já é o original).

Toda operação é fail-open: qualquer falha não impede o boot e apenas deixa
a interface no idioma original (inglês).
"""
from __future__ import annotations

import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

__all__ = [
    "I18N_PLUGIN",
    "I18N_LOCALE",
    "SUPPORTED_LOCALES",
    "parse_accept_language",
    "record_browser_locale",
    "browser_locale",
    "detect_locale",
    "merge_i18n_plugin",
    "deploy_i18n",
    "set_i18n_state",
    "apply_i18n",
]

I18N_PLUGIN = "opencode-i18n-v2"
I18N_LOCALE = "pt-BR"
SUPPORTED_LOCALES = ["en", "pt-BR", "zh-Hans", "zh-Hant"]

# ── caminhos (mesmos usados pelo plugin: pesquisai/i18n no seu lib.ts) ──────
_HOME = Path.home()
CONFIG_ROOT = Path(os.environ.get("XDG_CONFIG_HOME", _HOME / ".config")) / "opencode"
_STATE_ROOT = Path(os.environ.get("XDG_STATE_HOME", _HOME / ".local" / "state")) / "opencode"
LOCALES_DIR = CONFIG_ROOT / "i18n" / "locales"
I18N_INDEX_PATH = CONFIG_ROOT / "i18n" / "config.json"
STATE_PATH = _STATE_ROOT / "i18n-state.json"
BROWSER_LOCALE_PATH = _STATE_ROOT / "pesquisai-browser-locale.json"
ASSET_LOCALE_PATH = Path(__file__).resolve().parent / "assets" / "i18n" / "pt-BR.json"

_ACCEPT_LANG_RE = re.compile(r"([a-zA-Z]{1,8}(?:-[a-zA-Z0-9]{1,8})*)\s*(?:;\s*q\s*=\s*([0-9.]+))?")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


# ── detecção de idioma ──────────────────────────────────────────────────────
def parse_accept_language(header: str | None) -> str | None:
    """Extrai o melhor locale suportado de um header ``Accept-Language``.

    Prioriza ``pt``/``pt-BR``; aceita ``en``; ignora demais idiomas (ainda
    não há locale empacotado para eles). Retorna ``None`` se nada casar.
    """
    if not header:
        return None
    candidates: list[tuple[float, str]] = []
    for tag, q in _ACCEPT_LANG_RE.findall(header):
        try:
            quality = float(q) if q else 1.0
        except ValueError:
            quality = 1.0
        first = tag.lower().split("-")[0]
        if first == "pt":
            # pt-BR explícito vale mais que pt genérico (desempate estável)
            bonus = 0.001 if tag.lower().startswith("pt-br") else 0.0
            candidates.append((quality + bonus, "pt-BR"))
        elif first == "en":
            candidates.append((quality, "en"))
        elif first == "zh":
            candidates.append((quality, "zh-Hans"))
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def record_browser_locale(accept_language: str | None) -> bool:
    """Grava a língua do navegador informada pela UI web (chamado no HTTP)."""
    try:
        locale = parse_accept_language(accept_language)
        _write_json(
            BROWSER_LOCALE_PATH,
            {"locale": locale, "raw": (accept_language or "")[:300], "updatedAt": _now()},
        )
        return locale is not None
    except Exception:
        return False  # nunca quebra o request por causa do i18n


def _locale_from_environment() -> str | None:
    raw = os.environ.get("PESQUISAI_LOCALE") or os.environ.get("LC_ALL") or os.environ.get("LANG") or ""
    first = raw.split(".")[0].lower()
    if first.startswith("pt"):
        return "pt-BR"
    if first.startswith("en"):
        return "en"
    if first.startswith("zh"):
        return "zh-Hans"
    return None


def detect_locale() -> str:
    """Detecta o idioma da interface (ver docstring do módulo para a ordem)."""
    override = os.environ.get("PESQUISAI_LOCALE")
    if override:
        return SUPPORTED_LOCALES[0] if override.lower().startswith("en") else I18N_LOCALE
    browser = _read_json(BROWSER_LOCALE_PATH)
    if isinstance(browser, dict) and browser.get("locale"):
        return browser["locale"]
    env = _locale_from_environment()
    if env:
        return env
    return I18N_LOCALE


# ── plugin na lista ``plugins`` ──────────────────────────────────────────────
def browser_locale() -> str | None:
    """Locale registrado a partir da língua do NAVEGADOR (``None`` se não houve).

    Diferente de :func:`detect_locale`, NÃO devolve o fallback do produto:
    serve para quem precisa saber se houve sinal real do navegador (ex.: o
    patch das frases do prompt, que deve cair no sistema quando não houve).
    """
    data = _read_json(BROWSER_LOCALE_PATH)
    locale = data.get("locale") if isinstance(data, dict) else None
    return locale if isinstance(locale, str) and locale else None


def merge_i18n_plugin(existing: dict[str, Any]) -> dict[str, Any]:
    """Garante ``plugins: [opencode-i18n-v2]`` sem sobrescrever o usuário."""
    merged = dict(existing)
    plugins = list(merged.get("plugins") or [])
    if I18N_PLUGIN not in plugins:
        plugins.append(I18N_PLUGIN)
    merged["plugins"] = plugins
    return merged


# ── implantação do locale + índice ──────────────────────────────────────────
def deploy_i18n(locale: str | None = None) -> bool:
    """Copia o locale empacotado e garante o índice de idiomas do usuário."""
    try:
        if ASSET_LOCALE_PATH.is_file():
            LOCALES_DIR.mkdir(parents=True, exist_ok=True)
            target = LOCALES_DIR / ASSET_LOCALE_PATH.name
            if not target.is_file():  # não sobrescreve ajustes do usuário
                shutil.copyfile(ASSET_LOCALE_PATH, target)
        index = _read_json(I18N_INDEX_PATH)
        if not isinstance(index, dict) or "locales" not in index:
            locales = list(SUPPORTED_LOCALES)
            if locale and locale not in locales:
                locales.insert(1, locale)
            _write_json(
                I18N_INDEX_PATH,
                {"defaultLocale": locale or I18N_LOCALE, "locales": locales},
            )
        elif locale and locale not in (index.get("locales") or []):
            index["locales"] = list(index.get("locales") or []) + [locale]
            index.setdefault("defaultLocale", locale)
            _write_json(I18N_INDEX_PATH, index)
        return True
    except Exception:
        return False


def set_i18n_state(enabled: bool | None = None, locale: str | None = None) -> bool:
    """Atualiza ``~/.local/state/opencode/i18n-state.json`` (formato do plugin)."""
    try:
        current = _read_json(STATE_PATH) if STATE_PATH.is_file() else {}
        current = current if isinstance(current, dict) else {}
        state = {
            "version": 1,
            "enabled": bool(current.get("enabled", False)) if enabled is None else bool(enabled),
            "locale": locale or current.get("locale") or I18N_LOCALE,
            "updatedAt": _now(),
        }
        _write_json(STATE_PATH, state)
        return True
    except Exception:
        return False


def apply_i18n() -> dict[str, Any]:
    """Orquestra o i18n no boot (idempotente e fail-open)."""
    locale = detect_locale()
    result = {
        "locale": locale,
        "plugin": I18N_PLUGIN in (_read_json(CONFIG_ROOT / "opencode.json") or {}).get(
            "plugins", []
        ),
        "deployed": deploy_i18n(locale),
        "state": set_i18n_state(enabled=(locale != "en"), locale=locale),
    }
    return result
