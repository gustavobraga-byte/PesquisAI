"""Testes v0.6.7 — painel de boot do Colab (_BootPanel) + botão de lançamento.

O painel é no-op fora do Colab; os testes forçam o modo Colab injetando
display/HTML falsos nos globais do módulo e validam o HTML renderizado.

Revisão v0.6.7 (tema da logomarca): tela LEVE (papel off-white #f6f5f0,
azul-marinho "UFV" #2b2d3a + dourado "AI" #b8912f), mensagens SEMPRE
abaixo da barra e LOGO REAL acima do botão final.

v0.6.7 (barra desde o início): progress_bar.show() alimenta o MESMO painel
(singleton get_boot_panel(), display_id "ufvai_boot_panel") desde os
estágios do run(); begin() é idempotente e launch() continua de onde o
setup parou — uma única barra contínua, sem reinicialização nem duplicação.
"""

import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pesquisai import launch_app, progress_bar


class _FakeHTML:
    def __init__(self, data):
        self.data = data


class _DisplayRecorder:
    """Captura chamadas display/update_display simulando o IPython."""

    def __init__(self):
        self.calls = []

    def display(self, obj, display_id=None):
        self.calls.append(("create", display_id, obj.data))

    def update_display(self, obj, display_id=None):
        self.calls.append(("update", display_id, obj.data))

    @property
    def last(self):
        return self.calls[-1][2] if self.calls else ""


def _force_colab(monkeypatch):
    rec = _DisplayRecorder()
    monkeypatch.setattr(launch_app, "IN_COLAB", True)
    monkeypatch.setattr(launch_app, "display", rec.display)
    monkeypatch.setattr(launch_app, "HTML", _FakeHTML)
    monkeypatch.setattr(launch_app, "update_display", rec.update_display)
    return rec


class TestBootPanelColab:
    def test_begin_cria_painel_com_display_id(self, monkeypatch):
        rec = _force_colab(monkeypatch)
        boot = launch_app._BootPanel()
        boot.begin()
        assert rec.calls[0][0] == "create"
        assert rec.calls[0][1] == launch_app._BootPanel._DISPLAY_ID
        assert "width:0%" in rec.last

    def test_updates_usam_update_display(self, monkeypatch):
        rec = _force_colab(monkeypatch)
        boot = launch_app._BootPanel()
        boot.begin()
        boot.active("Instalando o terminal (ttyd)", 40)
        assert rec.calls[-1][0] == "update"
        assert "ufl-spin" in rec.last
        assert "width:40%" in rec.last

    def test_checkpoints_aparecem_um_a_um(self, monkeypatch):
        rec = _force_colab(monkeypatch)
        boot = launch_app._BootPanel()
        boot.begin()
        boot.active("a", 10); boot.done(20)
        assert '✓</span><span>a</span>' in rec.last
        # CSS estático contém ".ufl-spin{…}" — verificar ausência de ELEMENTO ativo
        assert '<span class="ufl-spin">' not in rec.last
        boot.active("b", 30)
        assert "b…" in rec.last and '✓</span><span>a</span>' in rec.last

    def test_mensagens_abaixo_da_barra(self, monkeypatch):
        """Ordem visual: cabeçalho → barra → % → checklist → status final."""
        rec = _force_colab(monkeypatch)
        boot = launch_app._BootPanel()
        boot.begin()
        boot.active("etapa", 50)
        html = rec.last
        i_head = html.index("ufl-wordmark")
        i_bar = html.index("ufl-barwrap")
        i_pct = html.index("ufl-pct")
        i_list = html.index("ufl-list")
        assert i_head < i_bar < i_pct < i_list
        boot.finish()
        assert html.index("ufl-list") < rec.last.index("ufl-ready")

    def test_finish_100_pronto(self, monkeypatch):
        rec = _force_colab(monkeypatch)
        boot = launch_app._BootPanel()
        boot.begin()
        boot.active("Preparando a interface web", 88)
        boot.finish()
        assert "width:100%" in rec.last
        assert "✨ UFVAI pronto!" in rec.last

    def test_fail_marca_com_x_e_classe_bad(self, monkeypatch):
        rec = _force_colab(monkeypatch)
        boot = launch_app._BootPanel()
        boot.begin()
        boot.active("Preparando a interface web", 88)
        boot.fail("porta ocupada")
        assert '✕</span><span>Preparando a interface web — porta ocupada</span>' in rec.last
        assert "ufl-row bad" in rec.last

    def test_tema_claro_da_logomarca_no_html(self, monkeypatch):
        rec = _force_colab(monkeypatch)
        boot = launch_app._BootPanel()
        boot.begin(); boot.active("x", 50); boot.done(); boot.finish()
        html = rec.last
        for token in (
            "#f6f5f0",   # papel off-white (fundo do logo)
            "#2b2d3a",   # azul-marinho "UFV"
            "#b8912f",   # dourado "AI"
            "Montserrat",
            "DM Mono",
            "INTELIGÊNCIA ARTIFICIAL",
        ):
            assert token in html, f"token ausente: {token}"
        # Sem resquícios do tema escuro anterior no painel
        assert "#141c24" not in html and "#1f2831" not in html
        css = html.split("<style>")[1].split("</style>")[0]
        assert css.count("{") == css.count("}"), "chaves de CSS desbalanceadas"

    def test_wordmark_ufv_ai_dourado(self, monkeypatch):
        rec = _force_colab(monkeypatch)
        boot = launch_app._BootPanel()
        boot.begin()
        html = rec.last
        assert '<div class="ufl-wordmark"><span>UFV</span>' in html
        assert '<span class="ufl-ai">AI</span></div>' in html

    def test_pct_limitado_a_99_durante_execucao(self, monkeypatch):
        rec = _force_colab(monkeypatch)
        boot = launch_app._BootPanel()
        boot.begin()
        boot.active("x", 150)
        assert "width:99%" in rec.last


