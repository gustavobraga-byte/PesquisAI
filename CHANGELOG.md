# Changelog — PesquisAI

## [0.7.12] — 2026-11-27 — 🎙️ Conversa ao vivo com voz · 🎛️ Download com barra de progresso

- **New features:** conversa ao vivo com voz (`voice/`: Gemini Live + LFM3-Omni-2B local, ASR/TTS/chat, auto-start no 1º `/voz/*`); download do modelo local com barra de progresso.
- **Fix:** `hf download` no lugar de `python -m huggingface_hub` (removido no hf_hub ≥1.x), `returncode` verificado e pesos detectados no cache HF; proxy `/voz` com POST lido uma única vez (antes: JSON vazio → 422 e travamento).

---

## [0.7.11-web] — 2026-11-08 — 🖥️ Interface web do OpenCode no lugar do ttyd

- **`pesquisai/ocweb.py` (novo):** proxy da SPA do OpenCode em 8002 com Basic auth injetada, SSE, túnel WebSocket e tema UFVAI; `ttyd` segue como fallback.
- Boot e iframe passam a usar a UI web, com abertura direta na sessão do projeto e sincronização de foco TUI ↔ web em tempo real.
- Correções web2–web13: árvore de boot correta, `fetch` com credenciais, catálogo com fallback, tema claro/escuro, "Working" preso, botão Parar e latência de foco reduzida.

---

## [0.7.12] — 2026-11-08 — 🪟 Windows (.exe + Menu Iniciar) e ações no menu do Linux

- Atalho do Menu Iniciar no `.deb` corrigido (`Exec=ufvai --gui`) com ações Abrir, Ver estado, Diagnóstico e Encerrar.
- Pipeline Windows em `packaging/windows/` (PyInstaller + Inno Setup, atalho `{autoprograms}`); o `.exe` é gerado em máquina Windows ou GitHub Actions.
- Compatibilidade `os.getuid`/`signal.SIGKILL` e ícone `ufvai.ico`; 14 testes.

---

## [0.7.11] — 2026-11-06 — 🛡 VPN da UFV no Colab

- OpenVPN em user+net namespace com `slirp4netns` e proxy SOCKS5 em `127.0.0.1:1081`; split tunnel padrão, túnel total opcional e modelo local da intranet por forward TCP.
- Tela "Você é aluno(a) da UFV?" e painel com CPF/senha, status, conectar/desconectar, testar acesso e perfil `.ovpn`; credenciais cifradas e senha nunca em log/linha de comando.
- API `/api/vpn/*` e CLI `python -m pesquisai.vpn`; 30 testes offline e prova de conceito no Colab (HTTP 200 via UFV).

---

## [0.7.10] — 2026-11-05 — 🧭 Onboarding de primeiro uso: provedor e chave

- Tela "você precisa de um provedor de IA" quando não há chave, com opções guiadas: Google Gemini (recomendado), NVIDIA, OpenRouter e OpenCode Go (pago).
- Motor espera a chave e reinicia com o modelo padrão `google/gemini-flash-lite-latest`; plugin `ufvai-retry` espera ~62 s em cota e troca modelo após 5 tentativas.
- API `/api/onboarding*`, módulo puro `onboarding.py` e 24 verificações.

---

## [0.7.9] — 2026-11-04 — 🔑 Chaves de API e free tier para novos usuários

- Sem chave, instruções e links para obter chave gratuita (OpenRouter/NVIDIA), guia `docs/CHAVES_API.md` e aviso de responsabilidade sobre a opção paga.
- `GET /api/free_models` e `POST /api/default_model` com seletor de modelo gratuito padrão; modelo pago recusado com 400.
- Botão ⚙ Autosave: intervalo 1–60 min e escopo (sessão ativa, todas ou escolhidas) com `session_ids`.

---

## [0.7.8] — 2026-10-29 — 🔑 Chaves do Drive no serviço do motor (OpenCode v2.2)

