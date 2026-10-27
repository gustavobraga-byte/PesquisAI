"""Diretório inicial do UFVAI = pasta PesquisAI no Drive (v0.7.7, sem bump).

Relato do autor (27/10/2026): "a versão 0.7.7 quando inicia está no root, deve
iniciar na pasta PesquisAI no drive".

Causa confirmada no runtime: o serviço de background do OpenCode
(``opencode serve --service``) nascia com cwd ``/root`` (kernel do Colab) e as
sessões criadas sem ``location`` herdavam esse diretório — o agente executava
ferramentas em ``/root`` mesmo com o ``cd`` no comando do ttyd.

Cobertura:
  * ``launch_app._project_dir()`` nunca devolve a raiz;
  * ``_spawn_ttyd`` passa ``cwd`` explícito ao ttyd;
  * ``preflight_ufvai_session_info`` cria a sessão com ``location`` explícita;
  * ``ensure_service_project_dir`` é fast-path quando o serviço já está certo.

    pytest -o addopts="" tests/test_v077_start_dir.py -v
"""
from __future__ import annotations

import json
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pesquisai import constants, launch_app as la, run_fast as rf  # noqa: E402


def test_project_dir_prefere_drive(tmp_path, monkeypatch):
    drive = tmp_path / "My Drive" / "PesquisAI"
    drive.mkdir(parents=True)
    home = tmp_path / "home"
    (home / "PesquisAI").mkdir(parents=True)
    monkeypatch.setattr(constants, "DRIVE_PATH", str(drive))
    monkeypatch.setenv("HOME", str(home))

    assert la._workspace_dir() == str(drive)


def test_project_dir_cai_para_home_pesquisai(tmp_path, monkeypatch):
    """Sem Drive (offline/.deb), usa ~/PesquisAI — nunca o cwd do processo."""
    home = tmp_path / "home"
    (home / "PesquisAI").mkdir(parents=True)
    monkeypatch.setattr(constants, "DRIVE_PATH", str(tmp_path / "sem-drive"))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)

    assert la._workspace_dir() == str(home / "PesquisAI")


def test_spawn_ttyd_passa_cwd_do_projeto(tmp_path, monkeypatch):
    drive = tmp_path / "My Drive" / "PesquisAI"
    drive.mkdir(parents=True)
    monkeypatch.setattr(constants, "DRIVE_PATH", str(drive))
    import io
    monkeypatch.setattr(la, "_ttyd_log_file", lambda: io.StringIO())

    captured: dict = {}

    class _FakeProc:
        pid = 1234

        def poll(self):  # pragma: no cover - só contrato
            return None

    def _fake_popen(args, **kwargs):
        captured["args"] = args
        captured.update(kwargs)
        return _FakeProc()

    monkeypatch.setattr(la.subprocess, "Popen", _fake_popen)
    la._spawn_ttyd(["ttyd", "-p", "8000"], {})

    assert captured["cwd"] == str(drive)
    assert captured.get("start_new_session") is True


def test_preflight_cria_sessao_com_location(tmp_path, monkeypatch):
    projeto = tmp_path / "PesquisAI"
    projeto.mkdir()
    monkeypatch.setattr(rf, "find_opencode", lambda: "/usr/bin/opencode")

    seen: dict = {}

    def _fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        return types.SimpleNamespace(
            stdout='{"data": {"id": "ses_teste123", "agent": "UFVAI"}}',
            stderr="",
            returncode=0,
        )

    monkeypatch.setattr(rf.subprocess, "run", _fake_run)
    sid, created = rf.preflight_ufvai_session_info(cwd=str(projeto), timeout_s=2)

    assert sid == "ses_teste123" and created is True
    payload = json.loads(seen["cmd"][seen["cmd"].index("--data") + 1])
    assert payload["location"] == {"directory": os.path.abspath(str(projeto))}
    assert payload["agent"] == "UFVAI"


def test_ensure_service_fast_path(tmp_path, monkeypatch):
    """Serviço já no projeto: não para nem sobe nada."""
    projeto = tmp_path / "PesquisAI"
    projeto.mkdir()
    monkeypatch.setattr(rf, "_service_cwd", lambda: str(projeto))

    chamadas: list = []
    monkeypatch.setattr(
        rf.subprocess, "run",
        lambda *a, **k: chamadas.append(a) or types.SimpleNamespace(stdout="", returncode=0),
    )
    monkeypatch.setattr(
        rf.subprocess, "Popen",
        lambda *a, **k: chamadas.append(("Popen", a)),
    )

    assert rf.ensure_service_project_dir(str(projeto)) is True
    assert chamadas == []


# ── Saudação no idioma do cliente (27/10/2026) ─────────────────────

def test_pref_do_drive_vence_current_lang(monkeypatch):
    """Prefs pt_BR + _current_lang herdado (en_US) → TUI abre em pt_BR."""
    monkeypatch.setattr(la, "_read_prefs", lambda: {"lang": "pt_BR", "lang_source": "user"})
    monkeypatch.setattr(la, "_current_lang", "en_US")
    monkeypatch.setattr(la, "resolve_opencode", lambda: ("/bin/true", {}))
    monkeypatch.setattr(la, "_sync_terminal_locale", lambda *_: None)
    monkeypatch.setattr(la, "preflight_ufvai_session_info", lambda cwd=None: ("ses_x", False))
    monkeypatch.setattr(la, "_build_ttyd_args", lambda args, env: args)

    _args, _env, full = la._build_ttyd_cmd(None, session_id="ses_x", seed_greeting=False)
    assert full == "pt_BR"


def test_fallback_da_saudacao_nao_usa_locale_do_servidor(monkeypatch):
    """Sem cliente, a saudação pendente sai em pt_BR — nunca no en_US do servidor."""
    monkeypatch.setattr(la, "_read_prefs", lambda: {})
    monkeypatch.setattr(la, "_current_lang", "en_US")
    captured: dict = {}
    monkeypatch.setattr(
        la, "_seed_greeting_async",
        lambda sid, lang, delay=0.0: captured.update(sid=sid, lang=lang),
    )
    import time as _time
    la._mark_greeting_pending("ses_fallback_teste", "en_US", fallback_s=1.0)
    _time.sleep(1.4)
    assert captured.get("lang") == "pt_BR"


def test_touch_script_tem_keepalive_e_sem_laco_de_reload():
    """ttyd: keepalive de aplicação (20 s) e reload limitado por sessionStorage."""
    js = la._get_touch_handler_script()
    assert "'1'+JSON.stringify" in js, "keepalive RESIZE ausente"
    assert "ufvai_ttyd_reloads" in js, "limite de reload ausente"
    assert "v.n>=2" in js, "orçamento de reload não aplicado"
