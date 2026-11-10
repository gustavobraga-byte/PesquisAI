# Changelog — PesquisAI

## [0.7.11-web] — 2026-11-08 — 🖥️ Interface web do OpenCode no lugar do ttyd

### 🎯 Pedido
- *"fazer uma versão 0.7.11 usando a versão web do opencode no lugar de mostrar
  o ttyd na janela. Personalize essa visão com os detalhes do ufvai (cores,
  etc.)"*.

### 🧱 Implementação
- **`pesquisai/ocweb.py`** (novo): proxy HTTP/1.1 em `0.0.0.0:8002` que
  publica a SPA do OpenCode (loopback + Basic auth) com:
  - **Basic auth injetada** a partir do `service.json` (o navegador nunca vê a
    senha);
  - repasse de `/_assets`, `/icons`, `/api/*` e **SSE** (`/api/event`) em
    chunks;
  - **túnel WebSocket** para o PTY (quando usado);
  - injeção de **tema UFVAI** (`--v2-*`: navy/dourado/creme, claro e escuro),
    barra degradê, badge **UFV·AI** e título “UFVAI · OpenCode”;
  - página 503 amigável (auto-refresh 3 s) enquanto o motor não sobe.
- **`launch_app.py`**: inicia o proxy no boot, aponta o iframe para
  `proxyPort(8002)` e expõe `GET /api/ocweb_ready` (proxy + upstream).
- **`launch_app_responsive_v041.py`**: `create_wrapper_html(..., web_mode=True)`
  troca o polling do splash de `/api/ttyd_ready` para `/api/ocweb_ready`.
- **`constants.py`**: `OCWEB_PORT = 8002`.
- O `ttyd` continua sendo iniciado como **fallback** (não aparece na janela).

### 🎨 Tema
- Tokens `--v2-*` sobrescritos em claro/escuro; tipografia do sistema; barra
  superior navy→dourado; badge fixo; título da aba.
- O botão de tema do próprio OpenCode continua controlando claro/escuro.

### 🧪 Testes
- `tests/test_v0711_ocweb.py` — **9 testes** (service.json, Basic auth,
  injeção de tema/badge/título, `ready()` sem serviço, status e o HTML do
  wrapper em `web_mode`).
- Validação HTTP real: HTML 200 com tema injetado, `/_assets` 200 (915 KB),
  `/api/session` 200 e `/api/event` em streaming.

### 🩹 Correção (revisão `web2`)

- **Causa do “continua abrindo o ttyd”:** `COLAB_BOOT_0.7.11.py` copiava a
  árvore fixa `UFVAI-v0.7.11` (sem a UI web) para `/tmp/pesquisai`, mesmo
  quando a célula era executada dentro de `UFVAI-v0.7.11-web/`.
- A célula agora resolve a origem pela própria pasta (ou pela pasta atual que
  contenha `pesquisai/ocweb.py`) e **aborta com instrução clara** quando a
  porta 8001 já está ocupada por uma sessão antiga — antes o bind falhava
  dentro de uma thread e o wrapper antigo continuava servindo.
- `ocweb` ganhou `GET /__ufvai_ready` (JSON + CORS): health-check do proxy e
  do motor, útil para diagnóstico e para o boot.
- Testes: 16 (inclui health-check e a checagem da célula de boot).

### 🩹 Correção (revisão `web3`)

- **“Can't reach this server”** no proxy do Colab: o `fetch` da SPA passou a
  enviar credenciais (`same-origin`), necessárias para o cookie do proxy.
- **Abre direto na sessão do projeto**: `launch_app` grava a sessão atual em
  `/tmp/ufvai-current-session`; o proxy serve `/__ufvai/boot.js` +
  `/__ufvai/session` e, na home, navega para
  `/server/<chave>/session/<id>` — a mensagem de saudação aparece sem clique.
- O script é **externo** (`script-src 'self'`), porque o CSP da SPA bloqueia
  script inline.
- Validação com Chromium headless (Playwright): home → redireciona para a
  sessão e renderiza “Olá! (Dica: …)”.

### 🔄 Correção (revisão `web10`)

- **Sincronização TUI ↔ web orientada a foco**: o plugin `ufvai-sync` publica a
  sessão que o terminal está exibindo a cada 250 ms (e no
  `session.execution.started`); o proxy lê o arquivo a cada 150 ms e faz
  *push* SSE (`/__ufvai/live`). A web troca em ~0,3 s.
- **Sentido inverso**: a web grava `/tmp/ufvai-web-focus.json` ao navegar
  (400 ms); o plugin navega a TUI para a sessão escolhida (~0,4 s).
- **Corrida resolvida**: ao abrir uma URL de sessão, a web **ignora o primeiro
  foco** do live e reporta a própria sessão ao terminal — a URL da web manda
  ao abrir; depois, as trocas da TUI mandam.
- Removido o canal redundante `/__ufvai/events`; o fallback de polling só roda
  se o EventSource não estiver conectado.
- 64 testes.

### 🛑 Correção (revisão `web13`) — “Working” preso e botão Parar

- **“Working” no fim da resposta**: o status é controlado por evento
  (`session.execution.started` → conjunto *working*; `succeeded/failed/
  interrupted` → limpa). Quando o evento final se perde (SSE bufferizado no
  proxy do Colab, reconexão), o rodapé fica “Working” para sempre. Agora o
  `boot.js` consulta `GET /__ufvai/run-state?sid=…`, que olha a **última
  mensagem do assistente** (e não `time.busy > idle`, que fica inconsistente
  quando um turno morre): se o turno terminou e a UI continua “Working”,
  revalida e recarrega **uma vez** (máx. 1×/30 s). Nada se perde — o estado
  está no servidor.
- **Botão Parar**: a SPA já chama `POST /api/session/<id>/interrupt?resume=true`
  (verificado: o turno vira `interrupted`). Se essa chamada não sair (handler
  perdido, botão desabilitado, UI travada), um fallback no `boot.js` envia a
  interrupção 600 ms depois do clique. Se o turno **já terminou** no servidor,
  o fallback apenas limpa a UI (reload único) em vez de um interrupt inócuo.
- **`/__ufvai/run-state`**: `running` = última mensagem do assistente sem
  `time.completed` e com atividade recente (< 120 s); `stale` = parada há mais
  de 120 s (turno órfão).
- Testes: **113 passed** (inclui `compute_run_state` e as redes de segurança).

### 🔁 Correção (revisão `web12`) — pergunta da UFV uma vez só e foco mais rápido

- **A pergunta “Você é aluno(a) da UFV?” voltava a cada acesso.** A decisão era
  gravada em `~/.config/ufvai/vpn/prefs.json` — no Colab isso é **efêmero**: um
  runtime novo (ou “Reiniciar sessão”) apagava tudo. Agora as preferências têm
  espelho persistente em `backups/ufvai_vpn_prefs.json` (Drive; offline em
  `~/PesquisAI/backups/`) e `load_prefs()` mescla os dois com OU lógico para
  `ask_dismissed` e `auto_connect`. **A resposta é dada uma vez por Drive.**
- **Ativação única de verdade**: ao escolher “sou aluno(a) da UFV”, a opção
  “Lembrar neste Drive (cifrado)” já vem marcada; conexão bem-sucedida com
  credenciais salvas arma `auto_connect`, e o boot seguinte reconecta a VPN
  sozinho (thread `ufvai-vpn-autoconnect`, 4 s após a UI subir, sem modal e sem
  bloquear nada). Desconectar no 🛡 ou apagar as credenciais **desarma** a
  reconexão — intenção explícita do usuário é respeitada.
- **Latência do foco TUI → web**: o plugin agora entrega a sessão por
  `POST /__ufvai/focus` (`source: "tui"`) e o proxy publica no SSE na hora —
  **14 ms** medidos no proxy (antes: até 150 ms de polling + tick). O arquivo
  continua sendo escrito como reserva; a checagem da rota caiu de 150 ms para
  100 ms e o polling de segurança do proxy de 150 ms para 50 ms.
- **Latência web → TUI**: `pushState`/`replaceState`/`popstate` são
  interceptados e publicam o foco imediatamente; o intervalo de reserva passou
  de 800 ms para 1.200 ms. Medido: **90 ms** (antes 720 ms).
- **Escrita de preferências não “esquece” a decisão**: `save_prefs()` mescla com
  o arquivo existente (`{**anterior, **novo}`), então uma gravação parcial de
  versão antiga não faz a pergunta voltar.
- Testes: **107 passed** (`ocweb` + `onboarding` + `vpn`), incluindo decisão que
  sobrevive a um runtime novo, auto-connect condicionado a credenciais salvas e
  o caminho rápido do foco por HTTP.

### 🔄 Correção (revisão `web11`) — sincronização em tempo real TUI ↔ web

