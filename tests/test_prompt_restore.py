# tests/test_prompt_restore.py — v0.6.24 (ajuste 18/10/2026, SEM bump)
"""Garante que NÃO se faz patch no binário e que patches antigos são revertidos.

Decisão do autor (18/10/2026): a tradução da TUI é responsabilidade exclusiva
do plugin ``ufvai-pt``; nada de substituir bytes no binário do motor (frágil em
atualização — o rename de `commands`, por exemplo, quebrou o SQLite:
`table project has no column named comandos`).

Estes testes travam:
- o módulo ``tui_prompt`` NÃO expõe mais função de patch;
- ``restore_if_needed`` restaura ``<binário>.orig-ufvai`` e remove o backup;
- sem backup, nada acontece (fail-open).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pesquisai import tui_prompt  # noqa: E402


def test_modulo_nao_expoe_patch():
    for proibido in (
        "patch_prompt_texts",
        "PROMPT_TEXTS",
        "FOOTER_TEXTS",
        "fields_for",
        "fit",
        "is_patched",
    ):
        assert not hasattr(tui_prompt, proibido), f"tui_prompt ainda expõe {proibido}"


def test_restore_sem_backup_nao_faz_nada(tmp_path):
    alvo = tmp_path / "opencode"
    alvo.write_bytes(b"binario-atual")
    assert tui_prompt.restore_if_needed(str(alvo)) == "clean"
    assert alvo.read_bytes() == b"binario-atual"
    assert tui_prompt.restore_backup(str(alvo)) is False


def test_restore_reverte_e_remove_backup(tmp_path):
    alvo = tmp_path / "opencode"
    alvo.write_bytes(b"binario-modificado-pela-v0-6-24")
    backup = tmp_path / "opencode.orig-ufvai"
    backup.write_bytes(b"binario-original")

    assert tui_prompt.restore_if_needed(str(alvo)) == "restored"
    assert alvo.read_bytes() == b"binario-original"
    assert not backup.exists()
    # idempotente: segunda chamada não faz nada
    assert tui_prompt.restore_if_needed(str(alvo)) == "clean"


def test_restore_falha_em_backup_ilegivel(tmp_path, monkeypatch):
    alvo = tmp_path / "opencode"
    alvo.write_bytes(b"atual")
    (tmp_path / "opencode.orig-ufvai").write_bytes(b"original")

    def _boom(*_a, **_k):
        raise OSError("sem espaço")

    monkeypatch.setattr(tui_prompt.shutil, "copyfile", _boom)
    assert tui_prompt.restore_if_needed(str(alvo)) == "failed"
    assert alvo.read_bytes() == b"atual"
