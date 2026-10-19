"""
opencode_config.py — Configuração do OpenCode V2 gerada pelo UFVAI.

Concentra a lógica de arquivos do motor (sem efeitos colaterais no import):

- leitura de JSON/JSONC com proteção contra sobrescrita (se o arquivo do
  usuário não puder ser lido, NÃO reescrevemos — evita perda de dados);
- escrita atômica de JSON;
- `cli.json` (V2: tema + modo do terminal);
- `opencode.json` (V2: `default_agent`);
- tema UFVAI no formato V1 com as 50 chaves exigidas pelo conversor do V2
  (o V2 converte o formato V1 internamente, via `ce()` no binário);
- agente Markdown (`agents/<nome>.md`) no frontmatter aceito pela V2.

Referências (documentação oficial OpenCode V2, consultada em 2026-10-13):
  - https://opencode.ai/v2/docs/cli/config/
  - https://opencode.ai/v2/docs/config/
  - https://opencode.ai/v2/docs/agents/
  - https://opencode.ai/v2/docs/cli/theme/
"""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any

CLI_SCHEMA_URL = "https://opencode.ai/v2/cli.json"
CONFIG_SCHEMA_URL = "https://opencode.ai/config.json"
THEME_SCHEMA_URL = "https://opencode.ai/theme.json"

UFVAI_THEME_NAME = "pesquisai"
UFVAI_THEME_MODES = ("dark", "light")


# ─────────────────────────────────────────────────────────────────
# JSON / JSONC
# ─────────────────────────────────────────────────────────────────

def strip_jsonc(text: str) -> str:
    """Remove comentários // e /* */ e vírgulas finais, respeitando strings."""
    out: list[str] = []
    i, n = 0, len(text)
    in_str = False
    while i < n:
        ch = text[i]
        if in_str:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_str = False
            i += 1
            continue
        if ch == '"':
            in_str = True
            out.append(ch)
            i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            end = text.find("*/", i + 2)
            i = n if end == -1 else end + 2
            continue
        out.append(ch)
        i += 1
    cleaned = "".join(out)
    # vírgula final antes de } ou ] (fora de strings: regex simples basta aqui)
    import re
    return re.sub(r",(\s*[}\]])", r"\1", cleaned)


