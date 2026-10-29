"""Testes v0.7.8 (ajuste 29/10/2026, SEM bump) — Ctrl+C copia / Ctrl+V cola.

O terminal do UFVAI é um ttyd com xterm.js. Sem esse ajuste, ``Ctrl+C`` virava
``^C`` no PTY e a TUI do opencode **encerrava a conversa** (o sintoma relatado:
"o Ctrl+C termina o terminal"). O contrato testado aqui é o do HTML injetado
via ``--index``:

  • ``Ctrl+C`` copia a seleção e NUNCA chega ao PTY;
  • ``Ctrl+Shift+C`` é a saída de emergência e envia ``\\x03``;
  • ``Ctrl+V`` cola (o xterm deixa de mandar ``^V``/0x16 e o evento
    ``paste`` do navegador é quem entrega o texto);
  • campos de formulário e quem não tem terminal montado ficam intocados.

Os testes abaixo verificam o **conteúdo do script** (sem navegador). O teste
funcional com Chromium/ttyd real fica em ``scripts/diag_clipboard_ttyd.py``.
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pesquisai import launch_app as la


def _js() -> str:
    return la._get_clipboard_script()


class TestScriptInjetado:
    def test_script_e_uma_tag_script_autocontida(self):
        js = _js()
        assert js.lstrip().startswith("<script>")
        assert js.rstrip().endswith("</script>")
        assert js.count("<script>") == 1

    def test_registra_listeners_em_fase_de_captura(self):
        js = _js()
        assert "document.addEventListener('keydown',onKeyDown,true)" in js
        assert "document.addEventListener('paste',onPaste,true)" in js

    def test_usa_api_publica_do_xterm_para_nao_gerar_byte_de_controle(self):
        js = _js()
        # attachCustomKeyEventHandler: evita ^C (0x03) e ^V (0x16) no PTY
        assert "attachCustomKeyEventHandler" in js
        assert "if(k==='c')return false;" in js
        assert "if(k==='v'&&!e.shiftKey)return false;" in js
        # instalação idempotente e com retry (o term só existe depois do boot)
        assert "setInterval(installKeyFilter" in js


class TestCtrlC:
    def test_ctrl_c_sempre_bloqueia_o_evento(self):
        js = _js()
        trecho = js.split("if(k==='c'){", 1)[1].split("// Ctrl+V:", 1)[0]
        assert "e.preventDefault();e.stopImmediatePropagation();" in trecho
        assert trecho.count("e.preventDefault()") == 2  # Ctrl+C e Ctrl+Shift+C

    def test_ctrl_c_copia_a_selecao_do_xterm(self):
        js = _js()
        assert "getSelection()" in js
        assert "navigator.clipboard.writeText" in js
        assert "document.execCommand('copy')" in js  # fallback (iframe sem API)

    def test_ctrl_shift_c_envia_x03_de_verdade(self):
        js = _js()
        assert "sendRaw('\\x03')" in js
        assert "window.__pesquisaiSendToPTY" in js

    def test_dica_quando_nao_ha_selecao_e_com_throttle(self):
        js = _js()
        assert "Nada selecionado" in js
        assert "Ctrl+Shift+C envia Ctrl+C" in js
        assert "if(now-lastHintAt<10000)return;" in js


class TestCtrlV:
    def test_ctrl_v_nao_intercepta_o_atalho_do_navegador(self):
        """Quem cola é o evento ``paste`` — reter o keydown quebraria o xterm."""
        js = _js()
        trecho = js.split("// Ctrl+V:", 1)[1].split("function onPaste", 1)[0]
        assert "preventDefault" not in trecho

    def test_paste_no_terminal_passa_direto_para_o_xterm(self):
        js = _js()
        assert "if(insideTerminal(e.target))return;" in js
        assert "getData('text/plain')" in js

    def test_paste_fora_do_terminal_vai_para_o_pty(self):
        js = _js()
        trecho = js.split("function onPaste", 1)[1]
        assert "pasteText(txt)" in js
        assert "e.preventDefault();e.stopImmediatePropagation();" in trecho

    def test_rede_de_seguranca_da_clipboard_api(self):
        js = _js()
        assert "navigator.clipboard.readText" in js
        assert "},400);" in js
        # não duplica quando o paste nativo já colou
        assert "if(!txt||lastPasteAt>=t0)return;" in js


class TestIntegracaoComTouch:
    def test_inject_junta_touch_e_teclado(self):
        js = la._get_terminal_inject_script()
        # touch/keepalive (já existente)
        assert "ufvai_ttyd_reloads" in js
        assert "window.__pesquisaiSendToPTY=sendToPTY;" in js
        # teclado novo
        assert "attachCustomKeyEventHandler" in js
        assert "Ctrl+C copia" in js
        # ordem: touch primeiro (define sendToPTY), teclado depois
        assert js.index("window.__pesquisaiSendToPTY=sendToPTY;") < js.index("function sendRaw")

    def test_prepare_index_injeta_o_script_combinado(self):
        src = inspect.getsource(la._prepare_ttyd_touch_index)
        assert "_get_terminal_inject_script()" in src

    def test_campos_de_formulario_ficam_intocados(self):
        js = _js()
        assert "isFormField(e.target)" in js
        assert "xterm-helper-textarea" in js


class TestSemBump:
    def test_versao_nao_mudou(self):
        from pesquisai import __version__ as v

        assert v.__version__ == "0.7.8"


class TestCacheDoIndex:
    """O HTML do ttyd não pode ser servido de uma versão anterior do script.

    Bug real (29/10/2026): ``_prepare_ttyd_touch_index`` devolvia o arquivo em
    cache só checando ``os.path.exists``. O ttyd em execução continuou usando
    um HTML de 14:06 (só touch) e o Ctrl+C seguia matando a conversa, mesmo com
    o script novo no módulo.
    """

    def test_fingerprint_tem_16_hex_e_muda_com_o_script(self, monkeypatch):
        fp1 = la._terminal_inject_fingerprint()
        assert len(fp1) == 16 and all(c in "0123456789abcdef" for c in fp1)
        monkeypatch.setattr(la, "_get_terminal_inject_script", lambda: "<script>x</script>")
        assert la._terminal_inject_fingerprint() != fp1

    def test_index_com_a_marca_atual_e_reaproveitado(self, tmp_path):
        p = tmp_path / "ttyd_touch.html"
        marca = la._TTYD_INJECT_MARK % la._terminal_inject_fingerprint()
        p.write_text(
            "<!DOCTYPE html><html><head>" + marca + "<script>touch</script></head></html>",
            encoding="utf-8",
        )
        assert la._ttyd_index_is_current(str(p))
        antigo = la._TTYD_TOUCH_INDEX_PATH
        try:
            la._TTYD_TOUCH_INDEX_PATH = str(p)
            # cache válido → devolve sem subir ttyd temporário (rápido)
            assert la._prepare_ttyd_touch_index({}) == str(p)
        finally:
            la._TTYD_TOUCH_INDEX_PATH = antigo

    def test_index_de_versao_anterior_e_invalidado(self, tmp_path):
        p = tmp_path / "ttyd_touch.html"
        p.write_text(
            "<!DOCTYPE html><html><head><script>// só touch, sem teclado</script></head></html>",
            encoding="utf-8",
        )
        assert not la._ttyd_index_is_current(str(p))

    def test_arquivo_ausente_nao_e_cache(self, tmp_path):
        assert not la._ttyd_index_is_current(str(tmp_path / "nao-existe.html"))

    def test_injecao_grava_a_marca_de_versao(self):
        src = inspect.getsource(la._prepare_ttyd_touch_index)
        assert "_TTYD_INJECT_MARK % _terminal_inject_fingerprint()" in src


class TestSelecaoNaTUI:
    """Bug relatado em 29/10/2026 (mesma sessão, sem bump).

    "Ctrl+C na TUI aparece *nada selecionado*". A TUI do opencode liga a
    captura de mouse (DECSET 1000/1002/1006) e o xterm, nesse estado, DESATIVA
    o serviço de seleção (``CoreMouseService.onProtocolChange`` →
    ``_selectionService.disable()``): arrastar não seleciona e ``getSelection()``
    fica vazio. O Ctrl+C estava certo — não havia seleção alguma.
    """

    def test_arrasto_forca_selecao_via_shift(self):
        js = _js()
        # mousedown sintético com shiftKey: xterm entende como "forçar seleção"
        assert "down.shiftKey=true" in js
        assert "el.dispatchEvent(new MouseEvent('mousedown',down))" in js

    def test_eventos_sinteticos_nao_contam_como_gesto(self):
        assert _js().count("e.isTrusted===false") == 3

    def test_copia_ao_selecionar_no_fim_do_arrasto(self):
        trecho = _js().split("document.addEventListener('mouseup'", 1)[1]
        assert "copyText(txt)" in trecho
        assert "Seleção copiada" in trecho

    def test_guarda_a_ultima_selecao(self):
        js = _js()
        assert "onSelectionChange" in js
        assert "Última seleção copiada" in js

    def test_dica_explica_o_arrasto_quando_a_tui_captura_o_mouse(self):
        assert "arraste para selecionar (ou Shift+arraste)" in _js()

    def test_preserva_barra_de_rolagem_da_tui(self):
        assert "nearRightEdge" in _js()

    def test_kill_switch_para_desligar_o_arrasto(self):
        js = _js()
        assert "window.__ufvaiDragSelect===false" in js
        # vale também EM TEMPO DE EXECUÇÃO (não só no boot): guarda nos 3 handlers
        assert js.count("if(window.__ufvaiDragSelect===false){dragSel.on=false;dragSel.moved=false;return}") == 3


class TestOsc52:
    """A TUI copia por OSC 52; o xterm.js do ttyd não implementa — o bridge
    entrega a cópia ao clipboard do navegador."""

    def test_script_injetado_no_terminal(self):
        inj = la._get_terminal_inject_script()
        assert "OSC 52" in inj
        assert "function scanOsc52" in inj

    def test_ordem_touch_osc52_teclado(self):
        inj = la._get_terminal_inject_script()
        assert inj.index("__pesquisaiSocket") < inj.index("function scanOsc52")
        assert inj.index("function scanOsc52") < inj.index("function sendRaw")

    def test_grava_no_clipboard_com_fallback(self):
        js = la._get_osc52_script()
        assert "navigator.clipboard" in js
        assert "execCommand('copy')" in js
        assert "b64ToText" in js

    def test_consulta_responde_com_o_clipboard(self):
        js = la._get_osc52_script()
        assert "payload==='?'" in js
        assert "navigator.clipboard.readText" in js

    def test_comando_de_limpar_nao_apaga_o_clipboard(self):
        assert "if(payload===''){return}" in la._get_osc52_script()

    def test_remonta_sequencia_cortada_entre_frames(self):
        js = la._get_osc52_script()
        assert "lastIndexOf('\\u001b]52;')" in js
        assert "bytes[0]!==48" in js  # só frames OUTPUT do ttyd
