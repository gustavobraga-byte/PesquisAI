"""
constants.py — Constantes e configurações centralizadas do PesquisAI.

Todas as paths, versões, listas de skills e configurações do sistema
são definidas aqui. A VERSÃO é importada de __version__.py (fonte única).
"""

import os
import logging
from typing import ClassVar

from .__version__ import (
    __version__ as VERSION,
    __author__ as AUTHOR_NAME,
    __author_email__ as AUTHOR_EMAIL,
    __institution__ as INSTITUTION,
    __registry__ as SISPPG_REGISTRY,
    __repo_url__ as REPO_URL,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("pesquisai")

# ── Google Drive ───────────────────────────────────────────
DRIVE_FOLDER: str = "PesquisAI"
MOUNT_PATH: str = "/content/drive"
DRIVE_PATH: str = os.path.join(MOUNT_PATH, "My Drive", DRIVE_FOLDER)
FALLBACK_URL: str = "https://drive.google.com/drive/my-drive"

# ── Diretórios temporários ─────────────────────────────────
WORK_DIR: str = "/tmp/pesquisai"
WRAPPER_DIR: str = "/tmp/pesquisai-wrapper"

# ── OpenCode ───────────────────────────────────────────────
SKILLS_DIR: str = os.path.expanduser("~/.agents/skills")
THEME_DIR: str = os.path.expanduser("~/.config/opencode/themes")
AGENT_DIR: str = os.path.expanduser("~/.config/opencode/agents")
OPENCODE_CFG: str = os.path.expanduser("~/.config/opencode/config.json")
TUI_JSON: str = os.path.expanduser("~/.config/opencode/tui.json")

# ── Portas ─────────────────────────────────────────────────
TERMINAL_PORT: int = 8000
WRAPPER_PORT: int = 8001

# ── Skills registradas ─────────────────────────────────────
# Formato: (repo_url, nome_destino, requerida)
SkillEntry = tuple[str, str, bool]

SKILL_REGISTRY: list[SkillEntry] = [
    ("https://github.com/gustavobraga-byte/Skill-IBGE.git", "ibge-br", True),
    ("https://github.com/gustavobraga-byte/Skill-DataSus.git", "opendatasus", True),
    ("https://github.com/gustavobraga-byte/scientific-agent-skills.git", "scientific", True),
    ("https://github.com/gustavobraga-byte/PesquisAI.git", "pesquisai", True),
    ("https://github.com/gustavobraga-byte/UFV-ABNT.git", "ufv-abnt", False),
    ("https://github.com/gustavobraga-byte/Skill_Analise_qualitativa.git", "qualitativa", False),
    ("https://github.com/gustavobraga-byte/skill_dados_brasil.git", "dados-brasil", False),
    ("https://github.com/gustavobraga-byte/skill_agrobr.git", "agrobr", False),
]

# Mapeamento de /tmp/skill_<nome> → diretório final em SKILLS_DIR
SKILL_MAPPINGS: list[tuple[str, str]] = [
    ("/tmp/skill_ibge-br", "ibge-br"),
    ("/tmp/skill_opendatasus", "opendatasus"),
    ("/tmp/skill_scientific/skills", "scientific"),
    ("/tmp/skill_ufv-abnt", "ufv-abnt"),
    ("/tmp/skill_qualitativa", "qualitativa"),
    ("/tmp/skill_dados-brasil", "dados-brasil"),
    ("/tmp/skill_agrobr", "agrobr"),
]

# Skills que o sistema considera ESSENCIAIS para funcionar
ESSENTIAL_SKILLS: set[str] = {
    name for _, name, required in SKILL_REGISTRY if required
}
