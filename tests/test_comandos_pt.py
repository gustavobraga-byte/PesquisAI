"""Testes do plugin de TUI multilíngue (v0.6.24, revisão de 18/10/2026).

Cobre:
- catálogo: 37 comandos nativos × 4 idiomas traduzidos (+ inglês nativo);
- rótulos de menu (`LABELS`): 80 ids × 4 idiomas, todos com a MESMA chave;
- categorias (`CATEGORIES`): `Session`/`Agent`/`System`/`Integration`/`VCS`
  traduzidas nos 4 idiomas;
- títulos curtos e descrições explicativas;
- slugs/aliases únicos e realmente traduzidos;
- regressão: o espelho é rastreado por `id` (`mirrored`), nunca por título;
- instalação idempotente do pacote local (package.json, locales.json, tui.ts);
- merge em `cli.json` (idempotente, preserva entradas do usuário, sem mutar).
"""

from __future__ import annotations

import json
import re

from pesquisai.opencode_config import merge_cli_plugins
from pesquisai.tui_pt import (
    CATEGORIES,
    LABELS,
    PT_CATALOG,
    PT_LANGUAGES,
    PT_PLUGIN_PACKAGE_JSON,
    PT_PLUGIN_TUI_TS,
    PT_SWITCHER,
    build_locales_payload,
    install_pt_plugin,
)

# Comandos barra nativos da TUI no OpenCode v2.0.32 (extraídos do keymap real).
NATIVE_COMMAND_IDS = {
    "session.new", "session.clear", "session.list", "open.menu", "session.rename",
    "session.timeline", "session.fork", "session.compact", "session.undo",
    "session.redo", "messages.copy", "session.export", "session.terminal",
    "session.aside", "session.cd", "session.move", "prompt.editor",
    "prompt.skills", "model.list", "agent.list", "mcp.list", "variant.list",
    "provider.connect", "opencode.highlights", "opencode.settings",
    "opencode.status", "opencode.update", "server.pair", "location.reload",
    "opencode.debug", "theme.switch", "help.show", "app.exit", "diff.open",
    "stats.open", "plugins.list", "service.restart",
}

LOCALES = {"pt-BR", "es", "fr", "zh"}

# Nomes de comando nativos (em inglês) — para detectar "tradução" falsa.
NATIVE_SLUGS = {
    "new", "clear", "sessions", "open", "rename", "timeline", "fork",
    "compact", "undo", "redo", "copy", "export", "terminal", "btw",
    "worktrees", "editor", "skills", "models", "agents", "mcps", "variants",
    "connect", "highlights", "settings", "status", "update", "pair", "reload",
    "debug", "themes", "help", "exit", "diff", "stats", "plugins", "restart",
}

# Palavras que são iguais nos idiomas (não são "inglês esquecido").
SAME_WORD_OK = {"editor", "terminal", "mcps", "plugins", "diff", "mcp",
                "sessions", "agents", "themes"}


def test_catalogo_cobre_todos_os_idiomas_e_comandos():
    assert set(PT_CATALOG) == LOCALES
    assert set(PT_LANGUAGES) == LOCALES | {"en"}
    assert set(PT_SWITCHER) == LOCALES | {"en"}
    for locale, commands in PT_CATALOG.items():
        assert set(commands) == NATIVE_COMMAND_IDS, f"{locale}: conjunto de comandos difere"
        assert len(commands) == 37


def test_titulos_identificaveis_e_descricoes_explicativas():
    """Títulos = tradução fiel do comando em inglês (identificável na paleta),
    sem voltar a serem frases longas; descrições seguem como documentação."""
    for locale, commands in PT_CATALOG.items():
        for native_id, spec in commands.items():
            title, description = str(spec["title"]), str(spec["description"])
            limit = 12 if locale == "zh" else 26
            assert len(title) <= limit, f"{locale}/{native_id}: título longo ({title})"
            assert len(description) > len(title), f"{locale}/{native_id}: descrição curta"


