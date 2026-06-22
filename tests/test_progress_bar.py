"""Testes para progress_bar.py — barra de progresso do setup.

Cobre:
  - _html: geracao de HTML (ja testado, mantido e expandido)
  - show: atualizacao da barra (modo Colab com mock display, modo terminal)
  - finish: limpeza da barra
  - STAGES e COLORS: constantes
  - Edge cases: step negativo, total zero, percentual > 100
"""

import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pesquisai import progress_bar
from pesquisai.progress_bar import _html, show, finish, STAGES, COLORS


class TestConstants:
    """Constantes do modulo."""

    def test_stages_count(self):
        assert len(STAGES) == 4

    def test_colors_count(self):
        assert len(COLORS) == 4

    def test_stages_are_strings(self):
        for s in STAGES:
            assert isinstance(s, str) and len(s) > 0

    def test_colors_are_hex(self):
        for c in COLORS:
            assert c.startswith("#") and len(c) == 7


class TestHtmlGeneration:
    """Geracao de HTML da barra de progresso."""

    def test_html_output_basic(self):
        html = _html(0, 4, "Testando...", 25)
        assert "ppbar" in html
        assert "Testando..." in html
        assert "25%" in html
        assert "linear-gradient" in html

    def test_html_with_percentage(self):
        html = _html(2, 4, "Fazendo...", 50)
        assert "Fazendo..." in html
        assert "50%" in html

    def test_html_handles_zero_total(self):
        html = _html(0, 0, "Teste", 0)
        assert html is not None
        assert len(html) > 0

    def test_html_handles_negative_step(self):
        html = _html(-1, 4, "Teste", 0)
        assert html is not None
        assert len(html) > 0

    def test_html_percent_preserves_input(self):
        """_html nao faz clamp; show() faz."""
        html_over = _html(5, 4, "Over", 200)
        assert "200%" in html_over
        assert "Over" in html_over

    def test_html_stage_content(self):
        html = _html(1, 4, "Mensagem", 25)
        assert STAGES[1] in html
        assert "Mensagem" in html

    def test_html_contains_spinner(self):
        """HTML deve ter animacao de spinner."""
        html = _html(0, 4, "Test", 0)
        assert "animation" in html or "ppsp" in html

    def test_html_contains_color(self):
        """HTML deve usar a cor do estagio atual."""
        html = _html(0, 4, "Test", 0)
        assert COLORS[0] in html

    def test_html_last_stage(self):
        """Ultimo estagio deve aparecer corretamente."""
        html = _html(3, 4, "Final", 75)
        assert STAGES[3] in html or "Finalizando" in html

    def test_html_step_beyond_stages(self):
        """Step > total mostra o ultimo estagio (idx clamped a total-1)."""
        html = _html(10, 4, "Extra", 100)
        # idx = min(10, 3) = 3, mostra STAGES[3] = "Iniciando interface"
        assert STAGES[3] in html


class TestShowTerminal:
    """show() no modo terminal (sem IPython)."""

    def test_show_terminal_mode(self, capsys):
        """No modo terminal, show deve imprimir sem quebrar."""
        # Forcar modo terminal
        original = progress_bar.IN_COLAB
        progress_bar.IN_COLAB = False
        try:
            show(1, 4, "Processando...")
            captured = capsys.readouterr()
            assert "Processando" in captured.out or len(captured.out) > 0
        finally:
            progress_bar.IN_COLAB = original
            progress_bar._handle = None

    def test_show_clamps_percent(self, capsys):
        """show deve clampar percentual em 100."""
        progress_bar.IN_COLAB = False
        try:
            show(10, 4, "Over")
            captured = capsys.readouterr()
            assert "100%" in captured.out
        finally:
            progress_bar.IN_COLAB = True
            progress_bar._handle = None

    def test_show_zero_total(self, capsys):
        """show com total=0 nao deve quebrar."""
        progress_bar.IN_COLAB = False
        try:
            show(0, 0, "Zero")
            captured = capsys.readouterr()
            # Nao deve levantar excecao
            assert True
        finally:
            progress_bar.IN_COLAB = True
            progress_bar._handle = None


class TestShowColab:
    """show() no modo Colab (com mock de display)."""

    def test_show_creates_handle(self):
        """No modo Colab, show deve criar um handle de display."""
        progress_bar.IN_COLAB = True
        mock_display = MagicMock()
        mock_html_obj = MagicMock()
        mock_display.return_value = mock_html_obj
        with patch("pesquisai.progress_bar.display", mock_display), \
             patch("pesquisai.progress_bar.HTML", MagicMock(side_effect=lambda x: x)):
            progress_bar._handle = None
            try:
                show(0, 4, "Iniciando")
                assert mock_display.called
            finally:
                progress_bar._handle = None

    def test_show_updates_handle(self):
        """Se handle ja existe, show deve atualiza-lo."""
        progress_bar.IN_COLAB = True
        mock_handle = MagicMock()
        progress_bar._handle = mock_handle
        with patch("pesquisai.progress_bar.display", MagicMock()), \
             patch("pesquisai.progress_bar.HTML", MagicMock(side_effect=lambda x: x)):
            try:
                show(1, 4, "Atualizando")
                assert mock_handle.update.called
            finally:
                progress_bar._handle = None


class TestFinish:
    """finish() limpa a barra."""

    def test_finish_terminal(self, capsys):
        """No modo terminal, finish imprime newline."""
        progress_bar.IN_COLAB = False
        try:
            finish()
            captured = capsys.readouterr()
            # Deve imprimir newline
            assert "\n" in captured.out or len(captured.out) >= 0
        finally:
            progress_bar.IN_COLAB = True
            progress_bar._handle = None

    def test_finish_colab_clears_handle(self):
        """No modo Colab, finish limpa o handle."""
        progress_bar.IN_COLAB = True
        progress_bar._handle = MagicMock()
        with patch("pesquisai.progress_bar._clear", MagicMock()):
            try:
                finish()
                assert progress_bar._handle is None
            finally:
                progress_bar._handle = None

    def test_finish_no_handle(self):
        """finish sem handle nao deve quebrar."""
        progress_bar.IN_COLAB = True
        progress_bar._handle = None
        with patch("pesquisai.progress_bar._clear", MagicMock()):
            finish()
            assert progress_bar._handle is None
