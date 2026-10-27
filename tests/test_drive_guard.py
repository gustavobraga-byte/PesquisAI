"""Testes do UFVAI Drive Guard (v0.7.7).

O guard é o plugin que impede o agente de acessar "My Drive" fora de
``My Drive/PesquisAI`` — inclusive com ``--auto``. Aqui se testa o lado
Python (instalação + regras no ``opencode.json``) e se delega a política de
caminhos ao teste em Node (``tests/js/test_drive_guard.mjs``), que é a mesma
usada em produção.
"""

import json
import os
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pesquisai.drive_guard import (  # noqa: E402
    PLUGIN_FILES,
    PLUGIN_SRC_DIR,
    ensure_drive_guard,
    install_plugin,
    status,
)
from pesquisai.opencode_config import (  # noqa: E402
    DRIVE_GUARD_ALLOWED,
    DRIVE_GUARD_MOUNT,
    drive_guard_permissions,
    merge_drive_guard,
)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class TestPermissions:
    def test_deny_antes_do_allow_por_acao(self):
        rules = drive_guard_permissions()
        for action in ("external_directory", "read", "edit"):
            deny = {"action": action, "resource": DRIVE_GUARD_MOUNT, "effect": "deny"}
            deny_tree = {
                "action": action,
                "resource": f"{DRIVE_GUARD_MOUNT}/*",
                "effect": "deny",
            }
            allow = {"action": action, "resource": DRIVE_GUARD_ALLOWED, "effect": "allow"}
            allow_tree = {
                "action": action,
                "resource": f"{DRIVE_GUARD_ALLOWED}/*",
                "effect": "allow",
            }
            for rule in (deny, deny_tree, allow, allow_tree):
                assert rule in rules
            assert rules.index(deny_tree) < rules.index(allow_tree)

    def test_raiz_exata_tambem_e_negada(self):
        rules = drive_guard_permissions()
        assert {"action": "read", "resource": DRIVE_GUARD_MOUNT, "effect": "deny"} in rules

    def test_chaves_protegidas_e_env_reafirmado(self):
        resources = [r["resource"] for r in drive_guard_permissions()]
        assert any(r.endswith("*keys_store.json") for r in resources)
        assert any(r.endswith("*keys_encryption_key.bin") for r in resources)
        assert any(r.endswith("*.env") for r in resources)
        assert any(r.endswith("*.env.*") for r in resources)

    def test_ultimas_regras_sao_do_guard(self):
        rules = drive_guard_permissions()
        assert rules[-1]["effect"] == "ask"
        assert rules[-2]["effect"] == "ask"


class TestMergeConfig:
    def test_idempotente(self):
        cfg = {"permissions": [{"action": "shell", "resource": "*", "effect": "ask"}]}
        first = merge_drive_guard(cfg, "/tmp/plugin")
        second = merge_drive_guard(first, "/tmp/plugin")
        assert first == second
        assert first["plugins"] == ["/tmp/plugin"]
        assert first["permissions"][0] == {"action": "shell", "resource": "*", "effect": "ask"}

    def test_plugin_em_formato_objeto_nao_duplica(self):
        cfg = {"plugins": [{"package": "/tmp/plugin", "options": {"x": 1}}]}
        merged = merge_drive_guard(cfg, "/tmp/plugin")
        assert merged["plugins"] == cfg["plugins"]

    def test_preserva_regras_do_usuario_e_coloca_guard_no_fim(self):
        user_rule = {"action": "read", "resource": "/content/drive/*", "effect": "allow"}
        merged = merge_drive_guard({"permissions": [user_rule]}, "/tmp/plugin")
        assert user_rule in merged["permissions"]
        assert merged["permissions"][-1] == drive_guard_permissions()[-1]
        # a regra do usuário fica ANTES do allow de PesquisAI (que vence)
        assert merged["permissions"].index(user_rule) < len(merged["permissions"]) - 10
        assert len(merged["permissions"]) == 1 + len(drive_guard_permissions())

    def test_permissions_em_formato_inesperado_nao_e_sobrescrito(self):
        cfg = {"permissions": {"read": "allow"}}
        merged = merge_drive_guard(cfg, "/tmp/plugin")
        assert merged["permissions"] == {"read": "allow"}
        assert merged["plugins"] == ["/tmp/plugin"]

    def test_schema_preservado(self):
        merged = merge_drive_guard({"$schema": "https://x/y.json"}, "/tmp/plugin")
        assert merged["$schema"] == "https://x/y.json"
        merged = merge_drive_guard({}, "/tmp/plugin")
        assert merged["$schema"].startswith("https://opencode.ai/")


