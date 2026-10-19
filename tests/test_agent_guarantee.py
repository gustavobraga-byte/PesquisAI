"""Garantia "terminal SEMPRE carrega o agente UFVAI" (v0.6.21 + ajustes v0.6.22).

Cobre:
- `merge_agent_policy`/`ensure_ufvai_agent` — default_agent + build/plan disabled;
- `preflight_ufvai_session` (v0.6.22b, 15/10/2026 — SEM bump) — pré-cria a
  sessão do terminal já presa ao UFVAI, pois o TUI criava a sessão nova com
  o agente `build` na primeira mensagem;
- `_build_ttyd_cmd` — usa `--session` quando o preflight responde e cai no
  comportamento anterior quando não responde (best-effort, nunca bloqueia).
"""

import json
import subprocess

import pytest

import pesquisai.launch_app as la
import pesquisai.run_fast as rf
from pesquisai.opencode_config import (
    load_json_config,
    merge_agent_policy,
    write_json_atomic,
)


# ── Política do agente (v0.6.22) ──────────────────────────────

class TestMergeAgentPolicy:
    def test_sets_default_and_disables_build_plan(self):
        cfg = {"$schema": "https://opencode.ai/config.json", "model": "x/y"}
        merged = merge_agent_policy(cfg, "UFVAI")
        assert merged["default_agent"] == "UFVAI"
        assert merged["agents"]["build"]["disabled"] is True
        assert merged["agents"]["plan"]["disabled"] is True
        # preserva chaves não relacionadas
        assert merged["model"] == "x/y"

    def test_preserves_existing_agent_config(self):
        cfg = {"agents": {"build": {"permissions": [{"action": "shell", "resource": "git status", "effect": "allow"}]}}}
        merged = merge_agent_policy(cfg, "UFVAI")
        assert merged["agents"]["build"]["permissions"][0]["resource"] == "git status"
        assert merged["agents"]["build"]["disabled"] is True

    def test_does_not_mutate_input(self):
        cfg = {}
        _ = merge_agent_policy(cfg, "UFVAI")
        assert cfg == {}


class TestEnsureUfvaiAgent:
    def test_writes_policy_and_agent(self, tmp_path, monkeypatch):
        agent_dir = tmp_path / "agents"
        monkeypatch.setattr(rf, "AGENT_DIR", str(agent_dir))
        monkeypatch.setattr(rf, "OPENCODE_CFG", str(tmp_path / "opencode.json"))
        monkeypatch.setattr(rf, "AGENT_FILE", "UFVAI.md")
        # categoria:_agents não existe → cria
        ok = rf.ensure_ufvai_agent()
        assert ok is True
        ok_cfg, cfg = load_json_config(str(tmp_path / "opencode.json"))
        assert ok_cfg
        assert cfg["default_agent"] == "UFVAI"
        assert cfg["agents"]["build"]["disabled"] is True
        assert (agent_dir / "UFVAI.md").exists()

    def test_idempotent_second_call(self, tmp_path, monkeypatch):
        for _ in range(2):
            monkeypatch.setattr(rf, "AGENT_DIR", str(tmp_path / "agents"))
            monkeypatch.setattr(rf, "OPENCODE_CFG", str(tmp_path / "opencode.json"))
            monkeypatch.setattr(rf, "AGENT_FILE", "UFVAI.md")
            assert rf.ensure_ufvai_agent() is True
        ok_cfg, cfg = load_json_config(str(tmp_path / "opencode.json"))
        assert ok_cfg and cfg["default_agent"] == "UFVAI"


# ── Preflight v0.6.22b (sessão presa ao UFVAI) ────────────────

class _Result:
    def __init__(self, payload: str):
        self.stdout = payload
        self.stderr = ""
        self.returncode = 0


