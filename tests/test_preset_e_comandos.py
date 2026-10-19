"""Presets de personalização da TUI (v0.6.22, 16/10/2026 — SEM bump de versão).

Recomendações 1 e 2 do estudo de 16/10:
- `merge_cli_preset` — preenche cli.json com defaults do UFVAI SOMENTE em
  chaves ausentes (session/diffs/tabs/highlights); escolha do usuário vence;
- `merge_ufvai_commands` — instala comandos slash em PT em opencode.json sem
  sobrescrever comandos já existentes do usuário;
- `merge_opencode_config` — cadeia de boot (agentes + comandos).

Restrição da V2 usada como promessa do módulo: o cli.json gerado contém apenas
chaves documentadas (a V2 rejeita desconhecidas na carga — se aparecer uma
chave nova aqui, o TUI não sobe).
"""

import pytest

from pesquisai.opencode_config import (
    CLI_PRESET,
    UFVAI_COMMANDS,
    merge_agent_policy,
    merge_cli_preset,
    merge_ufvai_commands,
    merge_opencode_config,
)

# Chaves documentadas do cli.json V2 (docs opencode.ai/v2/docs/cli/config).
CLI_TOPO_KNOWN = {
    "$schema", "theme", "keybinds", "plugins", "leader", "scroll",
    "animations", "cursor", "mouse", "prompt", "session", "tabs", "diffs",
    "attention", "highlights", "terminal", "mini", "debug", "experimental",
}


class TestMergeCliPreset:
    def test_preenche_chaves_ausentes(self):
        out = merge_cli_preset({"theme": {"name": "pesquisai", "mode": "dark"}})
        assert out["session"] == {"thinking": "show", "markdown": "rendered"}
        assert out["diffs"] == {"wrap": "word"}
        assert out["tabs"] == {"mode": "auto"}
        assert out["highlights"] is False
        # theme preservado intacto
        assert out["theme"] == {"name": "pesquisai", "mode": "dark"}

    def test_escolha_do_usuario_vence_nivel_topo(self):
        out = merge_cli_preset({"highlights": True, "session": {"thinking": "hide"}})
        assert out["highlights"] is True

    def test_escolha_do_usuario_vence_nao_sobrescreve_subitem(self):
        out = merge_cli_preset({"session": {"thinking": "hide"}})
        # subitem presente é preservado; ausente é preenchido
        assert out["session"]["thinking"] == "hide"
        assert out["session"]["markdown"] == "rendered"

    def test_grupo_nao_dicionario_do_usuario_é_preservado(self):
        out = merge_cli_preset({"session": True})
        assert out["session"] is True
        assert out["diffs"] == {"wrap": "word"}

    def test_nao_muta_o_argumento(self):
        original = {"session": {"thinking": "hide"}}
        merge_cli_preset(original)
        assert original == {"session": {"thinking": "hide"}}

    def test_vazio_seguro(self):
        out = merge_cli_preset({})
        assert out["session"] == CLI_PRESET["session"]

    def test_chaves_do_preset_estao_documentadas_na_v2(self):
        # promessa do módulo: só chaves conhecidas pelo schema do cli.json V2
        assert set(CLI_PRESET) <= CLI_TOPO_KNOWN


class TestMergeUfvaiCommands:
    def test_instala_comandos_pt(self):
        out = merge_ufvai_commands({"$schema": "https://opencode.ai/config.json"})
        for nome in UFVAI_COMMANDS:
            entry = out["commands"][nome]
            assert entry["description"]
            assert "$ARGUMENTS" in entry["template"] or nome == "referencias"

    def test_comando_do_usuario_vence(self):
        out = merge_ufvai_commands(
            {"commands": {"pesquisar": {"template": "MEU TEMPLATE"}}}
        )
        assert out["commands"]["pesquisar"]["template"] == "MEU TEMPLATE"

    def test_nao_muta_o_argumento(self):
        original = {"commands": {"abnt": {"template": "meu abnt"}}}
        merge_ufvai_commands(original)
        assert original["commands"]["abnt"] == {"template": "meu abnt"}


class TestMergeOpencodeConfig:
    def test_cadeia_agentes_mais_comandos(self):
        out = merge_opencode_config(
            {"$schema": "https://opencode.ai/config.json"}, "UFVAI"
        )
        assert out["default_agent"] == "UFVAI"
        assert out["agents"]["build"]["disabled"] is True
        assert out["agents"]["plan"]["disabled"] is True
        assert "pesquisar" in out["commands"]

    def test_preserva_providers_e_comandos_do_usuario(self):
        cfg = {
            "providers": {"x": {"models": {}}},
            "commands": {"abnt": {"template": "meu"}},
        }
        out = merge_opencode_config(cfg, "UFVAI")
        assert out["providers"]["x"]["models"] == {}
        assert out["commands"]["abnt"]["template"] == "meu"
