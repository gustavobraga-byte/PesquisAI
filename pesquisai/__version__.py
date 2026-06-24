"""
__version__.py — Fonte única de versão do PesquisAI v0.4.2.2.

Este repositório contém o **PesquisAI release v0.4.2.2** + sandbox pessoal:

Estrutura do repositório:
  /                       # PesquisAI release v0.4.2.2 (raiz)
  ├── agents/             # AGENTS.md multilíngues (4 idiomas)
  ├── docs/               # Documentação (CHANGELOG, PATCH, etc.)
  ├── grant_finder/       # Skill de busca de fomento
  ├── i18n/               # Módulo multilíngue
  ├── pesquisai/          # Módulo PesquisAI (v0.4.2.2)
  │   ├── __version__.py  # ⭐ Fonte única da versão (v0.4.2.2)
  │   ├── launch_app.py
  │   ├── launch_app_responsive.py
  │   └── launch_app_responsive_v041.py
  ├── releases/v0.4.0/    # Release isolada completa
  ├── sandbox/            # 🏖️ Arquivos não-PesquisAI
  ├── sessions/           # Logs de sessão
  └── skills/             # Skills adicionais (grant-finder, meta-search-br)

Compatível com o PesquisAI principal (v0.2.1+).

═════════════════════════════════════════════════════════════════════════
Histórico de versões:
═════════════════════════════════════════════════════════════════════════
  v0.4.0  — Release inicial com agente de pesquisa
  v0.4.1  — UI Fixes (Responsive + Theme + Language)
            • 6 media queries + hamburger menu
            • toggleTheme() recarrega iframe ttyd
            • Dropdown 4 idiomas (pt_BR, en_US, es_ES, fr_FR)
  v0.4.2  — Footer Responsive + Multilingual AGENTS.md
            • Rodapé 100% responsivo (flex-wrap + 2 linhas)
            • Modal de Diretrizes com AGENTS.md multilíngue
            • Endpoint GET /api/agents?lang=xx_XX
  v0.4.2.1 — Ses_10a4: 3 correções da sessão do usuário
            • Tema CLARO: contraste corrigido nos 6 modais
              (background:#181b1e fixo → variável CSS .modal-shell)
            • Dashboard de Saúde: openHealth() faz fetch em /api/health
              e popula a lista com badges de status
            • Modal de Diretrizes renderiza markdown (marked.js +
              github-markdown-css) ao invés de mostrar o .md como texto cru
  v0.4.2.3 — Ses_106b: 🔥 BUGFIX CRÍTICO — botões do wrapper não funcionavam
            • 🐛 JS BROKEN: a string tripla do launch_app_responsive_v041.py
              continha escapes de aspas que Python removia durante a compilação,
              gerando JavaScript com sintaxe inválida → TODOS os botões do HTML
              paravam de funcionar (erro SyntaxError no <script>)
            • ✅ renderSessions: trocado onclick inline (com escapes frágeis)
              por atributo data-session-id + event delegation (sem aspas dinâmicas)
            • ✅ restoreSession: trocado confirm com aspas escapadas por
              confirm(...chr(34)...) (concat JS, sem aspas escapadas)
            • ✅ escapeHtml: trocado object literal com aspas por if/else chain
              (evita conflito de aspas dentro do mapeamento)
            • ✅ Validado: Node.js --check passa, 79/79 testes pytest OK,
              10/10 funções JS verificadas
  v0.4.2.2 — Ses_10a4+: 6 correções adicionais (sessão do usuário)
            • 🖥️ FOOTER PC: botão provedor + "Powered by OpenCode"
              alinhados à direita no desktop (margin-left:auto)
            • 🧩 SKILLS: grant-finder e meta-search-br adicionados em
              skills/ com links para clonar do GitHub
            • 📜 SESSÕES: openSessions() agora faz fetch em /api/sessions
              e popula a lista (estava apenas abrindo o modal)
            • 🌍 LANG: ao trocar idioma, o ttyd é reiniciado com
              saudação no idioma + "(a partir de agora responda em X)"
              ao invés de "--prompt 'oi'" genérico
            • 📦 __version__.py movido para pesquisai/__version__.py
            • 🧹 AGENTS.md: removido "- [link/lien/enlace]" das 4 variantes
"""