class TestLaunchButtonRestyle:
    def test_logo_real_acima_do_botao(self, monkeypatch):
        """Com asset presente: <img> base64 no lugar do texto 'pronto'."""
        rec = _force_colab(monkeypatch)
        launch_app.show_launch_button("http://test.url")
        html = rec.last
        assert '<img class="ufb-logo" src="data:image/jpeg;base64,' in html
        assert 'alt="UFVAI — Inteligência Artificial"' in html
        # Texto antigo removido do card
        assert "✨ pronto" not in html
        assert "ufb-brand" not in html and "ufb-chip" not in html
        assert "🚀" not in html
        # Botão dourado com tipografia navy (par UFV/AI da marca)
        for token in ("#f6f5f0", "#2b2d3a", "#b8912f", "ABRIR O UFVAI",
                      "clique para começar"):
            assert token in html, f"token ausente: {token}"
        assert 'href="http://test.url"' in html
        assert "pesquisai-launch" in html                # compat com classe antiga
        assert "focus-visible" in html                   # a11y
        assert "prefers-reduced-motion" in html          # a11y movimento
        css = html.split("<style>")[1].split("</style>")[0]
        assert css.count("{") == css.count("}")

    def test_fallback_sem_asset_usa_wordmark_css(self, monkeypatch):
        rec = _force_colab(monkeypatch)
        monkeypatch.setattr(launch_app, "_UFVAI_LOGO_B64", "")  # cache = falha
        launch_app.show_launch_button("http://t")
        html = rec.last
        assert "data:image/jpeg" not in html
        assert "ufb-logo-fallback" in html
        assert "INTELIGÊNCIA ARTIFICIAL" in html

    def test_loader_b64_le_asset_do_repo(self):
        b64 = launch_app._load_logo_b64()
        assert b64  # assets/logo-oficial-288.jpg existe na árvore
        assert isinstance(b64, str) and len(b64) > 1000


class TestNoOpForaDoColab:
    def test_nenhum_display_chamado(self, monkeypatch):
        rec = _force_colab(monkeypatch)
        monkeypatch.setattr(launch_app, "IN_COLAB", False)
        boot = launch_app._BootPanel()
        boot.begin(); boot.active("x", 10); boot.done(20); boot.finish(); boot.fail("y")
        launch_app.show_launch_button("http://off")
        launch_app.show_ready_message()
        assert rec.calls == []