- **Causa do “não sincroniza”**: o `boot.js` montava a rota com a URL do
  **motor** (`/server/<base64(engine)>/session/…`). A SPA só conhece a origem
  em que está sendo servida, então a rota ficava sem servidor registrado e a
  sessão abria em branco. A chave agora é `base64url(location.origin)`.
- **Push de verdade**: a TUI publica a sessão exibida em
  `/tmp/ufvai-focus.json`; o proxy observa o arquivo e emite em
  `/__ufvai/live` (SSE). A web troca em **0,15–0,35 s** — sem polling.
- **Sem recarregar**: `navTo()` usa `history.pushState` + `popstate` e só cai
  para `location.replace` se o conteúdo de `<main>` não mudar em 700 ms.
  O estado da SPA sobrevive à troca de sessão.
- **Sem ping-pong**: navegação originada por push do terminal é marcada em
  `sessionStorage` (`ufvai-pushed`) e não é republicada como foco.
- **Foco inicial**: ao abrir uma sessão, a web publica a própria sessão para o
  terminal seguir (`POST /__ufvai/focus`); o plugin da TUI navega em 0,2–0,8 s.
- **Rascunho**: a troca só é bloqueada quando o prompt tem texto. A checagem
  por “Working”/“Trabalhando” no corpo da página dava falso positivo e
  congelava a sincronização — removida.
- 68 testes (`tests/test_v0711_ocweb.py` + `tests/test_v0710_onboarding.py`).

### 🔑 Correção (revisão `web9`)

- **Chave Google sem exigência de prefixo**: `validate_key_format` não bloqueia
  mais chaves que não começam com `AIza` (o prefixo é só heurística de
  reconhecimento); a validação real é no provedor. Texto/placeholder do
  onboarding atualizados.
- **`.deb` em máquina nova (fail-open)**: `run_fast.run()` não aborta se
  `setup_drive`, dependências, skills ou vault falharem — a interface sobe.
- **Sem motor, a interface sobe**: se o OpenCode 2.x não estiver instalado, o
  terminal é pulado (sem shell quebrado) e a página 503 explica
  `ufvai --engine-install`. O instalador versionado `ufvai-engine` é tentado
  antes do `curl | bash`.
- **Dependências do pacote**: `unzip` e `xz-utils` em `Depends`; o `ttyd`
  empacotado em `/opt/pesquisai/bin` entra no `PATH` mesmo fora do launcher.
- 58 testes.

### ⚡ Correção (revisão `web8`)

- **Modelos/provedores só apareciam ao abrir Configurações**: a SPA perde o
  primeiro `server.connected` quando o bundle ainda está carregando; sem o
  handshake ela não dispara `provider.sync`/`model.sync`. O proxy agora fecha
  a **primeira** conexão SSE de cada page load (1 s) e a SPA reconecta — o
  handshake real chega com o listener já registrado.
- **Cache do catálogo**: `/api/model` e `/api/provider` são pré-buscados no
  boot e servidos do cache (`X-UFVAI-Cache: hit`), com gzip. O *sync* da SPA
  tem timeout de 15 s; a resposta instantânea evita a lista em branco.
- **Sincronização em tempo real da sessão**: o evento
  `session.execution.started` grava a sessão ativa; a web segue o terminal
  (janela de 30 s) quando ele começa uma execução. O composer com texto e
  “Working” bloqueiam a troca.
- 26 testes.

### 🧯 Correção (revisão `web7`)

- **Provedores/modelos em branco**: a SPA consulta
  `/api/model?location[directory]=<projeto>` e `/api/provider?...`. Se o
  recorte do projeto vier vazio, inválido ou com erro, o proxy agora devolve
  o **catálogo global** (`/api/model` e `/api/provider` sem `location`) — a
  SPA não tem fallback próprio e deixava seletor e lista de provedores vazios.
- `GET /__ufvai/catalog` passou a verificar o **escopo do projeto**
  (`scoped_models` + `project`), não só o global.
- Novo `GET /__ufvai/diag`: mostra `project`, `model.scoped/global`,
  `provider.scoped/global` e se o fallback está ativo. Útil para diagnosticar
  o ambiente do Colab sem abrir o console.
- 25 testes.

### 🎨 Correção (revisão `web6`)

- **Tema claro/escuro chega à versão web**: o wrapper envia
  `postMessage({type:"ufvai-theme"})` ao iframe (e no evento `load`); o
  `boot.js` aplica em `data-color-scheme`, `localStorage` e dispara um
  `StorageEvent` para a SPA atualizar o próprio estado. O `?theme=` também
  é lido no primeiro load. Em modo web o iframe **não** é mais recarregado a
  cada troca (sem tela em branco).
- **Nova sessão com nome UFVAI**: títulos nulos ou `opencode` viram `UFVAI`
  na criação (`POST /api/session`), no restore e no boot; sessões criadas
  pela TUI são corrigidas pelo evento `session.created` do SSE. Títulos
  definidos pelo usuário são preservados.
- 23 testes (inclui tema, catálogo e normalização de título).

### 🩹 Correção (revisão `web5`)

- **Alternador com rótulo claro**: o botão da topbar e o item do menu ☰ agora
  dizem **“Alternar terminal / versão web”** (5 idiomas).
- **Fila do proxy**: `request_queue_size` passou de 5 para 128. A SPA dispara
  ~20 requisições ao abrir a sessão; o backlog padrão recusava conexões e a
  tela caía em “Can't reach this server”. 40 requisições paralelas agora
  respondem em ~0,3 s.
- **Catálogo antes da SPA**: novo `GET /__ufvai/catalog` (modelos/provedores)
  e o `boot.js` espera o catálogo ficar pronto antes de abrir a sessão. Numa
  sessão aberta direto, se o catálogo ficou pronto depois do load, a página
  recarrega **uma vez** — corrige a lista de modelos em branco no reload.
- **`Cache-Control: no-store`** em `/api/*`: um `/api/model` vazio (motor
  subindo) não fica mais preso no cache do navegador.
- **Sessão terminal ↔ web**: o relay SSE grava a sessão dos eventos
  `session.created`/`session.viewed`/`session.execution.started` em
  `/tmp/ufvai-current-session`; `/__ufvai/session?fallback=1` usa a sessão
  ativa/mais recente quando não há sessão persistida. Criar/trocar de conversa
  no terminal passa a abrir a mesma conversa no web.
- **Execuções órfãs**: no boot, sessões com `busy > idle` há mais de 15 min
  recebem `POST /interrupt` — evita “Trabalhando” eterno e mensagens presas em
  “pending” depois de um runtime interrompido.
- **Motor aquecido**: `/api/provider` e `/api/model` são consultados antes de
  a interface abrir, reduzindo a corrida do primeiro carregamento.
- **Retry de upstream** e descompressão defensiva (gzip/deflate) no proxy.

### ⚠️ Limitações
- A UI é a do OpenCode (não uma tela própria): a customização é visual.
- Sem navegador real neste ambiente; validação por HTTP + testes.
- O `ttyd` segue rodando em segundo plano como fallback.

## [0.7.12] — 2026-11-08 — 🪟 Windows (.exe + Menu Iniciar) e ações no menu do Linux

### 🎯 Pedido do autor
- *"confira a versão offline do ufvai. Ela deve ter um botão no menu iniciar que inicia ela. Também crie uma versão compatível com windows exe com iniciador no menu iniciar."*

### 🔎 Conferência do .deb (modo offline)
- O pacote **já instalava** o atalho: `build-deb.sh` copia `packaging/ufvai.desktop`
  para `/usr/share/applications/` e os ícones em
  `/usr/share/icons/hicolor/{scalable,256x256,64x64}/apps/` — confirmado com
  `dpkg-deb -c` sobre `pesquisai_0.7.11-offline1_amd64.deb`.
- **Lacuna corrigida:** com `Terminal=false` o clique no menu não dava retorno
  visível. Agora `Exec=ufvai --gui` — inicia, garante que o navegador abra e
  avisa pela área de notificação (`notify-send`, quando existe).
- Novas **ações** no atalho: `Abrir`, `Ver estado`, `Diagnóstico` e `Encerrar`.

### 🪟 Windows
- Pipeline completo em `packaging/windows/`: `ufvai_win.py` (entrypoint),
  `ufvai.spec` (PyInstaller, onefile `--windowed`), `installer.iss` (Inno Setup
  com atalho `{autoprograms}` no **Menu Iniciar**), `build_exe.ps1`/`build_exe.bat`,
  `requirements-windows.txt` e `.github/workflows/build-windows.yml`.
- ⚠️ **Limitação:** este runtime é Linux e o PyInstaller **não** compila de forma
  cruzada para Windows. O `.exe` é gerado executando o build em uma máquina
  Windows ou pelo workflow do GitHub Actions (que publica o artefato).

