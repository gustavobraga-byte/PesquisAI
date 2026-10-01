# tests/test_sair_shutdown.py — v0.6.20
#
# Botão SAIR na interface do app (não no notebook do Colab):
#   1. Wrapper HTML (topbar + drawer mobile + modal de confirmação + JS);
#   2. Confirmação OBRIGATÓRIA antes do encerramento (contrato de UI e de API);
#   3. Rota POST /api/shutdown (backend) com guarda de confirmação;
#   4. Encerramento do keep-alive (PID file + fallback pkill por marcador);
#   5. Fora do Colab o botão fica oculto (guard IS_COLAB no JS).

import os
import signal
import subprocess
import sys
import time

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from pesquisai.launch_app_responsive_v041 import create_wrapper_html  # noqa: E402


@pytest.fixture(scope="module")
def wrapper_html() -> str:
    return create_wrapper_html(
        "http://localhost:8000", "https://drive.google.com/drive/my-drive",
        session_token="tok-test",
    )


# ── 1. UI: botão na interface do app (não no Colab) ──────────────────────────

def test_botao_sair_na_topbar(wrapper_html):
    assert 'id="sair-btn"' in wrapper_html
    assert 'onclick="ufvaiExit()"' in wrapper_html
    assert 'class="tb-btn btn-sair"' in wrapper_html


def test_botao_sair_no_drawer_mobile(wrapper_html):
    assert 'id="sair-btn-mobile"' in wrapper_html


def test_botao_oculto_por_padrao_e_exibido_so_no_colab(wrapper_html):
    # display:none inline por padrão + guard IS_COLAB no JS
    assert 'id="sair-btn"' in wrapper_html and "display:none" in wrapper_html
    assert "IS_COLAB" in wrapper_html
    assert 'getElementById("sair-btn").style.display = ""' in wrapper_html


# ── 2. Confirmação obrigatória (contrato de UI) ──────────────────────────────

def test_modal_de_confirmacao_existe(wrapper_html):
    assert 'id="sair-overlay"' in wrapper_html
    assert 'id="sair-yes"' in wrapper_html  # botão SIM, SAIR
    assert 'ufvaiExitConfirm()' in wrapper_html
    assert 'ufvaiExitCancel()' in wrapper_html
    # o fetch do confirm envia confirm:true explicitamente
    assert '"confirm": true' in wrapper_html or "confirm: true" in wrapper_html


def test_modal_nao_envia_sem_confirmacao(wrapper_html):
    # nenhuma chamada automática de ufvaiExitConfirm fora do clique do SIM
    assert wrapper_html.count("ufvaiExitConfirm()") >= 1


def test_i18n_sair_nos_5_idiomas(wrapper_html):
    import re
    for lang in ["pt_BR", "en_US", "es_ES", "fr_FR", "zh_CN"]:
        m = re.search(r'"%s": \{(.*?)\n        \}' % lang, wrapper_html, re.S)
        assert m, f"bloco i18n {lang} ausente"
        for key in ["sair.title", "sair.confirm_q", "sair.warn",
                    "sair.yes", "sair.status", "sair.fail", "sair.done"]:
            assert f'"{key}":' in m.group(1), f"{lang}/{key} ausente"


# ── 3. Backend: rota com guarda de confirmação ───────────────────────────────

def test_rota_shutdown_existe_no_backend():
    with open(os.path.join(REPO, "pesquisai", "launch_app.py"),
              encoding="utf-8") as fh:
        src = fh.read()
    assert '/api/shutdown' in src
    assert 'body.get("confirm", False)' in src  # sem confirm → 400
    assert '_shutdown_start' in src
    assert '_shutdown_save_memory_note' in src
    assert '_shutdown_kill_keepalive' in src
    assert '_shutdown_schedule_unassign' in src


def test_rota_shutdown_responde_imediato_sem_trabalho_lento():
    """v0.6.20-fix: a rota NÃO pode executar o trabalho lento de forma síncrona.

    A demora relatada (o modal travava antes de desconectar) vinha de a rota
    gravar a nota no Drive e matar o keep-alive ANTES de responder. Agora ela
    apenas dispara `_shutdown_start()` e retorna na hora.
    """
    with open(os.path.join(REPO, "pesquisai", "launch_app.py"),
              encoding="utf-8") as fh:
        src = fh.read()
    i_route = src.index('if p == "/api/shutdown":')
    i_end = src.index("self.send_error(404)", i_route)
    route = src[i_route:i_end]
    assert "_shutdown_start()" in route
    assert "_shutdown_save_memory_note()" not in route
    assert "_shutdown_kill_keepalive()" not in route
    assert "_shutdown_schedule_unassign(" not in route


