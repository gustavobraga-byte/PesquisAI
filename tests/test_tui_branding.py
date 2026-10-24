"""Testes do patch de textos da TUI (pesquisai/tui_branding.py).

Usa um "binário" sintético (arquivo temporário) que contém os literais nas duas
tabelas — UTF-8 (texto-fonte) e UTF-16LE (bytecode) — para verificar:

- igualdade de comprimento (invariante que protege o bytecode);
- patch nas duas tabelas, com tamanho preservado;
- idempotência, troca de idioma a partir do backup pristine e restauração;
- desligamento por ``UFVAI_TUI_BRANDING=0``;
- ``status()`` reportando ``branded`` mesmo existindo backup.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

# Carrega o módulo pelo caminho: o pacote `pesquisai` da raiz deste repositório
# (diretório `pesquisai/`) pode ser sombreado por `/tmp/pesquisai/__init__.py`
# dependendo da ordem de `sys.path` — o carregamento explícito evita o falso
# negativo e testa exatamente o arquivo do pacote.
_MODULE = Path(__file__).resolve().parent.parent / "pesquisai" / "tui_branding.py"
_spec = importlib.util.spec_from_file_location("ufvai_tui_branding", _MODULE)
tb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tb)


def _u16(text: str) -> bytes:
    return text.encode("utf-16-le")


def _read(path: str) -> bytes:
    with open(path, "rb") as handle:
        return handle.read()


PRISTINE = (
    b"\x00\x00header\x00"
    + b"Ask anything\x00Ask anything, / for commands, @ for context\x00"
    + b"Fix a TODO in the codebase\x00What is the tech stack of this project?\x00"
    + b"Fix broken tests\x00tail"
    + b"\x00\x00"
    # tabela UTF-16LE (é a que a TUI renderiza)
    + _u16("Run a command… \"")
    + _u16("\x00Ask anything… \"\x00")
    + b"\x00\x00footer"
)


@pytest.fixture()
def fake_binary(tmp_path):
    path = tmp_path / "opencode"
    path.write_bytes(PRISTINE)
    os.chmod(path, 0o755)
    return str(path)


def test_pares_tem_mesmo_comprimento():
    """Importar o módulo já valida; aqui a checagem é explícita."""
    for locale, pairs in tb.LOCALIZED_TEXTS.items():
        for old, new in pairs:
            assert len(old) == len(new), (locale, old, new)
    for locale, pairs in tb._TEXT_U16.items():
        for old, new in pairs:
            assert len(_u16(old)) == len(_u16(new)), (locale, old, new)


def test_aplica_nas_duas_tabelas_preservando_tamanho(fake_binary):
    assert tb.apply_branding(fake_binary, "pt-BR") == "applied"

    data = _read(fake_binary)
    assert len(data) == len(PRISTINE)  # offsets do bytecode intactos

    # UTF-16: o placeholder da nova sessão (o que a tela realmente mostra)
    assert _u16("Escreva algo… \"") in data
    assert _u16("Ask anything… \"") not in data
    # UTF-16: placeholder do modo shell
    assert _u16("Rodar comando… \"") in data

    # UTF-8: sugestões (mesmo comprimento de byte)
    assert b"Monte um plano de pesquisa" in data
    assert b"Fix a TODO in the codebase" not in data
    # dica longa: o par de 43 B vence o de 12 B (ordenação por comprimento)
    assert b"Escreva algo, / comandos, @ para o contexto" in data
    assert tb.status(fake_binary) == "branded"


def test_idempotente(fake_binary):
    assert tb.apply_branding(fake_binary, "pt-BR") == "applied"
    assert tb.apply_branding(fake_binary, "pt-BR") == "already"
    assert len(_read(fake_binary)) == len(PRISTINE)


def test_troca_de_idioma_parte_do_backup_pristine(fake_binary):
    tb.apply_branding(fake_binary, "pt-BR")
    assert tb.apply_branding(fake_binary, "es") == "applied"

    data = _read(fake_binary)
    assert _u16("Escribe algo… \"") in data
    assert _u16("Escreva algo… \"") not in data  # não acumula patches
    assert len(data) == len(PRISTINE)


def test_restaura_original(fake_binary):
    tb.apply_branding(fake_binary, "pt-BR")
    assert tb.restore(fake_binary) is True
    assert _read(fake_binary) == PRISTINE
    # backup permanece (é a base pristine para o próximo boot)
    assert tb.status(fake_binary) == "backup-only"


def test_desligado_restaura(fake_binary, monkeypatch):
    tb.apply_branding(fake_binary, "pt-BR")
    monkeypatch.setenv("UFVAI_TUI_BRANDING", "0")
    assert tb.apply_branding(fake_binary, "pt-BR") == "disabled"
    assert _read(fake_binary) == PRISTINE


def test_binario_ausente(tmp_path):
    assert tb.apply_branding(str(tmp_path / "nao-existe"), "pt-BR") == "not-found"
    assert tb.status(str(tmp_path / "nao-existe")) == "missing"