def load_json_config(path: str) -> tuple[bool, dict[str, Any]]:
    """Carrega JSON/JSONC de um arquivo.

    Returns:
        (pode_gravar, dados). ``pode_gravar`` é False quando o arquivo existe
        mas não pode ser interpretado — nesse caso o chamador NÃO deve gravar
        por cima (evita apagar configuração do usuário).
    """
    if not os.path.exists(path):
        return True, {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = fh.read()
    except OSError:
        return False, {}
    if not raw.strip():
        return True, {}
    for candidate in (raw, strip_jsonc(raw)):
        try:
            data = json.loads(candidate)
        except (ValueError, TypeError):
            continue
        if isinstance(data, dict):
            return True, data
        return False, {}
    return False, {}


def write_json_atomic(path: str, data: dict[str, Any]) -> None:
    """Grava JSON de forma atômica (arquivo temporário + os.replace)."""
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


# ─────────────────────────────────────────────────────────────────
# cli.json (cliente de terminal — V2)
# ─────────────────────────────────────────────────────────────────

def merge_cli_theme(existing: dict[str, Any], theme_name: str, mode: str) -> dict[str, Any]:
    """Aplica tema e modo em cli.json preservando as demais configurações.

    A V2 rejeita chaves desconhecidas em cli.json, por isso só mexemos em
    ``theme`` e ``$schema``.
    """
    if mode not in UFVAI_THEME_MODES:
        mode = "dark"
    merged = dict(existing)
    theme = merged.get("theme")
    # Cópia também do theme: `dict(existing)` é rasa e escrever em theme
    # mutaria o dicionário do chamador (ex.: o config recarregado do disco).
    theme = dict(theme) if isinstance(theme, dict) else {}
    theme["name"] = theme_name
    theme["mode"] = mode
    merged["theme"] = theme
    merged["$schema"] = CLI_SCHEMA_URL
    return merged


def mode_from_ui_theme(ui_theme: str) -> str:
    """'pesquisai-light' → 'light'; qualquer outro valor → 'dark'."""
    return "light" if ui_theme == "pesquisai-light" else "dark"


def ui_theme_from_cli(cli: dict[str, Any]) -> str:
    """Converte o cli.json do V2 no nome de tema usado pela interface web."""
    theme = cli.get("theme")
    mode = theme.get("mode") if isinstance(theme, dict) else None
    return "pesquisai-light" if mode == "light" else "pesquisai"


# ─────────────────────────────────────────────────────────────────
# opencode.json (configuração global — V2)
# ─────────────────────────────────────────────────────────────────

def merge_default_agent(existing: dict[str, Any], agent_name: str) -> dict[str, Any]:
    """Define ``default_agent`` preservando o restante da configuração."""
    merged = dict(existing)
    merged["default_agent"] = agent_name
    merged.setdefault("$schema", CONFIG_SCHEMA_URL)
    return merged


# v0.6.22 (16/10/2026, SEM bump): presets de personalização da TUI
# (recomendações 1 e 2 do estudo de 16/10 — cli.json + comandos PT).
# Filosofia: preencher somente chaves AUSENTES (a escolha do usuário vence) e
# usar apenas chaves documentadas na V2 (a V2 rejeita desconhecidas em cli.json).
CLI_PRESET: dict[str, Any] = {
    # session.* — configuração de sessão (docs cli/config.md#sessions)
    "session": {"thinking": "show", "markdown": "rendered"},
    # diffs.* — revisão de mudanças (docs cli/config.md#diffs)
    "diffs": {"wrap": "word"},
    # tabs.* — faixa de abas (docs cli/config.md#tabs)
    "tabs": {"mode": "auto"},
    # banner de release da TUI desligado (docs cli/config.md#highlights)
    "highlights": False,
}


def merge_cli_preset(existing: dict[str, Any]) -> dict[str, Any]:
    """Aplica ``CLI_PRESET`` em cli.json preenchendo somente chaves ausentes.

    Regras:
    - valor presente do usuário é preservado (não sobrescreve, nem por nível);
    - chaves de grupo existentes recebem apenas os subitens ausentes;
    - nunca muta o argumento recebido (cópia em dois níveis).
    """
    merged = dict(existing)
    for key, value in CLI_PRESET.items():
        if key not in merged:
            merged[key] = dict(value) if isinstance(value, dict) else value
            continue
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            sub = dict(merged[key])  # preserva subitens já definidos pelo usuário
            for sub_key, sub_value in value.items():
                sub.setdefault(sub_key, sub_value)
            merged[key] = sub
    return merged


def merge_cli_plugins(existing: dict[str, Any], plugin_path: str) -> dict[str, Any]:
    """Habilita um plugin de CLI (TUI) em ``cli.json`` sem duplicar entradas.

    A lista ``plugins`` do cli.json aceita nomes de pacote, caminhos locais e
    o formato ``{"package": ...}``. Só acrescentamos o caminho do plugin do
    UFVAI se ele ainda não estiver presente (em qualquer das duas formas) e
    preservamos a ordem e as escolhas do usuário.

    Plugins de TUI são "CLI-only" (docs: opencode.ai/v2/docs/plugins): ficam
    em ``cli.json`` e continuam ativos mesmo quando a TUI se conecta a um
    servidor remoto.
    """
    merged = dict(existing)
    current = merged.get("plugins")
    items: list[Any] = list(current) if isinstance(current, list) else []
    if not any(
        item == plugin_path
        or (isinstance(item, dict) and item.get("package") == plugin_path)
        for item in items
    ):
        items.append(plugin_path)
    merged["plugins"] = items
    merged.setdefault("$schema", CLI_SCHEMA_URL)
    return merged


# Comandos slash em português para o fluxo científico do UFVAI.
# São PROMPT TEMPLATES (docs opencode.ai/v2/docs/commands/): rodam em sessão
# com o agente padrão (UFVAI). Os comandos NATIVOS da TUI (/new, /undo,
# /themes, /help, /models…) também estão em português desde a v0.6.24, mas por
# outra via: o plugin de CLI em `pesquisai/tui_pt.py`, que traduz o token
# digitado no próprio keymap (aqui ficam apenas os comandos de PROMPT).
UFVAI_COMMANDS: dict[str, dict[str, str]] = {
    "pesquisar": {
        "description": "Pesquisa científica completa sobre um tema",
        "template": (
            "Conduza uma pesquisa científica sobre: $ARGUMENTS.\n"
            "- Colete somente dados reais das skills adequadas (ibge-br, opendatasus etc.)\n"
            "  e papers validados (citation-management).\n"
            "- Marque cada afirmação com [DADO CONFIRMADO], [ESTIMATIVA FUNDAMENTADA]\n"
            "  ou [SEM DADOS SUFICIENTES].\n"
            "- Registre parâmetros e achados em Minha memória."
        ),
    },
    "revisar": {
        "description": "Revisão de literatura sobre um tema",
        "template": (
            "Faça uma revisão de literatura sobre: $ARGUMENTS.\n"
            "- Busque papers nas bases acadêmicas e registre cada referência em "
            "Minha memória, com DOI/ISBN validado.\n"
            "- Sintetize por eixo temático e indique lacunas de pesquisa."
        ),
    },
    "dados": {
        "description": "Dados oficiais brasileiros sobre um tema",
        "template": (
            "Consulte dados oficiais brasileiros sobre: $ARGUMENTS.\n"
            "- Use ibge-br, opendatasus, dados-brasil ou agrobr conforme o domínio.\n"
            "- Reporte cada número com fonte, série/ano e período; nunca invente dados."
        ),
    },
    "referencias": {
        "description": "Valida as referências citadas nesta conversa",
        "template": (
            "Valide todas as referências desta conversa com um identificador "
            "persistente (DOI/ISBN/ISSN/URL oficial) em Minha memória.\n"
            "- Reporte o status de cada uma (validada/inválida/pendente)\n"
            "  e corrija o que puder, sem inventar campos."
        ),
    },
    "abnt": {
        "description": "Normaliza texto ou referências no padrão UFV/ABNT",
        "template": "Normalize no padrão UFV/ABNT o texto ou as referências indicadas: $ARGUMENTS.",
    },
    "ajuda": {
        "description": "Help do UFVAI: uso, skills, comandos e atalhos (em PT)",
        "template": (
            "Explique de forma prática como usar o UFVAI: fluxo de trabalho\n"
            "(seções do §3), marcadores de evidência (§4.2), skills disponíveis\n"
            "e como registrar a sessão em Minha memória. Responda em português.\n"
            "Se o usuário indicar um tema, foque nele: $ARGUMENTS"
        ),
    },
    "memoria": {
        "description": "Consulta/salva na memória persistente (Minha memória)",
        "template": (
            "Trabalhe com Minha memória (vault do PesquisAI): $ARGUMENTS\n"
            "- Sem argumento: mostre o último estado (moc/last-state.md),\n"
            "  as 3 últimas dailies e o que está pendente (fila/próximos passos).\n"
            "- Para salvar: crie a nota com o template oficial da pasta certa\n"
            "  e o frontmatter obrigatório (created, created_by, updated,\n"
            "  tags da taxonomia oficial pesquisai/*)."
        ),
    },
    # Equivalentes em PT dos comandos de servidor nativos do motor
    # (/init e /review). São prompt templates: reproduzem o fluxo, não o
    # diálogo interativo original.
    "iniciar": {
        "description": "Configuração guiada do AGENTS.md (regras do projeto)",
        "template": (
            "Faça a configuração guiada do AGENTS.md deste projeto: $ARGUMENTS\n"
            "- Inspecione a estrutura, a stack e os comandos de build/teste reais.\n"
            "- Crie ou atualize AGENTS.md com o que um agente precisa saber\n"
            "  (arquitetura, como rodar, convenções, armadilhas).\n"
            "- Não invente comandos: confirme cada um no repositório."
        ),
    },
    "revisar-codigo": {
        "description": "Revisa mudanças de código (commit, branch ou PR)",
        "template": (
            "Revise as mudanças de código indicadas: $ARGUMENTS\n"
            "- Sem argumento, use as alterações não commitadas (git diff).\n"
            "- Aponte bugs, riscos, regressões e testes faltando, com arquivo:linha.\n"
            "- Não reescreva o código sem pedir; priorize achados acionáveis."
        ),
    },
}


def merge_ufvai_commands(existing: dict[str, Any]) -> dict[str, Any]:
    """Instala ``UFVAI_COMMANDS`` em opencode.json sem sobrescrever o usuário.

    Comandos já definidos pelo usuário (ou em outro nível de configuração)
    mantêm prioridade: aqui só adicionamos os que ainda não existem.
    """
    merged = dict(existing)
    commands = dict(merged.get("commands") or {})
    for name, spec in UFVAI_COMMANDS.items():
        if name not in commands:
            commands[name] = dict(spec)
    merged["commands"] = commands
    merged.setdefault("$schema", CONFIG_SCHEMA_URL)
    return merged


def cleanup_i18n_leftovers() -> list[str]:
    """Remove instalações/resíduos do plugin ``opencode-i18n`` (v0.6.24).

    Apaga ``~/.config/opencode/i18n/``, ``~/.local/state/opencode/i18n-state.json``
    e ``~/.local/state/opencode/pesquisai-browser-locale.json`` — arquivos que a
    v0.6.23 criava e que, se ficarem no disco, reativariam a camada de tradução
    concorrente assim que o plugin fosse reinstalado pelo usuário. Fail-open:
    qualquer erro de I/O é ignorado e o boot continua.

    Returns:
        Lista dos caminhos efetivamente removidos (para log).
    """
    removed: list[str] = []
    home = os.path.expanduser("~")
    config_root = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.join(home, ".config")), "opencode")
    state_root = os.path.join(os.environ.get("XDG_STATE_HOME", os.path.join(home, ".local", "state")), "opencode")
    targets = [
        os.path.join(config_root, "i18n"),
        os.path.join(state_root, "i18n-state.json"),
        os.path.join(state_root, "pesquisai-browser-locale.json"),
    ]
    for path in targets:
        try:
            if os.path.isdir(path):
                import shutil
                shutil.rmtree(path, ignore_errors=True)
                removed.append(path)
            elif os.path.exists(path):
                os.remove(path)
                removed.append(path)
        except OSError:
            continue
    return removed


