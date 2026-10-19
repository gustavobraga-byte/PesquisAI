"""Tests for constants and opencode_utils (atualizado p/ v0.6.22).

O original era do layout v0.6.0 (WEBCLI_PORT não existe mais; agents agora
em `~/.config/opencode/agents`, plural). Importa a fonte única de versão e
os nomes atuais de `pesquisai.constants`.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pesquisai.constants import (
    VERSION, WRAPPER_PORT, TERMINAL_PORT, SKILL_REGISTRY, ESSENTIAL_SKILLS,
    AGENT_DIR,
)
from pesquisai.__version__ import __version__
from pesquisai.opencode_utils import find_opencode, opencode_version_string


def test_version_consistente():
    assert VERSION == __version__
    assert __version__ == "0.6.24"


def test_portas_wrapper_e_terminal():
    assert isinstance(WRAPPER_PORT, int) and WRAPPER_PORT > 0
    assert isinstance(TERMINAL_PORT, int) and TERMINAL_PORT > 0


def test_agent_dir_usa_agents_plural():
    """V2: agentes em agents/ (plural) — v0.6.21+."""
    assert AGENT_DIR.endswith("/.config/opencode/agents")


def test_skill_registry_not_empty():
    assert len(SKILL_REGISTRY) > 0


def test_essential_skills_subset():
    registry_names = {name for _, name, _ in SKILL_REGISTRY}
    assert ESSENTIAL_SKILLS.issubset(registry_names)


def test_find_opencode():
    result = find_opencode()
    assert isinstance(result, str) and result


def test_opencode_version_string_safe():
    v = opencode_version_string()
    assert v is None or isinstance(v, str)


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
