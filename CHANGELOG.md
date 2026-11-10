# Changelog Resumido — PesquisAI

## [0.7.11-web] — 2026-11-08 — Interface web do OpenCode no lugar do ttyd

### Implementação
- Novo módulo `pesquisai/ocweb.py`: proxy HTTP/1.1 em `0.0.0.0:8002` que publica a SPA do OpenCode (loopback + Basic auth), com:
  - Basic auth injetada a partir do `service.json` (senha nunca chega ao navegador);
  - repasse de `/_assets`, `/icons`, `/api/*` e SSE (`/api/event`) em chunks;
  - túnel WebSocket para o PTY (quando usado);
  - injeção do **tema UFVAI** (`--v2-*`: navy/dourado/creme, claro e escuro), barra degradê, badge **UFV·AI** e título "UFVAI · OpenCode";
  - página 503 amigável (auto-refresh 3 s) enquanto o motor não sobe.
- `launch_app.py` inicia o proxy no boot, aponta o iframe para `proxyPort(8002)` e expõe `GET /api/ocweb_ready`.
- `launch_app_responsive_v041.py`: `create_wrapper_html(..., web_mode=True)` troca o polling do splash de `/api/ttyd_ready` para `/api/ocweb_ready`.
- `constants.py`: `OCWEB_PORT = 8002`. O `ttyd` continua iniciado como fallback (não aparece na janela).


### Testes
- `tests/test_v0711_ocweb.py` + `tests/test_v0710_onboarding.py` + `tests/test_v0711_vpn.py` → **107 passed**.
- Validação HTTP real: HTML 200 com tema, `/_assets` 200, `/api/session` 200, `/api/event` em streaming; Chromium headless (Playwright) confirmou home → sessão com "Olá!".

### Limitações
- UI é a do OpenCode (customização visual); sem navegador real no ambiente de validação; ttyd segue em segundo plano como fallback.

---

## [0.7.12] — 2026-11-08 —  ações no menu do Linux

### Conferência do `.deb` (modo offline)
- O pacote já instalava o atalho (`packaging/ufvai.desktop` em `/usr/share/applications/` + ícones hicolor) — confirmado com `dpkg-deb -c` sobre `pesquisai_0.7.11-offline1_amd64.deb`.
- **Lacuna corrigida:** com `Terminal=false` o clique não dava retorno visível. Agora `Exec=ufvai --gui`, garantindo navegador aberto e aviso via `notify-send`.
- Novas ações no atalho: `Abrir`, `Ver estado`, `Diagnóstico`, `Encerrar`.


### Compatibilidade de código
- `os.getuid()` → `getattr(os, "getuid", lambda: 0)()`; `signal.SIGKILL` → `getattr(signal, "SIGKILL", signal.SIGTERM)`; `assets/ufvai.ico` gerado a partir de `ufvai-256.png` (16→256 px).

### Testes
- `tests/test_v0712_menu_iniciar.py` — **14 passed** (entry válido, ações com `Exec`, sintaxe bash, `{autoprograms}`, `.ico` válido, workflow, guards de Windows).

---

## [0.7.11] — 2026-11-06 — VPN da UFV no Colab (OpenVPN em namespace isolado)

### O que a UFV usa
- **OpenVPN**, perfil público `https://vpn.ufvnet.ufv.br/configs/UFV-linux.ovpn` (5.052 B): `remote vpn.ufvnet.ufv.br 1195`, `proto udp`, `dev tun`, `auth-user-pass` (CPF + senha), `comp-lzo yes`.
- **Split tunnel** ("apenas recursos desta rede") e **1 dispositivo por CPF**.

### O problema do Colab e a solução
- Sem `/dev/net/tun` e sem `CAP_NET_ADMIN` (`CapEff=00000000a82c25fb`); `ip tuntap add` → `Operation not permitted`. `mknod /dev/net/tun` funciona (root + `MKNOD`).
- **Solução:** OpenVPN dentro de **user+net namespace** (`unshare -Urn`) + **`slirp4netns`** (NAT em espaço de usuário) + **proxy SOCKS5** (stdlib) em `127.0.0.1:1081` via `add_hostfwd`.
- **Não é túnel transparente:** só o que usa o proxy entra na VPN; o restante do Colab segue na internet normal.

### Modo total e modelo local
- **Modo total (padrão = split + serviço no netns):** OpenCode + ttyd rodam **dentro** do namespace (`unshare -Urnm`); só redes da UFV (`100.65.0.0/17`, `200.235.128.0/17`) saem por `tun0`; internet comum (LLM, GitHub, PyPI) continua pelo Colab via `tap0`.
- **Túnel total opcional** (`redirect-gateway def1`): medido em 07/11/2026 — a UFV **bloqueia saída externa** (OpenRouter, Google, OpenAI, GitHub, PyPI dão timeout; só hosts da UFV respondem 200). Serve só para serviços internos.
- **Modelo local:** encaminhador TCP `127.0.0.1:<porta>` → intranet (ex.: Ollama `10.0.0.10:11434`), com DNS da VPN; `baseURL` `http://127.0.0.1:<porta>/v1`.
- **DNS próprio:** `/etc/resolv.conf` bind-montado no namespace (DNS da VPN + públicos).

### Google no seletor de gratuitos + "Outro provedor"
- **Google Gemini** entra em 🎛️ Modelo gratuito padrão (junto de NVIDIA e OpenRouter); `is_free_model` e `merge_default_model` aceitam `google/*`.
- **"Outro provedor"** no onboarding: lista curada com OpenAI, Anthropic, Groq, Mistral, DeepSeek, Together, Fireworks, xAI e Cohere.
- Ordem das telas: Termos → VPN → provedor/chave.