class TestPreflightUfvaiSession:
    def test_success_returns_validated_id(self, monkeypatch):
        monkeypatch.setattr(rf, "find_opencode", lambda: "/usr/bin/opencode", raising=False)
        calls: list[list] = []

        def fake_run(argv, **kwargs):
            calls.append(argv)
            if "post" in argv:
                return _Result(json.dumps({"data": {"id": "ses_abc123", "agent": "UFVAI"}}))
            return _Result(json.dumps({"data": {"id": "ses_abc123", "agent": "UFVAI", "title": "x"}}))

        monkeypatch.setattr(rf.subprocess, "run", fake_run)
        assert rf.preflight_ufvai_session() == "ses_abc123"
        assert any("/api/session" in " ".join(argv) for argv in calls)

    def test_fails_closed_when_agent_not_ufvai(self, monkeypatch):
        monkeypatch.setattr(rf, "find_opencode", lambda: "/usr/bin/opencode", raising=False)

        def fake_run(argv, **kwargs):
            if "post" in argv:
                return _Result(json.dumps({"data": {"id": "ses_bad999", "agent": "build"}}))
            return _Result(json.dumps({"data": {"id": "ses_bad999", "agent": "build"}}))

        monkeypatch.setattr(rf.subprocess, "run", fake_run)
        assert rf.preflight_ufvai_session() is None

    def test_returns_none_without_binary(self, monkeypatch):
        def boom():
            raise FileNotFoundError("opencode não encontrado")

        monkeypatch.setattr(rf, "find_opencode", boom, raising=False)
        assert rf.preflight_ufvai_session() is None

    def test_returns_none_on_timeout(self, monkeypatch):
        monkeypatch.setattr(rf, "find_opencode", lambda: "/usr/bin/opencode", raising=False)

        def fake_run(argv, **kwargs):
            raise subprocess.TimeoutExpired(argv[0], 5)

        monkeypatch.setattr(rf.subprocess, "run", fake_run)
        assert rf.preflight_ufvai_session() is None

    def test_returns_none_on_bad_json(self, monkeypatch):
        monkeypatch.setattr(rf, "find_opencode", lambda: "/usr/bin/opencode", raising=False)
        monkeypatch.setattr(rf.subprocess, "run", lambda argv, **kw: _Result("não é json"))
        assert rf.preflight_ufvai_session() is None


# ── _build_ttyd_cmd: usa --session quando preflight responde ──

@pytest.fixture()
def _cmd_env(monkeypatch, tmp_path):
    monkeypatch.setattr(la, "resolve_opencode", lambda: ("opencode", {"HOME": str(tmp_path)}))
    monkeypatch.setattr(la, "_build_ttyd_args", lambda base_args, env: base_args)
    monkeypatch.delenv("PESQUISAI_YOLO", raising=False)


class TestBuildTtydCmdSession:
    def test_uses_session_id(self, _cmd_env, monkeypatch):
        # v0.6.22b: com sessão pré-criada, o TUI abre nela (--session) e SEM
        # --prompt — a saudação é semeada via `opencode run` em background.
        monkeypatch.setattr(la, "preflight_ufvai_session", lambda cwd=None: "ses_xyz789")
        seeds: list[list] = []
        monkeypatch.setattr(la.subprocess, "Popen", lambda argv, **kw: seeds.append(argv) or None)
        args, _, _ = la._build_ttyd_cmd(lang="en_US")
        joined = " ".join(str(a) for a in args)
        assert '--session "ses_xyz789"' in joined
        assert "--prompt" not in joined
        # seed da saudação em background: opencode run --session <id> <greeting>
        assert seeds, "esperava 1 chamada de seed (opencode run --session)"
        assert all("run" not in argv[:2] or argv[1] == "run" for argv in seeds)
        seed_joined = " ".join(str(a) for a in seeds[0])
        assert "--session" in seed_joined and "ses_xyz789" in seed_joined

    def test_preflight_receives_current_cwd(self, _cmd_env, monkeypatch):
        # v0.6.22b: o cwd do preflight é o diretório do projeto (DRIVE_PATH,
        # quando existente — alinhado ao TUI que será spawnado).
        seen: dict = {}

        def spy_preflight(cwd=None):
            seen["cwd"] = cwd
            return None

        monkeypatch.setattr(la, "preflight_ufvai_session", spy_preflight)
        la._build_ttyd_cmd(lang="en_US")
        try:
            from pesquisai.constants import DRIVE_PATH as _drive_path
        except Exception:  # noqa: BLE001
            _drive_path = la.os.path.join(la.os.environ.get("HOME", "/"), "PesquisAI")
        expected = _drive_path if (_drive_path and la.os.path.isdir(_drive_path)) else la.os.getcwd()
        assert seen["cwd"] == expected

    def test_fallback_without_session(self, _cmd_env, monkeypatch):
        monkeypatch.setattr(la, "preflight_ufvai_session", lambda cwd=None: None)
        args, _, _ = la._build_ttyd_cmd(lang="en_US")
        joined = " ".join(str(a) for a in args)
        assert "--session" not in joined
        assert "--prompt" in joined

    def test_missing_hd(self, _cmd_env, monkeypatch):
        """Preflight levantando exceção não impede o comando (best-effort)."""
        def boom(cwd=None):
            raise RuntimeError("inesperado")

        monkeypatch.setattr(la, "preflight_ufvai_session", boom)
        args, _, _ = la._build_ttyd_cmd(lang="en_US")
        joined = " ".join(str(a) for a in args)
        assert "--session" not in joined