def test_labels_cobrem_a_paleta_sem_slug():
    """`LABELS` traduz o que aparece na paleta ctrl+p, sem criar `/barra`."""
    assert set(LABELS) == LOCALES
    tamanhos = {locale: len(ids) for locale, ids in LABELS.items()}
    assert set(tamanhos.values()) == {len(LABELS["pt-BR"])}, f"tamanhos divergentes: {tamanhos}"
    primeira = set(LABELS["pt-BR"])
    for locale, ids in LABELS.items():
        assert set(ids) == primeira, f"{locale}: chaves de LABELS divergentes"
    # Nada de rótulo duplicando id do catálogo (senão haveria `/barra` ambíguo).
    assert not (primeira & set(PT_CATALOG["pt-BR"])), "LABELS × PT_CATALOG colidem"
    # Rótulos são curtos o bastante para a paleta.
    for locale, ids in LABELS.items():
        limite = 12 if locale == "zh" else 26
        for native_id, title in ids.items():
            assert title.strip(), f"{locale}/{native_id}: rótulo vazio"
            assert len(title) <= limite, f"{locale}/{native_id}: rótulo longo ({title})"


def test_categories_traduzem_as_categorias_nativas():
    nativas = {"Session", "Agent", "System", "Integration", "VCS"}
    assert set(CATEGORIES) == LOCALES
    for locale, mapa in CATEGORIES.items():
        assert nativas <= set(mapa), f"{locale}: categorias faltando"
        assert all(valor.strip() for valor in mapa.values())
    assert CATEGORIES["pt-BR"]["Session"] == "Sessão"
    assert CATEGORIES["pt-BR"]["System"] == "Sistema"
    assert CATEGORIES["zh"]["Agent"] == "代理"


def test_espelho_rastreado_por_id_e_nao_por_titulo():
    """Regressão de 18/10/2026: comparar TÍTULOS descartava o próprio espelho e
    comandos cuja tradução é igual ao inglês (`Plugins`, `Status`) nunca eram
    capturados — o menu ficava com título/categoria em inglês (`Close tab`)."""
    assert "const mirrored = new Set<string>()" in PT_PLUGIN_TUI_TS
    assert "mirrored.has(id)" in PT_PLUGIN_TUI_TS
    assert "mirrored.add(id)" in PT_PLUGIN_TUI_TS
    assert "command.title === translated" not in PT_PLUGIN_TUI_TS
    # O conjunto monitorado une catálogo e rótulos.
    assert "const tracked = new Set<string>()" in PT_PLUGIN_TUI_TS
    assert "Object.values(DATA.labels ?? {})" in PT_PLUGIN_TUI_TS
    # Categoria nativa traduzida e repassada ao espelho.
    assert "DATA.categories?.[locale] ?? {}" in PT_PLUGIN_TUI_TS
    # `/barra` só existe para comandos do catálogo.
    assert "...(spec?.slug" in PT_PLUGIN_TUI_TS


def test_slugs_unicos_e_traduzidos():
    for locale, commands in PT_CATALOG.items():
        slugs: list[str] = []
        for spec in commands.values():
            slugs.append(str(spec["slug"]))
            slugs.extend(str(alias) for alias in spec.get("aliases", []))
        assert len(slugs) == len(set(slugs)), f"{locale}: slug/alias duplicado"

        for native_id, spec in commands.items():
            slug = str(spec["slug"])
            if locale != "zh":
                assert re.fullmatch(r"[a-z][a-z0-9-]*", slug), f"{locale}/{native_id}: slug inválido"
            if slug in SAME_WORD_OK:
                continue
            assert slug not in NATIVE_SLUGS, f"{locale}/{native_id}: slug continua em inglês ({slug})"


def test_comandos_com_argumento_marcados():
    # renomear / diretório / aparte recebem texto depois do comando.
    for locale, commands in PT_CATALOG.items():
        for native_id in ("session.rename", "session.cd", "session.aside"):
            assert commands[native_id].get("args") is True, f"{locale}/{native_id}: falta args"


def test_paleta_mostra_apenas_o_comando():
    """ctrl+p sem descrições: o espelho não pode emitir `description`."""
    assert "description: spec.description" not in PT_PLUGIN_TUI_TS
    assert "description: switcher.description" not in PT_PLUGIN_TUI_TS
    # Mas o catálogo mantém as descrições (documentação/ajuda futura).
    for commands in PT_CATALOG.values():
        assert all(spec.get("description") for spec in commands.values())


