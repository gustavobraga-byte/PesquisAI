"""tests/test_v079_ui_contract.py — v0.7.9: contrato da interface e dos endpoints.

O que este arquivo protege (sem subir servidor nem navegador):
- os endpoints `/api/free_models` e `/api/default_model` existem no wrapper;
- o modal de Provedores mostra as instruções de chave gratuita quando não há
  nenhuma chave salva;
- o seletor de modelos gratuitos e o botão "Definir como padrão" estão ligados;
- o botão ⚙ do autosave abre intervalo (1–60 min) e escopo (ativa/todas/escolhidas);
- o backend aceita `session_ids` e grava só as conversas escolhidas;
- o guia `docs/CHAVES_API.md` existe e cobre OpenRouter, NVIDIA e OpenCode Go.
"""
import os
import re

ROOT = os.path.join(os.path.dirname(__file__), "..")


def _read(rel: str) -> str:
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


# ── Backend ──────────────────────────────────────────────────────────────


def test_endpoints_de_gratuitos_e_modelo_padrao_existem():
    src = _read("pesquisai/launch_app.py")
    assert '"/api/free_models"' in src
    assert '"/api/default_model"' in src
    assert "from . import free_models as _fm" in src


def test_free_models_filtra_catalogo_do_motor():
    src = _read("pesquisai/launch_app.py")
    assert "_fm.filter_free_models(_lines)" in src
    assert '"opencode"' in src and '"models"' in src  # `opencode models`


def test_default_model_preserva_config_e_recusa_pago():
    src = _read("pesquisai/launch_app.py")
    assert "_fm.merge_default_model(_existing, _model_id)" in src
    assert "is_free_model(_model_id)" in src
    assert "opencode.json" in src


def test_autosave_aceita_session_ids():
    src = _read("pesquisai/launch_app.py")
    assert 'body.get("session_ids")' in src
    assert "save_all_sessions(" in src
    assert '_per["scope"] = "selected"' in src


# ── Frontend ─────────────────────────────────────────────────────────────


def test_modal_de_provedores_mostra_instrucoes_sem_chave():
    src = _read("pesquisai/launch_app_responsive_v041.py")
    assert 'id="prov-howto"' in src
    assert 'openrouter.ai/keys' in src
    assert 'build.nvidia.com' in src
    assert "CHAVES_API.md" in src
    # aparece sozinho quando não há chave salva
    assert 'keys.length ? "none" : "block"' in src


def test_aviso_de_responsabilidade_na_abertura():
    src = _read("pesquisai/launch_app_responsive_v041.py")
    assert "Chaves de API são de sua responsabilidade" in src
    assert "não têm qualquer vínculo" in src


def test_seletor_de_gratuitos_e_modelo_padrao():
    src = _read("pesquisai/launch_app_responsive_v041.py")
    assert 'id="free-prov"' in src
    assert 'id="free-model"' in src
    assert "function loadFreeModels()" in src
    assert "function setDefaultModel()" in src
    assert '/api/default_model' in src


def test_botao_autosave_abre_intervalo_e_escopo():
    src = _read("pesquisai/launch_app_responsive_v041.py")
    assert 'onclick="openAutosaveCfg()"' in src
    assert 'id="as-interval"' in src
    assert 'value="1"' in src and 'value="60"' in src
    assert 'value="selected"' in src
    assert "AUTOSAVE_INTERVAL_KEY" in src
    assert "autosaveIntervalMs()" in src
    # o timer usa o intervalo escolhido
    assert "setInterval(() => autosaveTick(false), autosaveIntervalMs())" in src


def test_autosave_envia_session_ids_escolhidos():
    src = _read("pesquisai/launch_app_responsive_v041.py")
    assert "session_ids: autosaveScope() === \"selected\" ? autosaveSelectedIds() : []" in src


def test_intervalo_minimo_de_um_minuto():
    src = _read("pesquisai/launch_app_responsive_v041.py")
    m = re.search(r"function autosaveIntervalMs\(\) \{(.+?)\n    \}", src, re.S)
    assert m, "autosaveIntervalMs() não encontrada"
    assert "if (!(m >= 1)) m = 1;" in m.group(1)


# ── Documentação ─────────────────────────────────────────────────────────


def test_guia_de_chaves_cobre_os_tres_provedores():
    doc = _read("docs/CHAVES_API.md")
    assert "openrouter.ai/keys" in doc
    assert "build.nvidia.com" in doc
    assert "opencode.ai/go" in doc
    assert "responsabilidade" in doc.lower()
    # versão em inglês (mesmo arquivo)
    assert "API keys — read before you start" in doc


def test_readme_e_manual_apontam_para_0_7_9():
    for rel in ("README.md", "MANUAL.md"):
        src = _read(rel)
        assert "0.7.9" in src, f"{rel} não menciona 0.7.9"