### Tela inicial e painel
- Depois de Termos/onboarding: "Você é aluno(a) da UFV?" — **Sim** → painel com CPF e senha; **Não** → segue sem VPN (escolha em `prefs.json` + `localStorage`; botão 🛡 reabre).
- Painel: status ao vivo, avisos (1 dispositivo, túnel total, senha), Conectar/Desconectar, Testar acesso (`https://sistemas.ufv.br/`), baixar/colar `.ovpn`, esquecer credenciais, detalhes técnicos.
- **OpenCode pela VPN é o PADRÃO** (split tunnel); a conexão move o serviço para o namespace; porta republicada no host via slirp.

### Segurança
- Senha nunca em linha de comando, log ou `state.json`: arquivo `auth` `0600` em `~/.config/ufvai/vpn/run/`, apagado ao desconectar.
- "Lembrar neste Drive" grava CPF/senha **cifrados** (Fernet) com prefixo reservado `vpn_ufv_` (filtrado de `/api/apikey`). `_redact()` mascara CPF e `password=` nos logs.

### API e CLI
- `GET /api/vpn`, `POST /api/vpn/connect`, `/disconnect`, `/profile`, `/test`, `/forget`, `/answer`.
- CLI: `python -m pesquisai.vpn status|connect|disconnect|profile|test`.

### Testes
- `tests/test_v0711_vpn.py` — **30 testes offline** (perfil, máscara, redaction, prefs, credenciais cifradas, SOCKS5 + relay, capacidades, bind, padrão split tunnel).
- **Prova de conceito no Colab:** UDP 1195 alcança o servidor, TLS completa, credenciais falsas retornam `AUTH_FAILED`; caminho `netns → slirp → SOCKS5 → 127.0.0.1:1081` devolveu **HTTP 200** para `https://www.ufv.br/`.

### Limitações
- 1 dispositivo por CPF (conectar o Colab pode desconectar o computador); credenciais vão para a VM do Google ("lembrar" é opcional e cifrado); uso deve respeitar regras UFV/DTI e CAPES Periódicos.

---

## [0.7.10] — 2026-11-05 — Onboarding de primeiro uso: provedor e chave

### A tela
- Depois dos Termos (e do "Bem-vindo de volta"), surge **"Para usar o UFVAI você precisa de um provedor de IA"** com duas escolhas: **Já tenho um provedor** (modal `Conectar Provedor de IA` de sempre) e **Não tenho / não sei o que é isso** (opções guiadas).
- Condição objetiva: sem chave utilizável no `keys_store.json` nem no ambiente, a tela aparece — inclusive para usuário antigo que trocou de conta ou apagou chaves. Com qualquer chave, o app abre como sempre.

### Opções (tutorial + campo de colar)
- **Google Gemini — RECOMENDADO** (grátis no AI Studio), **NVIDIA NIM**, **OpenRouter** e **OpenCode Go** marcado como **PAGO**.
- Cada card: passos numerados, link oficial, reprodução da tela (rotulada) e campo para colar a chave.
- No Google: link direto `https://aistudio.google.com/api-keys`, instrução de **Copiar** e colar; salva como **`GOOGLE_GENERATIVE_AI_API_KEY`**.

### O motor espera a chave
- **Sem chave, o `opencode` não sobe.** `needs_onboarding_now()` é avaliado no boot: serviço e ttyd parados; só a interface web sobe para receber o onboarding.
- **Ao salvar a chave, reinício duro:** `_hard_restart_engine()` encerra terminal (ttyd + TUI), derruba o serviço (todas as sessões) e sobe tudo de novo.

### Retry automático em cota/429
- Plugin `ufvai-retry` (hook `retry`): **somente em cota** (`quota`, `RESOURCE_EXHAUSTED`, `free_tier`, `per minute`) espera **~62 s** (janela de 1 min da cota gratuita). "High demand"/"overloaded" esperam 5 s; outros 429/503 seguem o padrão do motor.
- Lê `retry in 23s`/`retryDelay` da mensagem; teto de 3 min; desiste após 8 tentativas. Instalado no boot por `retry_plugin.ensure_retry_plugin()`.
- **Fallback após 5 tentativas:** troca a sessão para `google/gemini-3.1-flash-lite` (uma troca por sessão a cada 30 min; `UFVAI_RETRY_SWITCH_AFTER`/`UFVAI_RETRY_FALLBACK`).

### Modelo padrão do Google
- Com chave do Google: padrão **`google/gemini-flash-lite-latest`** com variante **`high`** ("Gemini Flash-Lite Latest Google · high"), mantido nos próximos usos (aplicado no boot e em `load_keys_from_drive`).
- O `model` raiz não guarda variante (limite do V2); ela vai em `agents.UFVAI.model = "google/gemini-flash-lite-latest#high"`.
- Constante `GOOGLE_DEFAULT_MODEL` em `pesquisai/onboarding.py`; override `UFVAI_GOOGLE_MODEL`; desligamento `UFVAI_GOOGLE_MODEL_LOCK=0`.
- Id conferido contra o catálogo real quando disponível (`google_model_from_catalog`), com fallbacks declarados.

### API e arquitetura
- `GET /api/onboarding` → `{needs, has_key, google_model, providers[], docs, guide}`.
- `POST /api/onboarding/key` → valida formato, grava **cifrado** em `backups/`, injeta a variável no processo/serviço, define o modelo padrão e reinicia o terminal. **Nunca loga a chave**; devolve só `masked`.
- Módulo puro **`pesquisai/onboarding.py`** (prefixos, validação, `mask_key`, `needs_onboarding`, `merge_model`, `providers_public`), sem rede e sem disco.
- "Agora não" (✕) esconde só nesta aba (`sessionStorage`); a próxima abertura sem chave volta a mostrar.