# ── Versão semântica (SemVer) ──────────────────────────────────
__version__: str = "0.4.2.3"

# ── Metadados do release ───────────────────────────────────────
__release_date__: str = "2026-06-24"
__codename__: str = "ses_106b hotfix (JS broken escapes — buttons restored)"

# ── Identidade do projeto ──────────────────────────────────────
__author__: str = "Gustavo Bastos Braga"
__author_email__: str = "gustavo.braga@ufv.br"
__institution__: str = "Universidade Federal de Viçosa (UFV)"
__registry__: str = "10356285004"
__repo_url__: str = "https://github.com/gustavobraga-byte/PesquisAI"
__license__: str = "MIT"

# ── Compatibilidade ────────────────────────────────────────────
__pesquisai_min_version__: str = "0.2.1"
__pesquisai_max_version__: str = "0.3.x"  # até próximo major

# ── Tema padrão ────────────────────────────────────────────────
__default_theme__: str = "pesquisai"  # 🌙 ESCURO (anti-flash CSS ativo)
__supported_themes__: list[str] = ["pesquisai", "pesquisai-light"]

# ── Componentes incluídos neste release ─────────────────────────
__components__: dict[str, str] = {
    "grant_finder": "0.1.0",
    "grant_finder_skill": "0.1.0",       # NOVO v0.4.2.2: link clonar
    "i18n": "0.2.0",
    "launch_app_responsive": "0.2.0",     # base responsiva
    "launch_app_responsive_v041": "0.1.0",  # drop-in patch v0.4.1
    "launch_app_responsive_v0421": "0.1.0",  # v0.4.2.1: 3 correções ses_10a4
    "launch_app_responsive_v0422": "0.1.0",  # NOVO v0.4.2.2: 6 correções ses_10a4+
    "launch_app_responsive_v0423": "0.1.0",  # NOVO v0.4.2.3: hotfix escapes JS
    "agents_multilingual": "0.1.0",
    "agents_modal": "0.1.0",              # modal de Diretrizes com markdown
    "footer_responsive": "0.1.0",         # footer com flex-wrap + 2 linhas
    "footer_pc_align": "0.1.0",           # NOVO v0.4.2.2: provedor + OpenCode à direita
    "sessions_loader": "0.1.0",           # NOVO v0.4.2.2: openSessions faz fetch
    "lang_aware_greeting": "0.1.0",       # NOVO v0.4.2.2: saudação no idioma
}

# ── Idiomas suportados ─────────────────────────────────────────
__supported_languages__: list[str] = ["pt_BR", "en_US", "es_ES", "fr_FR"]

# ── Saudações iniciais por idioma (v0.4.2.2) ───────────────────
# Usadas pelo ttyd ao iniciar o terminal e ao trocar de idioma.
# Cada tupla = (saudação_curta, instrução_persistente, palavra "dica" no idioma)
# v0.4.2.2 (ajuste pós-ses_10a4+): removida a frase "Eu sou o PesquisAI" —
# a saudação agora é apenas a saudação curta + dica entre parênteses.
__language_greetings__: dict[str, tuple[str, str, str]] = {
    "pt_BR": (
        "Olá!",
        "A partir de agora responda em português brasileiro.",
        "Dica",
    ),
    "en_US": (
        "Hello!",
        "From now on, please respond in English.",
        "Tip",
    ),
    "es_ES": (
        "¡Hola!",
        "A partir de ahora responda en español.",
        "Consejo",
    ),
    "fr_FR": (
        "Bonjour !",
        "À partir de maintenant, répondez en français.",
        "Astuce",
    ),
}