def test_plugin_carrega_catalogo_e_delega_ao_nativo():
    assert 'import LOCALES from "./locales.json"' in PT_PLUGIN_TUI_TS
    assert "run: () => false" in PT_PLUGIN_TUI_TS
    assert "priority: 100" in PT_PLUGIN_TUI_TS
    assert "bind: false" in PT_PLUGIN_TUI_TS
    assert 'mode: "global"' in PT_PLUGIN_TUI_TS
    # Metadados do comando nativo preservados (palette/suggested/enabled).
    assert "const originals = new Map<string, KeymapCommand>()" in PT_PLUGIN_TUI_TS
    assert "...rest," in PT_PLUGIN_TUI_TS
    # Idioma reativo + comandos de sessão que entram depois.
    assert "context.storage.store(" in PT_PLUGIN_TUI_TS
    assert "context.storage.memory(" in PT_PLUGIN_TUI_TS


def test_deteccao_de_idioma_respeita_ordem():
    assert "UFVAI_LANG" in PT_PLUGIN_TUI_TS
    assert "LC_ALL" in PT_PLUGIN_TUI_TS
    # C/POSIX/inglês caem no padrão do produto.
    assert 'return DATA.fallback' in PT_PLUGIN_TUI_TS


def test_switcher_lista_os_cinco_idiomas():
    payload = build_locales_payload()
    assert set(payload["languages"]) == {"pt-BR", "en", "es", "fr", "zh"}
    # O seletor usa a lista de idiomas (inclui inglês, que não tem catálogo).
    assert "const SUPPORTED = Object.keys(DATA.languages)" in PT_PLUGIN_TUI_TS


def test_payload_serializavel():
    payload = build_locales_payload()
    data = json.dumps(payload, ensure_ascii=False)
    assert '"pt-BR"' in data and '"新建"' in data
    assert len(data) > 5000
    # Cobertura total da paleta: catálogo (com `/barra`) + rótulos de menu.
    total = len(PT_CATALOG["pt-BR"]) + len(LABELS["pt-BR"])
    assert total >= 117, f"cobertura da paleta caiu para {total} ids"
    assert set(payload["categories"]) == LOCALES
    assert set(payload["labels"]) == LOCALES


def test_install_pt_plugin_grava_pacote(tmp_path):
    install_pt_plugin(str(tmp_path / "ufvai-pt"))
    root = tmp_path / "ufvai-pt"
    package = json.loads((root / "package.json").read_text(encoding="utf-8"))
    assert package["exports"]["./tui"] == "./tui.ts"
    assert package == PT_PLUGIN_PACKAGE_JSON
    assert (root / "tui.ts").read_text(encoding="utf-8") == PT_PLUGIN_TUI_TS
    locales = json.loads((root / "locales.json").read_text(encoding="utf-8"))
    assert set(locales["catalog"]) == LOCALES
    assert len(locales["catalog"]["pt-BR"]["commands"]) == 37
    # Rótulos e categorias também vão para o pacote instalado.
    assert set(locales["labels"]) == LOCALES
    assert set(locales["categories"]) == LOCALES
    assert locales["labels"]["pt-BR"]["session.tab.close"] == "Fechar aba"
    assert locales["categories"]["pt-BR"]["System"] == "Sistema"


def test_install_pt_plugin_idempotente_e_preserva_extras(tmp_path):
    install_pt_plugin(str(tmp_path / "p"))
    extra = tmp_path / "p" / "nota.txt"
    extra.write_text("do usuário", encoding="utf-8")
    install_pt_plugin(str(tmp_path / "p"))
    assert extra.read_text(encoding="utf-8") == "do usuário"
    assert sorted(p.name for p in (tmp_path / "p").iterdir()) == [
        "locales.json", "nota.txt", "package.json", "tui.ts",
    ]


def test_merge_cli_plugins_adiciona_uma_vez():
    path = "/home/u/.config/opencode/tui/ufvai-pt"
    merged = merge_cli_plugins({}, path)
    assert merged["plugins"] == [path]
    assert merged["$schema"].endswith("/v2/cli.json")
    assert merge_cli_plugins(merged, path)["plugins"] == [path]


def test_merge_cli_plugins_preserva_usuario():
    path = "/x/ufvai-pt"
    original = {"plugins": ["opencode-i18n-v2", {"package": "./local", "options": {"a": 1}}]}
    merged = merge_cli_plugins(original, path)
    assert merged["plugins"] == ["opencode-i18n-v2", {"package": "./local", "options": {"a": 1}}, path]
    assert merge_cli_plugins({"plugins": [{"package": path}]}, path)["plugins"] == [{"package": path}]


def test_merge_cli_plugins_nao_muta_entrada():
    original = {"plugins": ["a"]}
    merge_cli_plugins(original, "/x")
    assert original == {"plugins": ["a"]}
