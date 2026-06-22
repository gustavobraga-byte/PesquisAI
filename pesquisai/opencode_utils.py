"""
opencode_utils.py — Utilitários para localizar e configurar o binário OpenCode.

Fornece funções para encontrar o executável opencode no sistema,
garantir que ele está no PATH, e construir o environment para execução.
"""

import os
import shutil
import subprocess
from typing import Optional

from .constants import logger

OPENCODE_BIN: Optional[str] = None

CANDIDATES: list[str] = [
    os.path.expanduser("~/.local/bin/opencode"),
    os.path.expanduser("~/bin/opencode"),
    "/root/.local/bin/opencode",
    "/root/bin/opencode",
    "/usr/local/bin/opencode",
    "/usr/bin/opencode",
]


def _search() -> Optional[str]:
    """Busca recursivamente o binário opencode no sistema."""
    result = subprocess.run(
        ["find", "/root", "/home", "/usr/local", "-name", "opencode", "-type", "f"],
        capture_output=True, text=True, timeout=10,
    )
    hits = [l.strip() for l in result.stdout.splitlines() if l.strip()]
    return hits[0] if hits else None


def find_opencode() -> str:
    """Localiza o binário do opencode, retornando o caminho completo.

    Ordem de busca:
    1. Cache global OPENCODE_BIN
    2. Variável de ambiente OPENCODE_BIN
    3. `which opencode`
    4. Lista de candidatos conhecidos
    5. Busca recursiva com find

    Raises:
        FileNotFoundError: se o binário não for encontrado em lugar nenhum.
    """
    global OPENCODE_BIN
    if OPENCODE_BIN:
        return OPENCODE_BIN
    if "OPENCODE_BIN" in os.environ and os.path.isfile(os.environ["OPENCODE_BIN"]):
        OPENCODE_BIN = os.environ["OPENCODE_BIN"]
        return OPENCODE_BIN
    w = shutil.which("opencode")
    if w:
        OPENCODE_BIN = w
        return OPENCODE_BIN
    found = next((p for p in CANDIDATES if os.path.isfile(p)), None)
    if found:
        OPENCODE_BIN = found
        return OPENCODE_BIN
    found = _search()
    if found:
        OPENCODE_BIN = found
        return OPENCODE_BIN
    raise FileNotFoundError(
        "opencode binary not found. Install it from https://opencode.ai"
    )


def ensure_opencode_in_path() -> None:
    """Garante que o diretório do opencode está no PATH."""
    bin_path = find_opencode()
    bin_dir = os.path.dirname(bin_path)
    if bin_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = bin_dir + ":" + os.environ["PATH"]
    os.environ["OPENCODE_BIN"] = bin_path
    logger.info("opencode encontrado: %s", bin_path)


def build_env(extra_vars: Optional[dict] = None) -> dict:
    """Constrói o dicionário de environment para executar o opencode.

    Args:
        extra_vars: Variáveis adicionais para injetar no environment.

    Returns:
        Dict com todas as variáveis de ambiente necessárias.
    """
    env: dict = {**os.environ}
    env["OPENCODE_EXPERIMENTAL_DISABLE_COPY_ON_SELECT"] = "1"
    bin_path = find_opencode()
    bin_dir = (
        os.path.dirname(bin_path)
        if os.path.isfile(bin_path)
        else os.path.expanduser("~/.local/bin")
    )
    env["PATH"] = env.get("PATH", "") + ":" + bin_dir
    if extra_vars:
        env.update(extra_vars)
    return env