def strip_i18n_plugin(existing: dict[str, Any]) -> dict[str, Any]:
    """Remove o plugin ``opencode-i18n`` (v1/v2) da lista de plugins.

    v0.6.24 (ajuste 18/10/2026, SEM bump): o plugin de i18n de terceiros
    duplicava os comandos na paleta (ele e o ``ufvai-pt`` criam camadas de
    espelho para os MESMOS ids) e injetava comandos próprios com título em
    chinês ("界面语言"). A tradução da TUI é responsabilidade exclusiva do
    plugin autoral ``ufvai-pt`` (``cli.json``), então o ``opencode.json``
    nunca deve conter o plugin de i18n.

    Preserva qualquer outro plugin do usuário; remove apenas entradas cujo
    nome/pacote comece por ``opencode-i18n``.
    """
    merged = dict(existing)
    plugins = list(merged.get("plugins") or [])

    def _is_i18n(entry: Any) -> bool:
        if isinstance(entry, str):
            return entry.split("/")[-1].startswith("opencode-i18n")
        if isinstance(entry, dict):
            package = entry.get("package")
            if isinstance(package, str):
                return package.split("/")[-1].startswith("opencode-i18n")
            if len(entry) == 1:
                key = next(iter(entry))
                if isinstance(key, str):
                    return key.split("/")[-1].startswith("opencode-i18n")
        return False

    filtered = [entry for entry in plugins if not _is_i18n(entry)]
    if filtered:
        merged["plugins"] = filtered
    elif "plugins" in merged:
        merged["plugins"] = filtered
    return merged