### 🔧 Compatibilidade de código
- `launch_app.py`: `os.getuid()` → `getattr(os, "getuid", lambda: 0)()`.
- `launch_app.py`: `signal.SIGKILL` → `getattr(signal, "SIGKILL", signal.SIGTERM)`.
- `assets/ufvai.ico` gerado a partir de `ufvai-256.png` (16→256 px).

### 🧪 Testes
- `tests/test_v0712_menu_iniciar.py` — **14 passed** (entry válido, ações com
  `Exec`, sintaxe bash do launcher, instalador com `{autoprograms}`, `.ico`
  válido, workflow e os dois guards de Windows).

## [0.7.11] — 2026-11-06 — 🛡 VPN da UFV no Colab (OpenVPN em namespace isolado)

### 🎯 Pedido do autor
- *"quero que o servidor do Colab conecte via internet via VPN da UFV"*.
- Depois: *"vai abrir uma tela logo quando ele iniciar para escolher se ele é
  aluno da UFV ou não. Se ele clicar em aluno da UFV, vai aparecer a interface
  solicitando o CPF e a senha, que são as credenciais para entrar no VPN"*.
- Tutorial indicado: <https://vpn.ufvnet.ufv.br/linux_ubuntu.html>.

### 🔎 O que a UFV usa (fonte oficial)
- **OpenVPN**, perfil público `https://vpn.ufvnet.ufv.br/configs/UFV-linux.ovpn`
  (5.052 B), `remote vpn.ufvnet.ufv.br 1195`, `proto udp`, `dev tun`,
  `auth-user-pass` (**CPF + senha**), `comp-lzo yes`.
- **Split tunnel**: “usar esta conexão apenas para recursos nesta rede”.
- **1 dispositivo por CPF**.

### 🧱 O problema do Colab (e a solução)
- Sem `/dev/net/tun` e sem `CAP_NET_ADMIN` (`CapEff=00000000a82c25fb`);
  `ip tuntap add` → `Operation not permitted`.
- `mknod /dev/net/tun` funciona (root + `MKNOD`).
- **Solução:** OpenVPN dentro de **user+net namespace** (`unshare -Urn`) +
  **`slirp4netns`** (NAT em espaço de usuário) + **proxy SOCKS5** (stdlib)
  publicado em `127.0.0.1:1081` por `add_hostfwd`.
- **Não é túnel transparente:** só o que usa o proxy entra na VPN — sem
  `NET_ADMIN` no namespace raiz isso é impossível. O restante do Colab
  continua na internet normal.

### 🌐 Modo total e modelo local (OpenCode)
- **Modo total (padrão = split + serviço no netns):** o serviço do OpenCode +
  ttyd rodam **dentro** do namespace (`unshare -Urnm`); só a rede da UFV
  (`100.65.0.0/17`…, `200.235.128.0/17`) sai por `tun0` e a internet comum
  (LLM, GitHub, PyPI) continua pelo Colab via `tap0`. O wrapper (8001) e o
  kernel do notebook continuam fora. Ativar/desativar reinicia o terminal/agente.
- **Túnel total opcional** (`redirect-gateway def1`, checkbox “Túnel total”):
  manda TODO o tráfego para a UFV — medido em 07/11/2026, a UFV **bloqueia a
  saída externa** (OpenRouter, Google, OpenAI, GitHub, PyPI dão timeout; só
  hosts da UFV respondem 200). Serve só para modelos/serviços internos da UFV.
- **Modelo local:** encaminhador TCP `127.0.0.1:<porta>` → serviço da
  intranet (ex.: Ollama `10.0.0.10:11434`), com DNS da VPN. No OpenCode,
  use `http://127.0.0.1:<porta>/v1` como `baseURL`.
- **DNS próprio:** `/etc/resolv.conf` bind-montado no namespace (DNS da VPN
  + públicos), para o OpenCode/terminal resolverem nomes internos.

### 🎛️ Google no seletor de gratuitos + “Outro provedor”
- **Google Gemini** entra em **🎛️ Modelo gratuito padrão** (junto de NVIDIA e
  OpenRouter); `is_free_model` e `merge_default_model` aceitam `google/*`.
- **“Outro provedor”** no onboarding: lista curada com **OpenAI, Anthropic,
  Groq, Mistral, DeepSeek, Together, Fireworks, xAI e Cohere**, cada um com
  link oficial e campo para a própria chave (variável padrão do provedor).
- O onboarding agora vem **depois** da pergunta da VPN, que vem **depois dos
  Termos** — a ordem é Termos → VPN → provedor/chave.

### 🖥️ Tela inicial e painel
- Nova tela, depois de Termos/onboarding: **“Você é aluno(a) da UFV?”**
  - **Sim** → painel com **CPF** e **senha da VPN**.
  - **Não** → segue sem VPN; a escolha fica em `prefs.json` + `localStorage`
    e não volta a perguntar (o botão 🛡 da topbar reabre quando quiser).
- Painel: status ao vivo (desconectado/conectando/conectado/erro), avisos
  (1 dispositivo por CPF, túnel total, senha), **Conectar/Desconectar**,
  **Testar acesso** (`https://sistemas.ufv.br/`), **baixar/colar** o `.ovpn`,
  **esquecer** credenciais e detalhes técnicos (modo, TUN, rotas, DNS, log).
- **OpenCode pela VPN é o PADRÃO**: “Usar a VPN em todo o UFVAI” já vem
  marcada (split tunnel); a conexão move o serviço do OpenCode
  + ttyd para o namespace. A porta do serviço é republicada no host via
  slirp (`add_hostfwd`), então o wrapper/CLI continuam funcionando.

### 🔐 Segurança
- Senha **nunca** em linha de comando, log ou `state.json`: arquivo `auth`
  `0600` em `~/.config/ufvai/vpn/run/`, apagado ao desconectar.
- “Lembrar neste Drive” grava CPF/senha **cifrados** (Fernet) no
  `keys_store.json`, com prefixo reservado `vpn_ufv_` — filtrado de
  `/api/apikey`.
- `_redact()` mascara CPF e `password=` em qualquer log.

### 🔌 API e CLI
- `GET /api/vpn` → status + capacidades + perfil + `should_ask`.
- `POST /api/vpn/connect` `{cpf, password, remember, use_saved}`.
- `POST /api/vpn/disconnect`, `/profile`, `/test`, `/forget`, `/answer`.
- CLI: `python -m pesquisai.vpn status|connect|disconnect|profile|test`.

### 🧪 Testes
- `tests/test_v0711_vpn.py` — **30 testes offline** (perfil, máscara,
  redaction, prefs, credenciais cifradas, SOCKS5 + relay local, capacidades,
  bind `0.0.0.0`/porta publicada do serviço, padrão split tunnel e modo
  total aceitando split).
- **Prova de conceito no Colab:** UDP 1195 alcança o servidor, o TLS completa
  e credenciais falsas retornam `AUTH_FAILED`; o caminho
  `netns → slirp → SOCKS5 → 127.0.0.1:1081` devolveu **HTTP 200** para
  `https://www.ufv.br/`. A conexão real depende das credenciais do usuário.

### ⚠️ Limitações
- 1 dispositivo por CPF: conectar o Colab pode desconectar o computador.
- Credenciais vão para a VM do Google; “lembrar” é opcional e cifrado.
- O uso deve respeitar as regras da UFV/DTI e da CAPES Periódicos.

## [0.7.10] — 2026-11-05 — 🧭 Onboarding de primeiro uso: provedor e chave

### 🚪 A tela que faltava
- **Pedido do autor:** *"um novo user, quero que ele use a apikey dele, mas de modo
  simples"* — e, para quem já usa, *"essa tela aparece se não tiverem uma apikey"*.
- Depois do aceite dos **Termos** (e do "Bem-vindo de volta", quando houver), surge a
  tela **"Para usar o UFVAI você precisa de um provedor de IA"** com duas escolhas:
  **Já tenho um provedor** (abre o modal `Conectar Provedor de IA` de sempre) e
  **Não tenho / não sei o que é isso** (abre as opções guiadas).
- A condição é **objetiva**: sem chave utilizável no `keys_store.json` nem no ambiente,
  a tela aparece — inclusive para usuário antigo que trocou de conta ou apagou as
  chaves. Com qualquer chave, o app abre como sempre.

### 🆓 Opções (com tutorial e campo de colar)
- **Google Gemini — RECOMENDADO** (grátis no AI Studio), **NVIDIA NIM**, **OpenRouter**
  e **OpenCode Go** marcado como **PAGO**.
- Cada card leva ao tutorial do provedor: passos numerados, **link oficial**, uma
  **reprodução da tela** (rotulada como reprodução) e o campo para colar a chave.
- No Google: link direto para `https://aistudio.google.com/api-keys`, instrução de
  clicar em **Copiar**, voltar para a janela e colar; a chave (`AIza…`) é salva como
  **`GOOGLE_GENERATIVE_AI_API_KEY`**.

