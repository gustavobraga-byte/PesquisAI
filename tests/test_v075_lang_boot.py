"""Idioma no boot + saudação no idioma do cliente (v0.7.5, sem bump).

Cobre o relato do autor (24/10/2026):

  * "está carregando sempre em inglês" — o backend detectava o idioma pelo
    locale do SERVIDOR (no Colab, ``en_US``) e o ``~/.config`` não sobrevive
    ao reinício do ambiente;
  * "quando troca o idioma tem que injetar a mensagem padrão da língua" —
    a saudação só era semeada em sessão nova, no spawn do ttyd;
  * "o carregamento deve ser mais otimizado" — o boot semeava a saudação
    (processo de LLM) junto com o TUI e a interface só se traduzia em
    ``window.load``.

    pytest -o addopts="" tests/test_v075_lang_boot.py -v
"""
from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pesquisai import launch_app as la  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(rel: str) -> str:
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


@pytest.fixture()
def prefs_tmp(tmp_path, monkeypatch):
    """Isola prefs e cookie local em tmp_path (nunca toca no Drive real)."""
    prefs = tmp_path / "config" / "prefs.json"
    cookie = tmp_path / "pesquisai_lang"
    monkeypatch.setattr(la, "_prefs_path", lambda: str(prefs))
    monkeypatch.setattr(la, "_LANG_COOKIE_FILE", str(cookie))
    monkeypatch.setattr(la, "_current_lang", "")
    monkeypatch.delenv("PESQUISAI_LANG", raising=False)
    return {"prefs": prefs, "cookie": cookie}


# ── 1. preferência persistida no Drive ──────────────────────────────────
class TestPrefsNoDrive:
    def test_persist_lang_grava_no_drive_quando_e_escolha(self, prefs_tmp):
        la._persist_lang("pt_BR", source="browser")
        data = json.loads(prefs_tmp["prefs"].read_text(encoding="utf-8"))
        assert data == {"lang": "pt_BR", "lang_source": "browser"}
        assert prefs_tmp["cookie"].read_text(encoding="utf-8") == "pt_BR"

    def test_deteccao_automatica_nao_vira_escolha(self, prefs_tmp):
        la._persist_lang("en_US", source="auto")
        assert not prefs_tmp["prefs"].exists()
        assert prefs_tmp["cookie"].read_text(encoding="utf-8") == "en_US"

    def test_prefs_do_drive_ganha_do_cookie_local(self, prefs_tmp):
        prefs_tmp["prefs"].parent.mkdir(parents=True, exist_ok=True)
        prefs_tmp["prefs"].write_text('{"lang": "fr_FR"}', encoding="utf-8")
        prefs_tmp["cookie"].write_text("en_US", encoding="utf-8")
        assert la._ensure_lang_initialized() == "fr_FR"

    def test_env_explicito_ganha_de_tudo(self, prefs_tmp, monkeypatch):
        prefs_tmp["prefs"].parent.mkdir(parents=True, exist_ok=True)
        prefs_tmp["prefs"].write_text('{"lang": "fr_FR"}', encoding="utf-8")
        monkeypatch.setenv("PESQUISAI_LANG", "es_ES")
        assert la._ensure_lang_initialized() == "es_ES"

    def test_sem_preferencia_detecta_o_sistema(self, prefs_tmp):
        assert la._ensure_lang_initialized() in la._LANG_MAP.values()

    def test_prefs_ilegivel_nao_derruba_o_boot(self, prefs_tmp):
        prefs_tmp["prefs"].parent.mkdir(parents=True, exist_ok=True)
        prefs_tmp["prefs"].write_text("{corrompido", encoding="utf-8")
        prefs_tmp["cookie"].write_text("es_ES", encoding="utf-8")
        assert la._ensure_lang_initialized() == "es_ES"