### Testes
- `tests/test_v0710_onboarding.py` — **24 verificações** (detecção por prefixo, chave ambígua, validação, mascaramento, `needs_onboarding`, modelo do Google e fallback de catálogo, `merge_model`, contrato do HTML/JS).

---

## [0.7.9] — 2026-11-04 — Chaves de API e free tier para novos usuários

### Quem chega sem chave vê como obter uma gratuita
- No modal **🔌 Provedores**, o bloco `#prov-howto` aparece sozinho quando não há chave salva (`renderSavedKeys()`): links para OpenRouter (`openrouter.ai/keys`), NVIDIA (`build.nvidia.com`), guia `docs/CHAVES_API.md` e aviso de responsabilidade.
- A opção paga (OpenCode Go) aparece como link separado: o UFVAI não emite, não cobra e não garante limites de nenhum provedor. O mesmo aviso está na tela de Termos.

### Seletor de modelos gratuitos + modelo padrão
- `GET /api/free_models` lê `opencode models` e filtra gratuitos (`openrouter/free`, `openrouter/*:free`, `nvidia/*`), cache de 10 min, com `key_links` e `docs`.
- `POST /api/default_model` grava o campo `model` do `opencode.json` preservando o restante (escrita atômica); recusa pago com **400**.
- No modal: seletor **🎛️ Modelo gratuito padrão** (OpenRouter/NVIDIA) e botão **Definir como padrão**.
- Regras em módulo puro **`pesquisai/free_models.py`** (`is_free_model`, `filter_free_models`, `merge_default_model`), testável sem rede.

### Botão ⚙ Autosave: intervalo e conversas
- Configuração: intervalo **1–60 min** (1, 3, 5, 10, 15, 30, 60) e escopo **sessão ativa · todas as conversas · escolher conversas** (checkboxes de `/api/sessions`).
- Preferências em `localStorage` (`ufvai_autosave_interval_min`, `ufvai_autosave_scope`, `ufvai_autosave_session_ids`).
- **Backend:** `POST /api/autosave` aceita `session_ids` e grava **somente** as escolhidas (`save_all_sessions`), sem tocar nos slots da sessão ativa.

### Documentação
- **`docs/CHAVES_API.md`** (PT + EN): como criar chave gratuita, limites do provedor, opção paga, onde a chave fica (cifrada no Drive) e o que o UFVAI nunca faz.
- README e MANUAL atualizados para **0.7.9** (badge, citação ABNT/BibTeX, rodapé).

### Testes
- `tests/test_v079_free_models.py` (classificação, rejeição de pagos, deduplicação, merge) + `tests/test_v079_ui_contract.py` (contrato dos endpoints, bloco de instruções, seletor, ⚙, `session_ids`). `test_version_sync` verde.

---

## [0.7.8] — 2026-10-29 — Chaves de API do Drive no serviço do motor (OpenCode v2.2)

### Sintoma e causa raiz
- Após o **OpenCode v2.2**, `opencode models` listava apenas `opencode` e `opencode-go`, embora as 5 chaves estivessem no `backups/keys_store.json` e no `~/.bashrc`.
- O boot chama `ensure_service_project_dir()` **antes** de `start_wrapper_server()` (onde as chaves são carregadas): o processo `opencode serve --service` nascia com **0 das 5 variáveis**. Até a 2.1 não aparecia porque a TUI resolvia provedores com o próprio ambiente; **na v2.2 o catálogo é resolvido dentro do serviço**.
- Prova: `opencode models` via serviço → 2; `--standalone` → 5.

### Correções
- **Injeção no serviço:** `ensure_service_project_dir(..., backup_dir=)` decifra o `keys_store.json` e injeta no `env` do `Popen` **e** no `os.environ` do boot (ttyd, wrappers, terminal também passam a ver).
- **Auto-cura:** serviço no diretório certo mas sem chaves é reiniciado (`service_missing_key_envs`).
- **Salvar/remover chave vale na hora:** `_apply_opencode_env_change_async` reergue o serviço com as chaves novas antes de reiniciar o terminal.
- Sem mudança de formato; nada copiado para o banco do motor; store resolvido Drive → `~/PesquisAI/backups`.

### Diagnóstico
- Novo `scripts/diag_keys_v22.py`: mostra store, processo, `~/.bashrc`, **ambiente do serviço** e provedores vistos — sem imprimir segredo. Saída `0` ok · `1` chaves não chegaram · `2` store vazio · `3` sem serviço/erro. `--json` para suporte/testes.

### Testes
- `tests/test_v078_service_keys.py` — 15 testes. Regressão (`test_v077_start_dir`, `test_drive_guard`, `test_version_sync`, `test_security`): 119 verdes.

