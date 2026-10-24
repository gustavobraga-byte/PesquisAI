# -*- coding: utf-8 -*-
"""Testes da v0.7.3 — o pacote `pesquisai` precisa estar INSTALADO.

Relato do novo usuário (Colab): "o pacote python pesquisai (api autopilot)
não está instalado no ambiente".

Cobre:
  * a distribuição chama-se `pesquisai` (e não `pesquisai-additions`);
  * `pyyaml` é dependência base (a "Minha memória" usa PyYAML no frontmatter);
  * a célula de boot do Colab INSTALA o pacote e PROVA a API do autopilot;
  * `install-offline.sh` não engole a falha do pip e verifica a API;
  * `scripts/install.sh` usa um extra que existe.

Executar:  python3 -m pytest tests/test_instalacao_pacote.py -q
"""
from __future__ import annotations

import json
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(rel: str) -> str:
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def _pyproject() -> dict:
    """Lê o pyproject.toml sem depender do tomllib (py3.10+ tem, mas seja)."""
    txt = _read("pyproject.toml")
    try:
        import tomllib
        data = tomllib.loads(txt)
    except Exception:
        data = {}
    project = data.get("project") or {}
    if not project:  # fallback sem tomllib
        bloco = txt.split("[project]", 1)[-1].split("\n[", 1)[0]
        for key in ("name", "version"):
            m = re.search(rf'^{key}\s*=\s*"([^"]+)"', bloco, re.M)
            if m:
                project[key] = m.group(1)
    return project


# ── 1. metadados da distribuição ────────────────────────────────────────
def test_distribuicao_chama_se_pesquisai():
    assert _pyproject().get("name") == "pesquisai", (
        "a distribuição precisa se chamar 'pesquisai' — senão "
        "`pip show pesquisai` responde 'Package(s) not found'")


def test_versao_da_distribuicao():
    assert re.match(r"^\d+\.\d+\.\d+$", str(_pyproject().get("version")))


def test_pyyaml_e_dependencia_base():
    txt = _read("pyproject.toml")
    bloco = txt.split("dependencies = [", 1)[1].split("]", 1)[0]
    assert "pyyaml" in bloco.lower(), (
        "pyyaml é dependência base: o frontmatter da memória é parseado com PyYAML")


# ── 2. a célula de boot instala o pacote ────────────────────────────────
def _boot_cell() -> str:
    nb = json.loads(_read("PesquisAI.ipynb"))
    for cell in nb["cells"]:
        if cell.get("cell_type") != "code":
            continue
        src = "".join(cell.get("source", []))
        if "git" in src and "clone" in src:
            return src
    return ""


def test_boot_cell_instala_o_pacote():
    src = _boot_cell()
    assert "_install_pesquisai" in src, "a célula de boot deve instalar o pacote"
    assert re.search(r'pip["\',\s]+"install"', src) or '"pip", "install"' in src, (
        "a instalação precisa usar `pip install`")
    assert re.search(r'-e["\',\s]+work_dir|"-e",\s*work_dir', src), (
        "a instalação deve ser editável (-e) para acompanhar o repo clonado")


def test_boot_cell_prova_a_api_do_autopilot():
    src = _boot_cell()
    assert "pesquisai.obsidian.autopilot" in src, (
        "a célula de boot deve IMPORTAR a API do autopilot para provar que ela funciona")
    assert "recall" in src and "save" in src


def test_boot_cell_verifica_a_partir_de_cwd_neutro():
    """O bug real: o agente roda em outro processo (outro CWD)."""
    src = _boot_cell()
    assert re.search(r'cwd\s*=\s*"/"', src), (
        "a verificação da API deve rodar fora da pasta do repo (CWD neutro)")


# ── 3. instaladores ─────────────────────────────────────────────────────
def test_install_offline_nao_engole_o_erro_do_pip():
    txt = _read("install-offline.sh")
    assert "-e \"$SCRIPT_DIR\" 2>/dev/null || true" not in txt, (
        "a instalação do pacote não pode esconder a falha (`2>/dev/null || true`)")
    assert "pip install" in txt


def test_install_offline_verifica_a_api():
    txt = _read("install-offline.sh")
    assert "pesquisai.obsidian.autopilot" in txt, (
        "o instalador deve verificar que a API do autopilot importa")
    assert "recall" in txt


def test_scripts_install_usa_extra_existente():
    txt = _read("scripts/install.sh")
    extras = set(re.findall(r'\.\[([a-zA-Z0-9_,-]+)\]', txt))
    pyproject = _read("pyproject.toml")
    for extra in extras:
        for one in extra.split(","):
            one = one.strip()
            if not one:
                continue
            assert f"{one} = [" in pyproject, (
                f"o extra '{one}' não existe em pyproject.toml")


# ── 4. o pacote realmente instalado no ambiente (opcional) ─────────────
def test_pacote_importavel_do_cwd_neutro():
    """Se o pacote estiver instalado, a API tem de importar de qualquer CWD."""
    try:
        from pesquisai.obsidian.autopilot import recall, save  # noqa: F401
    except ImportError:
        pytest.skip("pacote `pesquisai` não instalado neste ambiente (normal fora do boot)")
