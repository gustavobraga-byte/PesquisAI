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

# ── Marca ──────────────────────────────────────────────────
BRAND: str = "UFVAI"  # marca pública (v0.6.0); engine/pacote segue "pesquisai"

# ── Google Drive ───────────────────────────────────────────
# ATENÇÃO: NÃO renomear — é a pasta de DADOS do usuário no Drive.
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
# OpenCode V2 (v0.6.21): a configuração global do motor é
# ~/.config/opencode/opencode.json (JSONC aceito). O antigo config.json NÃO é
# lido pela V2 — por isso o default_agent passa a ser gravado em opencode.json.
OPENCODE_CFG: str = os.path.expanduser("~/.config/opencode/opencode.json")
# OpenCode V2: as configurações do cliente de terminal (tema, modo, atalhos)
# vivem SOMENTE em cli.json. tui.json é formato V1 e só é lido pela V2 para
# migração quando cli.json ainda não existe. Não gravamos mais tui.json.
TUI_JSON: str = os.path.expanduser("~/.config/opencode/tui.json")
CLI_JSON: str = os.path.expanduser("~/.config/opencode/cli.json")
# Pasta global de temas (V2 lê arquivos .json daqui; formato V1 é convertido).
OPENCODE_THEME_DIR: str = os.path.expanduser("~/.config/opencode/themes")
# Credenciais do motor V2 ficam no SQLite (opencode.db). Backup e restauração
# usam `opencode auth export` / `opencode auth import` — nunca copiamos o banco.
OPENCODE_DB_PATH: str = os.path.expanduser("~/.local/share/opencode/opencode.db")
# Instalador oficial do OpenCode V2 (substitui o binário V1 no mesmo path)
OPENCODE_INSTALL_V2: str = "https://opencode.ai/v2/install"
# Versão mínima do motor exigida pelo UFVAI (V2 = OpenCode 2.x)
OPENCODE_MIN_MAJOR: int = 2
# v0.6.21 — identidade do agente. A OpenCode V2 deriva o ID do agente do NOME DO
# ARQUIVO em agents/ (é por isso que o frontmatter não leva `name`: testado em
# 13/10/2026, um `name: UFVAI` no frontmatter é IGNORADO pelo motor). O ID pedido
# pelo autor é "UFVAI" — maiúsculo, como ele quer que o agente se chame; o
# arquivo antigo "pesquisai.md" é removido na migração.
AGENT_NAME: str = "UFVAI"
AGENT_FILE: str = "UFVAI.md"
# "pesquisai.md" = identidade antiga; "ufvai.md" = variante minúscula testada
# durante a validação (o motor a exibia como "ufvai", diferente do pedido).
LEGACY_AGENT_FILES: tuple[str, ...] = ("pesquisai.md", "ufvai.md")
# O TEMA tem identidade própria, independente do agente: continua "pesquisai".
THEME_NAME: str = "pesquisai"
LEGACY_THEME_FILES: tuple[str, ...] = ("pesquisai-light.json",)

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
    ("https://github.com/gustavobraga-byte/grant-finder.git", "grant-finder", False),
    ("https://github.com/gustavobraga-byte/meta-search-br.git", "meta-search-br", False),
    ("https://github.com/gustavobraga-byte/skill-obsidian-memory.git", "obsidian-memory", False),
    ("https://github.com/gustavobraga-byte/Memorial_ufv.git", "memorial", False),
    ("https://github.com/gustavobraga-byte/BR-DWGD.git", "BR-DWGD", False),
    ("https://github.com/gustavobraga-byte/cep-ufv.git", "cep-ufv", False),
    
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
    ("/tmp/skill_grant-finder", "grant-finder"),
    ("/tmp/skill_meta-search-br", "meta-search-br"),
    ("/tmp/skill_obsidian-memory", "obsidian-memory"),
    ("/tmp/skill_memorial", "memorial"),
    ("/tmp/skill_BR-DWGD", "BR-DWGD"), 
    ("/tmp/skill_cep-ufv", "cep-ufv"),
]

# Skills que o sistema considera ESSENCIAIS para funcionar
ESSENTIAL_SKILLS: set[str] = {
    name for _, name, required in SKILL_REGISTRY if required
}

# ── Skills personalizadas do usuário (v0.6.18) ───────────────
# Pasta persistente (Drive no Colab · ~/PesquisAI no offline) onde o
# usuário coloca skills próprias. Cada subpasta deve conter um SKILL.md
# no formato OpenCode. São carregadas a cada boot pelo setup_custom_skills().
CUSTOM_SKILLS_DIRNAME: str = "skills-personalizadas"

def custom_skills_dir() -> str:
    """Retorna o caminho da pasta de skills personalizadas do usuário.

    Colab: /content/drive/My Drive/PesquisAI/backups/skills-personalizadas/
    Offline: ~/PesquisAI/backups/skills-personalizadas/
    """
    if os.path.isdir(MOUNT_PATH):
        base = DRIVE_PATH
    else:
        base = os.path.expanduser("~/PesquisAI")
    return os.path.join(base, "backups", CUSTOM_SKILLS_DIRNAME)

# ── Obsidian Second-Brain (v0.5.0+) ───────────────────────────
# REGRA: o vault DEVE ficar no Google Drive do usuário.
# Caminho padrão: /content/drive/My Drive/PesquisAI/vault/
OBSIDIAN_VAULT_ENV: str = "PESQUISAI_OBSIDIAN_VAULT"
OBSIDIAN_DEFAULT_VAULT: str = "/content/drive/My Drive/PesquisAI/vault"
OBSIDIAN_DEFAULT_SUBDIR: str = "vault"

# Caminhos reconhecidos como "Google Drive" pelo discovery
OBSIDIAN_DRIVE_PREFIXES: tuple[str, ...] = (
    "/content/drive/",
    "/content/drive/.colab/",
    "/Volumes/GoogleDrive/",
    "/mnt/gdrive/",
    "/mnt/google-drive/",
    "G:/Meu Drive/",
    "G:/My Drive/",
)

# Configurações de comportamento
OBSIDIAN_AUTO_LOG_SESSIONS: bool = True
OBSIDIAN_AUTO_DAILY: bool = True
OBSIDIAN_CONTEXT_BRIEF: bool = True
OBSIDIAN_CONTEXT_BRIEF_MAX_CHARS: int = 4000
OBSIDIAN_PROTECT_HUMAN_NOTES: bool = True
OBSIDIAN_REQUIRE_DRIVE: bool = True  # rejeita fora do Drive no Colab

# Tags oficiais da taxonomia pesquisai/*
OBSIDIAN_OFFICIAL_TAGS: frozenset[str] = frozenset({
    "pesquisai/ibge", "pesquisai/datasus", "pesquisai/agrobr",
    "pesquisai/dados-brasil", "pesquisai/capes", "pesquisai/sucupira",
    "pesquisai/daily", "pesquisai/research", "pesquisai/literature",
    "pesquisai/session", "pesquisai/methodology", "pesquisai/datasource",
    "pesquisai/hypothesis", "pesquisai/reference", "pesquisai/moc",
    "pesquisai/inbox", "pesquisai/draft", "pesquisai/review",
    "pesquisai/published", "pesquisai/archived",
})