### Ajuste (29/10, sem bump) — Ctrl+C copia · Ctrl+V cola
- **Sintoma:** Ctrl+C chegava ao PTY como `^C` e encerrava a conversa na TUI com campo vazio; Ctrl+V mandava `^V` além de colar.
- **Correção:** Ctrl+C copia a seleção e **nunca** vai ao PTY (dica com throttle de 10 s); **Ctrl+Shift+C** envia `\x03`; **Ctrl+V** cola sem `^V`; Ctrl+Shift+V mantém o caminho nativo. Duas camadas: `attachCustomKeyEventHandler` + listeners em fase de captura; rede de segurança da Clipboard API em 400 ms (`lastPasteAt`).
- **Cache do HTML do ttyd:** `_prepare_ttyd_touch_index()` reaproveitava o arquivo só por existência — o JS velho continuava servido. Agora marca `<!-- ufvai-inject:<sha256[:16]> -->` e `_ttyd_index_is_current()` regenera quando não corresponde; um F5 já aplica.
- **Ajuste 2 — "Nada selecionado" com mouse reporting da TUI:** a TUI liga DECSET `1000`/`1002`/`1006` e o xterm.js desativa a seleção (só Shift+arraste). Correções: memória da última seleção (`onSelectionChange` + `lastSel`/`lastSelAt`); arrasto > 6 px vira seleção sintetizando `mouseup` + `mousedown{shiftKey:true}`, cópia no `mouseup`; dica correta por contexto; kill switch `window.__ufvaiDragSelect = false` desliga na hora.
- **Verificação:** `tests/test_ttyd_clipboard.py` 33/33 · `tests/js/test_v078_clipboard.js` 8/8 · `scripts/diag_clipboard_ttyd.py` 9/9 (Chromium + ttyd 1.7.4 reais) · teste de arrasto em navegador real 19/19.

---

## [0.7.7] — 2026-10-27 — Drive Guard: "My Drive" só dentro de PesquisAI

### Início na pasta PesquisAI
- Serviço do motor e terminais sobem com CWD na pasta PesquisAI (offline: `~/PesquisAI`); sessões novas nascem presas a esse diretório — efeito: abrem em `/content/drive/My Drive/PesquisAI`.

### Saudação no idioma do cliente
- Respeita o idioma do navegador, não o locale do servidor. Ordem: variável de ambiente → preferências salvas no Drive → idioma do navegador → sistema. Fallback 8 s → 60 s, com `pt_BR` quando não há confirmação.

### ttyd sem quedas
- **Keepalive** a cada 20 s (RESIZE) mantém o WebSocket no proxy do Colab; **auto-reconnect domado** (máx. 1 a cada 5 s, reload máx. 2× por aba/10 min). Basta recarregar a página.

### Bloqueio de "My Drive" fora de PesquisAI
- Plugin Drive Guard bloqueia acesso do agente a arquivos de `/content/drive` fora de `/content/drive/My Drive/PesquisAI/**`; decisão não depende de aprovação (`--auto` não contorna).
- **Três camadas:** regras declarativas em `opencode.json` (deny da raiz + allow de PesquisAI), hook de permissão e hook de pré-execução.
- Material criptográfico da memória preservado; `*.env` continua exigindo aprovação; o servidor Python da interface continua acessando o Drive normalmente.
- **Auditoria** em `~/.local/state/ufvai/drive-guard.log`; **fail-open** (falha do plugin não impede o boot, avisa no log).
- Instalado no boot e em todo (re)spawn do terminal.

### Testes
- `tests/js/test_drive_guard.mjs` 35/35 · `tests/test_drive_guard.py` 20/20 · `tests/test_v077_start_dir.py` 7/7.

---

## [0.7.6] — 2026-10-24 — Rebrand do agente: opencode → ufvai

- Documentos do agente (`AGENTS.md`, `agents/AGENTS.*.md`, novo `agents/UFVAI.md`): todas as ocorrências de `opencode`/`OpenCode` → `ufvai`/`UFVAI` — caminhos (`~/.config/ufvai/...`), arquivo `ufvai.json`, dados em `~/.local/share/ufvai/` e comando `ufvai auth export`.
- **Aliasing** (`scripts/ufvai-alias.sh`, idempotente e fail-open): symlinks (`~/.config/ufvai` → `~/.config/opencode`, `ufvai.json` → `opencode.json`, `~/.local/share/ufvai` → `~/.local/share/opencode`) e comando **`ufvai`**.
- **O que não mudou:** código-fonte, instaladores, binários e SQLite mantêm o nome original (renomear em execução quebraria o runtime).
- Verificações: `grep -ric opencode` → 0 nos 7 documentos de identidade; `ufvai --version` responde `opencode v2.1.4`.

---

## [0.7.5] — 2026-10-23 — Telas de abertura e retomada uma vez por sessão

- A tela de e-mail/"Bem-vindo" e a pergunta de retomada apareciam várias vezes na mesma sessão (`sessionStorage` se perdia nas recargas do proxy do Colab).
- **Correção em três camadas:** `sessionStorage` + `localStorage` (validade 12 h) + cookie de sessão, gravada antes de a tela aparecer. Recargas internas não consomem a marca; só o botão **↻** limpa a retomada. Nova aba/sessão → mostra de novo.
- A retomada espera Termos/"Bem-vindo" fechar. HTML com `Cache-Control: no-store`.

---

## [0.7.4] — 2026-10-23 — Autosave de todas as conversas · Free tier na restauração

### Autosave: várias sessões
- Slots `autosave_1..3` continuam como rotação da interação atual.
- Cada conversa viva com conteúdo novo ganha arquivo próprio em `backups/autosave/sessions/<id>.json`, visível no modal **🔄 Restaurar**. Só exporta a conversa que mudou (compara `time.updated`); limite de 6 por ciclo e 6 h de inatividade.
- **Alcance padrão:** só a sessão ativa, e só quando muda. Botão **"Todas as conversas"** liga o modo completo.

### Free tier do OpenCode Zen na restauração
- Sessões restauradas com modelo gratuito do Zen davam 403 ("free tier can only be used from within OpenCode").
- **Causa:** retomada gerava ids no formato legado; o gateway do Zen recusa ids fora do formato nativo.
- **Correção:** id nasce no formato nativo do motor; a sessão é ajustada ao contexto do modelo (compactação ou reimportação aparada).

