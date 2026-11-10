"""Testes do botão de menu iniciar (Linux .deb) e do pacote Windows.

Executar:  pytest tests/test_v0711_menu_iniciar.py -q
"""
from __future__ import annotations

import configparser
import py_compile
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGING = ROOT / "packaging"
WINDOWS = PACKAGING / "windows"

# ══════════════════════════════════════════════════════════════════════════
# 1. Menu iniciar no Linux (.deb)
# ══════════════════════════════════════════════════════════════════════════


def test_desktop_entry_existe():
    entry = PACKAGING / "ufvai.desktop"
    assert entry.is_file(), "packaging/ufvai.desktop ausente"


def test_desktop_entry_valido_e_com_acoes():
    entry = PACKAGING / "ufvai.desktop"
    cp = configparser.ConfigParser(strict=False, interpolation=None)
    cp.optionxform = str  # preserva Name[pt_BR]
    cp.read(entry, encoding="utf-8")

    assert cp["Desktop Entry"]["Type"] == "Application"
    assert cp["Desktop Entry"]["Icon"] == "ufvai"
    assert cp["Desktop Entry"]["Terminal"] == "false"
    # Clicar no menu abre a interface (modo --gui).
    assert cp["Desktop Entry"]["Exec"].strip() == "ufvai --gui"

    actions = [a.strip() for a in cp["Desktop Entry"]["Actions"].split(";") if a.strip()]
    assert actions, "nenhuma ação declarada"
    for action in actions:
        assert f"Desktop Action {action}" in cp, f"ação '{action}' sem seção"


def test_desktop_actions_tem_exec():
    cp = configparser.ConfigParser(strict=False, interpolation=None)
    cp.optionxform = str
    cp.read(PACKAGING / "ufvai.desktop", encoding="utf-8")
    for section in cp.sections():
        if section.startswith("Desktop Action "):
            assert cp[section]["Name"].strip(), f"{section} sem Name"
            assert "ufvai" in cp[section]["Exec"], f"{section} não chama o ufvai"


def test_launcher_implementa_modo_gui():
    launcher = PACKAGING / "ufvai"
    text = launcher.read_text(encoding="utf-8")
    assert "cmd_start_gui" in text
    assert "--gui)" in text
    for helper in ("_notify", "_open_url"):
        assert f"{helper}()" in text or f"{helper} " in text, f"helper {helper} ausente"


def test_launcher_sintaxe_bash():
    r = subprocess.run(
        ["bash", "-n", str(PACKAGING / "ufvai")], capture_output=True, text=True
    )
    assert r.returncode == 0, r.stderr


def test_deb_instala_entry_e_icones():
    """O build instala o .desktop e os ícones (conferido no build-deb.sh)."""
    build = ROOT / "build-deb.sh"
    src = build.read_text(encoding="utf-8")
    assert "usr/share/applications/ufvai.desktop" in src
    assert "icons/hicolor/scalable/apps/ufvai.svg" in src
    assert "icons/hicolor/256x256/apps/ufvai.png" in src


# ══════════════════════════════════════════════════════════════════════════
# 2. Pacote Windows
# ══════════════════════════════════════════════════════════════════════════


def test_arquivos_do_pacote_windows_existem():
    expected = [
        "ufvai_win.py",
        "ufvai.spec",
        "installer.iss",
        "build_exe.ps1",
        "build_exe.bat",
        "requirements-windows.txt",
        "README.md",
    ]
    for name in expected:
        assert (WINDOWS / name).is_file(), f"packaging/windows/{name} ausente"


def test_entrypoint_windows_compila():
    py_compile.compile(str(WINDOWS / "ufvai_win.py"), doraise=True)


def test_installer_cria_atalho_no_menu_iniciar():
    iss = (WINDOWS / "installer.iss").read_text(encoding="utf-8")
    assert "{autoprograms}" in iss, "instalador não cria atalho no Menu Iniciar"
    assert "UFVAI.exe" in iss
    # A desinstalação preserva a pasta de dados.
    assert "PRESERVADA" in iss


def test_spec_do_pyinstaller_congela_o_pacote():
    spec = (WINDOWS / "ufvai.spec").read_text(encoding="utf-8")
    assert "collect_submodules" in spec, "imports tardios ficariam de fora"
    assert 'name="UFVAI"' in spec


def test_icone_windows_valido():
    ico = ROOT / "assets" / "ufvai.ico"
    assert ico.is_file(), "assets/ufvai.ico ausente (ícone do .exe/atalho)"
    with open(ico, "rb") as fh:
        header = fh.read(4)
    # ICO: reservado(0,0) + tipo(1) + contagem
    assert header[:2] == b"\x00\x00" and header[2] == 0x01, "arquivo .ico inválido"


def test_workflow_windows_existe_e_e_yaml():
    wf = ROOT / ".github" / "workflows" / "build-windows.yml"
    assert wf.is_file()
    text = wf.read_text(encoding="utf-8")
    assert "windows-latest" in text
    assert "ISCC.exe" in text or "installer.iss" in text


# ══════════════════════════════════════════════════════════════════════════
# 3. Compatibilidade aplicada no código
# ══════════════════════════════════════════════════════════════════════════


def test_getuid_protegido_para_windows():
    src = (ROOT / "pesquisai" / "launch_app.py").read_text(encoding="utf-8")
    assert 'getattr(os, "getuid"' in src, "os.getuid() ainda quebra no Windows"


def test_sigkill_protegido_para_windows():
    src = (ROOT / "pesquisai" / "launch_app.py").read_text(encoding="utf-8")
    assert 'getattr(signal, "SIGKILL"' in src, "signal.SIGKILL ainda quebra no Windows"


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
