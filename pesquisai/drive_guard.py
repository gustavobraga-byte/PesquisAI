"""drive_guard.py — instalação e verificação do UFVAI Drive Guard (v0.7.7).

O Drive Guard é o plugin do motor que impede o agente de acessar "My Drive"
fora de ``My Drive/PesquisAI`` — inclusive com ``--auto``. Este módulo cuida do
lado Python:

- copia o plugin (``pesquisai/plugins/drive_guard/``) para
  ``<config>/plugins/ufvai-drive-guard/`` (``<config>`` = pasta do
  ``opencode.json``/``ufvai.json`` em uso);
- registra o plugin e as regras ``permissions`` no ``opencode.json``
  (idempotente, via :func:`pesquisai.opencode_config.merge_drive_guard`);
- expõe :func:`status` para diagnóstico.

Nenhuma função levanta exceção de propósito: o boot do UFVAI nunca pode cair
por causa da instalação do guard (mas um arquivo ilegível do usuário NUNCA é
sobrescrito — mesma política de ``opencode_config``).
"""

from __future__ import annotations

import hashlib
import logging
import os
from typing import Any

from .constants import OPENCODE_CFG
from .opencode_config import (
    DRIVE_GUARD_ALLOWED,
    DRIVE_GUARD_MOUNT,
    load_json_config,
    merge_drive_guard,
    write_json_atomic,
)

logger = logging.getLogger(__name__)

#: Pasta-fonte do plugin (dentro do pacote, vai junto na wheel).
PLUGIN_SRC_DIR: str = os.path.join(os.path.dirname(__file__), "plugins", "drive_guard")

#: Destino no perfil do usuário (a V2 carrega o diretório por caminho absoluto).
#: Derivado do ``opencode.json`` em uso — acompanha o rebrand
#: ``~/.config/ufvai`` (symlink) sem hard-code.
DEFAULT_INSTALL_DIR: str = os.path.join(
    os.path.dirname(OPENCODE_CFG), "plugins", "ufvai-drive-guard"
)

#: Arquivos copiados (todos obrigatórios para o plugin carregar).
PLUGIN_FILES: tuple[str, ...] = ("package.json", "index.js", "policy.js", "README.md")


def _digest(path: str) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def install_plugin(
    dest: str = DEFAULT_INSTALL_DIR,
    src: str = PLUGIN_SRC_DIR,
) -> list[str]:
    """Copia os arquivos do plugin para ``dest``.

    Só reescreve o que mudou (comparação por SHA-256), para não invalidar o
    cache de módulos do motor a cada boot.

    Returns:
        Lista de arquivos efetivamente gravados (vazia quando já estava igual).
    """
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


def ensure_drive_guard(
    cfg_path: str = OPENCODE_CFG,
    dest: str = DEFAULT_INSTALL_DIR,
    mount: str = DRIVE_GUARD_MOUNT,
    allowed: str = DRIVE_GUARD_ALLOWED,
) -> dict[str, Any]:
    """Instala o plugin e garante as regras no ``opencode.json``.

    Returns:
        ``{"ok": bool, "plugin_path": str, "written": [...], "config": str,
        "reason": str}``. ``ok=False`` quando o ``opencode.json`` existe mas
        não pôde ser lido/interpretado (nesse caso nada é sobrescrito).
    """
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
        logger.warning("drive-guard: falha ao copiar o plugin: %s", exc)
        result["reason"] = f"cópia do plugin falhou: {exc}"
        return result

    ok_cfg, cfg = load_json_config(cfg_path)
    if not ok_cfg:
        result["reason"] = "opencode.json ilegível — arquivo do usuário preservado"
        logger.warning("drive-guard: %s", result["reason"])
        return result

    merged = merge_drive_guard(cfg, dest, mount=mount, allowed=allowed)
    if merged != cfg:
        write_json_atomic(cfg_path, merged)
    result["ok"] = True
    return result


def status(
    cfg_path: str = OPENCODE_CFG,
    dest: str = DEFAULT_INSTALL_DIR,
) -> dict[str, Any]:
    """Diagnóstico do guard: arquivos presentes e registro no ``opencode.json``."""
    files = {name: os.path.exists(os.path.join(dest, name)) for name in PLUGIN_FILES}
    ok_cfg, cfg = load_json_config(cfg_path)
    plugins = cfg.get("plugins") if ok_cfg else None
    registered = bool(
        isinstance(plugins, list)
        and any(
            item == dest or (isinstance(item, dict) and item.get("package") == dest)
            for item in plugins
        )
    )
    rules = cfg.get("permissions") if ok_cfg else None
    deny_count = 0
    if isinstance(rules, list):
        deny_count = sum(
            1
            for rule in rules
            if isinstance(rule, dict)
            and rule.get("effect") == "deny"
            and str(rule.get("resource", "")).startswith(DRIVE_GUARD_MOUNT)
        )
    return {
        "installed": all(files.values()),
        "files": files,
        "registered": registered,
        "deny_rules": deny_count,
        "config_readable": ok_cfg,
        "plugin_path": dest,
    }