### Telas de abertura
- Termos e "Bem-vindo de volta" abrem uma vez por carga; "Bem-vindo" uma vez por aba.

---

## [0.7.3] — 2026-10-22 — Pacote instalado no ambiente · Autosave a cada 1 minuto · Fallback das 3 últimas interações

- **Intervalo do autosave:** 3 min → **1 minuto**.
- **Fallback:** o autosave não destrói mais o backup da sessão anterior; as 3 últimas interações ficam nos slots `autosave_4..6` e entram na lista do "Restaurar".
- **Sessão certa:** escolhe a sessão enviada → a do terminal → a mais recentemente atualizada (antes usava `sessions[0]`).
- **Retomada na entrada:** pergunta uma vez por aba, sem loop.
- **Pacote `pesquisai` instalado no ambiente:** antes o boot só adicionava o repo ao `sys.path` e o terminal (outro processo/CWD) não encontrava o pacote — memória não salvava. Agora o boot instala (`pip install -e`) e verifica o import de um diretório neutro. Distribuição renomeada de `pesquisai-additions` para `pesquisai`; instalador offline não esconde mais erros.
- **Restauração com modelos gratuitos:** correção do id da sessão no formato nativo (detalhada em 0.7.4).

---

## [0.7.2] — 2026-10-22 — Retomada uma única vez por aba · Calendário do "Restaurar" corrigido

- **Laço da retomada:** ao clicar em "Continuar de onde parei", o terminal recarregava e a confirmação voltava. Agora é oferecida uma vez por aba (`sessionStorage`); o **↻** reoferece e o menu **🔄 Restaurar** segue disponível.
- **Calendário do "Restaurar":** chips clicáveis dos meses com backup (+ contagem), contagem por dia, itens sem data no grupo "sem data", estado vazio acionável e botão **"Mais recente"**.

---

## [0.7.1] — 2026-10-22 — Retomada corrigida · autosave sem duplicata · apagar backup

- **Retomada na entrada não restaurava:** `list_autosaves()` devolvia o nome sem o prefixo `autosave/` → `/api/restore` recusava com 400. Corrigido (aceita com ou sem prefixo; validação de caminho mantida).
- **Autosave sem duplicata:** `content_digest()` impede gravar cópia idêntica; a interface avisa "sem novidades".
- **Botão 🗑 de apagar backup:** `POST /api/backup/delete` com confirmação obrigatória + botão por item no "Restaurar" · i18n em 5 idiomas.
- **Fallback na retomada:** se o autosave mais recente falhar, tenta o anterior (até 3).

---

## [0.7.0] — 2026-10-21 — "Restaurar" só backups com calendário · autosave a cada 3 min · marca UFVAI

- **Menu "Restaurar" reconstruído:** `GET /api/backups` devolve somente backups (data/hora/tamanho/título/integridade); `POST /api/restore` valida estritamente e recusa não-backups. Interface com calendário mensal, filtro por data, navegação de mês e lista agrupada por dia · i18n em 5 idiomas.
- **Autosave corrigido e ligado por padrão:** um `NameError` no branch `/api/autosave` matava toda gravação; a listagem estava no `do_POST` (404). Corrigido, com rotação invertida (slot 1 = mais recente).
- **Identidade e interface:** marca **UFVAI** na nova sessão · 🇨🇳 Chinês também troca o terminal · Manual e Diretrizes no tema claro · "Idioma" fora do sanduíche no responsivo.

---

## [0.6.21] — 2026-10-13 — Migração para o motor OpenCode V2 · Aviso de cookies · Keep-alive por célula

- **Motor OpenCode V2:** configuração em `~/.config/opencode/opencode.json` e `cli.json`; instalador V2 com fallback npm; `--auto` no lugar de `--yolo`; tema em um arquivo só (dark + light); agente `UFVAI` com `default_agent: "UFVAI"`; credenciais em SQLite com backup via `auth export` cifrado.
- **Aviso de cookies de terceiros do proxy do Colab:** testa em iframe; aparece só quando o bloqueio é detectado (nasce invisível). Idempotente.
- **Keep-alive como célula bloqueante:** roda na própria célula (o Colab decide ociosidade pela atividade do notebook); duas falhas seguidas disparam recuperação; botão **SAIR** encerra pelo PID file.
- **Módulo novo `opencode_config.py`:** toda a manipulação de arquivos do motor num módulo só; arquivo do usuário não interpretável nunca é sobrescrito.
- **Dockerfile:** instala o OpenCode V2 como não-root; build sem rede (`UFVAI_NO_OPENCODE_INSTALL=1`).
- **Correções dos testes:** `merge_cli_theme` mutava o dicionário do chamador; file handle vazado em `_setup_theme_and_agent`.
- **Validação de campo:** ciclo `auth export` → cifragem → `auth import` executado contra a V2.0.28 com credencial de teste — funciona ponta a ponta. Pendente: credencial real e retomada de sessão.

---

## [0.6.20] — 2026-10-01 — Keep-alive + botão SAIR · Rodapé com o site oficial · Planilha de contatos em 1 linha

- **`PesquisAI.ipynb` simplificado:** boot direto no kernel do Colab, keep-alive em subprocesso (log em `/tmp`), botão **SAIR** com confirmação obrigatória que encerra o keep-alive e desconecta o runtime.
- **Rodapé:** link **"🌐 Site"** para o site oficial; em <480px o texto "UFV · Viçosa, MG - Brasil" sai de cena para o link caber.
- **Planilha de contatos:** exatamente uma linha por ativação/retorno, no clique do usuário. O primeiro aceite não grava mais `novo_contato`.
- **Descartada** a abordagem de supervisor desacoplado de 30/09 (travava em "Aguardando a interface ficar pronta…"); base é a v0.6.19 estável.