### ⏳ O motor espera a chave
- **Sem chave, o `opencode` não sobe.** `needs_onboarding_now()` é avaliado no
  boot: o serviço do motor e o ttyd ficam parados; só a interface web sobe para
  receber o onboarding.
- **Ao salvar a chave, reinício duro:** `_hard_restart_engine()` encerra o
  terminal (ttyd + TUI), derruba o serviço (todas as sessões) e sobe tudo de novo
  já com a chave e o modelo corretos.

### 🔁 Retry automático em cota/429
- Plugin `ufvai-retry` (hook `retry` do motor): **somente quando a mensagem é de
  cota** (`quota`, `RESOURCE_EXHAUSTED`, `free_tier`, `per minute`) espera **~62 s**
  — a janela de 1 min da cota gratuita do Google. Mensagens de sobrecarga (“high demand”, “overloaded”) esperam só **5 s**;
  outros 429/503 seguem o retry padrão do motor.
- Lê `retry in 23s`/`retryDelay` da própria mensagem quando existir; teto de 3 min;
  desiste após 8 tentativas. Instalado no boot por `retry_plugin.ensure_retry_plugin()`.
- **Fallback após 5 tentativas:** se o modelo principal (Flash-Lite Latest) não
  passar, troca a sessão para `google/gemini-3.1-flash-lite` e repete a requisição
  (uma troca por sessão a cada 30 min; `UFVAI_RETRY_SWITCH_AFTER`/`UFVAI_RETRY_FALLBACK`).

### 🎛️ Modelo padrão do Google
- Com chave do Google, o modelo padrão passa a ser **`google/gemini-flash-lite-latest`**
  com variante **`high`** ("Gemini Flash-Lite Latest Google · high") e continua valendo
  nos próximos usos (aplicado no boot, em `load_keys_from_drive`).
- O `model` raiz não guarda variante (limite do V2); ela vai em
  `agents.UFVAI.model = "google/gemini-flash-lite-latest#high"`.
- Constante `GOOGLE_DEFAULT_MODEL` em `pesquisai/onboarding.py`; override por
  **`UFVAI_GOOGLE_MODEL`** e desligamento por **`UFVAI_GOOGLE_MODEL_LOCK=0`**.
- Se o catálogo do motor estiver disponível, o id é conferido contra a lista real
  (`google_model_from_catalog`) e cai nos fallbacks declarados — nada é inventado.

### 🔌 API e arquitetura
- `GET  /api/onboarding` → `{needs, has_key, google_model, providers[], docs, guide}`.
- `POST /api/onboarding/key` → valida formato, grava **cifrado** em `backups/`,
  injeta a variável no processo/serviço, define o modelo padrão e reinicia o terminal
  (`_apply_opencode_env_change_async`). **Nunca loga a chave**; devolve só `masked`.
- Módulo puro **`pesquisai/onboarding.py`** (prefixos, validação, `mask_key`,
  `needs_onboarding`, `merge_model`, `providers_public`), sem rede e sem disco.
- "Agora não" (✕) esconde apenas nesta aba (`sessionStorage`); a próxima abertura
  sem chave volta a mostrar.

### 🧪 Testes
- `tests/test_v0710_onboarding.py` — 24 verificações: detecção por prefixo, chave
  ambígua, validação de formato, mascaramento, `needs_onboarding` (store/ambiente),
  modelo do Google e fallback de catálogo, `merge_model` preservando config e o
  contrato do HTML/JS (overlay, endpoint, ordem das opções, badge de pago).

## [0.7.9] — 2026-11-04 — 🔑 Chaves de API e free tier para novos usuários

### 🆓 Quem chega sem chave vê **como obter uma gratuita**
- **Pedido do autor:** *"quem instala o UFVAI pela primeira vez não tem chave de API e não
  sabe como conseguir uma. Coloque as instruções e uma opção gratuita."*
- No modal **🔌 Provedores**, o bloco `#prov-howto` aparece **sozinho quando não há
  nenhuma chave salva** (`renderSavedKeys()`): links diretos para **OpenRouter**
  (`openrouter.ai/keys`) e **NVIDIA** (`build.nvidia.com`), o guia
  [`docs/CHAVES_API.md`](docs/CHAVES_API.md) e o aviso de responsabilidade.
- A **opção paga** (OpenCode Go) aparece como link separado: o UFVAI **não emite, não
  cobra e não garante limites** de nenhum provedor.
- O mesmo aviso foi incluído na **tela de Termos** (abertura), com link para o guia.

### 🎛️ Seletor de modelos gratuitos + **modelo padrão**
- **`GET /api/free_models`** lê `opencode models` e filtra apenas o que é gratuito:
  `openrouter/free`, `openrouter/*:free` e `nvidia/*` (cache de 10 min). A resposta
  inclui `key_links` e `docs`.
- **`POST /api/default_model`** grava o campo `model` do `opencode.json`
  **preservando o restante** da configuração (escrita atômica); recusa qualquer
  modelo pago com **400**.
- No modal, o seletor **🎛️ Modelo gratuito padrão** (OpenRouter/NVIDIA) e o botão
  **Definir como padrão** usam esses endpoints.
- Regras em módulo puro **`pesquisai/free_models.py`** (`is_free_model`,
  `filter_free_models`, `merge_default_model`), testável sem rede.

### 💾 Botão **⚙ Autosave**: intervalo e conversas
- **Pedido do autor:** *"queria escolher de quanto em quanto tempo salva e quais
  conversas salvar."*
- O **⚙** ao lado do autosave abre a configuração: intervalo **1–60 min**
  (1, 3, 5, 10, 15, 30, 60) e escopo **sessão ativa · todas as conversas · escolher
  conversas** (lista com checkboxes vinda de `/api/sessions`).
- Preferências em `localStorage` (`ufvai_autosave_interval_min`,
  `ufvai_autosave_scope`, `ufvai_autosave_session_ids`); o timer passa a usar o
  intervalo escolhido.
- **Backend:** `POST /api/autosave` aceita `session_ids` e grava **somente** as
  conversas escolhidas (`save_all_sessions`), sem tocar nos slots da sessão ativa.

### 📚 Documentação
- **`docs/CHAVES_API.md`** (PT + EN): como criar chave gratuita no OpenRouter/NVIDIA,
  limites definidos pelo provedor, opção paga, onde a chave fica (cifrada no Drive) e
  o que o UFVAI nunca faz.
- README e MANUAL atualizados para **0.7.9** (badge, citação ABNT/BibTeX, rodapé).

### 🧪 Testes
- **`tests/test_v079_free_models.py`** — classificação de gratuitos (`openrouter/free`,
  `:free`, `nvidia/*`), rejeição de pagos e do Zen fora do escopo, deduplicação e
  ordenação, merge que preserva a configuração e links.
- **`tests/test_v079_ui_contract.py`** (**novo**) — contrato dos endpoints
  (`/api/free_models`, `/api/default_model`), do bloco de instruções, do seletor, do
  ⚙ e do `session_ids`.
- `test_version_sync` verde: versão idêntica em `__version__.py`, `constants.py`,
  `pyproject.toml`, `Dockerfile` e CHANGELOG.

---

## [0.7.8] — 2026-10-29 — 🔑 Chaves de API do Drive no serviço do motor (OpenCode v2.2)

### 🐞 Sintoma
- Depois da atualização para o **OpenCode v2.2**, o UFVAI deixou de enxergar os provedores configurados: `opencode models` listava apenas `opencode` e `opencode-go`, embora as 5 chaves estivessem no `backups/keys_store.json` do Drive e no `~/.bashrc`.

### 🔎 Causa raiz (medida no runtime)
- O boot chama `ensure_service_project_dir()` **antes** de `start_wrapper_server()` — e é neste último que o UFVAI carrega as chaves do Drive. Resultado: o processo `opencode serve --service` nascia com **0 das 5 variáveis** de chave no próprio ambiente, enquanto o shell tinha as 5.
- Até o motor 2.1 isso não aparecia porque a TUI resolvia provedores com o ambiente dela (herdado do `~/.bashrc`). **Na v2.2 o catálogo de provedores é resolvido dentro do serviço** — por isso o sintoma surgiu só agora.
- Prova: `opencode models` (via serviço) → `opencode`, `opencode-go`; `opencode models --standalone` (mesmo ambiente do shell) → + `openrouter`, `google`, `nvidia`.