- **Fix:** o serviço nascia sem as chaves do Drive; `ensure_service_project_dir()` agora injeta as variáveis no `Popen` e no ambiente, com auto-cura para serviços já iniciados sem chave.
- `scripts/diag_keys_v22.py` diagnostica store × serviço sem imprimir segredo.
- Ctrl+C copia e Ctrl+V cola no ttyd (Ctrl+Shift+C envia `^C`), inclusive com mouse reporting; cache do HTML invalidado por fingerprint.

---

## [0.7.7] — 2026-10-27 — 🔒 Drive Guard: "My Drive" só dentro de PesquisAI

- Plugin bloqueia o acesso do agente a `/content/drive` fora de `PesquisAI/**` em três camadas, inclusive com `--auto`; auditoria em `~/.local/state/ufvai/drive-guard.log`.
- Serviço e terminais iniciam na pasta PesquisAI; saudação no idioma do cliente; keepalive e auto-reconnect domado do ttyd.
- Guard instalado no boot e em todo respawn do terminal; 62 testes.

---

## [0.7.6] — 2026-10-24 — 🏷️ Rebrand do agente: opencode → ufvai

- Documentos de identidade passam a usar `ufvai`/`UFVAI` (config, `ufvai.json`, SQLite e `ufvai auth export`).
- `scripts/ufvai-alias.sh` cria symlinks e o comando `ufvai`; código, binários e banco SQLite mantêm o nome original.

---

## [0.7.5] — 2026-10-23 — 🪟 Telas de abertura e retomada uma vez por sessão

- Telas de e-mail/"Bem-vindo" e pergunta de retomada passam a aparecer uma vez por sessão (`sessionStorage` + `localStorage` com validade de 12 h + cookie).
- Recargas internas não consomem a marca; só o botão ↻ a limpa. HTML com `Cache-Control: no-store`.

---

## [0.7.4] — 2026-10-23 — 💾 Autosave de todas as conversas · 🔓 Free tier na restauração

- Cada conversa viva com alterações ganha arquivo próprio em `backups/autosave/sessions/`; padrão continua gravando só a sessão ativa.
- Sessões restauradas com modelo gratuito do Zen voltam a funcionar (id no formato nativo do motor).

---

## [0.7.3] — 2026-10-22 — 📦 Pacote instalado no ambiente · ⏱️ Autosave a cada 1 minuto

- Autosave de 3 para 1 minuto; 3 últimas interações preservadas nos slots `autosave_4..6`.
- O boot instala o pacote `pesquisai` (`pip install -e`) e verifica o import fora do diretório do repo.

---

## [0.7.2] — 2026-10-22 — 🔄 Retomada uma vez por aba · 📅 Calendário do "Restaurar"

- Pergunta de retomada oferecida uma vez por aba; botão ↻ a reoferece.
- Calendário com chips por mês, contagem por dia, grupo "sem data" e botão "Mais recente".

---

## [0.7.1] — 2026-10-22 — 🔧 Retomada corrigida · 💾 autosave sem duplicata · 🗑 apagar backup

- Retomada aceita nome com ou sem o prefixo `autosave/`; `content_digest()` evita cópias idênticas.
- Botão 🗑 apaga backup com confirmação (`POST /api/backup/delete`) e fallback para os 3 autosaves anteriores.

---

## [0.7.0] — 2026-10-21 — 🗓️ "Restaurar" com calendário · ⏱️ autosave a cada 3 min · 🏷️ marca UFVAI

- Menu "Restaurar" com calendário mensal, filtro por data e validação estrita do backup; autosave corrigido (NameError) e ligado por padrão.
- Marca UFVAI na tela de nova sessão, chinês também no terminal e materiais de ajuda no tema claro.

---

## [0.6.21] — 2026-10-13 — 🔧 Motor OpenCode V2 · 🍪 Aviso de cookies · 🫀 Keep-alive por célula

- Migração para a configuração V2, `--auto`, tema único, agente padrão UFVAI e credenciais em SQLite com `auth export` cifrado.
- Aviso de cookies do proxy do Colab só quando detectado; keep-alive na própria célula com botão SAIR.
- Novo `opencode_config.py`; Dockerfile instala o motor como não-root.

---

## [0.6.20] — 2026-10-01 — 🫀 Keep-alive + botão SAIR · 🌐 Site no rodapé · 📄 Planilha de contatos