---

## [0.6.19] — 2026-09-29 — Menu mobile sem SVG + hamburger à direita

- Em ≤767px o hamburger aparecia colado no logo, à esquerda (o `.sep` absorvia o espaço antes do `margin-left: auto`). Corrigido: `#topbar .sep { display: none }` no breakpoint mobile → idioma + hamburger vão para a borda direita; desktop intacto.
- **Teste de regressão de cascata** (`tests/test_responsive_hamburger.py`): resolve a cascata CSS de verdade (especificidade + `!important` + ordem) para 10 larguras × 7 arquivos — 252/252 nos dois projetos.
- Docs em paridade (skills personalizadas) e rebuild do `.deb` 0.6.19-offline.

---

## [0.6.18] — 2026-09-19 — Skills personalizadas do usuário

- Nova pasta persistente `backups/skills-personalizadas/` (criada no boot, com README).
- **Carga a cada boot:** `setup_custom_skills()` copia cada subpasta válida (com `SKILL.md`) para `~/.agents/skills`; sem `SKILL.md` são ignoradas; falhas nunca interrompem o boot.
- O agente é instruído a gravar skills novas nessa pasta e informa que entram em vigor no próximo boot.

---

## [0.6.17] — 2026-09-01 — Memória abre instantânea via menu

- **Causa:** cada request criava um `ObsidianMemory` novo (re-parse do cache BM25 de 3,8 MB + árvore iterada 2× + LinkIndex reconstruído); qualquer mudança de arquivo invalidava o cache.
- **Fix backend:** singleton stale-while-revalidate — 1 instância em RAM compartilhada, rebuild em background após 30 s, warm-up no boot; o menu nunca bloqueia esperando o Drive.
- **Fix frontend:** cache do menu 5 s → 120 s com revalidação silenciosa + prefetch no `window load`.
- Endpoints e payload inalterados; apenas tempo de resposta (µs vs. segundos).

---

## [0.6.16] — 2026-09-01 — Fix retorno: 1 linha por clique

- No retorno o e-mail era enviado 2–3 vezes (heartbeat automático + timeout + clique). Removidos os disparos automáticos; `POST /api/access` só no clique em "Continuar", com guard `_heartbeatSent` contra duplo clique — exatamente 1 linha por retorno.

---

## [0.6.15] — 2026-09-01 — Prompt inicial respeita idioma detectado

- `_current_lang` iniciava fixo em `pt_BR`, então a detecção do sistema nunca era alcançada e o ttyd iniciava em português mesmo com sistema em inglês.
- **Fix:** `_ensure_lang_initialized()` (prioridade: preferência salva → env → sistema → persiste), chamado antes do primeiro `start_ttyd()`.
- **Frontend:** compara o idioma do backend com o do navegador e, se divergir, chama `setLang()` uma vez por sessão.

---

## [0.6.14] — 2026-09-01 — Fix IP localhost + todo acesso logado

- **IP registrava 127.0.0.1:** o proxy do Colab não injeta headers de IP na conexão local. O frontend captura o IP público via ipify e envia no body; o backend o prefere quando público.
- **Todo acesso gera linha na planilha:** o heartbeat `usuario_ativo` era disparado só no clique; agora também no carregamento da UI (com segunda tentativa após ipify resolver).

---

## [0.6.13] — 2026-09-01 — IP real do cliente + heartbeat na revisita

- **IP:** `_get_client_ip()` percorre `X-Forwarded-For` da direita para a esquerda saltando IPs privados, devolvendo o primeiro público; aceita `X-Real-IP`, `CF-Connecting-IP`, `Forwarded` etc.
- **Revisita:** o e-mail ficava em `~/.config` (efêmero) e o heartbeat lia só dali → vazio → nada gravado. `_read_profile()` agora cai no backup persistente do Drive.

---

## [0.6.12] — 2026-09-01 — Fix preview responsivo

- O preview markdown não aparecia no mobile (altura 0 no layout `flex-direction: column`). Corrigido com `min-height`/`overflow` adequados; `onEditorInput()` agora atualiza o preview também na aba Preview, não só em Split.

---

## [0.6.11] — 2026-09-01 — Hotfix memória: isoformat no cache BM25

- **Causa:** o cache BM25 reconstruía `NoteMetadata` com `created`/`updated` como string; ao exibir a árvore, `updated.isoformat()` quebrava com cache ativo.
- **Fix:** `_parse_date` robusto (ISO date, ISO datetime e formatos legados) + helper defensivo `_safe_isoformat()` no `launch_app.py`.
- Cache regenerado com `date` correto e validado (cache_hit ~0,2 s).

---

## [0.6.10] — 2026-09-01 — Memória otimizada + nome+IP + responsiva mobile

- **Memória:** cache BM25 em disco (247 notas em ~0,2 s), paginação, debounce e busca BM25 server-side para `q≥3`; responsiva mobile (sidebar 100%/38vh, alvos ≥44px).
- **Tela de Termos:** campo Nome ao lado do e-mail (lado a lado no desktop, coluna no mobile), validação de nome e e-mail; re-consentimento forçado (TV 5→6).
- **Backend:** grava nome + IP no perfil e no backup do Drive; planilha com 8 colunas (`Timestamp | Email | Nome | Email SHA-256 | Ambiente | Versão | Flag | IP`), migração automática e `MAX_ROWS` 1000→5000.