def merge_opencode_config(existing: dict[str, Any], agent_name: str) -> dict[str, Any]:
    """Cadeia oficial de boot: agentes + comandos UFVAI (PT), SEM plugin i18n.

    A referência a ``merge_agent_policy`` é resolvida no momento da chamada
    (o run_fast só invoca com todos os nomes já definidos), então posicioná-la
    antes da outra definição é apenas questão de leitura do fluxo de boot.
    v0.6.24 (ajuste 18/10/2026): o plugin ``opencode-i18n-v2`` da v0.6.23 foi
    REMOVIDO — ele duplicava os comandos na paleta e injetava entradas em
    chinês. O ``ufvai-pt`` (``cli.json``) é a única camada de tradução da TUI.
    """
    return strip_i18n_plugin(merge_ufvai_commands(merge_agent_policy(existing, agent_name)))



# v0.6.22 (15/10/2026): agentes embutidos que NUNCA podem ser usados pelo
# UFVAI. Regra do autor: "exclua o build e o plan… tem que SEMPRE carregar
# o ufvai". Como docs oficiais da V2 (opencode.ai/v2/docs/agents) não
# permitem remover built-ins do catálogo de fábrica — mas aceitam
# ``disabled: true`` para removê-los na carga de configuração — a garantia
# implementada abaixo os desliga em ``agents`` dentro do opencode.json.
DISABLED_BUILTIN_AGENTS: tuple[str, ...] = ("build", "plan")


