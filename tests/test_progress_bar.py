"""Testes para progress_bar.py — v0.6.7 (painel de boot desde o início).

A antiga barra escura virou driver do painel único (_BootPanel de
launch_app.py, singleton get_boot_panel()). Cobre:
  - show(): delegação ao painel compartilhado no modo Colab
    (mesmo display_id, mensagem abaixo da barra, percentual monotônico);
  - show(): fallback ASCII legado no terminal / sem o pacote;
  - finish(): limpeza da saída antes do card final;
  - Edge cases: step negativo, total zero, step além do total.
"""

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pesquisai import launch_app, progress_bar
from pesquisai.progress_bar import show, finish, _STAGE_PCT


class _FakeHTML:
    def __init__(self, data):
        self.data = data


class _DisplayRecorder:
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
    monkeypatch.setattr(launch_app, "_BOOT_SINGLETON", None)
    return rec


def _fill_pct(html: str) -> int:
    m = re.search(r"bottom:0;width:(\d+)%", html)
    return int(m.group(1)) if m else -1


class TestMapaDeEtapas:
    """Constantes do mapa de estágios do setup."""

    def test_cobertura_0_a_4(self):
        for step in range(5):
            assert step in _STAGE_PCT

    def test_monotonico_e_dentro_da_barra(self):
        pcts = [_STAGE_PCT[i] for i in sorted(_STAGE_PCT)]
        assert pcts == sorted(pcts), "percentuais dos estágios regredem"
        assert all(0 < p < 82 for p in pcts), (
            "estágios devem terminar abaixo da faixa interna do launch() (82+)"
        )


class TestShowColabPainelUnico:
    def test_show_delega_ao_painel_compartilhado(self, monkeypatch):
        rec = _force_colab(monkeypatch)
        show(1, 4, "Montando Google Drive...")
        assert {c[1] for c in rec.calls} == {launch_app._BootPanel._DISPLAY_ID}
        assert "Montando Google Drive" in rec.last
        # mensagem ativa (spinner) SEMPRE abaixo da barra
        assert rec.last.index("ufl-barwrap") < rec.last.index("ufl-spin")

    def test_show_consecutivos_acumula_checklist(self, monkeypatch):
        rec = _force_colab(monkeypatch)
        show(0, 4, "Preparando...")
        show(1, 4, "Montando Google Drive...")
        html = rec.last
        assert '✓</span><span>Preparando...</span>' in html.replace("…", "...")
        assert "Montando Google Drive" in html

    def test_show_mesmo_display_sem_duplicar(self, monkeypatch):
        rec = _force_colab(monkeypatch)
        for step in range(5):
            show(step, 4, f"etapa {step}")
        creates = [c for c in rec.calls if c[0] == "create"]
        assert len(creates) == 1, "painel deve ser criado UMA única vez"

    def test_show_percentual_monotonico(self, monkeypatch):
        rec = _force_colab(monkeypatch)
        for step in range(5):
            show(step, 4, f"etapa {step}")
        pcts = [_fill_pct(c[2]) for c in rec.calls]
        assert pcts == sorted(pcts), f"barra regrediu: {pcts}"

    def test_handoff_launch_continua_a_mesma_barra(self, monkeypatch):
        rec = _force_colab(monkeypatch)
        show(4, 4, "Iniciando servidores e interface web")
        boot = launch_app.get_boot_panel()
        boot.begin()  # idempotente — não zera
        boot.active("Preparando a interface web", 98)
        boot.done(99)
        boot.finish()
        pcts = [_fill_pct(c[2]) for c in rec.calls]
        assert pcts == sorted(pcts) and pcts[-1] == 100


class TestShowEdgeCases:
    def test_total_zero_nao_quebra(self, monkeypatch):
        rec = _force_colab(monkeypatch)
        show(0, 0, "Zero")
        assert rec.last  # renderizou algo

    def test_step_negativo_nao_quebra(self, monkeypatch):
        rec = _force_colab(monkeypatch)
        show(-1, 4, "Negativo")
        assert rec.last

    def test_step_além_do_mapa_usa_fórmula(self, monkeypatch):
        rec = _force_colab(monkeypatch)
        show(10, 4, "Além")
        pct = _fill_pct(rec.last)
        assert 0 < pct <= 99


class TestShowTerminalFallback:
    def test_ascii_sem_pacote_importavel(self, capsys, monkeypatch):
        monkeypatch.setattr(progress_bar, "IN_COLAB", False)
        monkeypatch.setitem(sys.modules, "pesquisai.launch_app", None)
        show(1, 4, "Montando Google Drive...")
        out = capsys.readouterr().out
        assert "Montando Google Drive" in out and "%" in out

    def test_ascii_clampa_percentual(self, capsys, monkeypatch):
        monkeypatch.setattr(progress_bar, "IN_COLAB", False)
        monkeypatch.setitem(sys.modules, "pesquisai.launch_app", None)
        show(10, 4, "Over")
        out = capsys.readouterr().out
        m = re.search(r"(\d+)%", out)
        assert m and int(m.group(1)) <= 100


class TestFinish:
    def test_finish_limpa_saida_no_ipython(self, monkeypatch):
        limpou = []
        monkeypatch.setattr(progress_bar, "IN_COLAB", True)
        monkeypatch.setattr(progress_bar, "_clear_func", lambda wait=False: limpou.append(wait))
        finish()
        assert limpou == [True]

    def test_finish_terminal_printa_newline(self, capsys, monkeypatch):
        monkeypatch.setattr(progress_bar, "IN_COLAB", False)
        finish()
        assert "\n" in capsys.readouterr().out

    def test_finish_tolerante_a_erro_do_clear(self, monkeypatch):
        def _boom(wait=False):
            raise RuntimeError("frontend indisponível")

        monkeypatch.setattr(progress_bar, "IN_COLAB", True)
        monkeypatch.setattr(progress_bar, "_clear_func", _boom)
        finish()  # não deve lançar