# ── Agências de fomento integradas ─────────────────────────────
__supported_grant_agencies__: list[str] = [
    # Brasil
    "CNPq", "CAPES", "FAPEMIG", "FAPESP", "FINEP",
    # Internacional
    "NIH", "NSF", "ERC", "Wellcome", "Horizon_Europe",
]

# ── Skills extras (v0.4.2.2) ────────────────────────────────────
__extra_skills__: list[dict[str, str]] = [
    {
        "id": "grant-finder",
        "name": "Grant Finder",
        "description": "Busca de editais de fomento em agências BR e internacionais.",
        "repo": "https://github.com/gustavobraga-byte/grant-finder",
        "local_path": "skills/grant-finder/",
    },
    {
        "id": "meta-search-br",
        "name": "Meta-Search BR",
        "description": "Busca unificada em 7 bases acadêmicas (PubMed, SciELO, LILACS, BDTD, OpenAlex, arXiv, bioRxiv).",
        "repo": "https://github.com/gustavobraga-byte/meta-search-br",
        "local_path": "skills/meta-search-br/",
    },
]

# ── Endpoints REST disponíveis ─────────────────────────────────
__api_endpoints__: list[str] = [
    "GET  /",                       # Wrapper HTML
    "GET  /api/sessions",           # Lista sessões
    "GET  /api/backups",            # Lista backups do Drive
    "GET  /api/health",             # Diagnóstico do sistema
    "GET  /api/theme",              # Tema atual
    "POST /api/theme",              # Persiste tema
    "GET  /api/diagnose",           # Diagnóstico completo
    "GET  /api/debug",              # Debug de chaves
    "GET  /api/apikey",             # Lista/máscara chaves
    "POST /api/apikey",             # Salva chave criptografada
    "POST /api/apikey/apply",       # Aplica chaves no env
    "POST /api/run_terminal",       # Executa comando no ttyd
    "POST /api/backup",             # Exporta sessão para Drive
    "POST /api/restore",            # Importa sessão do Drive
    "GET  /api/agents?lang=xx_XX",  # v0.4.2: serve AGENTS.md no idioma
    "POST /api/lang",               # NOVO v0.4.2.2: persiste idioma
    "GET  /api/lang",               # NOVO v0.4.2.2: lê idioma atual
]


def get_version() -> str:
    """Retorna a versão formatada para exibição."""
    return f"v{__version__} ({__codename__})"


def get_version_short() -> str:
    """Retorna apenas o número da versão."""
    return __version__


def get_greeting(lang: str = "pt_BR") -> str:
    """Retorna a saudação inicial do ttyd para o idioma solicitado.

    Formato: "{saudação_curta} ({dica}: {instrução_persistente})"
    Exemplo pt_BR: "Olá! (Dica: A partir de agora responda em português brasileiro.)"

    v0.4.2.2 (pós-ses_10a4+): a frase "Eu sou o PesquisAI" foi removida;
    agora a saudação é apenas a saudação curta + dica entre parênteses.
    """
    lang = (lang or "pt_BR").split("_")[0]
    full_lang = {"pt": "pt_BR", "en": "en_US", "es": "es_ES", "fr": "fr_FR"}.get(lang, "pt_BR")
    greeting, persist, tip = __language_greetings__.get(
        full_lang, __language_greetings__["pt_BR"]
    )
    return f"{greeting} ({tip}: {persist})"


def get_full_metadata() -> dict[str, str]:
    """Retorna todos os metadados como dict (útil para logging/diagnóstico)."""
    return {
        "version": __version__,
        "release_date": __release_date__,
        "codename": __codename__,
        "author": __author__,
        "email": __author_email__,
        "institution": __institution__,
        "registry": __registry__,
        "license": __license__,
        "languages": ", ".join(__supported_languages__),
        "agencies": ", ".join(__supported_grant_agencies__),
        "extra_skills": ", ".join(s["id"] for s in __extra_skills__),
        "endpoints_count": len(__api_endpoints__),
    }