def merge_agent_policy(existing: dict[str, Any], agent_name: str) -> dict[str, Any]:
    """Define ``default_agent`` e desabilita os built-ins ``build`` e ``plan``.

    Preserva todo o restante da configuração (providers, mcp, chaves já
    desabilitadas pelo usuário etc.). Entradas existentes em ``agents`` para
    os built-ins recebem ``disabled: True``; entradas inexistente são criadas
    já desabilitadas. Com isso a V2 não só evita cair em ``build``/``plan``
    no fallback do ``default_agent`` — como doc oficial: "Otherwise OpenCode
    uses ``build``, then the first visible primary-capable agent" — como
    também os remove da lista de agentes da TUI, impossibilitando seleção
    manual acidental.

    Returns:
        Dicionário mesclado (cópia; nunca muta o argumento recebido).
    """
    merged = merge_default_agent(existing, agent_name)
    agents = dict(merged.get("agents") or {})
    for name in DISABLED_BUILTIN_AGENTS:
        entry = dict(agents.get(name) or {})
        entry["disabled"] = True
        agents[name] = entry
    merged["agents"] = agents
    return merged


# ─────────────────────────────────────────────────────────────────
# Agente Markdown (agents/<nome>.md)
# ─────────────────────────────────────────────────────────────────

def strip_frontmatter(text: str) -> str:
    """Remove um bloco inicial de frontmatter YAML (---) do texto."""
    if not text.startswith("---"):
        return text
    lines = text.splitlines(keepends=True)
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            return "".join(lines[idx + 1:]).lstrip("\n")
    return text


def build_agent_markdown(description: str, color: str, body: str) -> str:
    """Monta o agente com frontmatter aceito pela V2.

    Campos usados: ``description``, ``mode`` (primary, explícito) e ``color``
    (hex de 6 dígitos). ``name`` NÃO é usado: a V2 define o ID pelo caminho do
    arquivo — verificado em 13/10/2026 na V2.0.28: um ``name: UFVAI`` no
    frontmatter é **ignorado** e o agente continua aparecendo como ``ufvai``.
    Para o agente se chamar "UFVAI", o arquivo precisa ser ``agents/UFVAI.md``.
    """
    # Aspas duplas (formato JSON é YAML válido): a descrição tem ": " e "#",
    # que quebrariam um escalar YAML sem aspas.
    safe_description = json.dumps(description.replace("\n", " ").strip(), ensure_ascii=False)
    return (
        "---\n"
        f"description: {safe_description}\n"
        "mode: primary\n"
        f'color: "{color}"\n'
        "---\n\n"
        f"{body.strip()}\n"
    )


# ─────────────────────────────────────────────────────────────────
# Tema UFVAI (formato V1 com as 50 chaves do tema embutido)
# ─────────────────────────────────────────────────────────────────

