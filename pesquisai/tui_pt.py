"""
tui_pt.py — Comandos barra (slash) da TUI em VÁRIOS IDIOMAS, com detecção.

Por que um plugin: os comandos nativos da TUI (`/new`, `/undo`, `/themes`,
`/help`, `/models`…) são definidos dentro do binário do OpenCode, em inglês,
e não existe opção de idioma na configuração (`cli.json`/`opencode.json`).
A via sancionada é o **plugin de CLI** (TUI), que recebe o keymap e pode
registrar uma camada com o MESMO `id` do comando nativo, traduzindo `slug`,
título e descrição. O título é a **tradução fiel** do comando em inglês
(ex.: `New session` → "Nova sessão"), para que o comando siga identificável na
paleta `ctrl+p`; as descrições ficam no catálogo como documentação e **não são
emitidas** (paleta enxuta, a pedido do usuário).

Como funciona (testado contra opencode v2.0.32):

- `context.keymap.layer({commands})` aceita comandos com `id` igual ao nativo;
  o keymap mescla por `id`, então o comando aparece no idioma escolhido no
  autocompletar de `/` e na paleta (`ctrl+p`).
- `run: () => false` interrompe a camada de tradução e CONTINUA a cadeia de
  dispatch: o comando nativo (camada inferior, mesmo `id`) é quem executa.
- `bind: false` mantém a camada sem capturar teclas.
- O espelho COPIA o objeto nativo (`...rest`) antes de sobrescrever os campos
  traduzidos: sem isso `palette`/`suggested`/`enabled` se perdem e os comandos
  somem da paleta `ctrl+p` (regressão corrigida em 18/10/2026).
- `slash.arguments: true` preserva o texto digitado após o comando nos nativos
  que recebem argumento (`renomear`, `diretório`, `aparte`).

Cobertura (revisão de 18/10/2026, dentro da v0.6.24 — sem bump):
- `PT_CATALOG` (37 comandos) = traduções que **também** viram comando `/barra`;
- `LABELS` (80 ids) = traduções de **menu** (sem slug), cobrindo toda a paleta
  `ctrl+p` e os comandos de tecla exibidos no painel de atalhos;
- `CATEGORIES` = categoria nativa (`Session`, `Agent`, `System`, `Integration`,
  `VCS`) → rótulo localizado, aplicado a **qualquer** comando — sem isso os
  itens não catalogados ficavam sob "Session"/"System"/"Agent";
- o espelho é rastreado pelo conjunto `mirrored`. A revisão anterior descartava
  o próprio espelho **comparando títulos**: comandos cuja tradução é igual ao
  inglês (`Plugins`, `Status`) nunca eram capturados e sobravam título e
  categoria em inglês (`Close tab` era o sintoma visível na paleta).

Textos internos do motor (tela de Configurações, descrições de teclas, chrome
da paleta `Commands`/`Search`/`Suggested`, `Ask anything…`, rodapé, logo) **não**
são traduzíveis pela API de plugins da V2: a tabela das Configurações
(`bn=[{title:"Theme",category:"Appearance",…}]`) é hardcoded no módulo compilado
e não há slot/hook para ela. Decisão de 18/10/2026: **não** patchar o binário.

Detecção de idioma (ordem):
  1. escolha do usuário feita com `/idioma` (persistida no storage do plugin);
  2. `UFVAI_LANG` / `PESQUISAI_LANG` (ex.: `UFVAI_LANG=es`);
  3. idioma do sistema (`LC_ALL`, `LC_MESSAGES`, `LANG`) quando for
     português, espanhol, francês ou chinês;
  4. `pt-BR` (padrão do produto — a interface do UFVAI também nasce em PT).
Locales `C`/`POSIX` e inglês caem no padrão; um usuário anglófono troca com
`/idioma` (ou define `UFVAI_LANG=en`). Em inglês nada é traduzido: os
comandos nativos já estão em inglês.

O pacote local é instalado em `~/.config/opencode/tui/ufvai-pt/` (com
`exports["./tui"]`) e habilitado em `cli.json` → `plugins` (plugins de TUI são
"CLI-only": continuam ativos mesmo conectados a um servidor remoto).
"""

from __future__ import annotations

import json
import os

# Pasta do plugin de TUI (pacote local lido pelo OpenCode via cli.json).
PT_PLUGIN_DIR: str = os.path.expanduser("~/.config/opencode/tui/ufvai-pt")

# Arquivo de idioma escolhido pelo usuário (gravado pelo plugin via `/idioma`).
# É a fonte de verdade do BOOT: se existir, o bootstrap reaplica os textos do
# prompt no binário nesse idioma na próxima inicialização.
LOCALE_FILE: str = os.path.expanduser("~/.config/opencode/ufvai-language.json")

# Locales aceitos (o padrão do produto é pt-BR).
PT_LOCALES: tuple[str, ...] = ("pt-BR", "en", "es", "fr", "zh")


