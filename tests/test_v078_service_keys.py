"""Chaves de API do Drive chegam ao SERVIÇO do motor (v0.7.8).

Relato do autor (29/10/2026): "o UFVAI não está carregando as chaves de API
que estão no Drive. Aconteceu depois que o opencode atualizou para a v2.2".

Causa confirmada no runtime: o ``opencode serve --service`` nasce no boot
**antes** de ``start_wrapper_server()`` chamar ``load_keys_from_drive()`` e,
portanto, sem nenhuma variável de chave no próprio ambiente. Até o motor 2.1
isso não aparecia porque a TUI resolvia provedores com o ambiente dela (que
herda o ``~/.bashrc``); na **v2.2 o catálogo de provedores é resolvido DENTRO
do serviço**. Medido nesta máquina:

    opencode models                (via serviço) → opencode, opencode-go
    opencode models --standalone   (env do shell) → + openrouter, google, nvidia

Cobertura:
  * ``keys_env_from_store`` traduz o store cifrado em variáveis de ambiente;
  * ``service_missing_key_envs`` detecta serviço sem as chaves (auto-cura);
  * ``ensure_service_project_dir`` injeta as chaves no Popen do serviço e
    reinicia o serviço quando ele está no diretório certo mas sem chaves;
  * ``_apply_opencode_env_change_async`` reergue o serviço com as chaves.

    pytest -o addopts="" tests/test_v078_service_keys.py -v
"""
from __future__ import annotations

import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pesquisai import launch_app as la, opencode_utils as ou, run_fast as rf  # noqa: E402

FAKE_VALUE = "fake-key-value-1234567890"


def _store(tmp_path, provider="fake_provider", var="FAKE_KEY"):
    """Grava um keys_store.json cifrado de teste e devolve a pasta."""
    from pesquisai.security import save_encrypted_keys

    backup = tmp_path / "backups"
    backup.mkdir(parents=True, exist_ok=True)
    assert save_encrypted_keys(
        str(backup), {provider: FAKE_VALUE, f"_env_{provider}": var}
    )
    return backup


# ── Leitura do store ──────────────────────────────────────────────

def test_keys_env_from_store_traduz_metadados(tmp_path):
    backup = _store(tmp_path)
    assert ou.keys_env_from_store(str(backup)) == {"FAKE_KEY": FAKE_VALUE}


def test_keys_env_from_store_sem_store(tmp_path):
    assert ou.keys_env_from_store(str(tmp_path / "nao-existe")) == {}


def test_keys_env_from_store_ignora_valor_vazio(tmp_path):
    from pesquisai.security import save_encrypted_keys

    backup = tmp_path / "backups"
    backup.mkdir(parents=True)
    save_encrypted_keys(
        str(backup), {"fake_provider": "", "_env_fake_provider": "FAKE_KEY"}
    )
    assert ou.keys_env_from_store(str(backup)) == {}


# ── Detecção no serviço ───────────────────────────────────────────

def test_service_missing_detecta_variavel_ausente(tmp_path, monkeypatch):
    backup = _store(tmp_path)
    monkeypatch.setattr(ou, "service_pids", lambda: ["4242"])
    monkeypatch.setattr(ou, "service_env", lambda pid: {"PATH": "/usr/bin"})
    assert ou.service_missing_key_envs(str(backup)) == ["FAKE_KEY"]


def test_service_missing_ok_quando_servico_tem_a_chave(tmp_path, monkeypatch):
    backup = _store(tmp_path)
    monkeypatch.setattr(ou, "service_pids", lambda: ["4242"])
    monkeypatch.setattr(ou, "service_env", lambda pid: {"FAKE_KEY": FAKE_VALUE})
    assert ou.service_missing_key_envs(str(backup)) == []


def test_service_missing_sem_servico(tmp_path, monkeypatch):
    backup = _store(tmp_path)
    monkeypatch.setattr(ou, "service_pids", lambda: [])
    assert ou.service_missing_key_envs(str(backup)) == []


def test_service_missing_sem_store(tmp_path, monkeypatch):
    monkeypatch.setattr(ou, "service_pids", lambda: ["4242"])
    assert ou.service_missing_key_envs(str(tmp_path)) == []


# ── ensure_service_project_dir ────────────────────────────────────

def test_ensure_service_injeta_chaves_no_popen(tmp_path, monkeypatch):
    """O Popen do serviço recebe as variáveis de chave do Drive."""
    projeto = tmp_path / "PesquisAI"
    projeto.mkdir()
    _store(projeto)

    monkeypatch.setattr(rf, "_service_cwd", lambda: None)
    monkeypatch.setattr(ou, "service_pids", lambda: [])
    monkeypatch.setattr(
        rf.subprocess, "run",
        lambda *a, **k: types.SimpleNamespace(stdout="http://127.0.0.1:4096", returncode=0),
    )

    capturado: dict = {}

    def _popen(cmd, **kw):
        capturado["cmd"] = cmd
        capturado["env"] = kw.get("env") or {}
        capturado["cwd"] = kw.get("cwd")
        return types.SimpleNamespace(pid=1)

    monkeypatch.setattr(rf.subprocess, "Popen", _popen)
    monkeypatch.delenv("FAKE_KEY", raising=False)

    try:
        assert rf.ensure_service_project_dir(str(projeto)) is True
        assert capturado["cwd"] == str(projeto)
        assert capturado["env"].get("FAKE_KEY") == FAKE_VALUE
        assert os.environ.get("FAKE_KEY") == FAKE_VALUE  # resto do boot também vê
    finally:
        os.environ.pop("FAKE_KEY", None)