# ── 2. saudação pendente (idioma do cliente) ───────────────────────────
class TestSaudacaoPendente:
    def test_ciclo_pendente_consome_uma_vez(self, monkeypatch):
        seeds = []
        monkeypatch.setattr(la, "_seed_greeting_async",
                            lambda sid, lang, delay=0.0: seeds.append((sid, lang)))
        monkeypatch.setitem(la._PENDING_GREETING, "ses_teste", True)
        assert la._greeting_pending("ses_teste") is True
        assert la._consume_greeting("ses_teste", "pt_BR") is True
        assert la._consume_greeting("ses_teste", "pt_BR") is False
        assert seeds == [("ses_teste", "pt_BR")]

    def test_sem_sessao_nao_semeia(self, monkeypatch):
        seeds = []
        monkeypatch.setattr(la, "_seed_greeting_async",
                            lambda *a, **k: seeds.append(a))
        assert la._consume_greeting(None, "pt_BR") is False
        assert seeds == []

    def test_seed_usa_a_saudacao_do_idioma(self, monkeypatch):
        """O seed leva a saudação do idioma pedido e o binário resolvido."""
        from pesquisai.__version__ import get_greeting
        capturado = {}

        class _Timer:
            def __init__(self, delay, fn):
                self.fn = fn

            def start(self):
                self.fn()

        def fake_seed(session_id, greeting, timeout_s=25.0, opencode_bin=None,
                      env=None, cwd=None):
            capturado.update({"sid": session_id, "greeting": greeting,
                              "bin": opencode_bin, "cwd": cwd})
            return True

        monkeypatch.setattr(la, "resolve_opencode", lambda: ("/bin/opencode", {}))
        monkeypatch.setattr(la, "seed_ufvai_greeting", fake_seed)
        monkeypatch.setattr(la.threading, "Timer", _Timer)
        la._seed_greeting_async("ses_x", "en_US", delay=0)
        assert capturado["sid"] == "ses_x"
        assert capturado["bin"] == "/bin/opencode"
        assert capturado["cwd"], "o seed precisa rodar no diretório do projeto"
        assert capturado["greeting"] == get_greeting("en_US")
        assert get_greeting("en_US").split("!")[0] == "Hello"

    def test_primeira_execucao_espera_o_cliente(self, monkeypatch):
        """Sem preferência salva, a saudação fica pendente para o cliente."""
        pend, seeds = [], []
        monkeypatch.setattr(la, "_mark_greeting_pending",
                            lambda sid, lang, fallback_s=8.0: pend.append(sid))
        monkeypatch.setattr(la, "_seed_greeting_async",
                            lambda sid, lang, delay=0.0: seeds.append(sid))
        monkeypatch.setattr(la, "_read_prefs", lambda: {})
        monkeypatch.setattr(la, "resolve_opencode", lambda: ("/bin/opencode", {}))
        monkeypatch.setattr(la, "preflight_ufvai_session_info",
                            lambda **k: ("ses_nova", True))
        monkeypatch.setattr(la, "_spawn_ttyd", lambda *a, **k: None)
        monkeypatch.setattr(la, "_current_lang", "pt_BR")
        la._build_ttyd_cmd("pt_BR")
        assert pend == ["ses_nova"] and seeds == []
        assert la._current_ttyd_session == "ses_nova"

    def test_tui_abre_no_idioma_resolvido(self, monkeypatch):
        """O locale da TUI é escrito no spawn — não só ao trocar o idioma."""
        syncs = []
        monkeypatch.setattr(la, "_sync_terminal_locale", lambda lang: syncs.append(lang))
        monkeypatch.setattr(la, "_read_prefs", lambda: {"lang": "pt_BR"})
        monkeypatch.setattr(la, "_seed_greeting_async", lambda *a, **k: None)
        monkeypatch.setattr(la, "resolve_opencode", lambda: ("/bin/opencode", {}))
        monkeypatch.setattr(la, "preflight_ufvai_session_info", lambda **k: ("ses_x", True))
        monkeypatch.setattr(la, "_spawn_ttyd", lambda *a, **k: None)
        la._build_ttyd_cmd("pt_BR")
        assert syncs == ["pt_BR"]

    def test_com_preferencia_semeia_no_boot(self, monkeypatch):
        """Usuário conhecido: a saudação sai já no boot, no idioma do Drive."""
        pend, seeds = [], []
        monkeypatch.setattr(la, "_mark_greeting_pending",
                            lambda sid, lang, fallback_s=8.0: pend.append(sid))
        monkeypatch.setattr(la, "_seed_greeting_async",
                            lambda sid, lang, delay=0.0: seeds.append((sid, lang)))
        monkeypatch.setattr(la, "_read_prefs", lambda: {"lang": "pt_BR"})
        monkeypatch.setattr(la, "resolve_opencode", lambda: ("/bin/opencode", {}))
        monkeypatch.setattr(la, "preflight_ufvai_session_info",
                            lambda **k: ("ses_nova", True))
        monkeypatch.setattr(la, "_spawn_ttyd", lambda *a, **k: None)
        monkeypatch.setattr(la, "_current_lang", "pt_BR")
        la._build_ttyd_cmd("pt_BR")
        assert seeds == [("ses_nova", "pt_BR")] and pend == []