### ✅ Correções
- **Injeção no serviço:** `ensure_service_project_dir(..., backup_dir=)` decifra o `keys_store.json` e injeta as variáveis no `env` do `Popen` do serviço **e** no `os.environ` do boot (o resto do processo — ttyd, wrappers, terminal — também passa a vê-las).
- **Auto-cura:** se o serviço já está no diretório certo mas nasceu sem as chaves, ele é reiniciado (`service_missing_key_envs`). Um boot antigo não deixa mais o motor "cego" até o próximo restart manual.
- **Salvar/remover chave vale na hora:** `_apply_opencode_env_change_async` agora reergue o serviço **já com as chaves novas** antes de reiniciar o terminal.
- **Sem quebra de compatibilidade:** o `keys_store.json` não muda de formato; nada é copiado para o banco do motor; a pasta do store é resolvida (Drive → `~/PesquisAI/backups`).

### 🩺 Diagnóstico
- Novo `scripts/diag_keys_v22.py`: mostra store, processo, `~/.bashrc`, **ambiente do serviço** e provedores vistos pelo motor — sem nunca imprimir segredo. Códigos de saída: `0` ok · `1` chaves não chegaram ao serviço · `2` store vazio · `3` sem serviço/erro.
- `--json` para uso em suporte e em testes.

### 🧪 Testes
- `tests/test_v078_service_keys.py` — 15 testes (store → env, detecção no serviço, fast-path x reinício, injeção no Popen, reerguer serviço, script sem vazamento de segredo).
- Regressão: `test_v077_start_dir` · `test_drive_guard` · `test_version_sync` · `test_security` — 119 testes verdes.

### ⌨️ Ajuste (29/10, **sem bump** — continua 0.7.8) — Ctrl+C copia · Ctrl+V cola no terminal

#### 🐞 Sintoma
- No terminal do UFVAI (ttyd 1.7.4 + xterm.js) o **Ctrl+C** chegava ao PTY como `^C` (0x03) e, na TUI do opencode com o campo vazio, **encerrava a conversa** — o terminal "morria" no meio do trabalho.
- O **Ctrl+V** mandava `^V` (0x16) para o aplicativo **além** de colar (literal-next do readline).

#### ✅ Correção
- **`Ctrl+C` copia** a seleção (`xterm.getSelection()`, com `navigator.clipboard.writeText` e fallback `document.execCommand('copy')`) e **nunca** vai ao PTY. Sem seleção, só aparece a dica (com throttle de 10 s).
- **`Ctrl+Shift+C`** envia `\x03` de verdade (saída de emergência para interromper um comando).
- **`Ctrl+V` cola** — o filtro impede o `^V` e a colagem vem do evento `paste` do navegador; se o foco estiver fora do terminal, o texto é entregue ao PTY (`term.paste` → `__pesquisaiSendToPTY`).
- **`Ctrl+Shift+V`** mantém o caminho nativo (texto puro). Campos de formulário da UI ficam intocados (`isFormField`), exceto o `xterm-helper-textarea`.
- Duas camadas independentes: `attachCustomKeyEventHandler` (API pública do xterm, impede os bytes de controle) + listeners em fase de **captura** no `document`; rede de segurança da Clipboard API em 400 ms, sem duplicar (`lastPasteAt`).

#### 🧠 Cache do HTML do ttyd (por que "não funcionava" mesmo com o código novo)
- `_prepare_ttyd_touch_index()` reaproveitava o `ttyd_touch_<uid>.html` só checando **existência**. O arquivo em disco (gerado antes do ajuste) continuou sendo servido pelo `--index` — o terminal rodava o JavaScript **velho**, sem o teclado.
- Agora o HTML injetado carrega a marca `<!-- ufvai-inject:<sha256[:16] do script> -->` e `_ttyd_index_is_current()` regenera o arquivo quando a marca não corresponde ao script atual. Como o ttyd relê o `--index` a cada requisição, **um F5 já aplica** — sem reiniciar o terminal.

#### 🖱️ Ajuste 2 (29/10, **sem bump**) — "Nada selecionado" com a TUI no controle do mouse
- **Sintoma (relatado pelo autor):** `Ctrl+V` passou a colar, mas `Ctrl+C` respondia *"Nada selecionado · Ctrl+Shift+C envia Ctrl+C"* — a área de transferência ficava vazia.
- **Causa:** a TUI do opencode liga *mouse reporting* (DECSET `1000`/`1002`/`1006`). Nesse estado o xterm.js **desativa o serviço de seleção**: arrastar não seleciona nada e `term.getSelection()` devolve `''`. Não é configuração da TUI a ser desligada — é o comportamento padrão de terminal com o mouse capturado (a seleção nativa só acontece com **Shift+arraste**).
- **Correções:**
  - **Memória da última seleção** (`onSelectionChange` + `lastSel`/`lastSelAt`): a TUI redesenha a cada token e o xterm invalida a seleção; sem isso, `Ctrl+C` logo após o arrasto voltava a dizer "nada selecionado".
  - **Arrasto vira seleção** (`installDragSelect`): em arrasto > 6 px com mouse capturado, sintetiza `mouseup` + `mousedown{shiftKey:true}` para o xterm entrar em modo seleção; a seleção é copiada no `mouseup` ("copiar ao selecionar"). Clique, duplo-clique e roda do mouse seguem para a TUI; a barra de rolagem (últimas ~2,5 colunas) é preservada.
  - **Dica correta por contexto:** *"Nada selecionado · arraste para selecionar (ou Shift+arraste)"* quando a captura está ativa; *"Nada selecionado · Ctrl+Shift+C envia Ctrl+C"* quando não está.
  - **Kill switch (tempo de execução):** `window.__ufvaiDragSelect = false` no console desliga o arrasto-vira-seleção **na hora** (guarda nos três handlers de mouse), mantendo só o caminho nativo (Shift+arraste), sem tocar no resto.
- **Status da verificação (29/10, após instalar as libs do Chromium):** `tests/test_ttyd_clipboard.py` **33/33** · `tests/js/test_v078_clipboard.js` **8/8** · `scripts/diag_clipboard_ttyd.py` **9/9 PASS** (Chromium + ttyd 1.7.4 reais) · teste de arrasto em navegador real **19/19** (ttyd de sandbox com *mouse reporting* ligado): seleção durante o arrasto, `Ctrl+C` copia, nenhum `^C`, `Ctrl+Shift+C` envia, arrasto simples seleciona e copia, clique/duplo-clique e roda seguem para a TUI, `Ctrl+V` cola sem `^V`, kill switch funciona.

#### 🧪 Testes
- `tests/test_ttyd_clipboard.py` — **33 testes** de contrato (script autocontido, listeners em captura, `attachCustomKeyEventHandler`, `Ctrl+Shift+C`, rede de segurança do paste, ordem touch→teclado, campos de formulário, fingerprint do cache, versão **0.7.8** inalterada, memória da última seleção, arrasto→Shift, eventos sintéticos ignorados como gesto, cópia ao selecionar, barra de rolagem preservada, kill switch).
- `scripts/diag_selecao_tui.py` — diagnóstico dedicado ao caminho de seleção (mouse capturado × Shift+arraste × `Ctrl+C`).
- `tests/js/test_v078_clipboard.js` — **8/8** de comportamento (DOM simulado, roda o script real): `Ctrl+C` copia e não envia `^C`; `Ctrl+Shift+C` envia `\x03`; `paste` fora do terminal entrega 1×; formulário intocado.
- `scripts/diag_clipboard_ttyd.py` — **9/9** com **Chromium + ttyd 1.7.4 reais** (Playwright): digitação chega ao PTY, `Ctrl+V` cola 1× sem `^V`, Clipboard API como rede de segurança, `Ctrl+C` copia e **não** gera `GOT_SIGINT`, `Ctrl+Shift+C` gera. O ttyd de teste sobe em porta livre e é encerrado no fim — o terminal real não é tocado.
- Regressão: `test_security` · `test_launch_app` · `test_run_fast` · `test_version_sync` (ver relatório da sessão).

---

## [0.7.7] — 2026-10-27 — 🔒 Drive Guard: "My Drive" só dentro de PesquisAI

### 📂 O app inicia na pasta PesquisAI (não em `/root`)
- O serviço do motor e os terminais agora sobem com o diretório de trabalho apontando para a pasta PesquisAI (offline: `~/PesquisAI`), e as sessões novas nascem presas a esse diretório.
- **Efeito:** sessões, terminal e ferramentas do agente abrem em `/content/drive/My Drive/PesquisAI` (offline: `~/PesquisAI`).

### 🌐 Saudação inicial no idioma do cliente
- A saudação passa a respeitar o idioma do navegador, não o locale do servidor.
- O idioma é resolvido na ordem: variável de ambiente → preferências salvas no Drive → idioma do navegador → sistema.
- O fallback passou de 8 s para 60 s e usa português (`pt_BR`) quando não há confirmação — nunca o locale do servidor.

