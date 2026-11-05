"""retry_plugin.py — instalação do UFVAI Retry (v0.7.10).

O plano gratuito do Google limita a cota **por minuto**. O retry padrão do
motor recomeça em segundos e bate na mesma janela; este plugin intercepta o
hook ``retry`` e espera a janela do provedor (~62 s) antes da nova tentativa.

Espelha :mod:`pesquisai.drive_guard`: copia o plugin de
``pesquisai/plugins/retry/`` para ``<config>/plugins/ufvai-retry/`` e o
registra em ``plugins`` no ``opencode.json`` — idempotente e best-effort.
Nunca levanta: o boot não pode cair por causa do plugin.
"""

from __future__ import annotations

import hashlib
import logging
import os
from typing import Any

from .constants import OPENCODE_CFG
from .opencode_config import load_json_config, merge_plugin, write_json_atomic

logger = logging.getLogger(__name__)

PLUGIN_SRC_DIR: str = os.path.join(os.path.dirname(__file__), "plugins", "retry")
DEFAULT_INSTALL_DIR: str = os.path.join(
    os.path.dirname(OPENCODE_CFG), "plugins", "ufvai-retry"
)
PLUGIN_FILES: tuple[str, ...] = ("package.json", "index.js", "README.md")


def _digest(path: str) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def install_plugin(dest: str = DEFAULT_INSTALL_DIR, src: str = PLUGIN_SRC_DIR) -> list[str]:
    """Copia os arquivos do plugin; só reescreve o que mudou."""
    if not os.path.isdir(src):
        raise FileNotFoundError(f"plugin-fonte ausente: {src}")
    os.makedirs(dest, exist_ok=True)
    written: list[str] = []
    for name in PLUGIN_FILES:
        origin = os.path.join(src, name)
        if not os.path.exists(origin):
            raise FileNotFoundError(f"arquivo do plugin ausente: {origin}")
        target = os.path.join(dest, name)
        if os.path.exists(target) and _digest(origin) == _digest(target):
            continue
        with open(origin, "rb") as fh:
            payload = fh.read()
        tmp = f"{target}.tmp"
        with open(tmp, "wb") as fh:
            fh.write(payload)
        os.replace(tmp, target)
        written.append(target)
    return written


def ensure_retry_plugin(
    cfg_path: str = OPENCODE_CFG,
    dest: str = DEFAULT_INSTALL_DIR,
) -> dict[str, Any]:
    """Instala o plugin e o registra no ``opencode.json`` (best-effort)."""
    result: dict[str, Any] = {
        "ok": False,
        "plugin_path": dest,
        "written": [],
        "config": cfg_path,
        "reason": "",
    }
    try:
        result["written"] = install_plugin(dest=dest)
    except Exception as exc:  # noqa: BLE001
        logger.warning("retry-plugin: falha ao copiar o plugin: %s", exc)
        result["reason"] = f"cópia do plugin falhou: {exc}"
        return result

    ok_cfg, cfg = load_json_config(cfg_path)
    if not ok_cfg:
        result["reason"] = "opencode.json ilegível — arquivo do usuário preservado"
        logger.warning("retry-plugin: %s", result["reason"])
        return result

    merged = merge_plugin(cfg, dest)
    if merged != cfg:
        write_json_atomic(cfg_path, merged)
    result["ok"] = True
    return result