def read_saved_locale() -> str | None:
    """Idioma gravado pelo plugin (`/idioma`), se houver e for válido."""
    try:
        with open(LOCALE_FILE, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    locale = data.get("locale") if isinstance(data, dict) else None
    return locale if locale in PT_LOCALES else None


def save_locale(locale: str) -> None:
    """Grava o idioma escolhido (usado pelo plugin e pelo boot)."""
    if locale not in PT_LOCALES:
        return
    os.makedirs(os.path.dirname(LOCALE_FILE), exist_ok=True)
    with open(LOCALE_FILE, "w", encoding="utf-8") as handle:
        json.dump({"locale": locale}, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _match_locale(tag: str) -> str | None:
    tag = tag.strip().lower().replace("_", "-")
    for prefix, locale in (("pt", "pt-BR"), ("es", "es"), ("fr", "fr"), ("zh", "zh"), ("en", "en")):
        if tag.startswith(prefix):
            return locale
    return None


def detect_locale() -> str:
    """Idioma do usuário: escolha salva → UFVAI_LANG → PESQUISAI_LOCALE → sistema → pt-BR.

    Segue a mesma ordem do plugin da TUI. Locales `C`/`POSIX` e inglês caem no
    padrão do produto (pt-BR), porque são o default de contêineres.
    `PESQUISAI_LOCALE` é o override documentado do i18n do motor (v0.6.23).
    """
    saved = read_saved_locale()
    if saved:
        return saved
    explicit = (
        os.environ.get("UFVAI_LANG")
        or os.environ.get("PESQUISAI_LOCALE")
        or os.environ.get("PESQUISAI_LANG")
        or ""
    )
    match = _match_locale(explicit)
    if match:
        return match
    system = os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES") or os.environ.get("LANG") or ""
    match = _match_locale(system)
    if match and match != "en":
        return match
    return "pt-BR"

# Nome do pacote — usado no package.json e nas mensagens de instalação.
PT_PLUGIN_NAME: str = "ufvai-pt"

PT_PLUGIN_PACKAGE_JSON: dict[str, object] = {
    "name": PT_PLUGIN_NAME,
    "version": "2.0.0",
    "private": True,
    "type": "module",
    "description": "UFVAI — comandos barra localizados para a TUI do OpenCode V2",
    "exports": {"./tui": "./tui.tsx"},
}

# Nome de cada idioma no seletor (`/idioma`).
PT_LANGUAGES: dict[str, str] = {
    "pt-BR": "Português (Brasil)",
    "en": "English",
    "es": "Español",
    "fr": "Français",
    "zh": "中文",
}

# Comando que troca o idioma (título/descrição no idioma corrente).
PT_SWITCHER: dict[str, dict[str, object]] = {
    "pt-BR": {
        "slug": "idioma",
        "aliases": ["language", "langue", "lang"],
        "title": "Idioma",
        "description": "Troca o idioma dos comandos (detectado do sistema)",
    },
    "en": {
        "slug": "idioma",
        "aliases": ["language", "langue", "lang"],
        "title": "Language",
        "description": "Change the command language (auto-detected from the system)",
    },
    "es": {
        "slug": "idioma",
        "aliases": ["language", "langue", "lang"],
        "title": "Idioma",
        "description": "Cambia el idioma de los comandos (detectado del sistema)",
    },
    "fr": {
        "slug": "idioma",
        "aliases": ["language", "langue", "lang"],
        "title": "Langue",
        "description": "Change la langue des commandes (détectée du système)",
    },
    "zh": {
        "slug": "idioma",
        "aliases": ["language", "langue", "lang"],
        "title": "语言",
        "description": "切换命令语言（根据系统自动检测）",
    },
}

GROUPS: dict[str, dict[str, str]] = {
    "pt-BR": {"session": "Sessão", "agent": "Agente", "system": "Sistema",
              "integration": "Integração", "vcs": "VCS", "prompt": "Prompt"},
    "es": {"session": "Sesión", "agent": "Agente", "system": "Sistema",
           "integration": "Integración", "vcs": "VCS", "prompt": "Prompt"},
    "fr": {"session": "Session", "agent": "Agent", "system": "Système",
           "integration": "Intégration", "vcs": "VCS", "prompt": "Prompt"},
    "zh": {"session": "会话", "agent": "代理", "system": "系统",
           "integration": "集成", "vcs": "VCS", "prompt": "提示"},
}

# Categorias nativas da paleta (campo `category` do OpenCode) → rótulo localizado.
# Sem isto, comandos não catalogados aparecem sob "Session"/"System"/"Agent".
CATEGORIES: dict[str, dict[str, str]] = {
    "pt-BR": {"Session": "Sessão", "Agent": "Agente", "System": "Sistema",
              "Integration": "Integração", "VCS": "VCS", "Prompt": "Prompt",
              "Tabs": "Abas", "Storybook": "Storybook", "Custom": "Personalizado"},
    "es": {"Session": "Sesión", "Agent": "Agente", "System": "Sistema",
           "Integration": "Integración", "VCS": "VCS", "Prompt": "Prompt",
           "Tabs": "Pestañas", "Storybook": "Storybook", "Custom": "Personalizado"},
    "fr": {"Session": "Session", "Agent": "Agent", "System": "Système",
           "Integration": "Intégration", "VCS": "VCS", "Prompt": "Prompt",
           "Tabs": "Onglets", "Storybook": "Storybook", "Custom": "Personnalisé"},
    "zh": {"Session": "会话", "Agent": "代理", "System": "系统",
           "Integration": "集成", "VCS": "VCS", "Prompt": "提示",
           "Tabs": "标签页", "Storybook": "Storybook", "Custom": "自定义"},
}


def _labels(pt: dict[str, str], es: dict[str, str], fr: dict[str, str],
            zh: dict[str, str]) -> dict[str, dict[str, str]]:
    """Monta `LABELS` garantindo que os 4 idiomas tenham as MESMAS chaves."""
    if not (len(pt) == len(es) == len(fr) == len(zh)
            and set(pt) == set(es) == set(fr) == set(zh)):
        raise ValueError("LABELS: chaves divergentes entre idiomas")
    return {"pt-BR": pt, "es": es, "fr": fr, "zh": zh}


# Rótulos de comando (sem slug de barra). Cobrem TODO comando que aparece na
# paleta ctrl+p e os comandos de tecla exibidos no painel de atalhos/ajuda.
# `PT_CATALOG` continua sendo a lista dos que também ganham comando `/barra`.
LABELS: dict[str, dict[str, str]] = _labels(
    pt={
        "session.tab.close": "Fechar aba",
        "session.tab.reopen": "Reabrir aba fechada",
        "session.tab.next": "Próxima aba",
        "session.tab.previous": "Aba anterior",
        "session.tab.next_unread": "Próxima aba não lida",
        "session.tab.previous_unread": "Aba anterior não lida",
        "session.tab.history.back": "Voltar no histórico",
        "session.tab.history.forward": "Avançar no histórico",
        "session.delete": "Excluir sessão",
        "session.copy": "Copiar transcrição",
        "session.copy.id": "Copiar ID da sessão",
        "session.interrupt": "Interromper sessão",
        "session.background": "Enviar a segundo plano",
        "session.queued_prompts": "Ver prompts na fila",
        "session.pin.toggle": "Fixar ou desafixar sessão",
        "session.sidebar.toggle": "Alternar barra lateral",
        "session.toggle.scrollbar": "Barra de rolagem",
        "session.toggle.thinking": "Mostrar ou ocultar pensar",
        "session.toggle.exploration_grouping": "Agrupar ferramentas",
        "session.verbosity.cycle": "Detalhamento da conversa",
        "session.child.first": "Seletor de subagentes",
        "session.child.next": "Próxima sessão filha",
        "session.child.previous": "Sessão filha anterior",
        "session.parent": "Ir para a sessão mãe",
        "session.message.next": "Próxima mensagem",
        "session.message.previous": "Mensagem anterior",
        "session.messages_last_user": "Última mensagem do usuário",
        "queued_prompt.undo": "Desfazer prompt da fila",
        "queued_prompt.delete": "Excluir prompt da fila",
        "agent.cycle": "Ciclar agentes",
        "agent.cycle.reverse": "Ciclar agentes (inverso)",
        "model.cycle_recent": "Ciclar modelos recentes",
        "model.cycle_recent_reverse": "Modelos recentes (inverso)",
        "model.cycle_favorite": "Ciclar modelos favoritos",
        "model.cycle_favorite_reverse": "Favoritos (inverso)",
        "model.dialog.provider": "Abrir lista de provedores",
        "model.dialog.favorite": "Favoritar modelo",
        "variant.cycle": "Ciclar variantes",
        "app.console": "Alternar console",
        "app.debug": "Painel de depuração",
        "app.clear": "Limpar tela",
        "app.scrap": "Abrir tela de rascunho",
        "docs.open": "Abrir documentação",
        "terminal.suspend": "Suspender terminal",
        "terminal.toggle": "Painel do terminal",
        "terminal.close": "Fechar painel do terminal",
        "terminal.select": "Selecionar terminal",
        "pane.focus.left": "Focar painel da sessão",
        "pane.focus.right": "Focar painel direito",
        "prompt.queue": "Enfileirar prompt",
        "prompt.clear": "Limpar campo de entrada",
        "prompt.paste": "Colar",
        "prompt.images.view": "Ver imagens anexadas",
        "prompt.editor_context.clear": "Limpar contexto do editor",
        "prompt.stash": "Guardar prompt",
        "prompt.stash.pop": "Restaurar prompt guardado",
        "prompt.stash.list": "Listar prompts guardados",
        "stash.delete": "Excluir item guardado",
        "diff.close": "Fechar visualizador",
        "diff.switch_source": "Escopo das diferenças",
        "diff.toggle_view": "Dividida ou unificada",
        "diff.toggle_file_tree": "Árvore de arquivos",
        "diff.toggle_fullscreen": "Alternar tela cheia",
        "diff.mark_reviewed": "Marcar como revisado",
        "diff.single_patch": "Visão de patch único",
        "plugins.toggle": "Ativar ou desativar plugin",
        "dialog.mcp.toggle": "Ativar servidor MCP",
        "dialog.plugins.update": "Atualizar plugin",
        "dialog.plugins.check": "Buscar atualizações",
        "which-key.toggle": "Alternar painel de atalhos",
        "which-key.layout.toggle": "Layout dos atalhos",
        "which-key.pending.toggle": "Atalhos pendentes",
        "which-key.group.previous": "Grupo de atalhos anterior",
        "which-key.group.next": "Próximo grupo de atalhos",
        "which-key.scroll.up": "Rolar atalhos para cima",
        "which-key.scroll.down": "Rolar atalhos para baixo",
        "which-key.page.up": "Página anterior de atalhos",
        "which-key.page.down": "Próxima página de atalhos",
        "which-key.home": "Primeiro atalho",
        "which-key.end": "Último atalho",
    },
    es={
        "session.tab.close": "Cerrar pestaña",
        "session.tab.reopen": "Reabrir pestaña cerrada",
        "session.tab.next": "Pestaña siguiente",
        "session.tab.previous": "Pestaña anterior",
        "session.tab.next_unread": "Pestaña sig. sin leer",
        "session.tab.previous_unread": "Pestaña ant. sin leer",
        "session.tab.history.back": "Atrás en el historial",
        "session.tab.history.forward": "Adelante en el historial",
        "session.delete": "Eliminar sesión",
        "session.copy": "Copiar transcripción",
        "session.copy.id": "Copiar ID de la sesión",
        "session.interrupt": "Interrumpir sesión",
        "session.background": "Enviar a segundo plano",
        "session.queued_prompts": "Ver prompts en cola",
        "session.pin.toggle": "Fijar o desfijar sesión",
        "session.sidebar.toggle": "Alternar barra lateral",
        "session.toggle.scrollbar": "Barra de desplazamiento",
        "session.toggle.thinking": "Mostrar u ocultar pensar",
        "session.toggle.exploration_grouping": "Agrupar herramientas",
        "session.verbosity.cycle": "Nivel de detalle",
        "session.child.first": "Selector de subagentes",
        "session.child.next": "Sesión hija siguiente",
        "session.child.previous": "Sesión hija anterior",
        "session.parent": "Ir a la sesión madre",
        "session.message.next": "Mensaje siguiente",
        "session.message.previous": "Mensaje anterior",
        "session.messages_last_user": "Último mensaje del usuario",
        "queued_prompt.undo": "Deshacer prompt en cola",
        "queued_prompt.delete": "Eliminar prompt en cola",
        "agent.cycle": "Cambiar de agente",
        "agent.cycle.reverse": "Agente anterior",
        "model.cycle_recent": "Cambiar modelo reciente",
        "model.cycle_recent_reverse": "Modelo reciente (inverso)",
        "model.cycle_favorite": "Cambiar modelo favorito",
        "model.cycle_favorite_reverse": "Modelo favorito (inverso)",
        "model.dialog.provider": "Lista de proveedores",
        "model.dialog.favorite": "Marcar como favorito",
        "variant.cycle": "Cambiar variante",
        "app.console": "Alternar consola",
        "app.debug": "Panel de depuración",
        "app.clear": "Limpiar pantalla",
        "app.scrap": "Abrir pantalla de borrador",
        "docs.open": "Abrir documentación",
        "terminal.suspend": "Suspender terminal",
        "terminal.toggle": "Panel del terminal",
        "terminal.close": "Cerrar panel del terminal",
        "terminal.select": "Seleccionar terminal",
        "pane.focus.left": "Enfocar panel de sesión",
        "pane.focus.right": "Enfocar panel derecho",
        "prompt.queue": "Encolar prompt",
        "prompt.clear": "Limpiar campo de entrada",
        "prompt.paste": "Pegar",
        "prompt.images.view": "Ver imágenes adjuntas",
        "prompt.editor_context.clear": "Limpiar contexto editor",
        "prompt.stash": "Guardar prompt",
        "prompt.stash.pop": "Restaurar prompt guardado",
        "prompt.stash.list": "Listar prompts guardados",
        "stash.delete": "Eliminar elemento guardado",
        "diff.close": "Cerrar diferencias",
        "diff.switch_source": "Alcance de diferencias",
        "diff.toggle_view": "Vista dividida o unificada",
        "diff.toggle_file_tree": "Alternar árbol de archivos",
        "diff.toggle_fullscreen": "Alternar pantalla completa",
        "diff.mark_reviewed": "Marcar como revisado",
        "diff.single_patch": "Vista de parche único",
        "plugins.toggle": "Activar plugin",
        "dialog.mcp.toggle": "Servidor MCP",
        "dialog.plugins.update": "Actualizar plugin",
        "dialog.plugins.check": "Buscar actualizaciones",
        "which-key.toggle": "Panel de atajos",
        "which-key.layout.toggle": "Diseño panel de atajos",
        "which-key.pending.toggle": "Atajos pendientes",
        "which-key.group.previous": "Grupo de atajos anterior",
        "which-key.group.next": "Grupo de atajos siguiente",
        "which-key.scroll.up": "Atajos hacia arriba",
        "which-key.scroll.down": "Atajos hacia abajo",
        "which-key.page.up": "Página anterior de atajos",
        "which-key.page.down": "Página sig. de atajos",
        "which-key.home": "Primer atajo",
        "which-key.end": "Último atajo",
    },
    fr={
        "session.tab.close": "Fermer l’onglet",
        "session.tab.reopen": "Rouvrir l’onglet fermé",
        "session.tab.next": "Onglet suivant",
        "session.tab.previous": "Onglet précédent",
        "session.tab.next_unread": "Onglet suiv. non lu",
        "session.tab.previous_unread": "Onglet préc. non lu",
        "session.tab.history.back": "Reculer (historique)",
        "session.tab.history.forward": "Avancer (historique)",
        "session.delete": "Supprimer la session",
        "session.copy": "Copier la transcription",
        "session.copy.id": "Copier l’ID de session",
        "session.interrupt": "Interrompre la session",
        "session.background": "Outils en arrière-plan",
        "session.queued_prompts": "Voir les prompts en file",
        "session.pin.toggle": "Épingler la session",
        "session.sidebar.toggle": "Barre latérale",
        "session.toggle.scrollbar": "Barre de défilement",
        "session.toggle.thinking": "Afficher/masquer penser",
        "session.toggle.exploration_grouping": "Regrouper les outils",
        "session.verbosity.cycle": "Niveau de détail",
        "session.child.first": "Choisir le sous-agent",
        "session.child.next": "Session enfant suivante",
        "session.child.previous": "Session enfant précédente",
        "session.parent": "Aller à la session parente",
        "session.message.next": "Message suivant",
        "session.message.previous": "Message précédent",
        "session.messages_last_user": "Dernier message",
        "queued_prompt.undo": "Annuler le prompt en file",
        "queued_prompt.delete": "Supprimer prompt en file",
        "agent.cycle": "Changer d’agent",
        "agent.cycle.reverse": "Agent précédent",
        "model.cycle_recent": "Modèle récent suivant",
        "model.cycle_recent_reverse": "Modèle récent (inverse)",
        "model.cycle_favorite": "Modèle favori suivant",
        "model.cycle_favorite_reverse": "Modèle favori (inverse)",
        "model.dialog.provider": "Liste des fournisseurs",
        "model.dialog.favorite": "Marquer comme favori",
        "variant.cycle": "Changer de variante",
        "app.console": "Console",
        "app.debug": "Panneau de débogage",
        "app.clear": "Effacer l’écran",
        "app.scrap": "Écran de brouillon",
        "docs.open": "Ouvrir la documentation",
        "terminal.suspend": "Suspendre le terminal",
        "terminal.toggle": "Panneau du terminal",
        "terminal.close": "Fermer le terminal",
        "terminal.select": "Choisir le terminal",
        "pane.focus.left": "Panneau de session",
        "pane.focus.right": "Panneau de droite",
        "prompt.queue": "Mettre le prompt en file",
        "prompt.clear": "Effacer la saisie",
        "prompt.paste": "Coller",
        "prompt.images.view": "Voir les images jointes",
        "prompt.editor_context.clear": "Contexte de l’éditeur",
        "prompt.stash": "Prompt mis de côté",
        "prompt.stash.pop": "Restaurer le prompt",
        "prompt.stash.list": "Prompts mis de côté",
        "stash.delete": "Élément mis de côté",
        "diff.close": "Fermer le visualiseur",
        "diff.switch_source": "Portée des différences",
        "diff.toggle_view": "Vue divisée ou unifiée",
        "diff.toggle_file_tree": "Arborescence",
        "diff.toggle_fullscreen": "Basculer plein écran",
        "diff.mark_reviewed": "Marquer comme révisé",
        "diff.single_patch": "Vue patch unique",
        "plugins.toggle": "Activer le plugin",
        "dialog.mcp.toggle": "Serveur MCP",
        "dialog.plugins.update": "Mettre à jour le plugin",
        "dialog.plugins.check": "Chercher les mises à jour",
        "which-key.toggle": "Panneau des raccourcis",
        "which-key.layout.toggle": "Disposition raccourcis",
        "which-key.pending.toggle": "Aperçu raccourcis",
        "which-key.group.previous": "Raccourcis : groupe préc.",
        "which-key.group.next": "Raccourcis : groupe suiv.",
        "which-key.scroll.up": "Raccourcis vers le haut",
        "which-key.scroll.down": "Raccourcis vers le bas",
        "which-key.page.up": "Raccourcis : page préc.",
        "which-key.page.down": "Raccourcis : page suiv.",
        "which-key.home": "Premier raccourci",
        "which-key.end": "Dernier raccourci",
    },
    zh={
        "session.tab.close": "关闭标签页",
        "session.tab.reopen": "重新打开标签页",
        "session.tab.next": "下一个标签页",
        "session.tab.previous": "上一个标签页",
        "session.tab.next_unread": "下个未读标签页",
        "session.tab.previous_unread": "上个未读标签页",
        "session.tab.history.back": "标签页历史后退",
        "session.tab.history.forward": "标签页历史前进",
        "session.delete": "删除会话",
        "session.copy": "复制会话记录",
        "session.copy.id": "复制会话 ID",
        "session.interrupt": "中断会话",
        "session.background": "工具转后台",
        "session.queued_prompts": "查看排队提示",
        "session.pin.toggle": "固定会话",
        "session.sidebar.toggle": "显示/隐藏侧栏",
        "session.toggle.scrollbar": "显示/隐藏滚动条",
        "session.toggle.thinking": "显示/隐藏思考",
        "session.toggle.exploration_grouping": "合并工具调用",
        "session.verbosity.cycle": "对话详细程度",
        "session.child.first": "选择子代理",
        "session.child.next": "下一个子会话",
        "session.child.previous": "上一个子会话",
        "session.parent": "转到父会话",
        "session.message.next": "下一条消息",
        "session.message.previous": "上一条消息",
        "session.messages_last_user": "最后一条用户消息",
        "queued_prompt.undo": "撤销排队提示",
        "queued_prompt.delete": "删除排队提示",
        "agent.cycle": "切换代理",
        "agent.cycle.reverse": "上一个代理",
        "model.cycle_recent": "切换最近模型",
        "model.cycle_recent_reverse": "最近模型（反向）",
        "model.cycle_favorite": "切换收藏模型",
        "model.cycle_favorite_reverse": "收藏模型（反向）",
        "model.dialog.provider": "打开提供商列表",
        "model.dialog.favorite": "收藏模型",
        "variant.cycle": "切换变体",
        "app.console": "切换控制台",
        "app.debug": "调试面板",
        "app.clear": "清屏",
        "app.scrap": "打开草稿屏",
        "docs.open": "打开文档",
        "terminal.suspend": "挂起终端",
        "terminal.toggle": "终端面板",
        "terminal.close": "关闭终端面板",
        "terminal.select": "选择终端",
        "pane.focus.left": "聚焦会话面板",
        "pane.focus.right": "聚焦右侧面板",
        "prompt.queue": "提示入队",
        "prompt.clear": "清空输入框",
        "prompt.paste": "粘贴",
        "prompt.images.view": "查看图片附件",
        "prompt.editor_context.clear": "清除编辑器上下文",
        "prompt.stash": "暂存提示",
        "prompt.stash.pop": "恢复暂存提示",
        "prompt.stash.list": "列出暂存提示",
        "stash.delete": "删除暂存项",
        "diff.close": "关闭差异查看器",
        "diff.switch_source": "切换差异范围",
        "diff.toggle_view": "切换分栏视图",
        "diff.toggle_file_tree": "显示/隐藏文件树",
        "diff.toggle_fullscreen": "切换全屏",
        "diff.mark_reviewed": "标记已审阅",
        "diff.single_patch": "单补丁视图",
        "plugins.toggle": "启用插件",
        "dialog.mcp.toggle": "MCP 服务器",
        "dialog.plugins.update": "更新插件",
        "dialog.plugins.check": "检查插件更新",
        "which-key.toggle": "快捷键面板",
        "which-key.layout.toggle": "快捷键面板布局",
        "which-key.pending.toggle": "待定快捷键预览",
        "which-key.group.previous": "上一组快捷键",
        "which-key.group.next": "下一组快捷键",
        "which-key.scroll.up": "快捷键上滚",
        "which-key.scroll.down": "快捷键下滚",
        "which-key.page.up": "快捷键上一页",
        "which-key.page.down": "快捷键下一页",
        "which-key.home": "第一个快捷键",
        "which-key.end": "最后一个快捷键",
    },
)

# Catálogo: id do comando nativo → slug, aliases, título e descrição.
# Títulos são a tradução fiel do comando em inglês (identificáveis na paleta
# ctrl+p); as descrições ficam guardadas como documentação e NÃO são emitidas.
PT_CATALOG: dict[str, dict[str, dict[str, object]]] = {
    "pt-BR": {
        "session.new": {"slug": "novo", "aliases": ["nova"], "title": "Nova sessão",
                        "description": "Inicia uma nova sessão de conversa", "group": "session"},
        "session.clear": {"slug": "limpar", "title": "Limpar sessão",
                          "description": "Limpa a sessão atual, mantendo o histórico salvo", "group": "session"},
        "session.list": {"slug": "sessoes", "aliases": ["retomar", "continuar"], "title": "Trocar sessão",
                         "description": "Lista e alterna entre as sessões abertas e recentes", "group": "session"},
        "open.menu": {"slug": "abrir", "aliases": ["projetos", "projeto"], "title": "Abrir sessão/projeto",
                      "description": "Abre uma sessão existente ou um projeto", "group": "session"},
        "session.rename": {"slug": "renomear", "title": "Renomear sessão",
                           "description": "Dá um novo título à sessão atual", "group": "session", "args": True},
        "session.timeline": {"slug": "mensagem", "aliases": ["linha-tempo"], "title": "Ir para mensagem",
                             "description": "Salta direto para uma mensagem da conversa", "group": "session"},
        "session.fork": {"slug": "bifurcar", "title": "Bifurcar sessão",
                         "description": "Cria uma nova ramificação a partir desta sessão", "group": "session"},
        "session.compact": {"slug": "compactar", "aliases": ["resumir"], "title": "Compactar sessão",
                            "description": "Resume o contexto para liberar espaço na janela", "group": "session"},
        "session.undo": {"slug": "desfazer", "title": "Desfazer",
                         "description": "Remove a última mensagem e reverte as alterações de arquivos", "group": "session"},
        "session.redo": {"slug": "refazer", "title": "Refazer",
                         "description": "Restaura a mensagem desfeita e as alterações de arquivos", "group": "session"},
        "messages.copy": {"slug": "copiar", "title": "Copiar resposta",
                          "description": "Copia a última resposta do assistente para a área de transferência", "group": "session"},
        "session.export": {"slug": "exportar", "title": "Exportar conversa",
                           "description": "Exporta a conversa em Markdown e abre no editor", "group": "session"},
        "session.terminal": {"slug": "terminal", "title": "Novo terminal",
                             "description": "Abre o terminal integrado na pasta do projeto", "group": "session"},
        "session.aside": {"slug": "aparte", "title": "Pergunta paralela",
                          "description": "Faz uma pergunta paralela sem interromper o fluxo principal",
                          "group": "session", "args": True},
        "session.cd": {"slug": "diretorio", "aliases": ["cd"], "title": "Mudar diretório",
                       "description": "Altera o diretório de trabalho da sessão",
                       "group": "session", "args": True},
        "session.move": {"slug": "areas", "aliases": ["worktrees"], "title": "Gerenciar workspaces",
                         "description": "Gerencia áreas de trabalho (worktrees) do projeto", "group": "session"},
        "prompt.editor": {"slug": "editor", "title": "Abrir editor",
                          "description": "Abre o editor externo para escrever a mensagem", "group": "session"},
        "prompt.skills": {"slug": "habilidades", "aliases": ["skills"], "title": "Habilidades",
                          "description": "Lista as skills disponíveis e insere uma na mensagem", "group": "prompt"},
        "model.list": {"slug": "modelos", "title": "Trocar modelo",
                       "description": "Lista os modelos disponíveis e troca o modelo em uso", "group": "agent"},
        "agent.list": {"slug": "agentes", "title": "Trocar agente",
                       "description": "Lista os agentes disponíveis e troca o agente em uso", "group": "agent"},
        "mcp.list": {"slug": "mcps", "aliases": ["mcp"], "title": "Servidores MCP",
                     "description": "Lista e gerencia os servidores MCP conectados", "group": "agent"},
        "variant.list": {"slug": "variantes", "aliases": ["pensamento", "esforco"], "title": "Variante do modelo",
                         "description": "Alterna a variante do modelo (esforço de raciocínio)", "group": "agent"},
        "provider.connect": {"slug": "conectar", "title": "Conectar integração",
                             "description": "Adiciona um provedor ou integração com credenciais",
                             "group": "integration"},
        "opencode.highlights": {"slug": "novidades", "title": "Novidades da versão",
                                "description": "Mostra as novidades da versão instalada", "group": "system"},
        "opencode.settings": {"slug": "ajustes", "aliases": ["configuracoes", "config"], "title": "Configurações",
                              "description": "Abre as configurações do OpenCode", "group": "system"},
        "opencode.status": {"slug": "estado", "aliases": ["status"], "title": "Status",
                            "description": "Mostra o status do servidor e da conexão", "group": "system"},
        "opencode.update": {"slug": "atualizar", "title": "Atualizar OpenCode",
                            "description": "Atualiza o OpenCode para a versão mais recente", "group": "system"},
        "server.pair": {"slug": "parear", "aliases": ["web"], "title": "Parear dispositivo",
                        "description": "Pareia outro dispositivo com este servidor", "group": "system"},
        "location.reload": {"slug": "recarregar", "title": "Recarregar configuração",
                            "description": "Recarrega a configuração sem fechar a sessão", "group": "system"},
        "opencode.debug": {"slug": "depurar", "title": "Depuração",
                           "description": "Mostra informações de depuração do ambiente", "group": "system"},
        "theme.switch": {"slug": "temas", "title": "Trocar tema",
                         "description": "Lista os temas disponíveis e troca o tema", "group": "system"},
        "help.show": {"slug": "ajuda", "aliases": ["atalhos", "ajudar", "help"], "title": "Ajuda",
                      "description": "Mostra a ajuda do OpenCode", "group": "system"},
        "app.exit": {"slug": "sair", "aliases": ["encerrar"], "title": "Sair",
                     "description": "Fecha o OpenCode e encerra a sessão", "group": "system"},
        "diff.open": {"slug": "diff", "aliases": ["diferencas"], "title": "Ver diferenças",
                      "description": "Abre o visualizador de diferenças do projeto", "group": "vcs"},
        "stats.open": {"slug": "estatisticas", "aliases": ["stats"], "title": "Estatísticas",
                       "description": "Mostra estatísticas de uso do OpenCode", "group": "system"},
        "plugins.list": {"slug": "plugins", "aliases": ["extensoes"], "title": "Plugins",
                         "description": "Lista e gerencia os plugins instalados", "group": "system"},
        "service.restart": {"slug": "reiniciar", "title": "Reiniciar serviço",
                            "description": "Reinicia o serviço do OpenCode em segundo plano", "group": "system"},
    },
    "es": {
        "session.new": {"slug": "nuevo", "aliases": ["nueva"], "title": "Nueva sesión",
                        "description": "Inicia una nueva sesión de conversación", "group": "session"},
        "session.clear": {"slug": "limpiar", "title": "Limpiar sesión",
                          "description": "Limpia la sesión actual y conserva el historial guardado", "group": "session"},
        "session.list": {"slug": "sesiones", "aliases": ["retomar", "continuar"], "title": "Cambiar sesión",
                         "description": "Lista y alterna entre las sesiones abiertas y recientes", "group": "session"},
        "open.menu": {"slug": "abrir", "aliases": ["proyectos", "proyecto"], "title": "Abrir sesión/proyecto",
                      "description": "Abre una sesión existente o un proyecto", "group": "session"},
        "session.rename": {"slug": "renombrar", "title": "Renombrar sesión",
                           "description": "Da un nuevo título a la sesión actual", "group": "session", "args": True},
        "session.timeline": {"slug": "mensaje", "title": "Ir al mensaje",
                             "description": "Salta directamente a un mensaje de la conversación", "group": "session"},
        "session.fork": {"slug": "bifurcar", "title": "Bifurcar sesión",
                         "description": "Crea una nueva rama a partir de esta sesión", "group": "session"},
        "session.compact": {"slug": "compactar", "aliases": ["resumir"], "title": "Compactar sesión",
                            "description": "Resume el contexto para liberar espacio en la ventana", "group": "session"},
        "session.undo": {"slug": "deshacer", "title": "Deshacer",
                         "description": "Elimina el último mensaje y revierte los cambios en archivos", "group": "session"},
        "session.redo": {"slug": "rehacer", "title": "Rehacer",
                         "description": "Restaura el mensaje deshecho y los cambios en archivos", "group": "session"},
        "messages.copy": {"slug": "copiar", "title": "Copiar respuesta",
                          "description": "Copia la última respuesta del asistente al portapapeles", "group": "session"},
        "session.export": {"slug": "exportar", "title": "Exportar conversación",
                           "description": "Exporta la conversación en Markdown y la abre en el editor", "group": "session"},
        "session.terminal": {"slug": "terminal", "title": "Nuevo terminal",
                             "description": "Abre el terminal integrado en la carpeta del proyecto", "group": "session"},
        "session.aside": {"slug": "aparte", "title": "Pregunta paralela",
                          "description": "Hace una pregunta paralela sin interrumpir el flujo principal",
                          "group": "session", "args": True},
        "session.cd": {"slug": "directorio", "aliases": ["cd"], "title": "Cambiar directorio",
                       "description": "Cambia el directorio de trabajo de la sesión", "args": True},
        "session.move": {"slug": "areas", "aliases": ["worktrees"], "title": "Gestionar workspaces",
                         "description": "Gestiona las áreas de trabajo (worktrees) del proyecto", "group": "session"},
        "prompt.editor": {"slug": "editor", "title": "Abrir editor",
                          "description": "Abre el editor externo para escribir el mensaje", "group": "session"},
        "prompt.skills": {"slug": "habilidades", "aliases": ["skills"], "title": "Habilidades",
                          "description": "Lista las skills disponibles e inserta una en el mensaje", "group": "prompt"},
        "model.list": {"slug": "modelos", "title": "Cambiar modelo",
                       "description": "Lista los modelos disponibles y cambia el modelo en uso", "group": "agent"},
        "agent.list": {"slug": "agentes", "title": "Cambiar agente",
                       "description": "Lista los agentes disponibles y cambia el agente en uso", "group": "agent"},
        "mcp.list": {"slug": "mcps", "aliases": ["mcp"], "title": "Servidores MCP",
                     "description": "Lista y gestiona los servidores MCP conectados", "group": "agent"},
        "variant.list": {"slug": "variantes", "aliases": ["pensamiento", "esfuerzo"], "title": "Variante del modelo",
                         "description": "Alterna la variante del modelo (esfuerzo de razonamiento)", "group": "agent"},
        "provider.connect": {"slug": "conectar", "title": "Conectar integración",
                             "description": "Añade un proveedor o integración con credenciales",
                             "group": "integration"},
        "opencode.highlights": {"slug": "novedades", "title": "Novedades de la versión",
                                "description": "Muestra las novedades de la versión instalada", "group": "system"},
        "opencode.settings": {"slug": "ajustes", "aliases": ["configuracion", "config"], "title": "Configuración",
                              "description": "Abre la configuración de OpenCode", "group": "system"},
        "opencode.status": {"slug": "estado", "aliases": ["status"], "title": "Estado",
                            "description": "Muestra el estado del servidor y de la conexión", "group": "system"},
        "opencode.update": {"slug": "actualizar", "title": "Actualizar OpenCode",
                            "description": "Actualiza OpenCode a la versión más reciente", "group": "system"},
        "server.pair": {"slug": "emparejar", "aliases": ["parear", "web"], "title": "Emparejar dispositivo",
                        "description": "Empareja otro dispositivo con este servidor", "group": "system"},
        "location.reload": {"slug": "recargar", "title": "Recargar configuración",
                            "description": "Recarga la configuración sin cerrar la sesión", "group": "system"},
        "opencode.debug": {"slug": "depurar", "title": "Depuración",
                           "description": "Muestra información de depuración del entorno", "group": "system"},
        "theme.switch": {"slug": "temas", "title": "Cambiar tema",
                         "description": "Lista los temas disponibles y cambia el tema", "group": "system"},
        "help.show": {"slug": "ayuda", "aliases": ["atajos", "ayudar"], "title": "Ayuda",
                      "description": "Muestra la ayuda de OpenCode", "group": "system"},
        "app.exit": {"slug": "salir", "aliases": ["cerrar"], "title": "Salir",
                     "description": "Cierra OpenCode y termina la sesión", "group": "system"},
        "diff.open": {"slug": "diff", "aliases": ["diferencias"], "title": "Ver diferencias",
                      "description": "Abre el visor de diferencias del proyecto", "group": "vcs"},
        "stats.open": {"slug": "estadisticas", "aliases": ["stats"], "title": "Estadísticas",
                       "description": "Muestra estadísticas de uso de OpenCode", "group": "system"},
        "plugins.list": {"slug": "plugins", "aliases": ["extensiones"], "title": "Plugins",
                         "description": "Lista y gestiona los plugins instalados", "group": "system"},
        "service.restart": {"slug": "reiniciar", "title": "Reiniciar servicio",
                            "description": "Reinicia el servicio de OpenCode en segundo plano", "group": "system"},
    },
    "fr": {
        "session.new": {"slug": "nouveau", "aliases": ["nouvelle"], "title": "Nouvelle session",
                        "description": "Démarre une nouvelle session de conversation", "group": "session"},
        "session.clear": {"slug": "effacer", "title": "Effacer la session",
                          "description": "Efface la session actuelle en conservant l'historique", "group": "session"},
        "session.list": {"slug": "sessions", "aliases": ["reprendre", "continuer"], "title": "Changer de session",
                         "description": "Liste et bascule entre les sessions ouvertes et récentes", "group": "session"},
        "open.menu": {"slug": "ouvrir", "aliases": ["projets", "projet"], "title": "Ouvrir session/projet",
                      "description": "Ouvre une session existante ou un projet", "group": "session"},
        "session.rename": {"slug": "renommer", "title": "Renommer la session",
                           "description": "Donne un nouveau titre à la session actuelle", "group": "session", "args": True},
        "session.timeline": {"slug": "message", "title": "Aller au message",
                             "description": "Saute directement à un message de la conversation", "group": "session"},
        "session.fork": {"slug": "bifurquer", "title": "Bifurquer la session",
                         "description": "Crée une nouvelle branche à partir de cette session", "group": "session"},
        "session.compact": {"slug": "compacter", "aliases": ["resumer"], "title": "Compacter la session",
                            "description": "Résume le contexte pour libérer de l'espace", "group": "session"},
        "session.undo": {"slug": "annuler", "title": "Annuler",
                         "description": "Supprime le dernier message et annule les modifications de fichiers", "group": "session"},
        "session.redo": {"slug": "refaire", "title": "Refaire",
                         "description": "Restaure le message annulé et les modifications de fichiers", "group": "session"},
        "messages.copy": {"slug": "copier", "title": "Copier la réponse",
                          "description": "Copie la dernière réponse de l'assistant dans le presse-papiers", "group": "session"},
        "session.export": {"slug": "exporter", "title": "Exporter la conversation",
                           "description": "Exporte la conversation en Markdown et l'ouvre dans l'éditeur", "group": "session"},
        "session.terminal": {"slug": "terminal", "title": "Nouveau terminal",
                             "description": "Ouvre le terminal intégré dans le dossier du projet", "group": "session"},
        "session.aside": {"slug": "aparte", "title": "Question parallèle",
                          "description": "Pose une question en parallèle sans interrompre le flux",
                          "group": "session", "args": True},
        "session.cd": {"slug": "dossier", "aliases": ["cd"], "title": "Changer de dossier",
                       "description": "Change le répertoire de travail de la session", "args": True},
        "session.move": {"slug": "espaces", "aliases": ["worktrees"], "title": "Gérer les workspaces",
                         "description": "Gère les espaces de travail (worktrees) du projet", "group": "session"},
        "prompt.editor": {"slug": "editeur", "title": "Ouvrir l’éditeur",
                          "description": "Ouvre l'éditeur externe pour rédiger le message", "group": "session"},
        "prompt.skills": {"slug": "competences", "aliases": ["skills"], "title": "Compétences",
                          "description": "Liste les skills disponibles et en insère une", "group": "prompt"},
        "model.list": {"slug": "modeles", "title": "Changer de modèle",
                       "description": "Liste les modèles disponibles et change de modèle", "group": "agent"},
        "agent.list": {"slug": "agents", "title": "Changer d’agent",
                       "description": "Liste les agents disponibles et change d'agent", "group": "agent"},
        "mcp.list": {"slug": "mcps", "aliases": ["mcp"], "title": "Serveurs MCP",
                     "description": "Liste et gère les serveurs MCP connectés", "group": "agent"},
        "variant.list": {"slug": "variantes", "aliases": ["reflexion", "effort"], "title": "Variante du modèle",
                         "description": "Change la variante du modèle (effort de raisonnement)", "group": "agent"},
        "provider.connect": {"slug": "connecter", "aliases": ["connexion"], "title": "Connecter une intégration",
                             "description": "Ajoute un fournisseur ou une intégration avec identifiants",
                             "group": "integration"},
        "opencode.highlights": {"slug": "nouveautes", "title": "Nouveautés de la version",
                                "description": "Affiche les nouveautés de la version installée", "group": "system"},
        "opencode.settings": {"slug": "reglages", "aliases": ["parametres", "config"], "title": "Configuration",
                              "description": "Ouvre la configuration d'OpenCode", "group": "system"},
        "opencode.status": {"slug": "etat", "aliases": ["statut"], "title": "État",
                            "description": "Affiche l'état du serveur et de la connexion", "group": "system"},
        "opencode.update": {"slug": "mettre-a-jour", "aliases": ["actualiser"], "title": "Mettre à jour OpenCode",
                            "description": "Met à jour OpenCode vers la dernière version", "group": "system"},
        "server.pair": {"slug": "appairer", "aliases": ["web"], "title": "Appairer un appareil",
                        "description": "Associe un autre appareil à ce serveur", "group": "system"},
        "location.reload": {"slug": "recharger", "title": "Recharger la configuration",
                            "description": "Recharge la configuration sans fermer la session", "group": "system"},
        "opencode.debug": {"slug": "deboguer", "title": "Débogage",
                           "description": "Affiche des informations de débogage", "group": "system"},
        "theme.switch": {"slug": "themes", "title": "Changer de thème",
                         "description": "Liste les thèmes disponibles et change de thème", "group": "system"},
        "help.show": {"slug": "aide", "aliases": ["raccourcis", "aider"], "title": "Aide",
                      "description": "Affiche l'aide d'OpenCode", "group": "system"},
        "app.exit": {"slug": "quitter", "aliases": ["sortir"], "title": "Quitter",
                     "description": "Ferme OpenCode et termine la session", "group": "system"},
        "diff.open": {"slug": "diff", "aliases": ["differences"], "title": "Voir les différences",
                      "description": "Ouvre le visualiseur de différences du projet", "group": "vcs"},
        "stats.open": {"slug": "statistiques", "aliases": ["stats"], "title": "Statistiques",
                       "description": "Affiche les statistiques d'utilisation", "group": "system"},
        "plugins.list": {"slug": "plugins", "aliases": ["extensions"], "title": "Plugins",
                         "description": "Liste et gère les plugins installés", "group": "system"},
        "service.restart": {"slug": "redemarrer", "title": "Redémarrer le service",
                            "description": "Redémarre le service OpenCode en arrière-plan", "group": "system"},
    },
    "zh": {
        "session.new": {"slug": "新建", "title": "新建会话",
                        "description": "开始一个新的对话会话", "group": "session"},
        "session.clear": {"slug": "清空", "title": "清空会话",
                          "description": "清空当前会话，已保存的历史仍会保留", "group": "session"},
        "session.list": {"slug": "会话", "aliases": ["恢复"], "title": "切换会话",
                         "description": "列出并在已打开和最近的会话之间切换", "group": "session"},
        "open.menu": {"slug": "打开", "aliases": ["项目"], "title": "打开会话或项目",
                      "description": "打开已有会话或项目", "group": "session"},
        "session.rename": {"slug": "重命名", "title": "重命名会话",
                           "description": "为当前会话设置新标题", "group": "session", "args": True},
        "session.timeline": {"slug": "消息", "title": "跳转消息",
                             "description": "直接跳转到对话中的某条消息", "group": "session"},
        "session.fork": {"slug": "分叉", "title": "分叉会话",
                         "description": "从当前会话创建新的分支", "group": "session"},
        "session.compact": {"slug": "压缩", "aliases": ["摘要"], "title": "压缩会话",
                            "description": "压缩上下文以释放窗口空间", "group": "session"},
        "session.undo": {"slug": "撤销", "title": "撤销",
                         "description": "删除最后一条消息并还原文件修改", "group": "session"},
        "session.redo": {"slug": "重做", "title": "重做",
                         "description": "恢复被撤销的消息和文件修改", "group": "session"},
        "messages.copy": {"slug": "复制", "title": "复制回复",
                          "description": "复制助手最后一条回复到剪贴板", "group": "session"},
        "session.export": {"slug": "导出", "title": "导出对话",
                           "description": "将对话导出为 Markdown 并在编辑器中打开", "group": "session"},
        "session.terminal": {"slug": "终端", "title": "新建终端",
                             "description": "在项目目录中打开内置终端", "group": "session"},
        "session.aside": {"slug": "旁问", "title": "旁支提问",
                          "description": "在不打断主流程的情况下提出旁支问题",
                          "group": "session", "args": True},
        "session.cd": {"slug": "目录", "aliases": ["cd"], "title": "更改目录",
                       "description": "更改会话的工作目录", "args": True},
        "session.move": {"slug": "工作区", "aliases": ["worktrees"], "title": "管理工作区",
                         "description": "管理项目的工作区（worktrees）", "group": "session"},
        "prompt.editor": {"slug": "编辑器", "title": "打开编辑器",
                          "description": "打开外部编辑器编写消息", "group": "session"},
        "prompt.skills": {"slug": "技能", "aliases": ["skills"], "title": "技能",
                          "description": "列出可用技能并插入到消息中", "group": "prompt"},
        "model.list": {"slug": "模型", "title": "切换模型",
                       "description": "列出可用模型并切换当前模型", "group": "agent"},
        "agent.list": {"slug": "代理", "title": "切换代理",
                       "description": "列出可用代理并切换当前代理", "group": "agent"},
        "mcp.list": {"slug": "mcp", "title": "MCP 服务器",
                     "description": "列出并管理已连接的 MCP 服务器", "group": "agent"},
        "variant.list": {"slug": "变体", "aliases": ["思考"], "title": "模型变体",
                         "description": "切换模型变体（推理强度）", "group": "agent"},
        "provider.connect": {"slug": "连接", "title": "连接集成",
                             "description": "添加带凭据的提供商或集成", "group": "integration"},
        "opencode.highlights": {"slug": "新功能", "title": "版本新功能",
                                "description": "查看当前版本的更新内容", "group": "system"},
        "opencode.settings": {"slug": "设置", "aliases": ["config"], "title": "设置",
                              "description": "打开 OpenCode 设置", "group": "system"},
        "opencode.status": {"slug": "状态", "title": "状态",
                            "description": "查看服务器和连接状态", "group": "system"},
        "opencode.update": {"slug": "更新", "title": "更新 OpenCode",
                            "description": "将 OpenCode 更新到最新版本", "group": "system"},
        "server.pair": {"slug": "配对", "aliases": ["web"], "title": "配对设备",
                        "description": "将其他设备与此服务器配对", "group": "system"},
        "location.reload": {"slug": "重载", "title": "重载配置",
                            "description": "重新加载配置而不关闭会话", "group": "system"},
        "opencode.debug": {"slug": "调试", "title": "调试信息",
                           "description": "显示环境调试信息", "group": "system"},
        "theme.switch": {"slug": "主题", "title": "切换主题",
                         "description": "列出并切换主题", "group": "system"},
        "help.show": {"slug": "帮助", "aliases": ["快捷键"], "title": "帮助",
                      "description": "显示 OpenCode 帮助", "group": "system"},
        "app.exit": {"slug": "退出", "title": "退出",
                     "description": "关闭 OpenCode 并结束会话", "group": "system"},
        "diff.open": {"slug": "差异", "title": "查看差异",
                      "description": "打开项目的差异查看器", "group": "vcs"},
        "stats.open": {"slug": "统计", "title": "使用统计",
                       "description": "显示 OpenCode 使用统计", "group": "system"},
        "plugins.list": {"slug": "插件", "title": "插件",
                         "description": "列出并管理已安装的插件", "group": "system"},
        "service.restart": {"slug": "重启", "title": "重启服务",
                            "description": "在后台重启 OpenCode 服务", "group": "system"},
    },
}


def build_locales_payload() -> dict[str, object]:
    """Monta o `locales.json` consumido pelo plugin (determinístico)."""
    catalog: dict[str, object] = {}
    for locale, commands in PT_CATALOG.items():
        catalog[locale] = {
            "groups": GROUPS[locale],
            "commands": commands,
        }
    return {
        "fallback": "pt-BR",
        "languages": PT_LANGUAGES,
        "switcher": PT_SWITCHER,
        "categories": CATEGORIES,
        "labels": LABELS,
        "catalog": catalog,
    }


# Fonte do plugin (TypeScript, executado pelo Bun embutido no OpenCode).
# `@opencode/plugin/tui` é resolvido em runtime pelo próprio OpenCode e o
# catálogo vem de `locales.json` (gerado a partir de PT_CATALOG).
PT_PLUGIN_TUI_TS: str = r'''import { Plugin } from "@opencode/plugin/tui"
import type { KeymapCommand } from "@opencode/plugin/tui/context"
import LOCALES from "./locales.json"
import { mkdirSync, readFileSync, writeFileSync } from "node:fs"
import { homedir } from "node:os"
import { dirname, join } from "node:path"

/**
 * UFVAI — comandos barra localizados (pt-BR, en, es, fr, zh).
 *
 * Cada entrada usa o MESMO id do comando nativo do OpenCode e apenas traduz
 * slug, título (curto) e descrição (explicativa). `run: () => false` deixa o
 * comando nativo executar; `bind: false` evita captura de teclas; o objeto
 * nativo é copiado (`...rest`) para preservar palette/suggested/enabled.
 */

type Entry = {
  slug?: string
  aliases?: string[]
  title: string
  description: string
  group?: string
  args?: boolean
}

type LocaleData = {
  groups: Record<string, string>
  commands: Record<string, Entry>
}

const DATA = LOCALES as unknown as {
  fallback: string
  languages: Record<string, string>
  switcher: Record<string, Entry>
  categories: Record<string, Record<string, string>>
  labels: Record<string, Record<string, string>>
  catalog: Record<string, LocaleData>
}

const SUPPORTED = Object.keys(DATA.languages)

/**
 * O boot (run_fast) lê este arquivo para aplicar os textos do prompt
 * (frases de exemplo e "Ask anything") no binário do OpenCode no idioma certo.
 */
const LOCALE_FILE = join(homedir(), ".config", "opencode", "ufvai-language.json")

function readLocaleFile(): string | undefined {
  try {
    const parsed = JSON.parse(readFileSync(LOCALE_FILE, "utf8"))
    const locale = parsed?.locale
    return typeof locale === "string" && SUPPORTED.includes(locale) ? locale : undefined
  } catch {
    return undefined
  }
}

function writeLocaleFile(locale: string) {
  try {
    mkdirSync(dirname(LOCALE_FILE), { recursive: true })
    writeFileSync(LOCALE_FILE, `${JSON.stringify({ locale }, null, 2)}\n`)
  } catch {
    // melhor esforço: nunca derruba a TUI por causa do arquivo
  }
}

function matchLocale(raw: string): string | undefined {
  const tag = raw.trim().toLowerCase().replace("_", "-")
  if (!tag) return undefined
  if (tag.startsWith("pt")) return "pt-BR"
  if (tag.startsWith("es")) return "es"
  if (tag.startsWith("fr")) return "fr"
  if (tag.startsWith("zh")) return "zh"
  if (tag.startsWith("en")) return "en"
  return undefined
}

/** Locale do sistema (C/POSIX/inglês caem no padrão do produto). */
function detectLocale(): string {
  const explicit = process.env.UFVAI_LANG || process.env.PESQUISAI_LANG || ""
  const explicitMatch = matchLocale(explicit)
  if (explicitMatch) return explicitMatch

  const system =
    process.env.LC_ALL || process.env.LC_MESSAGES || process.env.LANG || ""
  const systemMatch = matchLocale(system)
  // `C`, `POSIX` e `en_*` são comuns em contêineres: sem sinal confiável.
  if (systemMatch && systemMatch !== "en") return systemMatch
  return DATA.fallback
}

export default Plugin.define({
  id: "ufvai.pt",
  setup(context) {
    // Idioma escolhido pelo usuário (durable store) — vazio = automático.
    const [settings, updateSettings] = context.storage.store("ufvai.locale", {
      initial: { locale: "" },
    })
    // Estado reativo para reavaliar a camada quando novos comandos entram no
    // keymap (ex.: comandos de sessão ao abrir uma sessão).
    const [state, updateState] = context.storage.memory("ufvai.pt", {
      initial: { revision: 0 },
    })
    // Objetos ORIGINAIS do OpenCode por id: deles copiamos palette, suggested,
    // enabled, arguments etc. — sem isso os comandos somem da paleta ctrl+p.
    const originals = new Map<string, KeymapCommand>()

    // Acesso ao catálogo de comandos do keymap. A chamada canônica é
    // `commands()`; a leitura alternativa (`comandos`) é defensiva — a v0.6.24
    // chegou a renomear esse literal no binário e, naquele estado, a
    // propriedade do host passa a se chamar `comandos` (o rename global foi
    // revertido por quebrar o esquema SQLite, mas a tolerância fica).
    const keymapCommands = (): KeymapCommand[] => {
      const keymap = context.keymap as unknown as Record<string, unknown>
      const fn = (keymap["commands"] ?? keymap["comandos"]) as
        | undefined
        | (() => KeymapCommand[])
      return typeof fn === "function" ? fn.call(context.keymap) : []
    }

    const detect = detectLocale()
    // O arquivo gravado por `/idioma` (ou pelo painel) tem prioridade sobre o
    // ambiente: mantém TUI e textos do prompt no mesmo idioma.
    const savedLocale = readLocaleFile()
    if (savedLocale && settings.locale !== savedLocale) {
      updateSettings((draft) => { draft.locale = savedLocale })
    }

    // IDs traduzíveis: catálogo de comandos `/barra` + rótulos de menu
    // (`labels`). Capturamos o objeto nativo de cada um para espelhar título e
    // categoria sem perder palette/suggested/enabled/binding.
    const tracked = new Set<string>()
    for (const data of Object.values(DATA.catalog)) {
      for (const id of Object.keys(data.commands ?? {})) tracked.add(id)
    }
    for (const table of Object.values(DATA.labels ?? {})) {
      for (const id of Object.keys(table ?? {})) tracked.add(id)
    }

    // IDs que já emitimos como espelho — nunca devem voltar para `originals`.
    const mirrored = new Set<string>()

    const capture = () => {
      let changed = false
      for (const command of keymapCommands()) {
        const id = command.id
        // `mirrored` evita capturar o NOSSO próprio espelho de volta: comparar
        // títulos não serve, pois comandos como "Plugins" têm tradução igual ao
        // inglês e ficariam sem espelho (categoria em inglês na paleta).
        if (!id || !tracked.has(id) || originals.has(id) || mirrored.has(id)) continue
        originals.set(id, command)
        changed = true
      }
      if (changed) updateState((draft) => { draft.revision++ })
    }

    const currentLocale = () => {
      const chosen = settings.locale
      if (chosen && SUPPORTED.includes(chosen)) return chosen
      return detect
    }

    capture()
    const started = Date.now()
    let timer: ReturnType<typeof setTimeout> | undefined
    const tick = () => {
      capture()
      timer = setTimeout(tick, Date.now() - started < 5000 ? 400 : 3000)
    }
    timer = setTimeout(tick, 400)

    context.keymap.layer(() => {
      // Reage à troca de idioma e à chegada de novos comandos nativos.
      const locale = currentLocale()
      state.revision
      const localeData = DATA.catalog[locale]
      const categories = DATA.categories?.[locale] ?? {}
      const labels = DATA.labels?.[locale] ?? {}
      const commands: KeymapCommand[] = []
      // Categoria nativa (ex.: "Session") → rótulo localizado; desconhecidas
      // são preservadas como estão.
      const group = (value?: string) => (value && categories[value]) || value

      if (locale !== "en") {
        const ids = new Set<string>([
          ...Object.keys(localeData?.commands ?? {}),
          ...Object.keys(labels),
        ])
        for (const id of ids) {
          const base = originals.get(id)
          if (!base) continue
          const spec = localeData?.commands?.[id]
          const title = labels[id] ?? spec?.title
          if (!title) continue
          const { bind: _bind, title: _title, description: _description, group: _group, slash: _slash, ...rest } = base
          commands.push({
            ...rest,
            id,
            title,
            // Sem descrição na paleta/autocompletar: o usuário pediu "só o
            // comando" (a lista ficava poluída). As descrições continuam no
            // catálogo para documentação/ajuda futura, mas não são emitidas.
            group: group(spec?.group ? localeData!.groups[spec.group] : base.group),
            bind: false,
            // Só comandos do catálogo ganham atalho `/barra`.
            ...(spec?.slug
              ? {
                  slash: {
                    name: spec.slug,
                    ...(spec.aliases ? { aliases: spec.aliases } : {}),
                    ...(spec.args ?? _slash?.arguments ? { arguments: true as const } : {}),
                  },
                }
              : {}),
            run: () => false,
          })
          mirrored.add(id)
        }
      }

      // Comando de troca de idioma (sempre disponível, no idioma corrente).
      const switcher = DATA.switcher[locale] ?? DATA.switcher[DATA.fallback]
      commands.push({
        id: "ufvai.locale",
        title: switcher.title,
        group: localeData ? localeData.groups.system : undefined,
        palette: true,
        bind: false,
        slash: { name: switcher.slug, aliases: switcher.aliases },
        run: async () => {
          const picked = await context.ui.dialog.select<string>({
            title: switcher.title,
            current: locale,
            options: SUPPORTED.map((code) => ({
              title: DATA.languages[code] ?? code,
              value: code,
              description: code === locale ? "✓" : undefined,
            })),
          })
          if (!picked) return
          updateSettings((draft) => { draft.locale = picked })
          writeLocaleFile(picked)
          context.ui.toast.show({ message: `${DATA.languages[picked] ?? picked}` })
        },
      })

      return { mode: "global", priority: 100, commands }
    })

    // ── v0.6.25: marca UFVAI na tela de NOVA SESSÃO ──────────────────────
    // A arte de blocos do motor ("opencode") é desenhada PROCEDURALMENTE a
    // partir de dados que vivem no bytecode COMPRIMIDO (213 MB) — não há
    // literal substituível (varredura: as 173 ocorrências de "opencode" na
    // tabela UTF-16 são do catálogo de modelos; na fonte UTF-8 há só 6
    // escapes de bloco, todos da biblioteca `cfonts` embutida). Trocar a
    // arte exigiria recompilar o bytecode do motor.
    //
    // A identidade UFVAI é entregue pela API PÚBLICA de plugins. Slots
    // válidos no motor (registro interno): `home.footer`, `prompt.footer`,
    // `prompt.footer.status`, `sidebar.content`, `sidebar.footer`,
    // `session.panel`, `storybook`. (`session.composer.top` NÃO é slot de
    // plugin — é apenas um caminho da árvore de componentes: o registro o
    // ignora em silêncio.)
    const brandFooter = context.ui.slot({
      append: "prompt.footer",
      render: () => <text fg={context.theme.text.muted}>· pesquisa científica</text>,
    })

    const brandSlot = context.ui.slot({
      append: "prompt.footer.status",
      render: () => <text fg={context.theme.text.base}>UFVAI</text>,
    })

    return () => {
      if (timer) clearTimeout(timer)
      brandFooter?.()
      brandSlot?.()
    }
  },
})
'''


def install_pt_plugin(plugin_dir: str | None = None) -> str:
    """Grava o pacote do plugin de TUI e devolve o diretório instalado.

    Idempotente: reescreve apenas ``package.json``, ``locales.json`` e
    ``tui.tsx`` (conteúdo determinístico, sem estado do usuário dentro).
    Qualquer outro arquivo que o usuário tenha colocado na pasta é preservado.
    """
    root = plugin_dir or PT_PLUGIN_DIR
    os.makedirs(root, exist_ok=True)
    # v0.6.25: o plugin virou .tsx — os slots da API de plugins exigem JSX
    # (``render`` precisa devolver um elemento <text>, não texto solto).
    # ORDEM IMPORTA: o .tsx é gravado ANTES do package.json, senão há uma
    # janela em que o package.json aponta para um arquivo inexistente e o
    # motor recarrega o plugin sem os 37 comandos.
    with open(os.path.join(root, "tui.tsx"), "w", encoding="utf-8") as f:
        f.write(PT_PLUGIN_TUI_TS)
    with open(os.path.join(root, "package.json"), "w", encoding="utf-8") as f:
        json.dump(PT_PLUGIN_PACKAGE_JSON, f, ensure_ascii=False, indent=2)
        f.write("\n")
    with open(os.path.join(root, "locales.json"), "w", encoding="utf-8") as f:
        json.dump(build_locales_payload(), f, ensure_ascii=False, indent=2)
        f.write("\n")
    legacy = os.path.join(root, "tui.ts")
    if os.path.exists(legacy):
        try:
            os.remove(legacy)
        except OSError:
            pass
    return root