### 🔌 ttyd sem quedas
- **Keepalive:** a cada 20 s o terminal envia um sinal de vida (RESIZE) que mantém o WebSocket ativo no proxy do Colab.
- **Auto-reconnect domado:** no máximo 1 reconexão a cada 5 s, reload só como último recurso (máx. 2× por aba/10 min).
- **Efeito imediato:** basta recarregar a página para o keepalive entrar em vigor.

### 🔒 O agente não acessa mais "My Drive" fora da pasta PesquisAI
- Um plugin (Drive Guard) bloqueia o acesso do agente a qualquer arquivo de `/content/drive` fora de `/content/drive/My Drive/PesquisAI/**`.
- A decisão não depende de aprovação — `--auto` não a contorna.
- **Três camadas:** regras declarativas em `opencode.json` (deny da raiz + allow de PesquisAI), hook de permissão e hook de pré-execução de ferramenta.
- **Preservação:** material criptográfico da memória continua protegido; `*.env` continua exigindo aprovação.
- **O que não muda:** o servidor Python da interface continua acessando o Drive normalmente — o guard governa apenas as ferramentas do agente.
- **Auditoria:** cada bloqueio é registrado em `~/.local/state/ufvai/drive-guard.log`.
- **Fail-open:** se o plugin falhar, o app inicia normalmente e avisa no log.

### ⚙️ Instalação automática
- O Drive Guard é instalado no boot e em todo (re)spawn do terminal (troca de idioma, troca de chave, `/api/run_terminal`, import de sessão).

### 🧪 Testes
- `tests/js/test_drive_guard.mjs` 35/35 · `tests/test_drive_guard.py` 20/20 · `tests/test_v077_start_dir.py` 7/7.

---

## [0.7.6] — 2026-10-24 — 🏷️ Rebrand do agente: opencode → ufvai

- **Documentos do agente** (`AGENTS.md`, `agents/AGENTS.*.md`, novo `agents/UFVAI.md`): todas as ocorrências de `opencode`/`OpenCode` passaram a `ufvai`/`UFVAI` — caminhos de config (`~/.config/ufvai/...`), arquivo `ufvai.json`, dados em `~/.local/share/ufvai/` e comando `ufvai auth export`.
- **Aliasing do motor** (`scripts/ufvai-alias.sh`, idempotente e fail-open): cria symlinks (`~/.config/ufvai` → `~/.config/opencode`, `ufvai.json` → `opencode.json`, `~/.local/share/ufvai` → `~/.local/share/opencode`) e o comando **`ufvai`**.
- **O que NÃO mudou:** código-fonte, instaladores, binários e banco SQLite continuam com o nome original — renomear em execução quebraria o runtime.
- **Verificações:** `grep -ric opencode` → 0 nos 7 documentos de identidade · aliases aplicados no Colab e `ufvai --version` responde `opencode v2.1.4`.

---

## [0.7.5] — 2026-10-23 — 🪟 Telas de abertura e retomada uma vez por sessão

- A tela de e-mail/"Bem-vindo" e a pergunta de retomada apareciam várias vezes na mesma sessão (o `sessionStorage` se perdia nas recargas do proxy do Colab).
- **Correção em três camadas:** `sessionStorage` + `localStorage` (validade de 12 h) + cookie de sessão, gravada antes de a tela aparecer.
- Recargas internas não consomem a marca; só o botão **↻** limpa a marca da retomada. Nova aba/sessão → mostra de novo.
- A retomada espera a tela de Termos/"Bem-vindo" fechar antes de abrir.
- Resposta do HTML com `Cache-Control: no-store` (evita JavaScript antigo em cache).

---

## [0.7.4] — 2026-10-23 — 💾 Autosave de todas as conversas · 🔓 Free tier na restauração

### 💾 Autosave: com várias sessões, todas são salvas
- Os slots `autosave_1..3` continuam sendo a rotação da interação atual.
- **Cada conversa viva** com conteúdo novo ganha o seu próprio arquivo em `backups/autosave/sessions/<id>.json`, que aparece no modal **🔄 Restaurar**.
- Só é exportada a conversa que mudou (comparação de `time.updated`); limite de 6 conversas por ciclo e 6 horas de inatividade.

### 🎚️ Alcance do autosave: por padrão, só a sessão ativa
- O padrão grava só a sessão ativa — e só quando ela muda.
- O botão **"Todas as conversas"** liga o modo completo (um arquivo por sessão que mudou).

### 🔓 Free tier do OpenCode Zen na restauração
- Sessões restauradas com modelo gratuito do Zen davam erro 403 ("free tier can only be used from within OpenCode").
- **Causa:** a retomada gerava ids de sessão no formato legado; o gateway do Zen recusa ids fora do formato nativo.
- **Correção:** o id da sessão restaurada agora nasce no formato nativo do motor. A sessão também é ajustada ao contexto do modelo (compactação ou reimportação aparada).

### 🪟 Telas de abertura uma vez por entrada
- Termos e "Bem-vindo de volta" abrem uma vez por carga; o "Bem-vindo" uma vez por aba.

---

## [0.7.3] — 2026-10-22 — 📦 Pacote instalado no ambiente · ⏱️ Autosave a cada 1 minuto · 🗂️ Fallback das 3 últimas interações

- **Intervalo do autosave:** 3 minutos → **1 minuto**.
- **Fallback:** o autosave não destrói mais o backup da sessão anterior. As 3 últimas interações são preservadas nos slots `autosave_4..6` e entram na lista do "Restaurar".
- **A sessão certa:** o autosave escolhe a sessão enviada → a do terminal → a mais recentemente atualizada (antes usava `sessions[0]`, que nem sempre era a conversa do usuário).
- **Retomada na entrada:** a pergunta volta a ser feita uma vez por aba, sem loop.
- **Pacote `pesquisai` instalado no ambiente:** antes a célula de boot só adicionava o repo ao `sys.path`; o terminal (outro processo, outro CWD) não encontrava o pacote e a memória não salvava. Agora o boot instala o pacote (`pip install -e`) e verifica o import a partir de um diretório neutro. A distribuição passou a se chamar `pesquisai` (antes `pesquisai-additions`) e o instalador offline não esconde mais erros.
- **Restauração com modelos gratuitos:** correção do id da sessão no formato nativo (ver 0.7.4).

---

## [0.7.2] — 2026-10-22 — 🔄 Retomada uma única vez por aba · 📅 Calendário do "Restaurar" corrigido

- **Laço da retomada:** ao clicar em "Continuar de onde parei", o terminal recarregava e a tela de confirmação voltava. Agora a pergunta é oferecida uma vez por aba (`sessionStorage`); o botão **↻** reoferece e o menu **🔄 Restaurar** segue sempre disponível.
- **Calendário do "Restaurar":** chips clicáveis dos meses que têm backup (+ contagem), contagem por dia, itens sem data no grupo "sem data", estado vazio acionável e botão **"Mais recente"**.

---

## [0.7.1] — 2026-10-22 — 🔧 Retomada corrigida · 💾 autosave sem duplicata · 🗑 apagar backup

- **Retomada na entrada não restaurava:** `list_autosaves()` devolvia o nome sem o prefixo `autosave/` → o `/api/restore` recusava com 400. Corrigido (aceita com ou sem prefixo; validação de caminho mantida).
- **Autosave sem duplicata:** `content_digest()` impede gravar cópia idêntica; a interface avisa "sem novidades".
- **Botão 🗑 de apagar backup:** `POST /api/backup/delete` com confirmação obrigatória + botão por item no menu "Restaurar" · i18n em 5 idiomas.
- **Fallback na retomada:** se o autosave mais recente falhar, tenta o anterior (até 3).

---

## [0.7.0] — 2026-10-21 — 🗓️ "Restaurar" só backups com calendário · ⏱️ autosave a cada 3 min · 🏷️ marca UFVAI

- **Menu "Restaurar" reconstruído:** `GET /api/backups` devolve somente backups (com data/hora/tamanho/título/integridade); `POST /api/restore` valida estritamente e recusa arquivos que não são backup. Interface com calendário mensal, filtro por data, navegação de mês e lista agrupada por dia · i18n em 5 idiomas.
- **Autosave corrigido e ligado por padrão:** um `NameError` no branch `/api/autosave` matava toda gravação; a listagem estava no `do_POST` (404). Corrigido, com rotação invertida (slot 1 = mais recente).
- **Identidade e interface:** marca **UFVAI** na tela de nova sessão · 🇨🇳 Chinês também troca o terminal · Manual e Diretrizes no tema claro · "Idioma" fora do sanduíche no responsivo.

---

## [0.6.21] — 2026-10-13 — 🔧 Migração para o motor OpenCode V2 · 🍪 Aviso de cookies · 🫀 Keep-alive por célula

