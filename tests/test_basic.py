"""Tests for constants and opencode_utils."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pesquisai.constants import (
    VERSION, WEBCLI_PORT, SKILL_REGISTRY, ESSENTIAL_SKILLS,
    AGENT_DIR, is_colab,
)
from pesquisai.opencode_utils import find_opencode, opencode_installed, get_opencode_version


def test_version():
    assert VERSION == "0.6.0"


def test_webcli_port():
    assert isinstance(WEBCLI_PORT, int)
    assert WEBCLI_PORT > 0


def test_agent_dir_is_singular():
    """opencode v0.6.0 espera agents em agent/ (singular)."""
    assert AGENT_DIR.endswith("/.config/opencode/agent")


def test_skill_registry_not_empty():
    assert len(SKILL_REGISTRY) > 0


def test_essential_skills_subset():
    registry_names = {name for _, name, _ in SKILL_REGISTRY}
    assert ESSENTIAL_SKILLS.issubset(registry_names)


def test_is_colab_returns_bool():
    assert isinstance(is_colab(), bool)


def test_find_opencode():
    result = find_opencode()
    assert result is None or isinstance(result, str)


def test_opencode_installed():
    assert isinstance(opencode_installed(), bool)


def test_get_version():
    v = get_opencode_version()
    assert v is None or isinstance(v, str)


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