# Paleta UFVAI (mesmos valores históricos do tema do terminal)
_DARK: dict[str, str] = {
    "bg0": "#141c24", "bg1": "#1a232c", "bg2": "#1f2831", "bg3": "#26313c",
    "bg4": "#2f3d4a", "fg0": "#e8e6e0", "fg1": "#a8b2ba", "fg2": "#6b7684",
    "blue": "#d4b56a", "blueDim": "#8a6d33", "green": "#5dba7e",
    "greenDark": "#1d4a2e", "amber": "#D1A705", "red": "#e07a70",
    "redDark": "#571512", "cyan": "#7fa8bd", "purple": "#c98a76",
    "synKeyword": "#7fa8bd", "synString": "#5dba7e", "synComment": "#6b7684",
    "synNumber": "#D1A705", "synFunction": "#d4b56a", "synType": "#c98a76",
    "synOp": "#a8b2ba",
}

_LIGHT: dict[str, str] = {
    "bg0": "#faf9f6", "bg1": "#ffffff", "bg2": "#f1efe9", "bg3": "#e5e1d6",
    "bg4": "#d9d3c4", "fg0": "#1f2831", "fg1": "#4a5560", "fg2": "#857f72",
    "blue": "#8a6d33", "blueDim": "#d4b56a", "green": "#2e7d32",
    "greenDark": "#a5d6a7", "amber": "#a67c00", "red": "#c0392b",
    "redDark": "#ef9a9a", "cyan": "#4a7c8c", "purple": "#9a5a48",
    "synKeyword": "#4a7c8c", "synString": "#2e7d32", "synComment": "#857f72",
    "synNumber": "#a67c00", "synFunction": "#8a6d33", "synType": "#9a5a48",
    "synOp": "#4a5560",
}

# Cada chave do tema embutido do V2 aponta para um papel da paleta.
# As 50 chaves são exigidas pelo conversor (ausência gera erro e fallback).
_THEME_ROLES: dict[str, str] = {
    "primary": "blue", "secondary": "cyan", "accent": "purple",
    "error": "red", "warning": "amber", "success": "green", "info": "cyan",
    "text": "fg0", "textMuted": "fg1",
    "background": "bg0", "backgroundPanel": "bg1", "backgroundElement": "bg2",
    "border": "bg3", "borderActive": "bg4", "borderSubtle": "bg2",
    "diffAdded": "green", "diffAddedBg": "greenDark",
    "diffRemoved": "red", "diffRemovedBg": "redDark",
    "diffContext": "fg1", "diffContextBg": "bg1", "diffHunkHeader": "fg2",
    "diffHighlightAdded": "greenDark", "diffHighlightRemoved": "redDark",
    "diffLineNumber": "fg2", "diffAddedLineNumberBg": "greenDark",
    "diffRemovedLineNumberBg": "redDark",
    "syntaxComment": "synComment", "syntaxKeyword": "synKeyword",
    "syntaxFunction": "synFunction", "syntaxVariable": "fg0",
    "syntaxString": "synString", "syntaxNumber": "synNumber",
    "syntaxType": "synType", "syntaxOperator": "synOp",
    "syntaxPunctuation": "fg2",
    "markdownText": "fg0", "markdownHeading": "blue", "markdownLink": "cyan",
    "markdownLinkText": "cyan", "markdownCode": "green",
    "markdownCodeBlock": "fg0", "markdownBlockQuote": "fg2",
    "markdownEmph": "fg1", "markdownStrong": "fg0",
    "markdownHorizontalRule": "bg4", "markdownListItem": "blue",
    "markdownListEnumeration": "blue", "markdownImage": "cyan",
    "markdownImageText": "fg1",
}


def build_ufvai_theme() -> dict[str, Any]:
    """Retorna o tema UFVAI completo (dark + light) no formato V1 aceito pelo V2."""
    defs: dict[str, str] = {}
    for role, value in _DARK.items():
        defs[f"d_{role}"] = value
    for role, value in _LIGHT.items():
        defs[f"l_{role}"] = value
    theme: dict[str, Any] = {
        key: {"dark": f"d_{role}", "light": f"l_{role}"}
        for key, role in _THEME_ROLES.items()
    }
    return {"$schema": THEME_SCHEMA_URL, "defs": defs, "theme": theme}


def theme_key_count() -> int:
    """Quantidade de chaves do tema (deve ser 50, igual ao tema embutido)."""
    return len(_THEME_ROLES)