- **Motor OpenCode V2:** configuração em `~/.config/opencode/opencode.json` e `cli.json`; instalador V2 com fallback npm; `--auto` no lugar de `--yolo`; tema em um arquivo só (dark + light); agente `UFVAI` com `default_agent: "UFVAI"`; credenciais em SQLite com backup via `auth export` cifrado.
- **Aviso de cookies de terceiros do proxy do Colab:** teste em iframe; o aviso só aparece quando o bloqueio é detectado (nasce invisível). Idempotente e sem duplicar aviso.
- **Keep-alive como célula bloqueante:** roda na própria célula (o Colab decide ociosidade pela atividade do notebook); duas falhas seguidas disparam a recuperação; botão **SAIR** encerra pelo PID file.
- **Módulo novo `opencode_config.py`:** toda a manipulação de arquivos do motor num módulo só; arquivo do usuário que não pode ser interpretado nunca é sobrescrito.
- **Dockerfile:** instala o OpenCode V2 como usuário não-root; saída para build sem rede (`UFVAI_NO_OPENCODE_INSTALL=1`).
- **Correções encontradas pelos testes:** `merge_cli_theme` mutava o dicionário do chamador; file handle vazado em `_setup_theme_and_agent`.
- **Validação de campo:** ciclo `auth export` → cifragem → `auth import` executado contra a V2.0.28 com credencial de teste — funciona ponta a ponta. Pendente: validação com credencial real e retomada de sessão.

---

## [0.6.20] — 2026-10-01 — 🫀 Keep-alive + botão SAIR · 🌐 Rodapé com o site oficial · 📄 Planilha de contatos em 1 linha

- **`PesquisAI.ipynb` simplificado:** boot direto no kernel do Colab, keep-alive em subprocesso (log em `/tmp`), botão **SAIR** com confirmação obrigatória que encerra o keep-alive e desconecta o runtime.
- **Rodapé:** link **"🌐 Site"** para o site oficial; em telas <480px o texto "UFV · Viçosa, MG - Brasil" sai de cena para o link caber.
- **Planilha de contatos:** exatamente uma linha por ativação/retorno, gravada no clique do usuário. O primeiro aceite não grava mais linha `novo_contato`.
- **Descartada** a abordagem de supervisor desacoplado de 30/09 (travava em "Aguardando a interface ficar pronta…"); base é a v0.6.19 estável.

---

## [0.6.19] — 2026-09-29 — 📱 Menu mobile sem SVG + hamburger à direita

- Em ≤767px o hamburger aparecia colado no logo, à esquerda (o `.sep` absorvia o espaço antes do `margin-left: auto`). Corrigido: `#topbar .sep { display: none }` no breakpoint mobile → idioma + hamburguer vão para a borda direita. Desktop intacto.
- **Teste de regressão de cascata** (`tests/test_responsive_hamburger.py`): resolve a cascata CSS de verdade (especificidade + `!important` + ordem) para 10 larguras × 7 arquivos — 252/252 nos dois projetos.
- Docs em paridade (skills personalizadas) e rebuild do `.deb` 0.6.19-offline.

---

## [0.6.18] — 2026-09-19 — 🧩 Skills personalizadas do usuário

- Nova pasta persistente `backups/skills-personalizadas/` (criada automaticamente no boot, com README).
- **Carga a cada boot:** `setup_custom_skills()` copia cada subpasta válida (com `SKILL.md`) para `~/.agents/skills`; subpastas sem `SKILL.md` são ignoradas; falhas nunca interrompem o boot.
- O agente é instruído a gravar skills novas nessa pasta e informa que entram em vigor no próximo boot.

---

## [0.6.17] — 2026-09-01 — ⚡ Memória abre instantânea via menu

- **Causa:** cada request criava um `ObsidianMemory` novo (re-parse do cache BM25 de 3,8 MB + árvore iterada 2× + LinkIndex reconstruído). Qualquer mudança de arquivo invalidava o cache.
- **Fix backend:** singleton stale-while-revalidate — 1 instância em RAM compartilhada, rebuild em background após 30 s, warm-up no boot. O menu nunca bloqueia esperando o Drive.
- **Fix frontend:** cache do menu 5 s → 120 s com revalidação silenciosa + prefetch no `window load`.
- Endpoints e payload inalterados; apenas tempo de resposta (µs vs. segundos).

---

## [0.6.16] — 2026-09-01 — 🐛 Fix retorno: 1 linha por clique

- No retorno o e-mail era enviado 2–3 vezes (heartbeat automático + timeout + clique). Removidos os disparos automáticos; `POST /api/access` só no clique em "Continuar", com guard `_heartbeatSent` contra duplo clique — exatamente 1 linha por retorno.

---

## [0.6.15] — 2026-09-01 — 🐛 Prompt inicial respeita idioma detectado

- `_current_lang` iniciava fixo em `pt_BR`, então a detecção do sistema nunca era alcançada e o ttyd iniciava em português mesmo com sistema em inglês.
- **Fix:** `_ensure_lang_initialized()` (prioridade: preferência salva → env → sistema → persiste), chamado antes do primeiro `start_ttyd()`.
- **Frontend:** compara o idioma do backend com o do navegador e, se divergir, chama `setLang()` uma vez por sessão.

---

## [0.6.14] — 2026-09-01 — 🐛 Fix IP localhost + todo acesso logado

- **IP registrava 127.0.0.1:** o proxy do Colab não injeta headers de IP na conexão local. Agora o frontend captura o IP público via ipify e envia no body; o backend o prefere quando público.
- **Todo acesso gera linha na planilha:** o heartbeat `usuario_ativo` era disparado só no clique; agora também no carregamento da UI (com segunda tentativa após ipify resolver).

---

## [0.6.13] — 2026-09-01 — 🐛 IP real do cliente + heartbeat na revisita

- **IP:** `_get_client_ip()` percorre a cadeia `X-Forwarded-For` da direita para a esquerda saltando IPs privados, devolvendo o primeiro IP público; aceita também `X-Real-IP`, `CF-Connecting-IP`, `Forwarded` etc.
- **Revisita:** o e-mail ficava em `~/.config` (efêmero) e o heartbeat lia só dali → e-mail vazio → nada gravado. `_read_profile()` agora cai no backup persistente do Drive.

---

## [0.6.12] — 2026-09-01 — 📱 Fix preview responsivo

- O preview markdown não aparecia no mobile (altura 0 no layout `flex-direction: column`). Corrigido com `min-height`/`overflow` adequados; `onEditorInput()` agora atualiza o preview também na aba Preview, não só em Split.

---

## [0.6.11] — 2026-09-01 — 🐛 Hotfix memória: isoformat no cache BM25

- **Causa:** o cache BM25 reconstruía `NoteMetadata` com `created`/`updated` como string; ao exibir a árvore da memória, `updated.isoformat()` quebrava quando o cache estava ativo.
- **Fix:** `_parse_date` robusto (aceita ISO date, ISO datetime e formatos legados) + helper defensivo `_safe_isoformat()` no `launch_app.py`.
- Cache regenerado com `date` correto e validado (cache_hit ~0,2 s).

---

## [0.6.10] — 2026-09-01 — 🚀 Memória otimizada + nome+IP + responsiva mobile

- **Memória:** cache BM25 em disco (247 notas em ~0,2 s), paginação, debounce e busca BM25 server-side para `q≥3`; responsiva mobile (sidebar 100%/38vh, alvos ≥44px).
- **Tela de Termos:** campo Nome ao lado do e-mail (lado a lado no desktop, coluna no mobile), validação de nome e e-mail; re-consentimento forçado (TV 5→6).
- **Backend:** grava nome + IP no perfil e no backup do Drive; planilha com 8 colunas (`Timestamp | Email | Nome | Email SHA-256 | Ambiente | Versão | Flag | IP`), migração automática e `MAX_ROWS` 1000→5000.

---

## [0.6.9] — 2026-08-25 — 📜 Termos v2.1 · ✉️ e-mail de ativação · 📘 botão Manual

- **Termos v2.1 (re-consentimento):** telemetria ativa por padrão (opt-out, LGPD art. 7º IX); sem cookies (`analytics_storage:'denied'`); evento custom removido; e-mail de ativação obrigatório (400 se ausente, art. 7º V).
- **Perfil persistente:** `backups/ufvai_consentimento.json` no Drive; `GET /api/consent` inclui `profile` → pré-preenche e pula a tela se a versão já foi aceita.
- **Interface:** botão 📘 Manual ao lado do Dashboard de Saúde (nova rota `/api/manual`), ícones distintos, tela de Termos responsiva.
- **Correções:** DebugView (envia `debug_mode: 1`); logs fora do Drive no Colab (`/tmp/ufvai-logs/`).

---

## [0.6.8] — 2026-08-24 — 🧹 Painel único · reordenação LGPD · planilha de contatos

