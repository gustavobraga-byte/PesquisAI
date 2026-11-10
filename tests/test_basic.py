"""Testes básicos de constantes e utilidades do motor.

Atualizado na v0.7.9: o arquivo antigo ainda esperava a API da v0.6.0
(`WEBCLI_PORT`, `agent/` no singular, VERSION == "0.6.0", `is_colab` em
`constants`) e quebrava a coleta de toda a suíte. Agora valida o contrato
atual, sem números fixos.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pesquisai.constants import (
    VERSION,
    TERMINAL_PORT,
    WRAPPER_PORT,
    SKILL_REGISTRY,
    ESSENTIAL_SKILLS,
    AGENT_DIR,
    AGENT_NAME,
    BRAND,
    logger,
)
from pesquisai.__version__ import __version__
from pesquisai.opencode_utils import (
    find_opencode,
    is_opencode_v2,
    opencode_major,
    opencode_version_string,
)


def test_version():
    assert VERSION == __version__


def test_marca_e_agente():
    assert BRAND == "UFVAI"
    assert AGENT_NAME == "UFVAI"


def test_portas_do_terminal_e_do_wrapper():
    assert isinstance(TERMINAL_PORT, int) and TERMINAL_PORT > 0
    assert isinstance(WRAPPER_PORT, int) and WRAPPER_PORT > 0
    assert TERMINAL_PORT != WRAPPER_PORT


def test_agent_dir_plural():
    """O motor V2 lê os agentes de `agents/` (plural)."""
    assert AGENT_DIR.endswith("/.config/opencode/agents")


def test_skill_registry_not_empty():
    assert len(SKILL_REGISTRY) > 0


def test_essential_skills_subset():
    registry_names = {name for _, name, _ in SKILL_REGISTRY}
    assert ESSENTIAL_SKILLS.issubset(registry_names)


def test_logger_existe():
    assert logger is not None


def test_opencode_utils_tem_contrato_publico():
    assert callable(find_opencode)
    assert callable(is_opencode_v2)
    assert callable(opencode_major)
    assert callable(opencode_version_string)
