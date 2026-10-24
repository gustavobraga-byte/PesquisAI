# -*- coding: utf-8 -*-
"""Regressão v0.7.5 — abertura com UMA sessão, sem reload e mais rápida.

Relato (23/10/2026): o UFVAI 0.7.5 abria DUAS sessões e recarregava a página
na mesma entrada; às vezes a pergunta "Continuar de onde parei" não aparecia.

Causa [DADO CONFIRMADO] (cadeia):
  1. o backend detectava o idioma pelo locale do servidor (no Colab, en_US)
     e o frontend pelo navegador (pt_BR);
  2. na carga, o frontend chamava ``setLang()`` → ``POST /api/lang``;
  3. o endpoint matava o ttyd e chamava ``preflight_ufvai_session()``, que
     criava OUTRA sessão (``ses_*``) com a saudação;
  4. ao responder, o frontend fazia ``location.reload()`` — e a marca de
     "já mostrei a pergunta de retomada" (12 h no localStorage) podia ser
     gravada antes de o usuário responder, queimando a pergunta.

Estes testes travam o contrato novo:

  * ``preflight_ufvai_session_info()`` reaproveita a sessão na mesma execução
    e informa se ela é nova (a saudação só é semeada em sessão nova);
  * ``/api/lang`` aceita ``restart: false`` (adoção silenciosa) e não
    reinicia nada quando o idioma não mudou;
  * o bloco de sincronização do frontend NÃO chama ``setLang`` nem
    ``location.reload``;
  * a marca de abertura é escopada por execução (novo ``boot_id`` a cada
    ``create_wrapper_html``).
"""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from pesquisai import run_fast as rf  # noqa: E402


# ── 1. preflight: reaproveita a sessão (não cria a 2ª) ────────────────────
class _FakeCompleted:
    def __init__(self, stdout: str):
        self.stdout = stdout
        self.returncode = 0
        self.stderr = ""


def test_preflight_reaproveita_sessao_na_mesma_execucao(monkeypatch):
    calls: list[list[str]] = []
    sid = "ses_abcdef123456ABCDEF12345678"

    monkeypatch.setattr(rf, "find_opencode", lambda: "/usr/bin/opencode")

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        if "post" in cmd:
            return _FakeCompleted('{"data":{"id":"%s"}}' % sid)
        return _FakeCompleted('{"data":{"agent":"UFVAI"}}')

    monkeypatch.setattr(rf.subprocess, "run", fake_run)
    rf.reset_preflight_cache()

    got, created = rf.preflight_ufvai_session_info(cwd="/tmp/ufvai-teste", timeout_s=2)
    assert got == sid and created is True
    assert len(calls) == 2  # POST + GET de validação

    got2, created2 = rf.preflight_ufvai_session_info(cwd="/tmp/ufvai-teste", timeout_s=2)
    assert got2 == sid and created2 is False
    assert len(calls) == 2, "a 2ª chamada NÃO pode criar/validar outra sessão"


def test_remember_preflight_pins_restored_session(monkeypatch):
    rf.reset_preflight_cache()
    restored = "ses_001122334455ABCDEF12345678"
    rf.remember_preflight_session(restored, cwd="/tmp/ufvai-restore")

    def explode(*_a, **_k):
        raise AssertionError("não deveria consultar o motor")

    monkeypatch.setattr(rf.subprocess, "run", explode)
    got, created = rf.preflight_ufvai_session_info(cwd="/tmp/ufvai-restore", timeout_s=2)
    assert got == restored and created is False


# ── 2. contrato do backend ────────────────────────────────────────────────
def _read(rel: str) -> str:
    with open(os.path.join(ROOT, "pesquisai", rel), encoding="utf-8") as fh:
        return fh.read()


def test_preflight_pula_get_quando_post_ja_traz_agent(monkeypatch):
    calls: list[list[str]] = []
    sid = "ses_abcdef123456ABCDEF12345678"
    monkeypatch.setattr(rf, "find_opencode", lambda: "/usr/bin/opencode")

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        return _FakeCompleted('{"data":{"id":"%s","agent":"UFVAI"}}' % sid)

    monkeypatch.setattr(rf.subprocess, "run", fake_run)
    rf.reset_preflight_cache()
    got, created = rf.preflight_ufvai_session_info(cwd="/tmp/ufvai-posto", timeout_s=2)
    assert got == sid and created is True
    assert len(calls) == 1, "POST com agent não precisa do GET de validação"