def test_ensure_service_nao_reinicia_quando_tudo_certo(tmp_path, monkeypatch):
    projeto = tmp_path / "PesquisAI"
    projeto.mkdir()
    _store(projeto)

    monkeypatch.setattr(rf, "_service_cwd", lambda: str(projeto))
    monkeypatch.setattr(ou, "service_pids", lambda: ["4242"])
    monkeypatch.setattr(ou, "service_env", lambda pid: {"FAKE_KEY": FAKE_VALUE})

    chamadas: list = []
    monkeypatch.setattr(rf.subprocess, "run", lambda *a, **k: chamadas.append(a))
    monkeypatch.setattr(rf.subprocess, "Popen",
                        lambda *a, **k: chamadas.append(("Popen", a)))
    monkeypatch.delenv("FAKE_KEY", raising=False)

    try:
        assert rf.ensure_service_project_dir(str(projeto)) is True
        assert chamadas == []  # fast-path: nem stop, nem spawn
    finally:
        os.environ.pop("FAKE_KEY", None)


def test_ensure_service_reinicia_quando_servico_sem_chaves(tmp_path, monkeypatch):
    """Serviço no diretório certo, mas nascido sem chaves → precisa renascer."""
    projeto = tmp_path / "PesquisAI"
    projeto.mkdir()
    _store(projeto)

    monkeypatch.setattr(rf, "_service_cwd", lambda: str(projeto))
    monkeypatch.setattr(ou, "service_pids", lambda: ["4242"])
    monkeypatch.setattr(ou, "service_env", lambda pid: {"PATH": "/usr/bin"})
    monkeypatch.setattr(
        rf.subprocess, "run",
        lambda *a, **k: types.SimpleNamespace(stdout="http://127.0.0.1:4096", returncode=0),
    )

    acoes: list = []
    monkeypatch.setattr(rf.subprocess, "Popen", lambda cmd, **k: acoes.append(cmd))
    monkeypatch.delenv("FAKE_KEY", raising=False)

    try:
        assert rf.ensure_service_project_dir(str(projeto)) is True
        assert acoes and acoes[0][1:3] == ["serve", "--service"]
    finally:
        os.environ.pop("FAKE_KEY", None)


def test_ensure_service_fallback_para_pasta_local(tmp_path, monkeypatch):
    """Store só em ~/PesquisAI/backups (offline) também é encontrado."""
    home = tmp_path / "home"
    (home / "PesquisAI").mkdir(parents=True)
    _store(home / "PesquisAI")
    projeto = tmp_path / "projeto-sem-store"
    projeto.mkdir()

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(rf, "_service_cwd", lambda: None)
    monkeypatch.setattr(ou, "service_pids", lambda: [])
    monkeypatch.setattr(
        rf.subprocess, "run",
        lambda *a, **k: types.SimpleNamespace(stdout="http://127.0.0.1:4096", returncode=0),
    )
    capturado: dict = {}
    monkeypatch.setattr(
        rf.subprocess, "Popen",
        lambda cmd, **kw: capturado.update(env=kw.get("env") or {}) or types.SimpleNamespace(pid=1),
    )
    monkeypatch.delenv("FAKE_KEY", raising=False)

    try:
        assert rf.ensure_service_project_dir(str(projeto)) is True
        assert capturado["env"].get("FAKE_KEY") == FAKE_VALUE
    finally:
        os.environ.pop("FAKE_KEY", None)


# ── Reinício do serviço ao salvar/remover chave ───────────────────

def test_start_service_usa_a_pasta_de_chaves_resolvida(tmp_path, monkeypatch):
    monkeypatch.setattr(la, "_KEYS_BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setattr(la, "_workspace_dir", lambda: str(tmp_path))

    visto: dict = {}

    def _fake_ensure(project, timeout_s=20.0, backup_dir=None):
        visto["project"] = project
        visto["backup_dir"] = backup_dir
        return True

    monkeypatch.setitem(
        sys.modules,
        "pesquisai.run_fast",
        types.SimpleNamespace(ensure_service_project_dir=_fake_ensure),
    )

    assert la._start_opencode_service_with_keys() is True
    assert visto["backup_dir"] == str(tmp_path / "backups")


def test_apply_env_change_reergue_servico(monkeypatch):
    ordem: list = []
    monkeypatch.setattr(la, "_shutdown_stop_opencode_service", lambda: ordem.append("stop"))
    monkeypatch.setattr(la, "_start_opencode_service_with_keys",
                        lambda *a, **k: ordem.append("start") or True)
    monkeypatch.setattr(la, "restart_ttyd_with_lang", lambda lang: ordem.append("ttyd"))

    la._apply_opencode_env_change_async()
    import time
    for _ in range(300):
        if "ttyd" in ordem:
            break
        time.sleep(0.01)

    assert ordem == ["stop", "start", "ttyd"]


def test_keys_backup_dir_usa_global(tmp_path, monkeypatch):
    monkeypatch.setattr(la, "_KEYS_BACKUP_DIR", str(tmp_path / "b"))
    assert la._keys_backup_dir() == str(tmp_path / "b")


def test_diag_script_nao_expoe_segredo(tmp_path):
    """O script de diagnóstico lista nomes de variáveis, nunca valores."""
    import subprocess as sp
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    r = sp.run(
        [sys.executable, os.path.join(raiz, "scripts", "diag_keys_v22.py"),
         "--backup-dir", str(tmp_path / "vazio"), "--json"],
        capture_output=True, text=True, timeout=120,
    )
    assert FAKE_VALUE not in r.stdout
    assert "env_vars_expected" in r.stdout