- Notebook simplificado, keep-alive em subprocesso com log em `/tmp` e botão SAIR com confirmação.
- Link "🌐 Site" no rodapé e uma linha por ativação/retorno na planilha de contatos.

---

## [0.6.19] — 2026-09-29 — 📱 Menu mobile sem SVG + hamburger à direita

- Hamburger vai para a borda direita no mobile (`.sep` oculto no breakpoint); desktop intacto.
- Teste de cascata CSS: 252/252 verificações.

---

## [0.6.18] — 2026-09-19 — 🧩 Skills personalizadas do usuário

- Pasta `backups/skills-personalizadas/` criada no boot; subpastas com `SKILL.md` são copiadas para `~/.agents/skills` a cada inicialização.

---

## [0.6.17] — 2026-09-01 — ⚡ Memória abre instantânea via menu

- Backend: singleton stale-while-revalidate com rebuild em background e warm-up no boot.
- Frontend: cache do menu de 5 s para 120 s com revalidação silenciosa e prefetch.

---

## [0.6.16] — 2026-09-01 — 🐛 Fix retorno: 1 linha por clique

- Removidos os heartbeats automáticos; `POST /api/access` só no clique em "Continuar", com guard contra duplo clique.

---

## [0.6.15] — 2026-09-01 — 🐛 Prompt inicial respeita idioma detectado

- `_ensure_lang_initialized()` resolve idioma antes do primeiro ttyd; frontend compara com o navegador e corrige uma vez por sessão.

---

## [0.6.14] — 2026-09-01 — 🐛 IP localhost + todo acesso logado

- IP público capturado via ipify e enviado no body; heartbeat `usuario_ativo` também no carregamento da UI.

---

## [0.6.13] — 2026-09-01 — 🐛 IP real do cliente + heartbeat na revisita

- `_get_client_ip()` percorre `X-Forwarded-For` da direita para a esquerda e aceita headers extras.
- Perfil de e-mail passa a cair no backup persistente do Drive, restaurando o heartbeat da revisita.

---

## [0.6.12] — 2026-09-01 — 📱 Fix preview responsivo

- Preview markdown volta a aparecer no mobile; aba Preview também atualiza o conteúdo.

---

## [0.6.11] — 2026-09-01 — 🐛 Hotfix memória: isoformat no cache BM25

- Datas do cache BM25 passam por `_parse_date` robusto e helper defensivo `_safe_isoformat()`.

---

## [0.6.10] — 2026-09-01 — 🚀 Memória otimizada + nome+IP + responsiva mobile

- Cache BM25 em disco, paginação, debounce e busca server-side; interface responsiva com alvos ≥44 px.
- Termos com campo Nome; planilha passa a 8 colunas com migração automática.

---

## [0.6.9] — 2026-08-25 — 📜 Termos v2.1 · ✉️ e-mail de ativação · 📘 botão Manual

- Telemetria opt-out (LGPD art. 7º IX), sem cookies; e-mail de ativação obrigatório (art. 7º V).
- Perfil persistente no Drive, botão 📘 Manual com rota `/api/manual` e logs fora do Drive no Colab.

---

## [0.6.8] — 2026-08-24 — 🧹 Painel único · reordenação LGPD · planilha de contatos

- Colab passa a ter um único painel de feedback; opcionais LGPD antes do aceite obrigatório.
- Planilha de contatos criada via Drive/Sheets API, com fallback manual documentado.

---

## [0.6.7] — 2026-08-23 — 🖼️ Tela de carregamento na marca · ✉️ contato configurável

- Barra de boot contínua no tema da logomarca e botão final com a logo real.
- URL de contato configurável no painel Admin, gravada localmente e exigindo HTTPS.

---

## [0.6.6] — 2026-08-22 — 🖼️ Favicon UFVAI · ✉️ contato opt-in LGPD

- Favicon na interface (com prefixo do proxy no Colab) e rota `/favicon.ico`.
- Contato por e-mail opt-in com SHA-256; GA4 nunca recebe o endereço.

---