# ── 3. endpoint /api/lang ──────────────────────────────────────────────
class TestEndpointLang:
    def test_get_informa_saudacao_pendente(self):
        src = _read("pesquisai/launch_app.py")
        assert '"greeting_pending": _greeting_pending(_current_ttyd_session)' in src

    def test_restart_false_consome_a_pendencia(self):
        src = _read("pesquisai/launch_app.py")
        start = src.find('if p == "/api/lang":', src.find("def _do_POST_impl"))
        bloco = src[start:src.find('if p == "/api/backups":', start)]
        assert "_set_lang_only(full_lang, source=_source)" in bloco
        assert "seeded = _consume_greeting(_current_ttyd_session, full_lang)" in bloco

    def test_troca_de_idioma_injeta_a_mensagem(self):
        src = _read("pesquisai/launch_app.py")
        start = src.find('if p == "/api/lang":', src.find("def _do_POST_impl"))
        bloco = src[start:src.find('if p == "/api/backups":', start)]
        assert "_seed_greeting_async(_current_ttyd_session, full_lang, delay=1.0)" in bloco

    def test_get_informa_a_origem_do_idioma(self):
        src = _read("pesquisai/launch_app.py")
        assert '"lang_source": str(_prefs_lang.get("lang_source") or "auto")' in src

    def test_dica_do_navegador_nao_sobrescreve_escolha_do_usuario(self):
        src = _read("pesquisai/launch_app.py")
        start = src.find('if p == "/api/lang":', src.find("def _do_POST_impl"))
        bloco = src[start:src.find('if p == "/api/backups":', start)]
        assert '_source = str(body.get("source") or "browser")' in bloco
        assert '_prefs_now.get("lang_source") or "") == "user"' in bloco
        assert '"ignored": True' in bloco

    def test_restart_persiste_como_escolha_do_usuario(self):
        src = _read("pesquisai/launch_app.py")
        bloco = src[src.find("def restart_ttyd_with_lang"):]
        bloco = bloco[:bloco.find("def ", 10)]
        assert '_persist_lang(lang, source="user")' in bloco


class TestDeteccaoNoNavegador:
    """O cookie automático não pode vencer o idioma do navegador."""

    def test_cookie_automatico_nao_vence_o_navegador(self):
        src = _read("pesquisai/launch_app_responsive_v041.py")
        assert "function browserLang()" in src
        assert 'getCookie(LANG_SRC_COOKIE) === "user"' in src
        # a ordem: navegador ANTES do cookie automático
        i_nav = src.find("const nav = browserLang();")
        i_auto = src.find("gravados automaticamente (fallback)")
        assert i_nav > 0 and i_auto > i_nav

    def test_setlang_marca_escolha_explicita(self):
        src = _read("pesquisai/launch_app_responsive_v041.py")
        bloco = src[src.find("async function setLang(lang)"):]
        bloco = bloco[:bloco.find("function buildLangMenu")]
        assert 'setCookie(LANG_SRC_COOKIE, "user")' in bloco

    def test_adocao_envia_source_browser(self):
        src = _read("pesquisai/launch_app_responsive_v041.py")
        assert 'source: "browser"' in src

    def test_lista_de_idiomas_do_navegador(self):
        src = _read("pesquisai/launch_app_responsive_v041.py")
        assert "navigator.languages" in src


# ── 4. carregamento mais leve ──────────────────────────────────────────
class TestCarregamento:
    def test_init_roda_em_domcontentloaded(self):
        src = _read("pesquisai/launch_app_responsive_v041.py")
        assert "document.addEventListener(\"DOMContentLoaded\", _ufvaiInit" in src
        assert "function _ufvaiInit()" in src

    def test_pergunta_de_retomada_em_350ms(self):
        src = _read("pesquisai/launch_app_responsive_v041.py")
        assert "setTimeout(() => checkAutosaveResume(), 350)" in src

    def test_html_servido_com_gzip(self, tmp_path):
        """300 KB de HTML viram ~75 KB no proxy do Colab."""
        idx = tmp_path / "index.html"
        idx.write_text("<html>" + "x" * 50_000 + "</html>", encoding="utf-8")
        raw, gz = la._index_payload(str(idx))
        assert raw.startswith(b"<html>")
        assert len(gz) < len(raw) / 2
        import gzip as _gzip
        assert _gzip.decompress(gz) == raw
        # cache: segunda chamada não relê o arquivo
        raw2, gz2 = la._index_payload(str(idx))
        assert raw2 is raw and gz2 is gz
        # arquivo novo (mtime/tamanho) invalida
        idx.write_text("<html>novo</html>", encoding="utf-8")
        raw3, _ = la._index_payload(str(idx))
        assert raw3 != raw

    def test_handler_negocia_gzip(self):
        src = _read("pesquisai/launch_app.py")
        assert 'self.send_header("Content-Encoding", "gzip")' in src
        assert 'self.send_header("Vary", "Accept-Encoding")' in src

    def test_css_externo_nao_bloqueia_a_renderizacao(self):
        src = _read("pesquisai/launch_app_responsive_v041.py")
        assert 'rel="stylesheet" media="print" onload="this.media=\'all\'"' in src
        # nenhuma dessas folhas pode voltar a ser bloqueante
        assert 'github-markdown-dark.min.css">' not in src
        assert 'display=swap" rel="stylesheet">' not in src


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v", "-o", "addopts="]))
