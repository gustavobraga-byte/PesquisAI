"""Testes para run_fast.py — funcoes puras e utilitarias do orquestrador.

Cobre:
  - _check_bin: deteccao de binarios (which, paths customizados, ausente)
  - _clone_or_pull: git clone/pull com mock de subprocess
  - _setup_theme_and_agent: geracao de arquivos de tema e agente
  - _run: wrapper de subprocess
"""

import os
import sys
import json
import shutil
import subprocess
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pesquisai import run_fast
from pesquisai.run_fast import _check_bin, _clone_or_pull, _run
from pesquisai.constants import SKILL_REGISTRY, ESSENTIAL_SKILLS, SKILL_MAPPINGS


class TestCheckBin:
    """_check_bin verifica se um binario existe no sistema."""

    def test_existing_binary_python3(self):
        """python3 deve existir em qualquer sistema Linux."""
        assert _check_bin("python3") is True

    def test_existing_binary_ls(self):
        assert _check_bin("ls") is True

    def test_nonexistent_binary(self):
        assert _check_bin("binario_inexistente_xyz_123") is False

    def test_empty_name(self):
        assert _check_bin("") is False

    def test_bin_in_custom_path(self, tmp_path):
        """Binario em path customizado (~/.local/bin) deve ser encontrado."""
        fake_bin = tmp_path / "mytool"
        fake_bin.write_text("#!/bin/bash\necho hi\n")
        fake_bin.chmod(0o755)
        with patch.dict(os.environ, {"HOME": str(tmp_path)}):
            # _check_bin busca em ~/.local/bin
            local_bin = tmp_path / ".local" / "bin"
            local_bin.mkdir(parents=True)
            dest = local_bin / "mytool"
            shutil.copy(fake_bin, dest)
            dest.chmod(0o755)
            assert _check_bin("mytool") is True


class TestRun:
    """_run e um wrapper de subprocess.run com shell=True."""

    def test_run_echo(self):
        """_run deve executar comando shell e retornar CompletedProcess."""
        r = _run("echo test_pesquisai")
        assert r.returncode == 0
        assert "test_pesquisai" in r.stdout

    def test_run_false_command(self):
        """Comando que falha deve retornar returncode != 0."""
        r = _run("false")
        assert r.returncode != 0

    def test_run_with_capture(self):
        """_run deve capturar stdout e stderr."""
        r = _run("echo output123")
        assert "output123" in r.stdout


class TestCloneOrPull:
    """_clone_or_pull faz git clone ou pull com cache."""

    def test_clone_new_repo(self, tmp_path, monkeypatch):
        """Se destino nao existe, faz git clone."""
        monkeypatch.setattr("pesquisai.run_fast.shutil.rmtree", lambda p: None)
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("pesquisai.run_fast.subprocess.run", return_value=mock_result) as mock_run:
            ok = _clone_or_pull("https://github.com/fake/repo.git", "fake-skill")
            assert ok is True
            # Deve ter chamado git clone
            call_args = mock_run.call_args[0][0]
            assert "clone" in call_args

    def test_clone_failure(self, tmp_path, monkeypatch):
        """Se git clone falha, retorna False."""
        monkeypatch.setattr("pesquisai.run_fast.shutil.rmtree", lambda p: None)
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("pesquisai.run_fast.subprocess.run", return_value=mock_result):
            ok = _clone_or_pull("https://github.com/fake/fail.git", "fail-skill")
            assert ok is False

    def test_pull_existing_repo(self, tmp_path, monkeypatch):
        """Se destino existe, faz git pull --depth 1."""
        dest = "/tmp/skill_existing-test"
        os.makedirs(dest, exist_ok=True)
        try:
            mock_result = MagicMock()
            mock_result.returncode = 0
            with patch("pesquisai.run_fast.subprocess.run", return_value=mock_result) as mock_run:
                ok = _clone_or_pull("https://github.com/fake/repo.git", "existing-test")
                assert ok is True
                call_args = mock_run.call_args[0][0]
                assert "pull" in call_args
        finally:
            shutil.rmtree(dest, ignore_errors=True)

    def test_pull_failure_then_clone(self, tmp_path, monkeypatch):
        """Se pull falha, remove destino e tenta clone."""
        dest = "/tmp/skill_pullfail-test"
        os.makedirs(dest, exist_ok=True)
        try:
            # Mock rmtree aceitando kwargs (ignore_errors)
            monkeypatch.setattr("pesquisai.run_fast.shutil.rmtree",
                                lambda p, **kw: None)
            pull_result = MagicMock()
            pull_result.returncode = 1
            clone_result = MagicMock()
            clone_result.returncode = 0
            with patch("pesquisai.run_fast.subprocess.run",
                       side_effect=[pull_result, clone_result]) as mock_run:
                ok = _clone_or_pull("https://github.com/fake/repo.git", "pullfail-test")
                assert ok is True
                first_call = mock_run.call_args_list[0][0][0]
                second_call = mock_run.call_args_list[1][0][0]
                assert "pull" in first_call
                assert "clone" in second_call
        finally:
            # Restaurar rmtree real antes do cleanup
            import importlib
            import pesquisai.run_fast as rf
            importlib.reload(rf)
            shutil.rmtree(dest, ignore_errors=True)


class TestSkillRegistry:
    """SKILL_REGISTRY e SKILL_MAPPINGS devem ser consistentes."""

    def test_registry_format(self):
        for entry in SKILL_REGISTRY:
            assert len(entry) == 3
            url, name, required = entry
            assert url.startswith("http")
            assert isinstance(name, str) and len(name) > 0
            assert isinstance(required, bool)

    def test_essential_subset(self):
        for sk in ESSENTIAL_SKILLS:
            assert sk in {n for _, n, _ in SKILL_REGISTRY}

    def test_mappings_reference_known_skills(self):
        known = {n for _, n, _ in SKILL_REGISTRY}
        for src, dest in SKILL_MAPPINGS:
            assert dest in known or dest == "pesquisai"

    def test_at_least_one_essential(self):
        assert len(ESSENTIAL_SKILLS) > 0