---

## [0.6.9] — 2026-08-25 — Termos v2.1 · e-mail de ativação · botão Manual

- **Termos v2.1 (re-consentimento):** telemetria ativa por padrão (opt-out, LGPD art. 7º IX); sem cookies (`analytics_storage:'denied'`); evento custom removido; e-mail de ativação obrigatório (400 se ausente, art. 7º V).
- **Perfil persistente:** `backups/ufvai_consentimento.json` no Drive; `GET /api/consent` inclui `profile` → pré-preenche e pula a tela se a versão já foi aceita.
- **Interface:** botão 📘 Manual ao lado do Dashboard de Saúde (nova rota `/api/manual`), ícones distintos, tela de Termos responsiva.
- **Correções:** DebugView (envia `debug_mode: 1`); logs fora do Drive no Colab (`/tmp/ufvai-logs/`).

---

## [0.6.8] — 2026-08-24 — Painel único · reordenação LGPD · planilha de contatos

- **Painel único (Colab):** todo feedback visual vem só do painel de boot; prints verbosos suprimidos; offline mantém prints normais.
- **Reordenação LGPD:** opcionais (estatísticas + e-mail) antes do aceite obrigatório; `ufvai_terms_version=4`.
- **Planilha de contatos automática:** criação via Drive/Sheets API, Apps Script pronto, endpoint injetado no painel Admin; fallback manual documentado.

---

## [0.6.7] — 2026-08-23 — Tela de carregamento na marca · canal de contato configurável

- **Barra de carregamento contínua no tema da logomarca (Colab):** painel off-white + wordmark UFV/AI, mensagens abaixo da barra (spinner dourado na etapa ativa, ✓ na concluída, ✕ em falhas sem abortar), percentual monotônico. Instância única via `get_boot_panel()`.
- **Botão de lançamento no tema da marca:** logo real embutida em base64 + botão pílula dourada "ABRIR O UFVAI".
- **URL de contato no painel Telemetria (Admin):** campo opcional, grava em `~/.config/ufvai_telemetry.json`, aplica na hora; salvar é parcial (dá para salvar só o canal sem redigir GA4); URL exige `https://`.

---

## [0.6.6] — 2026-08-22 — Favicon UFVAI · contato opt-in LGPD

- **Favicon na interface:** `<link rel="icon">` + PNG 64 fallback + apple-touch-icon; nova rota `/favicon.ico`; no Colab os favicons são injetados com o prefixo do proxy.
- **Contato opt-in:** campo opcional de e-mail na tela de Termos (LGPD art. 7º I), gravação local com SHA-256, GA4 nunca recebe o e-mail (só evento contador), endpoint próprio opcional (`UFVAI_CONTACT_ENDPOINT`), direitos do titular (eliminação por campo vazio ou `POST /api/contact/delete`).

---

## [0.6.5] — 2026-08-22 — Terminal à prova de travamentos · splash de carregamento

- **Kill cirúrgico por árvore:** o ttyd é líder do próprio grupo e é morto com um único `killpg` — acaba o `pkill -f opencode` global. Fallback `pkill -9 -x ttyd` (COMM exato).
- **`GET /api/ttyd_ready`:** o frontend faz polling antes de apontar o iframe — fim do `ERR_CONNECTION_REFUSED` no boot, na troca de idioma e na restauração.
- **Splash de boot** com logomarca, spinner, status em 3 estados, erro com indicação do log e botão Recarregar — i18n nos 5 idiomas.

---

## [0.6.4] — 2026-08-22 — Marca UFVAI completa · Temas UFVAI · Logo oficial · Termos v2

- **Marca:** AGENTS.md e variantes se apresentam como **UFVAI** (frontmatter, identidade, capacidades, rodapé); IDs técnicos preservados.
- **Terminal:** temas regenerados na paleta UFVAI (azul-noite + dourado; claro com papel quente); azul antigo eliminado.
- **Abertura:** removido o onboarding antigo (`welcome-hint`) que empilhava com os Termos — a tela de Termos é a única abertura. Logo oficial via nova rota `/assets/*` (whitelist estrita + traversal guard).
- **Termos v2.0:** integridade acadêmica (Portaria CNPq nº 2.664/2026, POSIC/UFV), LGPD completa (arts. 7º, 18, 33–36), foro Viçosa/MG; re-consentimento forçado.
- **Telemetria:** gtag.js client-side com consent-gate (só após aceite) + painel 📊 Telemetria (Admin) com ID/Secret salvos localmente.

---

## [0.6.3] — 2026-08-22 — Servidor persistente offline · Ícone UFVAI no dock

- **Bug crítico (offline):** o wrapper HTTP roda em thread daemon e o processo encerrava ao fim de `run()`, matando o servidor segundos depois. `_offline_keep_alive()` mantém o processo ativo fora do Colab (Ctrl+C ou `kill $(cat ~/PesquisAI/pesquisai.pid)`).
- **Servidor dual-stack:** além do IPv4, sobe loopback IPv6 (`::1`) quando local — Chromium/Firefox preferem `::1` ao resolver "localhost".
- **Ícone no dock:** janela com `--class="UFVAI"` casa com `ufvai-app.desktop` e PNGs nos temas hicolor.

---

## [0.6.2] — 2026-08-22 — Terminal gravável · Launcher app-mode · Telemetria debug

- **Bug crítico:** o v0.6.0 perdeu a flag `--writable` do ttyd e o terminal ficava read-only. Restaurada.
- **Offline (.deb):** launcher restaurado (espera ativa da porta 8001, abertura como app separado via Chrome `--app` → Chromium → Firefox → `xdg-open`).
- **Telemetria:** `UFVAI_TELEMETRY_DEBUG=1` envia eventos para o DebugView do GA4; o launcher carrega `~/PesquisAI/config/ufvai.env` antes de iniciar.