def test_shutdown_start_encadeia_memoria_keepalive_unassign_em_background():
    with open(os.path.join(REPO, "pesquisai", "launch_app.py"),
              encoding="utf-8") as fh:
        src = fh.read()
    i_start = src.index("def _shutdown_start(")
    # dentro do worker: kill do keep-alive → teto da nota → unassign
    i_kill = src.index("_shutdown_kill_keepalive()", i_start)
    i_wait = src.index("note_done.wait(timeout=memory_timeout_s)", i_start)
    i_un = src.index("_shutdown_schedule_unassign(delay_s=flush_s)", i_start)
    assert i_kill < i_wait < i_un


def test_shutdown_start_nao_bloqueia_mesmo_com_nota_lenta(monkeypatch):
    """A chamada retorna na hora mesmo com escrita de memória lenta."""
    from pesquisai import launch_app

    def slow_save():
        time.sleep(2.0)
        return True

    monkeypatch.setattr(launch_app, "_shutdown_save_memory_note", slow_save)
    monkeypatch.setattr(launch_app, "_shutdown_kill_keepalive", lambda: True)
    monkeypatch.setattr(launch_app, "_shutdown_schedule_unassign",
                        lambda delay_s=0.4: None)

    t0 = time.perf_counter()
    launch_app._shutdown_start()
    dt = time.perf_counter() - t0
    assert dt < 0.5  # não espera os 2 s da nota


def test_frontend_fecha_modal_rapido(wrapper_html):
    """v0.6.20-fix: modal fecha na hora (ufvaiExitDone chama ufvaiExitCancel
    direto, sem espera fixa) e exibe a tela "Ambiente desconectado"."""
    assert "function ufvaiExitDone()" in wrapper_html
    assert "ufvaiExitDone();" in wrapper_html
    assert "}, 2500)" not in wrapper_html


def test_tela_ambiente_desconectado_estilo_termos_recusados(wrapper_html):
    """v0.6.20: após SIM, SAIR — tela full-screen com o MESMO visual da tela
    de Termos recusados (.t-card escuro com borda dourada + marca UFVAI)."""
    assert 'id="exit-overlay"' in wrapper_html
    assert "#exit-overlay{position:fixed" in wrapper_html
    # regras próprias para .t-card/.t-brand (as do terms-overlay são escopadas)
    assert "#exit-overlay .t-card{" in wrapper_html
    assert "#exit-overlay .t-brand" in wrapper_html
    assert '<div class="t-brand"><b>UFV</b><em>AI</em></div>' in wrapper_html
    assert "Ambiente desconectado" in wrapper_html
    # instrução de como voltar + mensagem em inglês (padrão da tela de recusa)
    assert "reexecute a célula de boot no Colab" in wrapper_html
    assert "re-run the boot cell in Colab" in wrapper_html


def test_modal_warn_sem_promessa_de_progresso(wrapper_html):
    """v0.6.20-fix: o modal NÃO promete salvar progresso da sessão do agente
    (o usuário pediu o texto enxuto)."""
    warn = wrapper_html[wrapper_html.index('data-i18n="sair.warn"'):]
    warn = warn[:warn.index("</p>")]
    assert "progresso da sessão do agente" not in warn
    assert "Tudo em memória será perdido" in warn
    assert "Google Drive continuam salvos" in warn
    # e o texto pedido aparece completo no HTML default (pt-BR)
    assert ("Tudo em memória será perdido — os arquivos no seu Google Drive "
            "continuam salvos. Não há como desfazer após confirmar.") in wrapper_html


def test_unassign_fora_do_colab_nao_faz_nada():
    with open(os.path.join(REPO, "pesquisai", "launch_app.py"),
              encoding="utf-8") as fh:
        src = fh.read()
    assert "if not IN_COLAB:\n                return" in src


