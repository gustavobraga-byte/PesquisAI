"""
pesquisai.obsidian — Integração do PesquisAI com Obsidian como segundo cérebro.

Este módulo é **opcional**: o PesquisAI continua funcionando integralmente
sem ele. A integração entra em modo "passivo" (read-only) se o pacote
``pyyaml`` não estiver instalado, e em modo "desativado" se a variável de
ambiente ``PESQUISAI_OBSIDIAN_VAULT`` não estiver definida.

Modos de operação:

==================  ======================================================
Variável ausente    Módulo desativado (importar é seguro; tudo é no-op)
Pasta ausente       Módulo desativado silenciosamente
pyyaml ausente      Fallback: lê/escreve YAML manualmente (sem dependência)
Vault OK            Módulo ativo: lê no início, grava ao final
==================  ======================================================

Política de segurança:

- O agente **só escreve** em notas com ``created_by: pesquisai`` no
  frontmatter, exceto quando o usuário pedir explicitamente para criar
  uma nova nota. Notas humanas são **read-only** para o agente.
- Toda escrita é feita com ``fsync()`` e validação de integridade
  (mantendo o padrão introduzido em v0.2.3 para backups).
- Logs de gravação são registrados em ``vault/.pesquisai-audit.log``.

Camada pública (importação usual)::

    from pesquisai.obsidian import ObsidianMemory, Note, Vault

    mem = ObsidianMemory.from_env()           # detecta vault automaticamente
    if mem.enabled:
        notes = mem.search("PNAE", limit=10)  # busca textual + tag
        mem.log_session(...)                  # grava nota de sessão
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from .models import Note, NoteMetadata, SearchResult, SessionLog, TagIndex  # noqa: F401
from .vault import Vault, VaultNotFoundError, VaultPermissionError  # noqa: F401
from .discovery import (  # noqa: F401
    DRIVE_PATH_PREFIXES,
    ensure_drive_path,
    get_default_vault_path,
    is_available,
    _find_template,
)

logger = logging.getLogger("pesquisai.obsidian")

__all__ = [
    "ObsidianMemory",
    "ObsidianMemoryStatus",
    "Note",
    "NoteMetadata",
    "SearchResult",
    "SessionLog",
    "TagIndex",
    "Vault",
    "VaultNotFoundError",
    "VaultPermissionError",
    "is_available",
    "get_default_vault_path",
    "ensure_drive_path",
    "DRIVE_PATH_PREFIXES",
    "OBSIDIAN_SKILL_VERSION",
]

__version__ = "0.5.0"
OBSIDIAN_SKILL_VERSION: str = __version__

# Lazy import de memory para evitar circular import
_LAZY_MEMORY = {"loaded": False, "ObsidianMemory": None, "ObsidianMemoryStatus": None}


def _ensure_memory():
    """Carrega ``memory.py`` sob demanda."""
    if not _LAZY_MEMORY["loaded"]:
        from .memory import ObsidianMemory, ObsidianMemoryStatus
        _LAZY_MEMORY["ObsidianMemory"] = ObsidianMemory
        _LAZY_MEMORY["ObsidianMemoryStatus"] = ObsidianMemoryStatus
        _LAZY_MEMORY["loaded"] = True
    return _LAZY_MEMORY["ObsidianMemory"], _LAZY_MEMORY["ObsidianMemoryStatus"]


# Re-export lazy para compatibilidade
def __getattr__(name):
    if name in ("ObsidianMemory", "ObsidianMemoryStatus"):
        cls, status = _ensure_memory()
        return cls if name == "ObsidianMemory" else status
    raise AttributeError(f"module 'pesquisai.obsidian' has no attribute {name!r}")