class TestInstall:
    def test_copia_todos_os_arquivos(self, tmp_path):
        written = install_plugin(dest=str(tmp_path))
        assert len(written) == len(PLUGIN_FILES)
        for name in PLUGIN_FILES:
            assert (tmp_path / name).exists(), name

    def test_nao_reescreve_arquivo_identico(self, tmp_path):
        install_plugin(dest=str(tmp_path))
        assert install_plugin(dest=str(tmp_path)) == []

    def test_recupera_arquivo_alterado(self, tmp_path):
        install_plugin(dest=str(tmp_path))
        target = tmp_path / "policy.js"
        target.write_text("// adulterado\n", encoding="utf-8")
        assert install_plugin(dest=str(tmp_path)) == [str(target)]
        assert "makeGuard" in target.read_text(encoding="utf-8")

    def test_fonte_ausente_falha_alto(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            install_plugin(dest=str(tmp_path), src=str(tmp_path / "nao-existe"))

    def test_fonte_do_pacote_existe(self):
        for name in PLUGIN_FILES:
            assert os.path.exists(os.path.join(PLUGIN_SRC_DIR, name)), name


class TestEnsure:
    def test_instala_e_registra(self, tmp_path):
        cfg_path = tmp_path / "opencode.json"
        dest = tmp_path / "plugins" / "ufvai-drive-guard"
        cfg_path.write_text(json.dumps({"default_agent": "UFVAI"}), encoding="utf-8")

        result = ensure_drive_guard(cfg_path=str(cfg_path), dest=str(dest))
        assert result["ok"] is True
        assert result["plugin_path"] == str(dest)

        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        assert data["default_agent"] == "UFVAI"
        assert str(dest) in data["plugins"]
        assert any(r["effect"] == "deny" for r in data["permissions"])

        info = status(cfg_path=str(cfg_path), dest=str(dest))
        assert info["installed"] is True
        assert info["registered"] is True
        assert info["deny_rules"] >= 3

        # segunda passada não muda nada
        before = cfg_path.read_text(encoding="utf-8")
        ensure_drive_guard(cfg_path=str(cfg_path), dest=str(dest))
        assert cfg_path.read_text(encoding="utf-8") == before

    def test_config_ilegivel_nao_e_sobrescrito(self, tmp_path):
        cfg_path = tmp_path / "opencode.json"
        cfg_path.write_text("{ isto nao e json", encoding="utf-8")
        dest = tmp_path / "plugins" / "ufvai-drive-guard"
        result = ensure_drive_guard(cfg_path=str(cfg_path), dest=str(dest))
        assert result["ok"] is False
        assert cfg_path.read_text(encoding="utf-8") == "{ isto nao e json"
        assert (dest / "index.js").exists()  # o plugin em si foi copiado


class TestEntryPoint:
    @staticmethod
    def _read(name: str) -> str:
        with open(os.path.join(PLUGIN_SRC_DIR, name), encoding="utf-8") as fh:
            return fh.read()

    def test_index_js_e_modulo_esm_com_plugin_define(self):
        source = self._read("index.js")
        assert "export default" in source
        assert "id: PLUGIN_ID" in source
        assert "permission.hook" in source
        assert "tool.hook" in source

    def test_plugin_registra_as_duas_camadas(self):
        source = self._read("index.js")
        assert '"evaluate"' in source
        assert '"execute.before"' in source

    def test_politica_nao_importa_modulos_do_motor(self):
        source = self._read("policy.js")
        assert "@opencode" not in source
        assert "node:" in source

    @pytest.mark.skipif(shutil.which("node") is None, reason="node indisponível")
    def test_politica_em_node(self):
        proc = subprocess.run(
            ["node", os.path.join(ROOT, "tests", "js", "test_drive_guard.mjs")],
            capture_output=True,
            text=True,
            cwd=ROOT,
            timeout=120,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "verificações ok" in proc.stdout
