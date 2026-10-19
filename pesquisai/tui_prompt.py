"""
tui_prompt.py — REVERSÃO de patches antigos no binário do OpenCode (v0.6.24).

⚠️ Decisão de 18/10/2026 (autor): **não se faz mais patch no binário do
motor**. A v0.6.24 chegou a traduzir textos internos por substituição de
bytes na tabela de strings internada (frases de exemplo, prefixos do prompt,
rótulo `agents` do rodapé). Isso era eficaz, mas frágil diante de atualização
do OpenCode:

- o binário é `@bun @bytecode`; o patch depende de o literal existir, na mesma
  codificação e com o mesmo comprimento;
- literais são COMPARTILHADOS entre exibição e contratos internos. Renomear
  `commands`, por exemplo, quebrou o motor com
  `SQLiteError: table project has no column named comandos` (o mesmo literal
  é nome de método da API de keymap e identificador de esquema no SQLite);
- uma atualização pode mudar/remover os literais — no melhor caso o patch é
  ignorado (textos voltam ao inglês) e no pior pode tocar o lugar errado.

Por isso a tradução da TUI é responsabilidade EXCLUSIVA do plugin autoral
`ufvai-pt` (`pesquisai/tui_pt.py`), que usa a API pública de plugins. Textos
internos do binário (exemplos da tela inicial, "Ask anything…", rodapé)
permanecem no idioma original do motor.

Este módulo é mantido apenas para **migração**: se um binário já tiver sido
alterado por uma versão anterior, existe o backup `<binário>.orig-ufvai` e o
boot restaura o original (e remove o backup). Tudo fail-open.
"""

from __future__ import annotations

import os
import shutil
import tempfile

__all__ = ["BACKUP_SUFFIX", "restore_if_needed", "restore_backup"]

BACKUP_SUFFIX = ".orig-ufvai"


def restore_backup(binary: str) -> bool:
    """Restaura ``<binary>.orig-ufvai`` sobre ``binary`` (se o backup existir).

    Usa ``os.replace`` (troca atômica do diretório) em vez de sobrescrever o
    arquivo: o binário pode estar em execução e um ``open(..., "wb")`` direto
    falharia com ``Text file busy``.

    Returns:
        True se restaurou, False se não havia backup ou falhou (fail-open).
    """
    backup = binary + BACKUP_SUFFIX
    if not os.path.exists(backup):
        return False
    directory = os.path.dirname(binary) or "."
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".opencode-restore-")
        os.close(fd)
        shutil.copyfile(backup, tmp)
        os.chmod(tmp, 0o755)
        os.replace(tmp, binary)
        tmp = None
    except OSError:
        return False
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
    try:
        os.remove(backup)
    except OSError:
        pass
    return True


def restore_if_needed(binary: str) -> str:
    """Status da reversão para o log: ``restored`` / ``clean`` / ``failed``."""
    if not os.path.exists(binary + BACKUP_SUFFIX):
        return "clean"
    return "restored" if restore_backup(binary) else "failed"