class TestBootContinuoDesdeOInicio:
    """v0.6.7 — a barra nasce no início do carregamento e não reinicia."""

    @pytest.fixture(autouse=True)
    def _fresh_singleton(self, monkeypatch):
        monkeypatch.setattr(launch_app, "_BOOT_SINGLETON", None)
        yield
        monkeypatch.setattr(launch_app, "_BOOT_SINGLETON", None, raising=False)

    @staticmethod
    def _pct_of(html: str) -> int:
        # alvo específico do PREENCHIMENTO (evita o width:78% da régua)
        m = re.search(r"bottom:0;width:(\d+)%", html)
        return int(m.group(1)) if m else -1

    def test_show_do_setup_alimenta_o_painel_unico(self, monkeypatch):
        rec = _force_colab(monkeypatch)
        progress_bar.show(0, 4, "Preparando...")
        progress_bar.show(2, 4, "Instalando dependências...")
        ids = {c[1] for c in rec.calls}
        assert ids == {launch_app._BootPanel._DISPLAY_ID}
        assert "Preparando" in rec.last and "Instalando dependências" in rec.last
        # mensagem ativa com spinner ABAIXO da barra (ordem visual)
        assert rec.last.index("ufl-barwrap") < rec.last.index("ufl-spin")

    def test_percentual_monotonico_setup_ate_launch(self, monkeypatch):
        rec = _force_colab(monkeypatch)
        for step in range(5):
            progress_bar.show(step, 4, f"estágio {step}")
        boot = launch_app.get_boot_panel()
        boot.begin()                      # idempotente — NÃO zera a barra
        boot.active("Localizando o núcleo opencode", 82)
        boot.done(85)
        boot.finish()
        pcts = [self._pct_of(c[2]) for c in rec.calls]
        assert pcts == sorted(pcts), f"barra regrediu: {pcts}"
        assert pcts[0] > 0 and pcts[-1] == 100

    def test_begin_idempotente_preserva_estado(self, monkeypatch):
        rec = _force_colab(monkeypatch)
        boot = launch_app.get_boot_panel()
        boot.begin(); boot.active("a", 40); boot.done(45)
        n_antes = len(rec.calls)
        boot.begin()                      # já criado → nenhum reset/zerada
        html = rec.last
        assert len(rec.calls) == n_antes or "width:45%" in html
        assert self._pct_of(html) == 45
        # um begin() em instância NOVA continua criando normalmente
        fresh = launch_app._BootPanel()
        fresh.begin()
        assert "width:0%" in rec.last

    def test_active_commita_checkpoint_pendente_sem_spinner_duplicado(self, monkeypatch):
        rec = _force_colab(monkeypatch)
        boot = launch_app.get_boot_panel()
        boot.begin()
        boot.active("Iniciando servidores e interface web", 80)
        boot.active("Localizando o núcleo opencode", 82)   # troca direta de etapa
        html = rec.last
        assert html.count('class="ufl-spin"') == 1          # só UM spinner
        assert '✓</span><span>Iniciando servidores e interface web</span>' in html
        assert "Localizando o núcleo opencode…" in html

    def test_finish_limpa_saida_contradolegado(self, monkeypatch):
        limpou = []
        monkeypatch.setattr(progress_bar, "IN_COLAB", True)
        monkeypatch.setattr(progress_bar, "_clear_func", lambda wait=False: limpou.append(wait))
        progress_bar.finish()
        assert limpou == [True]

    def test_fallback_ascii_fora_do_ipython(self, capsys, monkeypatch):
        monkeypatch.setattr(progress_bar, "IN_COLAB", False)

        def _import_error(*a, **k):
            raise ImportError("sem pesquisai")

        monkeypatch.setitem(__import__("sys").modules, "pesquisai.launch_app", None)
        # show() deve degradar para o print ASCII sem lançar exceção
        progress_bar.show(1, 4, "Montando Google Drive...")
        out = capsys.readouterr().out
        assert "Montando Google Drive" in out and "%" in out