---

## [0.6.1] — 2026-08-22 — Idioma do sistema · troca de idioma robusta · auto-open offline

- **Troca de idioma:** o frontend recarregava antes de o ttyd reiniciar; `setLang()` virou `async` (aguarda o POST com timeout de 15 s) e o backend só responde com a porta do terminal já aceitando conexões.
- **Idioma do sistema detectado na 1ª execução** (`$LANGUAGE` → `$LC_ALL` → `$LC_MESSAGES` → `$LANG` → `locale`), persistido em `~/.config/pesquisai_lang`.
- **Offline (.deb):** o navegador abre sozinho após a porta da UI responder (desabilitar com `UFVAI_NO_OPEN=1`).

---

## [0.6.0] — 2026-08-21 — UFVAI · hardening · telemetria opt-in · zh_CN · Termos

- **Marca:** rebrand visual PesquisAI → UFVAI (dourado + azul profundo, wordmark UFV+AI); identificadores técnicos preservados.
- **Segurança:** CORS `*` removido e token de sessão obrigatório em `/api/*`; sanitização por segmento `&&`; `opencode_auth.json` cifrado; chaves sempre mascaradas; proteção anti-path-traversal; cap de corpo (10 MB) e rate limit; bind local em `127.0.0.1` (Colab mantém `0.0.0.0`).
- **Telemetria anônima opt-in:** `pesquisai/telemetry.py` (GA4 Measurement Protocol); sem consentimento/config não envia nada; kill-switch `UFVAI_TELEMETRY=0`; zero conteúdo.
- **Termos de Uso:** tela de aceite obrigatória na 1ª entrada + `/api/consent`.
- **i18n:** 中文（简体） zh_CN completo.

---

## [0.5.1.9] — 2026-07-18 — Versão offline para Linux e reescrita do AGENTS.md

- **Instalador offline (.deb)** para uso sem rede.
- **AGENTS.md reescrito do zero:** clareza, consistência normativa, economia de tokens (~18–25% menos) e alinhamento com o código (`constants.SKILL_REGISTRY`).
- **Nova arquitetura de diretórios:** `vault/` (memória interna) × `outputs-<slug>/` (entregáveis por projeto).
- **Integridade e segurança:** defesa contra prompt injection, proteção de arquivos de segredos, LGPD com "hard stop" em dados sensíveis não anonimizados.
- **Skills:** catálogo sincronizado com o registry real (IDs canônicos).
- **Memória:** frontmatter enriquecido, atualização obrigatória de `moc/last-state.md` ao fim de tarefas relevantes.
- **PDF** obrigatório apenas para entregáveis finais; notas internas não geram mais PDF automaticamente.

---

## [0.5.1.8] — 2026-07-10 — 3 bugfixes + nova skill Memorial UFV

- **Provider buttons:** `JSON.stringify` inline em `onclick` gerava SyntaxError; trocado por `data-provider` + `this.dataset.provider`.
- **Restauração de sessão:** `opencode session restore` não atualizava o ttyd; trocado por `opencode -s <id>` com `no_fallback: true` + reload da página.
- **Confirmação antes de restaurar backup:** `doRestore()` agora pede confirmação.
- **Nova skill `memorial-ufv`:** gera o Memorial RSC-PCCTAE a partir do PDF do Relatório Detalhado (saída `.md` e `.docx`).
- **Provider flow:** nova tela inicial com chaves salvas (editar/excluir), botão Voltar, botão ↻ Atualizar no modal de sessões.

---

## [0.5.1.5] — 2026-07-01 — Editor de Memória Obsidian

- Modal split view (lista de notas + editor com abas Edit/Preview/Split).
- **4 endpoints novos:** ler nota, árvore por subdiretório, busca BM25 e lista de tags; POST com ações save/create/delete (delete move para `.trash/`).
- Preview com `marked.js`, destaque de `[[wikilinks]]` e `#tags`; indicador de edição não salva; 20 chaves i18n em 4 idiomas.
- **Hotfix:** botões do editor não funcionavam (SyntaxError JS) — corrigido.

---

## [0.5.1.3] — 2026-06-30 — Conectores de provedor de IA

- `confirmProvider()` crashava antes de salvar a API key; captura local dos dados antes de fechar o modal, verificação de `r.ok`/`d.ok` no fetch e fechamento só após sucesso.

---

## [0.5.1.2] — 2026-06-30 — Botão Memória Obsidian no topbar

- Overlay com status, stats, notas recentes e daily notes; endpoint `GET /api/obsidian`.

---

## [0.5.1] — 2026-06-29 — Obsidian Autopilot

- **O agente salva sozinho:** `autopilot.py` com `recall`, `save`, `save_finding`, `start_session`/`end_session`, `log_skill`/`log_file` e `auto_init()` (chamado no boot).
- Vault criado automaticamente em `<DRIVE>/PesquisAI/vault/`; daily note e MOC raiz criados no boot; tudo é no-op se o vault não estiver disponível.
- Vault sempre no Google Drive (validação obrigatória).

---

## [0.5.0] — 2026-06-28 — Obsidian Second Brain (memória de longo prazo)

- Módulo `pesquisai.obsidian` (8 arquivos, ~1.500 linhas) + skill `obsidian-memory` + 10 templates.
- Memória persistente entre sessões via vault no Drive; busca BM25 offline, backlinks, wikilinks e tags; taxonomia `pesquisai/*` 