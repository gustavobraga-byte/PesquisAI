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
═══════════════════════════════════════════════════════════════════════
  v0.6.16 — 🐛 Fix retorno: heartbeat único apenas no clique "Continuar"
             • BUG v0.6.14: ao exibir "Bem-vindo de volta" o frontend disparava
               _heartbeat() imediato + setTimeout 2,5s + clique → 2-3 linhas
               "usuario_ativo" por retorno na planilha.
             • FIX: removidos os dois disparos automáticos; /api/access agora
               só é chamado no clique "Continuar". Guard _heartbeatSent impede
               duplo clique. Planilha registra exatamente 1 linha por retorno.
  v0.6.15 — 🐛 Prompt inicial respeita idioma detectado do sistema/navegador
            • BUG: _current_lang="pt_BR" fixo impedia _detect_system_lang() de
              rodar (truthy → nunca caía no `if not _current_lang`). ttyd
              sempre iniciava em pt_BR mesmo com LANG=en_US ou navegador em
              inglês. launch() chamava start_ttyd() ANTES de start_wrapper_server()
              que faria a detecção — ordem errada.
            • FIX backend `launch_app.py`: _current_lang inicia "" (vazio);
              novo helper _ensure_lang_initialized() (cookie file > PESQUISAI_LANG
              env > _detect_system_lang() > persiste) chamado em launch() ANTES
              do 1º ttyd e em start_wrapper_server() (idempotente). _build_ttyd_cmd
              agora cai em _detect_system_lang() quando _current_lang vazio.
              Normalização _LANG_MAP e _persist_lang garantidas.
            • FIX frontend `launch_app_responsive_v041.py`: window.load agora
              compara `GET /api/lang` (backend) com `getCurrentLang()` (navegador
              via navigator.language/cookie). Se divergir e LANGS válido, chama
              automaticamente `setLang(_currentLang)` uma vez por sessão
              (sessionStorage "ufvai_lang_synced") — corrige instalações antigas
              onde backend ficou preso em pt_BR.
  v0.6.14 — 🐛 Fix IP localhost + todo acesso logado na planilha
            • IP LOCALHOST FIX: _get_client_ip() agora aceita IP enviado pelo
              cliente (via JS ipify → POST /api/consent e /api/access) e o
              prefere quando for público — corrige Colab onde o proxy NÃO
              injeta X-Forwarded-For e o servidor via só 127.0.0.1. Fallback
              mantém headers (X-Forwarded-For, X-Real-IP etc.). Log de headers
              quando IP ainda é privado para diagnóstico.
            • TODO ACESSO NA PLANILHA: frontend agora busca IP público via
              https://api.ipify.org?format=json (CORS) no carregamento e o
              envia junto ao heartbeat; /api/access aceita {"ip": "..."} e
              registra flag "usuario_ativo" em TODO carregamento de usuário
              já registrado (antes só no clique "Continuar"). Backend também
              registra heartbeat automaticamente no GET /api/consent quando
              detecta revisita (perfil já aceito).
  v0.6.13 — 🐛 IP real do cliente + heartbeat "usuario_ativo" na revisita
            • IP: _get_client_ip() agora percorre a cadeia X-Forwarded-For
              da DIREITA para a esquerda, saltando IPs privados/loopback
              (127.0.0.1, 10.x, 172.16-31.x, 192.168.x) e devolve o
              primeiro IP PÚBLICO — no Colab o proxy do Google injeta o IP
              real do navegador; antes caía em client_address=127.0.0.1.
              Headers extra: X-Real-IP, CF-Connecting-IP, True-Client-IP,
              X-Forwarded, Forwarded (RFC 7239).
            • REVISITA: telemetry._read_profile() agora cai no backup
              persistente (Drive/~/PesquisAI backups/ufvai_consentimento.json)
              quando o ~/.config efêmero perdeu o e-mail — o heartbeat
              /api/access (flag "usuario_ativo") voltava SKIP e não gravava
              a revisita do usuário já registrado na planilha.
  v0.6.9 — 📜 Termos v2.1: telemetria opt-out + e-mail obrigatório +
            perfil persistente + botão Manual
            • TELEMETRIA OPT-OUT (LGPD art. 7º IX): caixa vem MARCADA
              (ativa por padrão), sem cookie _ga (analytics_storage
              'denied'); evento custom ufvai_session removido — canal
              client-side limitado ao page_view padrão; oposição a
              qualquer momento (art. 18 §2º) via caixa ou UFVAI_TELEMETRY=0.
            • E-MAIL DE ATIVAÇÃO OBRIGATÓRIO (art. 7º V): POST /api/consent
              devolve 400 sem e-mail válido; eliminação (art. 18) mantida.
            • PERFIL PERSISTENTE: backups/ufvai_consentimento.json (Colab:
              no Drive) guarda e-mail+SHA-256+preferências; GET /api/consent
              expõe profile → tela de Termos pré-preenchida e, se a mesma
              versão já foi aceita, pulada diretamente.
            • LOGS FORA DO DRIVE (Colab): ttyd.log → /tmp/ufvai-logs/;
              pasta logs/ do Drive não é mais criada.
            • BOTÃO 📘 MANUAL: rota /api/manual serve o MANUAL.md local
              (fallback GitHub); modal com Recarregar/Ver fonte; ícones
              distintos p/ Diretrizes (clipboard-list) e Manual (book-open);
              i18n manual.* nos 5 idiomas; tela de Termos responsiva
              (mobile/tablet, media queries ≤640px e landscape).
            • CORREÇÃO DebugView (bug v0.6.2): UFVAI_TELEMETRY_DEBUG agora
              envia "debug_mode":1 no params do evento (o antigo parâmetro
              de URL &debug_view=1 era ignorado pelo GA4).
            • Docs: TERMS_OF_USE v2.1 §7 (opt-out art. 7º IX + e-mail
              art. 7º V), PRIVACY.md, TELEMETRY.md §§4-5.
  v0.6.8 — 🧹 Painel único (zero prints) + LGPD reordenação + planilha de contatos
            • POLÍTICA PAINEL ÚNICO: em Colab todo feedback visual vem só do
              painel de boot (_BootPanel); prints verbosos suprimidos
              (launch_app/ttyd/jokes → logger.debug), warnings httplib2
              silenciados, drive.mount sem "Mounted at..." — painel é a única
              saída; offline mantém prints normais. progress_bar ASCII só offline.
            • LGPD: opcionais (estatísticas + e-mail) AGORA ANTES do
              "Li e aceito" — ordem: [ ] Opcional estatísticas → [ ] Opcional
              e-mail → [x] Li e aceito (obrigatório); vTerms 3 → 4.
            • Versão na tela de Termos corrigida: placeholder {__VERSION__} e
              variante __UFVAI_VERSION__ substituídos por 0.6.8; citação ABNT
              atualizada; favicon/proxy continua ok.
            • Planilha de contatos: criação automática via Drive/Sheets API
              (título "UFVAI — Contatos"), Apps Script Web App pronto
              (APPS_SCRIPT_PLANILHA_CONTATO.gs), endpoint injetado no painel
              Admin e em ufvai.env; fallback manual documentado.
  v0.6.7 — 🖼️ Tela de carregamento do Colab no tema da logomarca +
             ✉️ canal de contato opt-in configurável pela UI
            • BARRA DESDE O INÍCIO: um único painel leve no tema da
              logomarca (papel off-white, wordmark UFV navy + AI dourado)
              nasce na fase de clone do notebook e percorre TODA a
              inicialização (setup → launch) sem reiniciar; mensagens/
              checkpoints sempre ABAIXO da barra, percentual monotônico.
            • progress_bar.py aposentou a barra escura e virou driver do
              painel único (singleton get_boot_panel(), mesmo display_id);
              begin() idempotente; active() commita checkpoint pendente.
            • Botão final com a LOGO REAL (base64) no lugar do texto
              "✨ pronto"; badge verde separado removido no Colab;
              PesquisAI.ipynb rebrandizado (citação ABNT v0.6.7).
            • Canal de contato: URL HTTPS configurável no painel 📊
              Telemetria (Admin), salva em ~/.config/ufvai_telemetry.json;
              save_admin_config() parcial por campo; TELEMETRY.md §9.
  v0.6.6 — 🔐 Registro voluntário LGPD + Google Sheets (rebuild sobre 0.6.4)
            • registration.py: opt-in separado dos Termos, revogável
              (art. 18 VI), backup criptografado no Drive; webhook
              genérico UFVAI_REGISTRATION_URL (sem SMTP; PII nunca ao GA4).
            • scripts/google-apps-script/registration_webhook.gs + guia
              docs/REGISTRATION_SHEETS.md (+ token opcional).
            • Base = 0.6.4 estável (0.6.5 retirado por falha de splash/
              killpg/launcher); pytest 227/227.═
  v0.6.5 — 🔐 Terminal à prova de travamentos + splash de carregamento
            • KILL CIRÚRGICO: o ttyd é LÍDER do próprio grupo de processos
              (start_new_session=True) e fica rastreado em _TTYD_PROC —
              _stop_terminal() mata a árvore inteira (ttyd + bash + opencode)
              com um único killpg, sem o antigo pkill -f opencode global que
              matava o agente hospedeiro. Fallback determinístico:
              pkill -9 -x ttyd (COMM exato, nunca -f).
            • /api/ttyd_ready: o frontend faz polling antes de apontar o
              iframe — fim do ERR_CONNECTION_REFUSED exibido no boot, na
              troca de idioma e na restauração de sessão.
            • SPLASH DE CARREGAMENTO (boot-splash) na UI: logo UFVAI +
              status "Iniciando terminal…" e botão Recarregar nos 5 idiomas;
              timeout/falha com retorno honesto (sem reload às cegas).
            • _build_ttyd_cmd() extraído para retry determinístico;
              restart por idioma e restauração usam _ensure_terminal_ready()
              com retorno REAL (antes respondiam "ok" mesmo com a porta
              travada — causa do ERR_CONNECTION_REFUSED persistente).
  v0.6.4 — 🪪 Marca UFVAI completa · 🎨 Temas UFVAI no terminal · 🖼️ Logo oficial
            • AGENTS.md + agents/*.md (5 idiomas): agente agora se apresenta
              como UFVAI (IDs técnicos preservados: PESQUISAI_OBSIDIAN_VAULT,
              ~/PesquisAI, pacote pesquisai, tags pesquisai/*).
            • TEMAS DO TERMINAL (TUI): paleta harmonizada com a identidade
              UFVAI — escuro: fundos azul-noite #141c24/#1f2831, acento dourado
              #d4b56a/#b29149, amarelo UFV #D1A705; claro: papel quente + texto
              azul-escuro. Azul antigo #4fc3f7 eliminado.
            • Wrapper: fallback JS do applyWrapperTheme() alinhado ao CSS
              canônico (antes sobrescrevia com teal #157a73/#46a39b); tema
              claro dourado sobre papel; anti-flash #141c24; banner Colab em
              gradiente dourado.
            • LOGO OFICIAL na tela de Termos (assets/logo-oficial-288.jpg,
              servida por nova rota /assets/* offline-safe com whitelist e
              traversal guard). Modal de onboarding antigo do PesquisAI
              (welcome-hint) REMOVIDO — Termos é a única abertura.
            • Termos de Uso v2.0 (LGPD art. 7ºI/18, Portaria CNPq 2.664/2026,
              POSIC-UFV Res. Consu 12/2024, foro Viçosa/MG) + PRIVACY.md
              (direitos art. 18, DPO UFV, transferência internacional) +
              LICENSE com NOTICE de marca. Re-consentimento forçado
              (ufvai_terms_version=2).
            • TELEMETRY.md: guia do administrador em 8 passos (GA4 MP:
              propriedade → ID de medição → api_secret → ufvai.env/Colab →
              DebugView) + o que o admin vê × nunca vê + LGPD operacional.
            • install-offline.sh reescrito v0.6.4 (marca, portas 8001/8000,
              modelo config/ufvai.env, atalho ufvai).
  v0.6.3 — 🔌 Servidor persistente (offline) + 🎨 ícone UFVAI no dock
            • BUG CRÍTICO (offline): o wrapper HTTP roda em thread daemon —
              quando run() retornava, o interpretador encerrava e a porta
              8001 CAIA segundos após iniciar ("ERR_CONNECTION_REFUSED").
              No Colab não aparecia porque o kernel fica vivo.
              Fix: _offline_keep_alive() mantém o processo vivo fora do
              Colab (Ctrl+C / SIGTERM encerra; UFVAI_NO_KEEPALIVE=1 desliga).
            • REGRESSÃO restaurada: servidor dual-stack no loopback —
              Chromium/Firefox preferem ::1; sem listener IPv6 dava
              "conexão recusada" (padrão do 0.5.x).
            • Ícone: janela --app com WM_CLASS "UFVAI" agora casa com
              ufvai-app.desktop (StartupWMClass) + PNGs hicolor 256/128/64 —
              o dock mostra a lupa UFVAI em vez do ícone do Chromium.
  v0.6.2 — ⌨️ Terminal gravável + 🖥️ launcher app-mode + 📊 telemetria debug
            • BUG CRÍTICO (input): v0.6.0 perdeu a flag --writable do ttyd —
              o terminal ficava READ-ONLY ("não consigo digitar"). Restaurada
              em start_ttyd() e na restauração de sessão.
            • LAUNCHER (.deb): restaurado o comportamento do v0.5.1.10 que
              abria a UI como APP separado (Chrome --app/Chromium/Firefox/
              xdg-open) após esperar a porta 8001 responder (curl, até 180 s),
              com PID-file e reabertura se já estiver rodando.
            • TELEMETRIA: UFVAI_TELEMETRY_DEBUG=1 envia os eventos para o
              DebugView do GA4 (tempo real); launcher carrega
              ~/PesquisAI/config/ufvai.env (onde ficam UFVAI_GA_*).
  v0.6.1 — 🌐 Idioma do sistema + troca de idioma robusta + auto-open (offline)
            • BUG 1 (troca de idioma): o frontend recarregava a página em
              700ms enquanto o backend ainda reiniciava o ttyd (~3-4s) — a
              mensagem inicial não mudava de idioma. Agora setLang() é async,
              aguarda o POST /api/lang concluir e o backend só responde
              quando a porta do terminal já aceita conexões (_wait_port_open).
            • FEATURE 2: detecção do idioma do SISTEMA na 1ª execução
              ($LANGUAGE/$LC_ALL/$LC_MESSAGES/$LANG/locale) — saudação
              inicial no idioma do usuário; preferência fica persistida.
            • FEATURE 3 (offline/.deb): navegador abre AUTOMATICAMENTE
              quando a UI está pronta (thread + poll da porta; webbrowser
              com fallback xdg-open/open; UFVAI_NO_OPEN=1 desabilita).
            • REBRAND: banners Colab/console agora dizem "UFVAI pronto!" /
              "ABRIR O UFVAI".
  v0.5.1.8 — 🐛 3 bugfixes: provider buttons, session restore, backup confirm
            • BUG 1 (provider): JSON.stringify em onclick gerava SyntaxError
              em Python string tripla — trocado por data-provider +
              this.dataset.provider
            • BUG 2 (session history): "opencode session restore <id>"
              restaurava dados mas iniciava opencode do zero
              (linha 1600: ; {_opencode_bin}). Trocado para
              "opencode -s <id>" com no_fallback=true, + location.reload()
              para reconectar ao ttyd com a sessão correta.
            • FEATURE 3 (backup restore): pesquisaiConfirm() adicionado
              em doRestore(file) para confirmar antes de importar backup.
  v0.5.1.4 — 🧠 Editor de Memória Obsidian no botão 🧠
    v0.5.1.5 — 🔧 Botões não funcionavam (SyntaxError JS em string multilinha)
            • NOVO split view no overlay de Memória: lista de notas
              à esquerda + editor markdown com tabs Edit/Preview/Split
              à direita
            • 4 endpoints REST novos:
              GET  /api/obsidian/note?path=...     — ler nota crua
              GET  /api/obsidian/tree?subdir=...  — árvore agrupada
              GET  /api/obsidian/search?q=...     — busca BM25
              GET  /api/obsidian/tags             — tags com contagem
            • POST /api/obsidian/note (3 actions):
              action=save   — sobrescrever nota (force=true para humanas)
              action=create — criar nova nota de template
              action=delete — mover para .trash/ (force=true para humanas)
            • Buscar (debounce 150ms), editar com dirty indicator, salvar
              com confirmação, criar com diálogo de template, excluir
              com confirmação
            • Preview markdown via marked.js com destaque de [[wikilinks]]
              e #tags; estilo obsidian-like
            • 20 novas chaves i18n (memory.editor.*) em pt_BR, en_US,
              es_ES, fr_FR
            • Bugfix: from pathlib import Path (faltava — quebrava tree)
  v0.5.1.3 — 🔌 Conectores de Provedor de IA não salvavam (confirmProvider)
            • Bugfix: confirmProvider() crashava com TypeError antes de
              salvar a API key
            • Captura local de _selProv.id/env/name antes de closeProvider()
            • Verifica r.ok e d.ok no fetch (antes: sempre "✅ Salvo!")
            • closeProvider() movido para após sucesso
            • Não altera o array PROVIDERS (opencode_go/zen compartilham
              OPENCODE_API_KEY por design)
  v0.5.1.2 — 🧠 Botão Memória Obsidian no topbar
            • Overlay de Memória mostra status (ready/disabled/...) +
              stats (notas, tags, links) + notas recentes + daily notes
            • Endpoints: GET /api/obsidian (status)
  v0.5.1  — 🤖 Obsidian Autopilot (salvamento autônomo)
            • Módulo pesquisai.obsidian.autopilot (API de alto nível)
            • run_fast.py chama auto_init() na inicialização
            • Vault é CRIADO AUTOMATICAMENTE no Google Drive
            • Daily note e MOC raiz criados automaticamente
            • Sessão de log iniciada automaticamente
            • AGENTS.md injetado com instruções de salvamento autônomo
            • O agente SALVA SOZINHO — não espera o usuário pedir
            • API: recall(), save(), save_finding(), end_session()
  v0.5.0  — 🧠 Obsidian Second Brain (Long-Term Memory)
            • Módulo pesquisai.obsidian (8 arquivos, ~1.500 linhas)
            • Skill obsidian-memory (repositório git separado)
            • 10 templates Obsidian (daily, research, literature, ...)
            • Memória persistente entre sessões via vault no Google Drive
            • Busca BM25 offline + backlinks + wikilinks + tags
            • REGRA: vault SEMPRE no Google Drive (rejeita fora no Colab)
            • 71 testes pytest (100% passing) + teste e2e validado
            • Bugs corrigidos: update_note frozen + write_from_template dedup
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
__version__: str = "0.6.17"
__brand__: str = "UFVAI"
__brand_tagline__: str = "Pesquisa científica com integridade."

# ── Metadados do release ───────────────────────────────────────
__release_date__: str = "2026-09-01"
__codename__: str = "Memória abre instantânea via menu (singleton + warm-up)"

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
    "zh_CN": (
        "你好！",
        "从现在开始请用简体中文回答。",
        "提示",
    ),
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
    "GET  /api/obsidian",           # v0.5.1.2: status da memória
    "GET  /api/obsidian/note",      # NOVO v0.5.1.4: ler nota
    "GET  /api/obsidian/tree",      # NOVO v0.5.1.4: árvore de pastas
    "GET  /api/obsidian/search",    # NOVO v0.5.1.4: busca BM25
    "GET  /api/obsidian/tags",      # NOVO v0.5.1.4: lista de tags
    "POST /api/obsidian/note",      # NOVO v0.5.1.4: save/create/delete
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
    full_lang = {"pt": "pt_BR", "en": "en_US", "es": "es_ES", "fr": "fr_FR", "zh": "zh_CN"}.get(lang, "pt_BR")
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
