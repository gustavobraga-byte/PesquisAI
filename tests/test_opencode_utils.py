"""Testes para opencode_utils.py — localizacao e configuracao do binario opencode."""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pesquisai import opencode_utils
from pesquisai.opencode_utils import (
    find_opencode,
    ensure_opencode_in_path,
    build_env,
    _search,
    CANDIDATES,
)


@pytest.fixture(autouse=True)
def reset_opencode_bin():
    """Reseta OPENCODE_BIN antes e depois de cada teste."""
    opencode_utils.OPENCODE_BIN = None
    yield
    opencode_utils.OPENCODE_BIN = None


class TestCandidates:
    """Lista de candidatos deve ser valida."""

    def test_candidates_are_absolute(self):
        for path in CANDIDATES:
            assert os.path.isabs(path)

    def test_candidates_nonempty(self):
        assert len(CANDIDATES) >= 3


class TestFindOpencode:
    """find_opencode com diferentes cenarios."""

    def test_cache_hit(self):
        opencode_utils.OPENCODE_BIN = "/fake/opencode"
        assert find_opencode() == "/fake/opencode"

    def test_env_var_hit(self, monkeypatch):
        fake_bin = "/usr/bin/python3"
        monkeypatch.setenv("OPENCODE_BIN", fake_bin)
        assert find_opencode() == fake_bin

    def test_env_var_nonexistent_falls_through(self, monkeypatch, tmp_path):
        monkeypatch.setenv("OPENCODE_BIN", str(tmp_path / "nao_existe"))
        monkeypatch.setattr("shutil.which", lambda name: None)
        monkeypatch.setattr("pesquisai.opencode_utils.CANDIDATES", [])
        with patch("pesquisai.opencode_utils._search", return_value=None):
            with pytest.raises(FileNotFoundError):
                find_opencode()

    def test_which_hit(self, monkeypatch):
        monkeypatch.delenv("OPENCODE_BIN", raising=False)
        monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/opencode")
        assert find_opencode() == "/usr/local/bin/opencode"

    def test_candidate_hit(self, monkeypatch, tmp_path):
        monkeypatch.delenv("OPENCODE_BIN", raising=False)
        monkeypatch.setattr("shutil.which", lambda name: None)
        fake_path = str(tmp_path / "opencode")
        with open(fake_path, "w") as f:
            f.write("#!/bin/bash\necho fake\n")
        monkeypatch.setattr("pesquisai.opencode_utils.CANDIDATES", [fake_path])
        with patch("pesquisai.opencode_utils._search", return_value=None):
            assert find_opencode() == fake_path

    def test_search_hit(self, monkeypatch):
        monkeypatch.delenv("OPENCODE_BIN", raising=False)
        monkeypatch.setattr("shutil.which", lambda name: None)
        monkeypatch.setattr("pesquisai.opencode_utils.CANDIDATES", [])
        with patch("pesquisai.opencode_utils._search", return_value="/found/opencode"):
            assert find_opencode() == "/found/opencode"

    def test_not_found_raises(self, monkeypatch):
        monkeypatch.delenv("OPENCODE_BIN", raising=False)
        monkeypatch.setattr("shutil.which", lambda name: None)
        monkeypatch.setattr("pesquisai.opencode_utils.CANDIDATES", [])
        with patch("pesquisai.opencode_utils._search", return_value=None):
            with pytest.raises(FileNotFoundError):
                find_opencode()


class TestEnsureOpencodeInPath:
    """ensure_opencode_in_path modifica PATH."""

    def test_adds_bin_dir_to_path(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda name: "/custom/bin/opencode")
        monkeypatch.setenv("PATH", "/usr/bin:/bin")
        ensure_opencode_in_path()
        assert "/custom/bin" in os.environ["PATH"]
        assert os.environ["OPENCODE_BIN"] == "/custom/bin/opencode"

    def test_path_already_present(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/opencode")
        monkeypatch.setenv("PATH", "/usr/bin:/bin")
        ensure_opencode_in_path()
        assert "/usr/bin" in os.environ["PATH"]


class TestBuildEnv:
    """build_env constroi dicionario de environment."""

    def test_returns_dict(self):
        assert isinstance(build_env(), dict)

    def test_sets_disable_copy(self):
        assert build_env()["OPENCODE_EXPERIMENTAL_DISABLE_COPY_ON_SELECT"] == "1"

    def test_path_present(self):
        assert "PATH" in build_env() and len(build_env()["PATH"]) > 0

    def test_extra_vars_merged(self):
        assert build_env({"CUSTOM_VAR": "val"})["CUSTOM_VAR"] == "val"

    def test_extra_vars_override(self):
        env = build_env({"OPENCODE_EXPERIMENTAL_DISABLE_COPY_ON_SELECT": "0"})
        assert env["OPENCODE_EXPERIMENTAL_DISABLE_COPY_ON_SELECT"] == "0"


class TestSearch:
    """_search executa find nos diretorios esperados."""

    @patch("pesquisai.opencode_utils.subprocess.run")
    def test_search_calls_find(self, mock_run):
        mock_run.return_value = MagicMock(stdout="/usr/local/bin/opencode\n", returncode=0)
        assert _search() == "/usr/local/bin/opencode"
        call_args = mock_run.call_args[0][0]
        assert "/root" in call_args and "/home" in call_args

    @patch("pesquisai.opencode_utils.subprocess.run")
    def test_search_no_results(self, mock_run):
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        assert _search() is None

    @patch("pesquisai.opencode_utils.subprocess.run")
    def test_search_multiple_returns_first(self, mock_run):
        mock_run.return_value = MagicMock(stdout="/a/opencode\n/b/opencode\n", returncode=0)
        assert _search() == "/a/opencode"