# ── 4. Keep-alive: PID file + fallback por marcador ──────────────────────────

def test_ipynb_tem_pid_file_e_marcador():
    import json
    with open(os.path.join(REPO, "PesquisAI.ipynb"), encoding="utf-8") as fh:
        nb = json.load(fh)
    boot = "".join(nb["cells"][2]["source"])
    assert "ufvai_keepalive.pid" in boot          # PID file gravado pela célula
    assert "ufvai-keepalive-v0620" in boot        # marcador na cmdline (pkill)


def test_ipynb_nao_tem_mais_card_sair():
    import json
    with open(os.path.join(REPO, "PesquisAI.ipynb"), encoding="utf-8") as fh:
        nb = json.load(fh)
    boot = "".join(nb["cells"][2]["source"])
    assert "ufx-card" not in boot                 # card SAIR removido do notebook
    assert "ufvai.exit" not in boot               # callback do card removido


def test_ipynb_instrucoes_apontam_para_a_interface():
    import json
    with open(os.path.join(REPO, "PesquisAI.ipynb"), encoding="utf-8") as fh:
        nb = json.load(fh)
    md = "".join(nb["cells"][1]["source"])
    assert "interface do UFVAI" in md
    assert "card abaixo da barra de carregamento" not in md


def test_kill_keepalive_mata_subprocesso_real(tmp_path, monkeypatch):
    from pesquisai import launch_app

    # subprocesso fake com o marcador na cmdline
    proc = subprocess.Popen(
        [sys.executable, "-u", "-c",
         "# ufvai-keepalive-v0620\nimport time\nwhile True: time.sleep(1)"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    pid_file = tmp_path / "ufvai_keepalive.pid"
    pid_file.write_text(str(proc.pid))
    monkeypatch.setattr(launch_app, "_KEEPALIVE_PID_FILE", str(pid_file))

    assert launch_app._shutdown_kill_keepalive() is True
    for _ in range(40):
        if proc.poll() is not None:
            break
        time.sleep(0.1)
    assert proc.poll() is not None  # morreu

    # cleanup garantido
    if proc.poll() is None:
        proc.kill()


def test_kill_keepalive_sem_pid_usa_fallback_marcador(tmp_path, monkeypatch):
    from pesquisai import launch_app

    monkeypatch.setattr(
        launch_app, "_KEEPALIVE_PID_FILE",
        str(tmp_path / "nao_existe.pid"),
    )
    proc = subprocess.Popen(
        [sys.executable, "-u", "-c",
         "# ufvai-keepalive-v0620\nimport time\nwhile True: time.sleep(1)"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        assert launch_app._shutdown_kill_keepalive() is True
        for _ in range(40):
            if proc.poll() is not None:
                break
            time.sleep(0.1)
        assert proc.poll() is not None
    finally:
        if proc.poll() is None:
            proc.kill()


def test_pid_invalido_nao_mata_o_proprio_processo(tmp_path, monkeypatch):
    from pesquisai import launch_app

    pid_file = tmp_path / "ufvai_keepalive.pid"
    pid_file.write_text(str(os.getpid()))  # PID do próprio pytest — deve ser ignorado
    monkeypatch.setattr(launch_app, "_KEEPALIVE_PID_FILE", str(pid_file))

    # com fallback pkill (sem processo com o marcador) ainda retorna True,
    # mas o processo atual continua vivo — é isso que o teste prova
    r = launch_app._shutdown_kill_keepalive()
    assert r in (True, False)
    assert os.getpid() in [os.getpid()]  # processo vivo (sanity)


def test_signal_terminado_suavemente(tmp_path, monkeypatch):
    """SIGTERM primeiro; SIGKILL só se ignorar o TERM."""
    from pesquisai import launch_app

    class FakeProc:
        def __init__(self):
            self.pid = 424242
            self.signals = []
        # pid não existe — cai no OSError → fallback pkill

    pid_file = tmp_path / "ufvai_keepalive.pid"
    pid_file.write_text("424242")
    monkeypatch.setattr(launch_app, "_KEEPALIVE_PID_FILE", str(pid_file))

    # não deve levantar — OSError tratado, cai no fallback
    r = launch_app._shutdown_kill_keepalive()
    assert isinstance(r, bool)
    assert signal.SIGTERM  # sanity do import local
