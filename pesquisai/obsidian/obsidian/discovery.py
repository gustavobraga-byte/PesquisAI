"""
discovery.py — Detecção automática do vault e do ambiente.

Este módulo é separado do :mod:`__init__` para evitar import circular
(``memory.py`` precisa chamar ``get_default_vault_path()`` mas
``__init__`` já importa ``memory``).

Modos de detecção (em ordem de prioridade):

1. ``PESQUISAI_OBSIDIAN_VAULT`` (variável explícita) — **validada**
2. ``<PESQUISAI_DRIVE_PATH>/vault`` (convenção PesquisAI) — **validada**
3. ``~/Obsidian/PesquisAI`` (uso local fora do Colab) — apenas aviso
4. ``None`` (módulo desativado)

REGRA DE PERSISTÊNCIA: a partir da v0.5.0, o PesquisAI **exige** que o
vault esteja no Google Drive do usuário. Caminhos fora do Drive são
**rejeitados** quando o ambiente parece ser Colab (/content existe).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


# ── Constantes ────────────────────────────────────────────────
# Caminhos considerados "no Google Drive" (FUSE mount no Colab).
DRIVE_PATH_PREFIXES: tuple[str, ...] = (
    "/content/drive/",             # Colab FUSE mount
    "/content/drive/.colab/",      # Colab alternate
    "/Volumes/GoogleDrive/",       # Google Drive File Stream (macOS)
    "/mnt/gdrive/",                # Linux google-drive-ocamlfuse
    "/mnt/google-drive/",          # Linux GNOME Online Accounts
    "G:/Meu Drive/",               # Windows Google Drive app
    "G:/My Drive/",                # Windows EN
    "G:/.shortcut-targets-by-id/", # Windows shortcuts
)


def _is_in_drive(path: str) -> bool:
    """Verifica se o caminho está dentro do Google Drive."""
    path = os.path.abspath(path)
    for prefix in DRIVE_PATH_PREFIXES:
        if path.startswith(os.path.abspath(prefix)):
            return True
    return False


def _is_in_colab() -> bool:
    """Detecta se estamos rodando no Google Colab."""
    try:
        import google.colab  # type: ignore  # noqa: F401
        return True
    except ImportError:
        return False


def _validate_drive_path(path: str) -> Optional[str]:
    """Valida que o caminho está no Drive.

    Returns:
        O caminho validado, ou ``None`` se inválido.
    """
    if _is_in_drive(path):
        return path
    # Em Colab, sempre rejeitar caminhos fora do Drive
    if _is_in_colab():
        return None
    # Fora do Colab, aceitar (uso local)
    return path


def get_default_vault_path() -> Optional[str]:
    """Detecta o caminho do vault a partir de variáveis de ambiente.

    Returns:
        O caminho do vault validado, ou ``None`` se não foi possível
        detectar ou se a validação falhou.
    """
    explicit = os.environ.get("PESQUISAI_OBSIDIAN_VAULT", "").strip()
    if explicit:
        validated = _validate_drive_path(explicit)
        if validated is None:
            import logging
            logging.getLogger("pesquisai.obsidian").warning(
                "PESQUISAI_OBSIDIAN_VAULT (%s) não está no Google Drive. "
                "No Colab, isso causaria perda de dados. Ignorando.",
                explicit,
            )
            return None
        return validated

    # Convenção: subpasta "vault" dentro da pasta PesquisAI no Drive
    drive_path = os.environ.get("PESQUISAI_DRIVE_PATH", "").strip()
    if drive_path:
        candidate = os.path.join(drive_path, "vault")
        if Path(candidate).is_dir():
            validated = _validate_drive_path(candidate)
            if validated is not None:
                return validated

    # Padrão PesquisAI: /content/drive/My Drive/PesquisAI/vault
    default_drive = "/content/drive/My Drive/PesquisAI/vault"
    if Path(default_drive).is_dir():
        return default_drive

    # Convenção desktop: ~/Obsidian/PesquisAI (uso local sem Colab)
    if not _is_in_colab():
        home_obsidian = Path.home() / "Obsidian" / "PesquisAI"
        if home_obsidian.is_dir():
            return str(home_obsidian)

    return None


def is_available() -> bool:
    """Retorna True se o módulo pode ser usado (variável + pasta + Drive).

    Uso::

        from pesquisai.obsidian import is_available
        if is_available():
            ... # usar a memória
    """
    path = get_default_vault_path()
    if path is None:
        return False
    if not Path(path).is_dir():
        return False
    return True


def ensure_drive_path(path: Optional[str] = None) -> str:
    """Garante que o vault está no Drive, criando-o se necessário.

    Args:
        path: caminho desejado. Se None, usa o padrão do Drive.

    Returns:
        O caminho do vault (garantido estar no Drive).

    Raises:
        RuntimeError: se o caminho não pode ser colocado no Drive.
    """
    target = path or "/content/drive/My Drive/PesquisAI/vault"
    if not _is_in_drive(target):
        raise RuntimeError(
            f"O caminho '{target}' NÃO está no Google Drive. "
            "Configure PESQUISAI_OBSIDIAN_VAULT para um caminho "
            "dentro de /content/drive/ (no Colab) ou faça o mount "
            "do Google Drive antes de usar o PesquisAI."
        )
    Path(target).mkdir(parents=True, exist_ok=True)
    return target


def _find_template(name: str) -> str:
    """Encontra um template oficial pelo nome (sem extensão).

    Ordem de busca:
    1. Skill instalada em ``~/.agents/skills/obsidian-memory/templates/``
    2. Skill em ``skills/obsidian-memory/templates/`` (dev local)
    3. Templates embutidos em ``builtin_templates.py`` (fallback)

    Args:
        name: nome do template (ex.: ``"daily-note"`` ou ``"daily"``).

    Returns:
        O conteúdo do template.

    Raises:
        FileNotFoundError: se o template não existe em nenhuma fonte.
    """
    import importlib.resources as resources
    from pathlib import Path
    import os

    candidates: list[str] = [name, f"{name}.md", f"{name}-note", f"{name}-note.md"]

    # 1. Skill instalada (~/.agents/skills/obsidian-memory/templates/)
    skill_templates_dir = Path.home() / ".agents" / "skills" / "obsidian-memory" / "templates"
    if skill_templates_dir.is_dir():
        for cand in candidates:
            p = skill_templates_dir / cand if cand.endswith(".md") else skill_templates_dir / f"{cand}.md"
            if p.is_file():
                return p.read_text(encoding="utf-8")

    # 2. Skill em dev local (skills/obsidian-memory/templates/)
    here = Path(__file__).resolve().parent
    dev_dir = here.parent.parent / "skills" / "obsidian-memory" / "templates"
    if dev_dir.is_dir():
        for cand in candidates:
            p = dev_dir / cand if cand.endswith(".md") else dev_dir / f"{cand}.md"
            if p.is_file():
                return p.read_text(encoding="utf-8")

    # 3. Fallback: templates embutidos
    from .builtin_templates import BUILTIN_TEMPLATES
    for cand in candidates:
        key = cand.replace(".md", "")
        if key in BUILTIN_TEMPLATES:
            return BUILTIN_TEMPLATES[key]

    raise FileNotFoundError(
        f"Template '{name}' não encontrado. Procurado em: "
        f"{skill_templates_dir}, {dev_dir}, builtin_templates"
    )