- **Painel único (Colab):** todo feedback visual vem só do painel de boot; prints verbosos suprimidos; offline mantém prints normais.
- **Reordenação LGPD:** opcionais (estatísticas + e-mail) antes do aceite obrigatório; `ufvai_terms_version=4`.
- **Planilha de contatos automática:** criação via Drive/Sheets API, Apps Script pronto, endpoint injetado no painel Admin; fallback manual documentado.

---

## [0.6.7] — 2026-08-23 — 🖼️ Tela de carregamento na marca · ✉️ canal de contato configurável

- **Barra de carregamento contínua no tema da logomarca (Colab):** painel off-white + wordmark UFV/AI, mensagens abaixo da barra (spinner dourado na etapa ativa, ✓ na concluída, ✕ em falhas sem abortar), percentual monotônico. Uma única instância via `get_boot_panel()` — fim de barras duplicadas.
- **Botão de lançamento no tema da marca:** logo real embutida em base64 + botão pílula dourada "ABRIR O UFVAI".
- **URL de contato no painel Telemetria (Admin):** campo opcional, grava em `~/.config/ufvai_telemetry.json`, aplica na hora; salvar é parcial (dá para salvar só o canal sem redigir GA4); URL exige `https://`.

---

## [0.6.6] — 2026-08-22 — 🖼️ Favicon UFVAI · ✉️ contato opt-in LGPD

- **Favicon na interface:** `<link rel="icon">` + PNG 64 fallback + apple-touch-icon; nova rota `/favicon.ico`; no Colab os favicons são injetados com o prefixo do proxy.
- **Contato opt-in:** campo opcional de e-mail na tela de Termos (LGPD art. 7º I), gravação local com SHA-256, GA4 nunca recebe o e-mail (só evento contador), endpoint próprio opcional (`UFVAI_CONTACT_ENDPOINT`), direitos do titular (eliminação por campo vazio ou `POST /api/contact/delete`).

---

## [0.6.5] — 2026-08-22 — 🔐 Terminal à prova de travamentos · 🚀 splash de carregamento

- **Kill cirúrgico por árvore:** o ttyd é líder do próprio grupo de processos e é morto com um único `killpg` — acaba o `pkill -f opencode` global, que matava qualquer processo com "opencode" na cmdline. Fallback `pkill -9 -x ttyd` (COMM exato).
- **`GET /api/ttyd_ready`:** o frontend faz polling antes de apontar o iframe — fim do `ERR_CONNECTION_REFUSED` visível no boot, na troca de idioma e na restauração.
- **Splash de boot** com logomarca, spinner, status em 3 estados, erro com indicação do log e botão Recarregar — i18n completo nos 5 idiomas.

---

## [0.6.4] — 2026-08-22 — 🪪 Marca UFVAI completa · 🎨 Temas UFVAI · 🖼️ Logo oficial · 📜 Termos v2

- **Marca:** AGENTS.md e variantes agora se apresentam como **UFVAI** (frontmatter, identidade, capacidades, rodapé); IDs técnicos preservados.
- **Terminal:** temas regenerados na paleta UFVAI (azul-noite + dourado; claro com papel quente); azul antigo eliminado.
- **Abertura:** removido o onboarding antigo (`welcome-hint`) que empilhava com os Termos — a tela de Termos é a única abertura. Logo oficial via nova rota `/assets/*` (whitelist estrita + traversal guard).
- **Termos v2.0:** integridade acadêmica (Portaria CNPq nº 2.664/2026, POSIC/UFV), LGPD completa (arts. 7º, 18, 33–36), foro Viçosa/MG; re-consentimento forçado.
- **Telemetria:** gtag.js client-side com consent-gate (só após aceite) + painel 📊 Telemetria (Admin) na UI com ID/Secret salvos localmente.

---

## [0.6.3] — 2026-08-22 — 🔌 Servidor persistente offline · 🎨 Ícone UFVAI no dock

- **Bug crítico (offline):** o wrapper HTTP roda em thread daemon e o processo encerrava ao fim de `run()`, matando o servidor segundos depois. `_offline_keep_alive()` mantém o processo ativo fora do Colab (Ctrl+C ou `kill $(cat ~/PesquisAI/pesquisai.pid)`).
- **Servidor dual-stack:** além do listener IPv4, sobe um loopback IPv6 (`::1`) quando local — Chromium/Firefox preferem `::1` ao resolver "localhost".
- **Ícone no dock:** janela com `--class="UFVAI"` casa com `ufvai-app.desktop` e PNGs nos temas hicolor.

---

## [0.6.2] — 2026-08-22 — ⌨️ Terminal gravável · 🖥️ Launcher app-mode · 📊 Telemetria debug

- **Bug crítico:** o v0.6.0 perdeu a flag `--writable` do ttyd e o terminal ficava read-only. Restaurada.
- **Offline (.deb):** launcher restaurado (espera ativa da porta 8001, abertura como app separado via Chrome `--app` → Chromium → Firefox → `xdg-open`).
- **Telemetria:** `UFVAI_TELEMETRY_DEBUG=1` envia eventos para o DebugView do GA4; o launcher carrega `~/PesquisAI/config/ufvai.env` antes de iniciar.

---

## [0.6.1] — 2026-08-22 — 🌐 Idioma do sistema · 🔁 troca de idioma robusta · 🌍 auto-open offline

- **Troca de idioma:** o frontend recarregava antes de o ttyd reiniciar; `setLang()` virou `async` (aguarda o POST com timeout de 15 s) e o backend só responde com a porta do terminal já aceitando conexões.
- **Idioma do sistema detectado na 1ª execução** (`$LANGUAGE` → `$LC_ALL` → `$LC_MESSAGES` → `$LANG` → `locale`), persistido em `~/.config/pesquisai_lang`.
- **Offline (.deb):** o navegador abre sozinho após a porta da UI responder (desabilitar com `UFVAI_NO_OPEN=1`).

---

## [0.6.0] — 2026-08-21 — 🏷️ UFVAI · 🔐 hardening · 📊 telemetria opt-in · 🇨🇳 zh_CN · 📜 Termos

- **Marca:** rebrand visual PesquisAI → UFVAI (paleta dourado + azul profundo, wordmark UFV+AI); identificadores técnicos preservados.
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

## [0.5.1.8] — 2026-07-10 — 🐛 3 bugfixes + nova skill Memorial UFV

- **Provider buttons:** `JSON.stringify` inline em `onclick` gerava SyntaxError; trocado por `data-provider` + `this.dataset.provider`.
- **Restauração de sessão:** `opencode session restore` não atualizava o ttyd; trocado por `opencode -s <id>` com `no_fallback: true` + reload da página.
- **Confirmação antes de restaurar backup:** `doRestore()` agora pede confirmação.
- **Nova skill `memorial-ufv`:** gera o Memorial RSC-PCCTAE a partir do PDF do Relatório Detalhado (saída `.md` e `.docx`).
- **Provider flow:** nova tela inicial com chaves salvas (editar/excluir), botão Voltar, botão ↻ Atualizar no modal de sessões.

---

## [0.5.1.5] — 2026-07-01 — 🧠 Editor de Memória Obsidian

- Modal split view (lista de notas + editor com abas Edit/Preview/Split).
- **4 endpoints novos:** ler nota, árvore por subdiretório, busca BM25 e lista de tags; POST com ações save/create/delete (delete move para `.trash/`).
- Preview com `marked.js`, destaque de `[[wikilinks]]` e `#tags`; indicador de edição não salva; 20 chaves i18n em 4 idiomas.
- **Hotfix:** botões do editor não funcionavam (SyntaxError JS) — corrigido.

---

## [0.5.1.3] — 2026-06-30 — 🔌 Conectores de provedor de IA

- `confirmProvider()` crashava antes de salvar a API key; captura local dos dados antes de fechar o modal, verificação de `r.ok`/`d.ok` no fetch e fechamento só após sucesso.

---

## [0.5.1.2] — 2026-06-30 — 🧠 Botão Memória Obsidian no topbar

- Overlay com status, stats, notas recentes e daily notes; endpoint `GET /api/obsidian`.

---

## [0.5.1] — 2026-06-29 — 🤖 Obsidian Autopilot

- **O agente salva sozinho:** `autopilot.py` com `recall`, `save`, `save_finding`, `start_session`/`end_session`, `log_skill`/`log_file` e `auto_init()` (chamado no boot).
- Vault criado automaticamente em `<DRIVE>/PesquisAI/vault/`; daily note e MOC raiz criados no boot; tudo é no-op se o vault não estiver disponível.
- Vault sempre no Google Drive (validação obrigatória).

---

## [0.5.0] — 2026-06-28 — 🧠 Obsidian Second Brain (memória de longo prazo)

- Módulo `pesquisai.obsidian` (8 arquivos, ~1.500 linhas) + skill `obsidian-memory` + 10 templates.
- Memória persistente entre sessões via vault no Drive; busca BM25 offline, backlinks, wikilinks e tags; taxonomia `pesquisai/*` (