## [0.6.5] — 2026-08-22 — 🔐 Terminal à prova de travamentos · 🚀 splash

- ttyd como líder de grupo de processos, morto com `killpg` (fim do `pkill -f opencode` global).
- `GET /api/ttyd_ready` evita `ERR_CONNECTION_REFUSED`; splash de boot com 3 estados e i18n em 5 idiomas.

---

## [0.6.4] — 2026-08-22 — 🪪 Marca UFVAI · 🎨 Temas · 🖼️ Logo · 📜 Termos v2

- Agentes passam a se apresentar como UFVAI; temas do terminal na paleta azul-noite + dourado.
- Termos v2.0 com integridade acadêmica, LGPD e foro Viçosa/MG; telemetria com consent-gate.

---

## [0.6.3] — 2026-08-22 — 🔌 Servidor persistente offline · 🎨 Ícone no dock

- `_offline_keep_alive()` impede o encerramento do wrapper HTTP fora do Colab.
- Listener dual-stack (IPv4 + `::1`) e janela com `WM_CLASS` UFVAI para o ícone do dock.

---

## [0.6.2] — 2026-08-22 — ⌨️ Terminal gravável · 🖥️ Launcher app-mode · 📊 Debug

- Flag `--writable` do ttyd restaurada; launcher offline abre a UI como app separado.
- `UFVAI_TELEMETRY_DEBUG=1` envia eventos para o DebugView do GA4.

---

## [0.6.1] — 2026-08-22 — 🌐 Idioma do sistema · 🔁 troca robusta · 🌍 auto-open

- `setLang()` virou `async` e o backend só responde com a porta do ttyd pronta.
- Idioma do sistema detectado na 1ª execução; no offline o navegador abre sozinho.

---

## [0.6.0] — 2026-08-21 — 🏷️ UFVAI · 🔐 hardening · 📊 telemetria opt-in · 🇨🇳 zh_CN

- Rebrand visual e reforço de segurança (CORS restrito, token de sessão, sanitização, cifragem, rate limit).
- Telemetria anônima opt-in, tela de Termos obrigatória e chinês simplificado completo.

---

## [0.5.1.9] — 2026-07-18 — Versão offline para Linux e reescrita do AGENTS.md

- Instalador `.deb` offline e AGENTS.md reescrito (economia de 18–25% de tokens).
- Nova arquitetura `vault/` (memória) × `outputs-<slug>/` (entregáveis); defesas contra prompt injection e dados sensíveis.

---

## [0.5.1.8] — 2026-07-10 — 🐛 3 bugfixes + skill Memorial UFV

- Botões de provedor (`data-provider`), restauração com `opencode -s <id>` e confirmação antes de restaurar backup.
- Nova skill `memorial-ufv` (Relatório Detalhado RSC → `.md`/`.docx`).

---

## [0.5.1.5] — 2026-07-01 — 🧠 Editor de Memória Obsidian

- Modal split com lista de notas e abas Edit/Preview/Split; endpoints de leitura, árvore, busca BM25 e tags.
- Save/create/delete (delete para `.trash/`), preview com wikilinks e 20 chaves i18n.

---

## [0.5.1.3] — 2026-06-30 — 🔌 Conectores de provedor de IA

- `confirmProvider()` corrigido: dados capturados antes de fechar o modal, fetch verificado e fechamento só no sucesso.

---

## [0.5.1.2] — 2026-06-30 — 🧠 Botão Memória Obsidian no topbar

- Overlay com status, estatísticas, notas recentes e dailies; endpoint `GET /api/obsidian`.

---

## [0.5.1] — 2026-06-29 — 🤖 Obsidian Autopilot

- API `recall`/`save`/`save_finding`/`end_session`/`log_skill`/`log_file` com `auto_init()` no boot.
- Vault criado automaticamente no Drive com daily note e MOC raiz; tudo é no-op sem vault.

---

## [0.5.0] — 2026-06-28 — 🧠 Obsidian Second Brain

- Módulo `pesquisai.obsidian`, skill `obsidian-memory` e 10 templates.
- Memória persistente no Drive com BM25 offline, backlinks, wikilinks e tags `pesquisai/*`.
