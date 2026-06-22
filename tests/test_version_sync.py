"""Testes de sincronia de versão entre __version__.py, pyproject.toml e Dockerfile.

Garante que bumpar a versão não dessincroniza os arquivos.
"""

import os
import re
import sys
import tomllib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pesquisai.__version__ import __version__
from pesquisai.constants import VERSION

ROOT = os.path.join(os.path.dirname(__file__), "..")


class TestVersionSync:
    """Versão deve ser idêntica em todos os arquivos."""

    def test_constants_matches_version_file(self):
        """constants.VERSION deve igualar __version__.__version__."""
        assert VERSION == __version__, (
            f"constants.VERSION ({VERSION}) != __version__.__version__ ({__version__})"
        )

    def test_pyproject_matches_version_file(self):
        """pyproject.toml [project].version deve igualar __version__."""
        with open(os.path.join(ROOT, "pyproject.toml"), "rb") as f:
            data = tomllib.load(f)
        pp_version = data["project"]["version"]
        assert pp_version == __version__, (
            f"pyproject.toml ({pp_version}) != __version__.py ({__version__})"
        )

    def test_dockerfile_matches_version_file(self):
        """Dockerfile LABEL version deve igualar __version__."""
        dockerfile = os.path.join(ROOT, "Dockerfile")
        if not os.path.exists(dockerfile):
            import pytest
            pytest.skip("Dockerfile não existe")
        with open(dockerfile) as f:
            content = f.read()
        m = re.search(r'org\.opencontainers\.image\.version="([^"]+)"', content)
        assert m is not None, "LABEL version não encontrada no Dockerfile"
        docker_version = m.group(1)
        assert docker_version == __version__, (
            f"Dockerfile ({docker_version}) != __version__.py ({__version__})"
        )

    def test_version_format_semver(self):
        """Versão deve seguir semver: X.Y ou X.Y.Z."""
        parts = __version__.split(".")
        assert len(parts) in (2, 3), f"Versão deve ser X.Y ou X.Y.Z, got {__version__}"
        for p in parts:
            assert p.isdigit(), f"Parte não-numérica na versão: {p} em {__version__}"

    def test_changelog_has_current_version_entry(self):
        """CHANGELOG.md deve ter entrada para a versão atual."""
        changelog = os.path.join(ROOT, "CHANGELOG.md")
        if not os.path.exists(changelog):
            import pytest
            pytest.skip("CHANGELOG.md não existe")
        with open(changelog) as f:
            content = f.read()
        assert f"v{__version__}" in content or __version__ in content, (
            f"CHANGELOG.md não menciona versão {__version__}"
        )