def test_api_lang_aceita_restart_false_e_nao_reinicia_sem_mudanca():
    src = _read("launch_app.py")
    # o primeiro `if p == "/api/lang":` é o GET; o POST é o que lê `body`.
    start = src.find('if p == "/api/lang":', src.find("def _do_POST_impl"))
    assert start > 0
    bloco = src[start:src.find('if p == "/api/backups":', start)]
    assert 'body.get("restart"' in bloco
    assert "_set_lang_only(full_lang)" in bloco
    assert "if not changed and _wait_port_open" in bloco
    assert '"restarted": False' in bloco


def test_build_ttyd_so_semeia_saudacao_em_sessao_nova():
    src = _read("launch_app.py")
    i = src.find("def _build_ttyd_cmd(")
    bloco = src[i:src.find("def start_ttyd(", i)]
    assert "if created and seed_greeting:" in bloco
    assert "preflight_ufvai_session_info" in bloco
    assert "_current_ttyd_session = str(session_id)" in bloco


def test_restart_por_idioma_reabre_a_sessao_atual():
    src = _read("launch_app.py")
    i = src.find("def restart_ttyd_with_lang(")
    bloco = src[i:src.find("\ndef ", i + 10)]
    assert "session_id=_current_ttyd_session" in bloco


def test_restore_e_run_terminal_fixam_a_sessao_exibida():
    src = _read("launch_app.py")
    assert "def _remember_ttyd_session(" in src
    i = src.find("def _remember_ttyd_session(")
    bloco = src[i:i + 600]
    assert "global _current_ttyd_session" in bloco
    assert "remember_preflight_session(sid)" in bloco
    # restore e run_terminal usam o helper (não só o cache do preflight)
    assert src.count("_remember_ttyd_session(") >= 4  # def + restore + 2 no run_terminal


def test_agente_nao_e_regravado_em_cada_spawn():
    src = _read("launch_app.py")
    i = src.find("def _ensure_ufvai_agent_before_spawn(")
    bloco = src[i:src.find("def _set_lang_only(", i)]
    assert "_AGENT_ENSURE_TTL_S" in bloco
    assert "if (now - _LAST_AGENT_ENSURE) < _AGENT_ENSURE_TTL_S" in bloco


# ── 3. contrato do frontend ───────────────────────────────────────────────
def _render(boot_id: str | None = None) -> str:
    path = os.path.join(ROOT, "pesquisai", "launch_app_responsive_v041.py")
    spec = importlib.util.spec_from_file_location("ufvai_resp_teste", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ufvai_resp_teste"] = mod
    spec.loader.exec_module(mod)
    mod.WRAPPER_DIR = tempfile.mkdtemp(prefix="ufvai-teste-")
    return mod.create_wrapper_html(
        "http://localhost:8000", "https://drive.google.com", boot_id=boot_id
    )


def test_boot_id_e_injetado_e_muda_entre_execucoes():
    html_a = _render()
    html_b = _render()
    assert "{__BOOT_ID__}" not in html_a
    assert "const UFVAI_BOOT_ID" in html_a
    assert html_a != html_b  # IDs diferentes → nova execução volta a abrir as telas


def test_boot_id_explicito_e_respeitado():
    html = _render(boot_id="abc123def456")
    assert 'const UFVAI_BOOT_ID = "abc123def456"' in html


def test_sync_de_idioma_nao_reinicia_nem_recarrega():
    html = _render(boot_id="abc123def456")
    i = html.find("// v0.6.15 — ADOÇÃO SILENCIOSA")
    j = html.find("try {", i)
    k = html.find("// 2. Carrega tema", j)
    bloco = html[j:k]
    assert "restart: false" in bloco
    assert "setLang(" not in bloco
    assert "location.reload" not in bloco


def test_navegador_em_chines_mapeia_para_zh_CN():
    html = _render(boot_id="abc123def456")
    assert 'if (nav.startsWith("zh")) return "zh_CN";' in html


def test_retomada_guarda_por_execucao_e_nao_consome():
    html = _render(boot_id="abc123def456")
    assert "function markAutosaveResumeOffered()" in html
    i = html.find("function showAutosaveResume(item)")
    bloco = html[i:i + 900]
    assert bloco.index("markAutosaveResumeOffered") < bloco.index('classList.add("open")')
    j = html.find("async function checkAutosaveResume()")
    check = html[j:j + 900]
    assert 'ufvaiOpeningGet("resume")' in check
    assert check.index("ufvaiOpeningGet") < check.index("fetch(")
    assert "ufvaiOpeningClear" not in check
