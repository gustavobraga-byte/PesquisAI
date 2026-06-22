"""
__version__.py — Versão única e centralizada do PesquisAI.

ATENÇÃO: Este é o ÚNICO arquivo onde a versão deve ser alterada.
Todos os outros arquivos importam daqui. pyproject.toml deve ser
atualizado manualmente para refletir o mesmo valor.
"""

# ── Versão semântica (SemVer) ────────────────────────────────
# Formato: MAJOR.MINOR.PATCH
#   MAJOR: mudanças incompatíveis na arquitetura/API
#   MINOR: novas funcionalidades compatíveis
#   PATCH: correções de bugs e segurança
__version__: str = "0.2.3"

# ── Metadados do release ─────────────────────────────────────
__release_date__: str = "2026-06-18"
__codename__: str = "Backup Integrity Fix"

# ── Identidade do projeto ────────────────────────────────────
__author__: str = "Gustavo Bastos Braga"
__author_email__: str = "gustavo.braga@ufv.br"
__institution__: str = "Universidade Federal de Viçosa (UFV)"
__registry__: str = "10356285004"
__repo_url__: str = "https://github.com/gustavobraga-byte/PesquisAI.git"
__license__: str = "MIT"


def get_version() -> str:
    """Retorna a versão formatada para exibição."""
    return f"v{__version__} ({__codename__})"


def get_version_short() -> str:
    """Retorna apenas o número da versão."""
    return __version__
