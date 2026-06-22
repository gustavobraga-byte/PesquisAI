"""Testes para constants.py — versão, paths, e registro de skills."""

import os
import sys

# Garantir que o diretório raiz está no path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pesquisai.constants import (
    VERSION,
    AUTHOR_NAME,
    AUTHOR_EMAIL,
    INSTITUTION,
    REPO_URL,
    DRIVE_FOLDER,
    SKILL_REGISTRY,
    SKILL_MAPPINGS,
    ESSENTIAL_SKILLS,
    TERMINAL_PORT,
    WRAPPER_PORT,
)


class TestConstants:
    """Suite de testes para constantes do PesquisAI."""

    def test_version_consistency(self):
        """Versão deve ser string não vazia e seguir semver."""
        assert isinstance(VERSION, str)
        assert len(VERSION) > 0
        parts = VERSION.split(".")
        assert len(parts) in (2, 3), "Versão deve seguir formato X.Y ou X.Y.Z"

    def test_author_info(self):
        """Informações do autor devem estar preenchidas."""
        assert AUTHOR_NAME
        assert "@" in AUTHOR_EMAIL
        assert INSTITUTION

    def test_repo_url(self):
        """URL do repositório deve ser válida."""
        assert REPO_URL.startswith("https://")
        assert "github.com" in REPO_URL

    def test_drive_folder(self):
        """Nome da pasta no Drive deve ser definido."""
        assert isinstance(DRIVE_FOLDER, str)
        assert len(DRIVE_FOLDER) > 0

    def test_skill_registry_not_empty(self):
        """Registro de skills não pode estar vazio."""
        assert len(SKILL_REGISTRY) > 0

    def test_skill_registry_format(self):
        """Cada entrada deve ser (url, nome, requerida)."""
        for entry in SKILL_REGISTRY:
            assert len(entry) == 3, f"Entrada inválida: {entry}"
            url, name, required = entry
            assert url.startswith("http"), f"URL inválida para skill {name}"
            assert isinstance(name, str) and len(name) > 0
            assert isinstance(required, bool)

    def test_skill_mappings_consistency(self):
        """SKILL_MAPPINGS deve conter skills conhecidas."""
        known_names = {name for _, name, _ in SKILL_REGISTRY}
        for src, dest in SKILL_MAPPINGS:
            assert dest in known_names or dest == "pesquisai", (
                f"Mapping para skill desconhecida: {dest}"
            )

    def test_essential_skills_subset(self):
        """ESSENTIAL_SKILLS deve ser subconjunto das skills registradas."""
        all_names = {name for _, name, _ in SKILL_REGISTRY}
        for sk in ESSENTIAL_SKILLS:
            assert sk in all_names, f"Skill essencial '{sk}' não está no registro"

    def test_essential_skills_required_flag(self):
        """Skills em ESSENTIAL_SKILLS devem ter required=True."""
        required_names = {name for _, name, req in SKILL_REGISTRY if req}
        assert ESSENTIAL_SKILLS == required_names, (
            "ESSENTIAL_SKILLS deve corresponder às skills com required=True"
        )

    def test_ports_range(self):
        """Portas devem estar na faixa válida (1024-65535)."""
        for port in [TERMINAL_PORT, WRAPPER_PORT]:
            assert 1024 <= port <= 65535, f"Porta inválida: {port}"
        assert TERMINAL_PORT != WRAPPER_PORT, "Portas não podem ser iguais"


class TestVersionFile:
    """A versão em constants.py deve estar sincronizada com pyproject.toml."""

    def test_version_matches_pyproject(self):
        """Verifica que constants.VERSION == pyproject.toml version."""
        import tomllib

        pyproject_path = os.path.join(os.path.dirname(__file__), "..", "pyproject.toml")
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        pyproject_version = data["project"]["version"]
        assert VERSION == pyproject_version, (
            f"constants.VERSION ({VERSION}) != pyproject.toml ({pyproject_version})"
        )
