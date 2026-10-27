# Changelog — PesquisAI


## [0.7.7] — 2026-10-27 — 🔒 Drive Guard: **“My Drive” só dentro de PesquisAI**

### 📂 O app inicia na pasta PesquisAI (não em `/root`)
- **Relato do autor (27/10/2026):** *“a versão 0.7.7 quando inicia está no root,
  deve iniciar na pasta PesquisAI no Drive.”*
- **Causa [DADO CONFIRMADO no runtime]:** o motor V2 sobe um
  `opencode serve --service` desanexado que **herda o cwd de quem o inicia**. No
  Colab, o kernel roda em `/root`; o serviço nascia ali e as sessões criadas sem
  `location` explícita adotavam `/root` como diretório de projeto — o agente
  executava ferramentas fora do Drive mesmo com o `cd` no comando do ttyd.
- **Correção (três camadas):**
  1. `ensure_service_project_dir()` (`run_fast.py`) roda no boot, depois das
     dependências: se o serviço está em outro cwd, faz `service stop` e sobe
     `opencode serve --service` **com `cwd` = pasta PesquisAI** (fast-path quando
     já está correto; best-effort, nunca derruba o boot).
  2. `_workspace_dir()` (`launch_app.py`) resolve o diretório do projeto sem
     nunca cair na raiz: `DRIVE_PATH` → `~/PesquisAI` → cria `DRIVE_PATH`. Todos
     os spawns de terminal (`start_ttyd`, auto-cura, troca de idioma,
     `/api/run_terminal`, importação de sessão) usam esse valor no `cd` **e** no
     `cwd` do `Popen` do ttyd.
  3. `preflight_ufvai_session_info()` cria a sessão com
     `location: {"directory": <projeto>}` explícito — a sessão nasce presa ao
     Drive mesmo se o processo estiver em outro diretório.
- **Efeito:** sessões novas, o terminal e as ferramentas do agente passam a
  abrir em `/content/drive/My Drive/PesquisAI` (offline: `~/PesquisAI`).
- **Testes:** `tests/test_v077_start_dir.py` — 5/5 (preferência do Drive,
  fallback offline, `cwd` do ttyd, `location` da sessão, fast-path do serviço).

### 🌐 Saudação inicial no idioma do CLIENTE (nunca no locale do servidor)
- **Relato do autor (27/10/2026):** *“ainda está com a mensagem em inglês
  `Hello! (tip: ...)` mesmo com a interface detectando corretamente o
  português.”*
- **Causa [DADO CONFIRMADO]:** quando não havia preferência no Drive, a
  saudação ficava pendente e um **fallback de 8 s** a semeava com
  `_current_lang` — que, no Colab, vinha do locale do **servidor** (`en_US`).
  A interface abria depois (em português) e o `/api/lang` já não tinha o que
  consumir: a mensagem em inglês permanecia no histórico.
- **Correção:**
  1. `_build_ttyd_cmd()` resolve o idioma na ordem **env → prefs do Drive →
     `_current_lang` → sistema** (antes `_current_lang` vencia as prefs).
  2. Só semeia a saudação imediatamente quando o idioma é **confirmado**
     (env ou preferência salva). Sem confirmação, fica pendente para o
     `/api/lang` do navegador.
  3. O fallback passou de **8 s → 60 s** e usa **prefs ou `pt_BR`** — nunca
     o locale do servidor.
  4. Caminho `--prompt` (sem sessão pré-criada) usa `pt_BR` quando o idioma
     não está confirmado.
- **Testes:** +2 em `tests/test_v077_start_dir.py` (prefs vencem
  `_current_lang`; fallback não usa locale do servidor) — **7/7**.

### 🔌 ttyd sem quedas: keepalive de aplicação e fim do laço de reload
- **Relato do autor (27/10/2026):** *“o terminal ttyd está desconectando
  constantemente”*.
- **Evidência [DADO CONFIRMADO]:** `ttyd.log` mostrava `WS closed` a cada
  30–60 s, sempre seguido de `/token` + `/ws` novos — a página recarregava em
  laço. O reload vinha do auto-reconnect injetado em v0.7.5, cujo contador
  reiniciava a cada recarga (`_reloads<3`), e o proxy do Colab derruba
  WebSocket **sem tráfego de aplicação** (o ping do ttyd é controle de
  protocolo e não conta).
- **Correção (no HTML injetado no ttyd, `_get_touch_handler_script`):**
  1. **Keepalive**: a cada **20 s** envia um `RESIZE` do próprio protocolo do
     ttyd (`'1' + JSON`) com o tamanho atual — idempotente, invisível na tela,
     mantém o socket ativo.
  2. **Auto-reconnect domado**: Enter no máximo 1×/5 s e só após 3 s de socket
     fechado; reload só como último recurso, no máximo **2× por aba/10 min**
     (`sessionStorage`) e apenas se o terminal exibir “Reconnect/Connection
     closed”.
- **Efeito imediato:** o ttyd serve o `index.html` do disco a cada request —
  basta **recarregar a página** para o keepalive entrar em vigor (sem
  reiniciar o app).
- **Teste:** `test_touch_script_tem_keepalive_e_sem_laco_de_reload` — 8/8.

### 🔒 O agente não acessa mais “My Drive” fora da pasta PesquisAI
- **Regra do autor:** *“não deixe acessar a pasta My Drive exceto a subpasta PesquisAI e
  todas as suas subpastas — mesmo estando em auto.”*
- **Antes:** o agente rodava com `--auto` (auto-aprovação) e podia ler, listar e gravar
  qualquer arquivo de `/content/drive/My Drive` — inclusive os documentos pessoais do
  usuário que não fazem parte da memória.
- **Agora:** um plugin do servidor UFVAI V2 (`pesquisai/plugins/drive_guard/`) fecha
  `/content/drive` e libera **somente** `/content/drive/My Drive/PesquisAI/**`. A decisão
  **não depende de aprovação**, então `--auto` não a contorna.
- **Três camadas independentes:**
  1. **Regras declarativas** em `opencode.json` — `permissions` com `deny` da raiz vigiada
     seguido de `allow` de PesquisAI para `external_directory`, `read` e `edit`. No motor,
     `deny` é **final**: nenhuma flag de auto-aprovação a transforma em `allow`.
  2. **Hook `permission.evaluate`** — qualquer decisão que sobrevenha para `read`, `edit`,
     `external_directory`, `shell`, `glob` ou `grep` apontando para fora de PesquisAI é
     reescrita para `deny`.
  3. **Hook `tool.execute.before`** — inspeciona a entrada da ferramenta (`path`, `file`,
     `pattern`, `command`, `cwd`, inclusive aninhada) e lança erro **antes** de tocar no disco.
- **Resolução de caminho:** `realpath` do ancestral mais próximo (resolve symlinks e
  alvos que ainda não existem), `..`, `file://`, `~`, `$HOME`, aspas e escapes. O alias
  `MyDrive` do Colab (mesmo diretório de `My Drive`, mesmo inode) é normalizado na
  comparação. Em comando de shell, além dos tokens, procura caminhos absolutos do Drive em
  qualquer posição — pega `python3 -c "open('/content/drive/My Drive/x')"`. Referência
  ofuscada (variável montada em tempo de execução) cai em **falha fechada**.
- **Preservação:** o material criptográfico de “Minha memória”
  (`*keys_store.json`, `*keys_encryption_key.bin`) continua com `deny`; `*.env` continua
  exigindo aprovação. Arquivos do usuário relacionados ao agente não são tocados.
- **O que NÃO muda:** o servidor Python da interface (memória, backups, autosave) continua
  acessando o Drive normalmente — o guard governa **as ferramentas do agente**.
- **Auditoria:** cada bloqueio é registrado em `~/.local/state/ufvai/drive-guard.log`
  (ISO-8601, uma linha por evento).
- **Fail-open no boot:** se a cópia do plugin falhar, o UFVAI inicia normalmente e avisa no
  log; um `opencode.json` ilegível **nunca** é sobrescrito (as regras já gravadas
  permanecem).

### ⚙️ Instalação automática
- `ensure_drive_guard()` é chamado por `ensure_ufvai_agent()` — portanto roda no boot e em
  **todo** (re)spawn do terminal (troca de idioma, troca de chave, `/api/run_terminal`,
  import de sessão). O plugin vai para `<config>/plugins/ufvai-drive-guard/` e o caminho
  absoluto é registrado em `plugins`.

### 🧪 Testes
- `tests/js/test_drive_guard.mjs` (**novo**) 35/35 — caminhos, symlink real, comandos de
  shell, entradas de ferramenta, hook de permissão e o contrato do `setup()` (um evento
  que chega como `allow` — o que a auto-aprovação faz — é reescrito para `deny`).
- `tests/test_drive_guard.py` (**novo**) 20/20 — ordem `deny` → `allow`, idempotência do
  merge, preservação de regras do usuário, cópia do plugin e config ilegível.

## [0.7.6] — 2026-10-24 — 🏷️ Rebrand do agente: **opencode → ufvai** (identidade completa, estilo Flint)

### 🎯 Pedido do autor
- *"faça uma nova versão trocando o 'opencode' por 'ufvai' como o Flint fez customizando o opencode"*
  — o Flint rebrandizou o motor de verdade (binário `flint`, config em `~/.config/flint/`).
  Aqui a troca é de **IDENTIDADE** (documentos do agente + nome de comando), com o
  runtime físico preservado para não quebrar nada em execução.

### 🏷️ O que virou "ufvai"
- **Documentos do agente** (`AGENTS.md`, `agents/AGENTS.{pt,en,es,fr,zh}.md` e o **novo**
  `agents/UFVAI.md` — o arquivo que era instalado como agente padrão): todas as ocorrências
  de `opencode`/`OpenCode` passaram a `ufvai`/`UFVAI` — caminhos de config
  (`~/.config/ufvai/...`), arquivo `ufvai.json`, dados em `~/.local/share/ufvai/` e comando
  `ufvai auth export`. §0.1 rebatizada de **"Motor UFVAI V2"**; versão do agente → **v0.7.6**.
  Frases que ficariam redundantes foram reescritas ("O UFVAI opera sobre o **motor UFVAI 2.x**").
- **Aliasing do motor** (novo `scripts/ufvai-alias.sh`, idempotente e fail-open): cria
  `~/.config/ufvai` → `~/.config/opencode` (symlink), `ufvai.json` → `opencode.json`,
  `~/.local/share/ufvai` → `~/.local/share/opencode` e o comando **`ufvai`** (wrapper POSIX
  com `OPENCODE_CONFIG_DIR`/`OPENCODE_CONFIG`). O motor físico continua sendo o mesmo —
  nada é renomeado em execução (banco SQLite e crédenciais intactos).

### 🧱 O que NÃO mudou (de propósito)
- **Código-fonte** (`pesquisai/opencode_*.py`), `install-offline.sh`, `Dockerfile` e
  binários continuam referenciando o motor real — renomear módulos/imports quebraria o
  runtime sem ganho de marca.
- **CHANGELOG/histórico** e citações funcionais do gateway (`OpenCode Zen`,
  erro `OpenCode's free tier...`) permanecem intactos — são registros factuais.
- **Banco de dados:** o SQLite continua com o nome original (renomear com o motor em
  execução corromperia o WAL); os docs referenciam o **diretório** `~/.local/share/ufvai/`,
  que resolve para o mesmo banco via symlink.

### 🧪 Verificações
- `grep -ric opencode` → **0** nos 7 documentos de identidade ·
  `bash -n scripts/ufvai-alias.sh` OK · `py_compile` de `__version__.py` OK ·
  aliases aplicados no ambiente Colab e `ufvai --version` responde `opencode v2.1.4`.

## [0.7.5] — 2026-10-23 — 🪟 Telas de abertura e retomada **UMA VEZ POR SESSÃO**

### 🪟 A tela de e-mail/"Bem-vindo" e a pergunta de retomada apareciam várias vezes
- **Relato do autor:** *"a tela de email/boas vindas está aparecendo inúmeras vezes na mesma
  sessão. Ela deve aparecer somente uma vez em cada sessão. A opção por restaurar sessão
  também deve aparecer somente uma vez."*
- **Causa:** a marca de "já mostrei" vivia **só no `sessionStorage`** — e o UFVAI roda no
  proxy/iframe do Colab, onde o `sessionStorage` pode ser particionado e o cookie de
  terceiros bloqueado. A abertura faz **2–3 recargas** (idioma → terminal → restore), então
  a marca se perdia e a tela voltava. No caso da retomada, o estado `"restored"` era
  **consumido a cada load**: a recarga seguinte voltava a perguntar.
- **Correção — marca em TRÊS camadas:** `sessionStorage` + `localStorage` (validade de 12 h)
  + cookie de sessão, gravada **ANTES** de a tela aparecer. Recargas internas não a
  consomem; só o botão **↻** limpa a marca da retomada. Nova aba/sessão → mostra de novo.
- **Sequenciamento:** a retomada espera a tela de Termos/"Bem-vindo" fechar antes de abrir
  (nunca duas telas de abertura ao mesmo tempo).
- **Cache:** a resposta do HTML agora leva `Cache-Control: no-store` — o navegador não
  reutiliza o JavaScript antigo depois de uma correção.

### 🧪 Testes
- `tests/js/test_v075_opening_once.js` (**novo**) 26/26 — mecânica das 3 camadas, expiração
  de 12 h, limpeza pelo ↻ e contrato das telas.
- `tests/js/test_v072_resume_once.js` 43/43 · `tests/js/test_v073_autosave_policy.js` 21/21
  — atualizados para o contrato "uma vez por sessão".
- `tests/js/test_autosave_ui.js` 27/27 · `tests/js/test_restore_calendar.js` 47/47 ·
  `tests/js/test_v074_autosave_scope.js` 20/20 · **Python 118/118** → **302 verdes**.

## [0.7.4] — 2026-10-23 — 💾 Autosave de **todas** as conversas · 🔓 Free tier do OpenCode Zen na restauração · 🪟 Telas de abertura uma vez por entrada

### 💾 Autosave: com várias sessões, **todas** são salvas
- **Pedido do autor:** *"quando tem várias sessões o autosave salva somente uma. Queria que
  salvasse todas ou a que está ativa."*
- **Antes:** o `POST /api/autosave` exportava **uma** sessão — a do terminal (`opencode -s <id>`)
  — para os slots rotativos `autosave_1..3`. As outras conversas abertas (o TUI tem abas) ficavam
  **sem backup**.
- **Agora:**
  1. os slots `autosave_1..3` (e o histórico `autosave_4..6`) continuam sendo a **rotação da
     interação atual** — nenhuma mudança no que já funcionava;
  2. **cada conversa viva** que tenha conteúdo novo recebe o seu **próprio arquivo** em
     `backups/autosave/sessions/<id>.json`;
  3. esses arquivos entram na lista do modal **🔄 Restaurar** (`GET /api/backups`) e podem ser
     restaurados (`POST /api/restore` com `autosave/sessions/<id>.json`).
- **Custo controlado:** só é exportada a conversa que **mudou** (o `time.updated` da sessão é
  comparado com a data do arquivo salvo); limite de **6 conversas por ciclo** e de **6 horas** de
  inatividade; a conversa de outro projeto (ex.: `/root`) fica de fora — o projeto é deduzido
  das próprias conversas (`infer_project_dir()`), não do CWD do processo.
- **Arquivos:** `session_restore.session_autosave_dir/path()` · `write_session_autosave()` ·
  `list_session_autosaves()` · `save_all_sessions()` · `infer_project_dir()`.
- **Testes:** `tests/test_autosave_multi_session.py` (**novo**) **18/18** (nome seguro sem
  traversal · grava e não reescreve conteúdo idêntico · listagem no formato aceito pelo restore ·
  dedução do projeto ignorando as sessões de preflight · salva todas · pula as que não mudaram ·
  respeita o limite por ciclo · o restore aceita `autosave/sessions/<id>.json` e barra traversal).

### 🎚️ O alcance do autosave: **por padrão, só a sessão ativa**
- **Pedido do autor:** *"tem como alterar, só salvar a sessão ativa com mudança?"*
- **Padrão (v0.7.4):** o autosave grava **só a sessão ativa** — e **só quando ela muda**
  (o `content_digest` impede a reescrita de conteúdo idêntico; a interface avisa
  *"Sem novidades — o autosave mais recente já é o atual"*).
- **Opção:** o botão **"Todas as conversas"** no rodapé (ao lado do liga/desliga do autosave)
  liga o modo completo — **um arquivo por sessão** em `backups/autosave/sessions/<id>.json`,
  com as conversas que **mudaram** (as que não mudaram são puladas, sem escrita no Drive).
- A preferência fica no `localStorage` (`ufvai_autosave_all_sessions`) e é enviada no
  `POST /api/autosave` (`all_sessions`); a resposta traz `sessions_saved.scope`
  (`active` | `all`).
- **Testes:** `tests/js/test_v074_autosave_scope.js` (**novo**) **20/20**.

### 🔓 Free tier do OpenCode Zen na restauração (id da sessão no formato nativo)
- **Sintoma (print do autor):** sessão restaurada ("Greeting", 298.326 tokens, 28%) + modelo
  **free do Zen** ("Nemotron 3.5 Super VL Free") → `Error: OpenCode's free tier can only be used
  from within OpenCode`. Uma sessão **nova** funcionava.
- **Causa (reproduzida, não presumida):** o gateway do *free tier* do **Zen** valida o cabeçalho
  `x-opencode-session` e recusa ids fora do formato nativo do motor. A retomada gerava
  `ses_` + **16 hex** (legado) → **HTTP 403** em **qualquer modelo gratuito** (o **OpenCode Go**
  não aplica o mesmo portão).
- **Correção:** `NATIVE_ID_RE`/`LEGACY_ID_RE` viram **contrato**; `mint_id_like()` usa **apenas
  amostras nativas** (a regra anterior, "tamanho majoritário", podia escolher o formato legado —
  o banco tinha 9 nativos × 4 legados); sem amostra, monta o formato oficial. A sessão restaurada
  ainda é **ajustada ao contexto do modelo** (`fit_to_context()`: cabe → nada · não cabe →
  compactação **manual** · falhou → reimporta aparada).
- **Prova:** `POST /api/restore` → id nativo `ses_e99ced15dffeiN0kC8uDy2xYXy` e **"OK"** com
  modelo free do Zen na sessão restaurada.

### 🪟 Telas de abertura (Termos / "Bem-vindo de volta") **uma vez por entrada**
- Termos **e** "Bem-vindo de volta" abrem **uma vez por carga**; o "Bem-vindo" (que mostra o
  e-mail) **uma vez por aba** (`sessionStorage` + cookie); os Termos não reabrem se a versão atual
  já foi aceita neste navegador; a sincronização de idioma **espera** as telas fecharem e não
  repete a cada recarga.

### 🧪 Testes — 272 verificações verdes
- **Python 118/118** (100 da v0.7.3 + **18** de `tests/test_autosave_multi_session.py`) ·
  **JS 154/154** (27 + 47 + 39 + 21 + **20** de `tests/js/test_v074_autosave_scope.js`).

## [0.7.3] — 2026-10-22 — 📦 O pacote `pesquisai` instalado no ambiente · ⏱️ Autosave a cada 1 minuto · 🗂️ Fallback das 3 últimas interações · 🔄 Retomada uma vez na entrada

### ⏱️ Intervalo do autosave: 3 minutos → **1 minuto**
- `AUTOSAVE_INTERVAL_MS` no frontend: `180000` → `60000`.

### 🗂️ Fallback: o backup da sessão anterior não é mais destruído
- **Diagnóstico (verificado nos arquivos do Drive):** os 3 slots do autosave misturavam
  **duas conversas** e o `autosave_3.json` ficava **mais novo** que o `autosave_1.json`.
  Causa: o motor **re-gera o `id` da sessão a cada reinício do terminal** — a mesma
  conversa aparece com `info.time.created` igual e `info.id` diferente.
- **Correção 1 — chave estável:** `content_digest()` passa a usar `info.time.created`
  (fallback `info.id`) → a mesma conversa **não** vira "versão distinta" quando o id muda
  (o sintoma de "3 cópias do mesmo arquivo").
- **Correção 2 — histórico das 3 últimas interações:** `preserve_autosave_history()` copia
  o **último autosave da interação que terminou** para os slots `autosave_4..6`
  (no máximo 3, rotação, mtime original preservado). O autosave de agora **não** destrói
  o backup da sessão anterior; `list_autosaves()` devolve os 6 (vivos + preservados) com
  a marca `history: true/false`, e o fallback da retomada alcança as conversas anteriores.
- **Correção 3 — a sessão certa:** `POST /api/autosave` escolhe, nesta ordem, o
  `session_id` enviado → a sessão do **terminal** (lida do `ps`: `opencode -s "<id>"`) →
  a sessão **mais recentemente atualizada** do motor. Antes usava `sessions[0]`, que nem
  sempre era a conversa do usuário.

### 🔄 A retomada volta a ser perguntada **na entrada** (uma vez, sem loop)
- **Bug da v0.7.2:** a flag "pergunta já oferecida" vivia no `sessionStorage` da aba e era
  gravada **no momento da oferta** → qualquer recarga posterior (inclusive um F5) nunca mais
  perguntava → *"não pediu para restaurar o último autosave quando entrei"*.
- **Correção (máquina de estados em `sessionStorage`):** vazio → **pergunta** (entrada
  normal) · `"restored"` → **não pergunta** e é **consumido** no load (pula só o reload do
  restore) · `"new"` → o autor escolheu "Nova sessão" → não pergunta de novo nesta aba.
  A **oferta não grava mais nada**.

### 📦 O pacote `pesquisai` passa a ser INSTALADO no ambiente (API do autopilot)

**Relato de um novo usuário (Colab):** *"o pacote python `pesquisai` (api autopilot) não está
instalado no ambiente"*. Verificado no ambiente: `pip show pesquisai` → **"Package(s) not
found"** e `from pesquisai.obsidian.autopilot import recall` a partir de um diretório
**neutro** → **`ModuleNotFoundError: No module named 'pesquisai'`**.

**Três causas:**
1. **A célula de boot nunca instalava o pacote** — apenas `sys.path.insert(0, WORK_DIR)`. O
   import só funcionava **dentro** da pasta do repo; o **terminal (e o agente) rodam em outro
   processo, com outro CWD** → a **"Minha memória" não salvava nada**, sem erro visível.
2. **A distribuição chamava-se `pesquisai-additions`** → `pip show pesquisai` não encontrava
   (o nome `pesquisai` está **livre** no PyPI).
3. **`install-offline.sh` engolia a falha** (`pip install ... 2>/dev/null || true`).

**Correções:**
- **`pyproject.toml`**: `name = "pesquisai"` (igual ao nome de importação) · `pyyaml>=6.0`
  como dependência **base** (o frontmatter da memória é parseado com PyYAML).
- **Célula de boot (`PesquisAI.ipynb`)**: após o clone, `pip install -e` (sem dependências →
  com dependências → `--user --break-system-packages`) e **verificação real** — importa
  `pesquisai.obsidian.autopilot` a partir de um **CWD neutro** (`/`), exatamente como o
  agente usa a API. O painel de boot mostra o passo e o resultado.
- **`install-offline.sh`**: instalação **sem** esconder o erro + verificação da API.
- **`scripts/install.sh`**: `pip install -e ".[colab]"` → `".[obsidian]"` (o extra `colab`
  não existia).

### 🔓 Restauração com modelos gratuitos: o id da sessão nasce no formato nativo (23/10)
- **Sintoma:** ao restaurar um autosave, o terminal mostrava `✗ Compaction` com
  `OpenCode's free tier can only be used from within OpenCode…`; uma sessão **nova**
  (criada pelo próprio motor) funcionava.
- **Causa:** a sessão restaurada é criada pelo UFVAI, não pelo motor, e o id saía como
  `ses_` + 16 hex. O gateway do *free tier* valida o cabeçalho `x-opencode-session`
  (upstream #49433) e recusa ids fora do padrão com **HTTP 403** — na primeira mensagem
  **ou na compactação**.
- **Correção:** `id_shape()` + `mint_id_like()` **inferem** o formato dos ids nativos vivos
  (`ses_` + 12 hex + 14 base62) e geram o id importado nesse formato; sem amostras, usam o
  padrão oficial. Vale também para os ids de mensagem (`msg_`). O import registra aviso se
  o id ficar fora do formato nativo.
- **Efeito:** sessões restauradas voltam a funcionar com modelos gratuitos.

#### 🔬 Reprodução controlada (23/10, sandbox isolado `/tmp/ft-test`)

| Sessão importada | id | Modelo | Resultado |
|---|---|---|---|
| formato **nativo** (26) | `ses_e99ced15dffe…` | Zen `beam-free` (1M) | ✅ responde |
| formato **nativo** (26) | `ses_e99ced15dffe…` | Zen `deepseek-v4.1-flash-free` (200k) | ✅ responde |
| formato **nativo** (26) | `ses_e99ced15dffe…` | TUI (tmux) | ✅ responde |
| formato **LEGADO** (20) | `ses_566e11111111abcd` | Zen `beam-free` | ❌ **403 free tier** |
| formato **LEGADO** (20) | `ses_566e00000000abcd` | Go `beam-free` | ✅ responde |

→ O portão é do **OpenCode Zen** (`providerID=opencode`); o **OpenCode Go** não aplica o
mesmo bloqueio. Medido no `opencode.db` vivo: **9 ids nativos** (`ses_` + 12 hex + 14 base62)
e **4 legados** (`ses_` + 16 hex).

#### 🔧 Refinamentos (23/10, sem bump)

1. **`NATIVE_ID_RE` / `LEGACY_ID_RE` / `is_native_id()` / `native_ids()`** — o formato
   nativo passa a ser **contrato** (medido, não presumido).
2. **`mint_id_like()` usa SOMENTE amostras nativas.** A regra anterior ("tamanho
   majoritário") podia escolher o formato **legado** quando os ids antigos fossem mais
   numerous que os nativos — reintroduzindo o bug (o banco tinha 9 nativos × 4 legados).
   Sem amostra nativa, monta o formato oficial (12 hex + 14 base62).
3. **Ajuste ao contexto do modelo na restauração** (`fit_to_context()`): cabe → não faz
   nada · não cabe → **compactação manual** (`POST /api/session/<id>/compact`, caminho que
   o gateway **não** recusa) · falhou → **reimporta aparado** (as mensagens mais recentes
   que cabem). O orçamento é 85% do contexto do modelo (130 mil tokens quando o modelo é
   desconhecido). O `POST /api/restore` devolve o ajuste em `fit`.
4. **Aviso no import** quando o id resultante não segue o formato nativo.
5. **Prova end-to-end no runtime vivo:** `POST /api/restore` → `session_id`
   `ses_e99ced15dffeiN0kC8uDy2xYXy` (**nativo**, 30 caracteres), `fit.action = "none"`
   (279.506 tokens ≤ 891.289 do modelo de 1M) e mensagem **"OK"** com **modelo free do
   Zen** na sessão restaurada — o cenário que antes devolvia 403.

### 🪟 Telas de abertura (Termos / "Bem-vindo") **uma vez por carga** (23/10)
- A sincronização de idioma recarregava a página e reabria as telas de abertura. Agora a
  guarda é **dupla** (`sessionStorage` + cookie de sessão), a sincronização **espera** as
  telas fecharem (e não roda por cima da restauração), e a abertura — Termos **ou**
  "Bem-vindo de volta" — acontece **uma vez** por carga.
- **Detalhamento:** `_shown` garante **uma** abertura por carga (Termos ou "Bem-vindo");
  o "Bem-vindo de volta" grava `ufvai_welcome_seen` no `sessionStorage` (fallback: cookie
  de sessão) → **não reabre a cada recarga** da aba; se o navegador já aceitou a versão
  atual dos Termos (`localStorage.ufvai_terms_version`), a tela de Termos **não reabre**;
  a sincronização de idioma guarda `ufvai_lang_synced` (sessionStorage + cookie) e só
  reinicia o terminal **depois** que as telas de abertura fecharam.

### 🧪 Testes — 225 verificações verdes
- `tests/js/test_v073_autosave_policy.js` (**novo**) 21/21 · `tests/test_autosave_history_v073.py`
  (**novo**) 13/13 · `tests/js/test_v072_resume_once.js` 39/39 (seções 1, 2 e 4 atualizadas
  para o contrato novo) · `tests/js/test_autosave_ui.js` 27/27 ·
  `tests/js/test_restore_calendar.js` 47/47 · `tests/test_restore_backups.py` 26/26
  (2 testes ajustados: a listagem inclui o histórico) · `tests/test_session_restore.py` 22/22 · `tests/test_instalacao_pacote.py` (**novo**) 10/10 (pacote instalado, nome da distribuição, boot cell, instaladores) · `tests/test_session_id_format.py` (**novo**, 23/10) 9/9 (formato nativo inferido, id de mensagem, unicidade e fallback sem amostras) · `tests/test_restore_free_tier.py` (**novo**, 23/10) 20/20 (filtro de ids nativos, regressão "id legado no meio das amostras", ids de mensagem, estimativa de tokens, aparo, orçamento de contexto e os três caminhos do `fit_to_context`).

## [0.7.2] — 2026-10-22 — 🔄 Retomada do autosave uma única vez por aba + 📅 Calendário do "Restaurar" corrigido

### 🔄 Laço da retomada do autosave (o "restore" recarregava tudo)
- **Sintoma:** com autosave disponível, ao clicar em **"Continuar de onde parei"**: o terminal recarregava (`location.reload()`) → a tela de confirmação da retomada **voltava** → o clique no "Continuar" repetia o ciclo.
- **Causa-raiz:** `checkAutosaveResume()` é chamado ~2,5 s depois de cada carregamento de página e reoferecia a pergunta sempre que houvesse autosave válido, sem nenhuma guarda de idempotência.
- **Fix (frontend `pesquisai/launch_app_responsive_v041.py`):** flag `ufvai_autosave_resume_offered` em `sessionStorage` — sobrevive ao reload da **mesma** aba (o caso do laço) e morre ao fechar a aba. Marcada em `showAutosaveResume()`, `autosaveResumeContinue()` e `_doRestoreSession()`; `checkAutosaveResume()` retorna **antes de qualquer `fetch`** se a flag existir. **Escape hatch:** botão **↻** no rodapé (`reofferAutosaveResume()`); o menu **🔄 Restaurar** segue sempre disponível.

### 📅 Calendário do "Restaurar" (datas faltando / erradas)
- **Diagnóstico com os dados reais do Drive:** 44 backups em 20 datas (26/05 → 22/10/2026), concentrados em jun/2026 (24) e jul/2026 (10) — meses que o calendário não sinalizava, o que produzia a impressão de datas faltando.
- **Fix:** chips clicáveis dos meses que **têm** backup (+ contagem) · contagem de backups em cada dia · tooltip `3 backups` (era `3)`) · data deduzida de `datetime`/`timestamp` · item sem data vai para o grupo **"sem data"** (nunca some do filtro) · estado vazio acionável ("Todas as datas") · botão **"Mais recente"** (`restoreGoNewest()`).
- **Verificado e NÃO é bug:** o alinhamento dos dias da semana está correto (grade e cabeçalho começam na segunda).

### 🧪 Testes — 161 verificações verdes
- `tests/js/test_v072_resume_once.js` (**novo**) 39/39 · `tests/js/test_autosave_ui.js` 27/27 · `tests/js/test_restore_calendar.js` 47/47 · `tests/test_restore_backups.py` 26/26 · `tests/test_session_restore.py` 22/22.
- **Correção de teste pré-existente:** `test_restore_backups.py::test_ordenacao_decrescente_por_data` dependia da **data do dia** (mtime "atual" dos autosaves) e passou a falhar ao virar o dia (22/10) → *fixture* com mtime fixo em 20/10/2026 12:00.

### 📚 Documentação sincronizada em 0.7.2
- `AGENTS.md` + `agents/AGENTS.{en,es,fr,pt,zh}.md` (frontmatter `version: 0.7.2`).
- `MANUAL.md` (cabeçalho **v0.7.2 · Outubro 2026**, ficha de catalogação, citação ABNT, BibTeX, §5.4/§5.5, §12) e `README.md` (badge, novidades, histórico 0.7.x, citação, BibTeX).
- `pyproject.toml` (`version = "0.7.2"`), `Dockerfile` (label OCI), `install-offline.sh` (`VERSION="0.7.2"`), `PesquisAI.ipynb` (painel de boot e citação ABNT).
- `CHANGELOG.md` (este arquivo) + `LEIA-ME-v0.7.2.md`.

## [0.7.1] — 2026-10-22 — 🔧 Retomada do autosave corrigida na entrada + 💾 autosave sem duplicata + 🗑 botão de apagar backup

### 🔧 A retomada na entrada não restaurava (o botão do menu funcionava)
- **Causa-raiz:** `list_autosaves()` devolvia o nome **sem** o prefixo `autosave/` (enquanto `list_backups()` traz o prefixo) → o `/api/restore` recusava com **400** "Este arquivo não é um backup de sessão".
- **Fix:** `list_autosaves` passa a devolver `autosave/<nome>` (+ campo `name`) e `_resolve_restore_path` aceita o nome **com ou sem** prefixo — recusa do que não é backup e bloqueio de *path traversal* mantidos.

### 💾 Autosave sem duplicata
- `content_digest()` (sha256 de id + mensagens, ignorando `info.time.updated/viewed`) impede gravar cópia idêntica → os 3 slots são **3 versões distintas** (fallback preservado). A interface avisa "sem novidades" (`autosave.unchanged`).

### 🗑 Botão de apagar backup
- `POST /api/backup/delete` com `confirm: true` **obrigatório** (mesma validação de caminho do `/api/restore`) + botão 🗑 por item no menu "Restaurar", com confirmação e recarga da lista · i18n em **5 idiomas**.

### 🔁 Fallback na retomada
- Se o autosave mais recente falhar, tenta o anterior (até 3).

### 🧪 Testes
- `test_restore_backups.py` 26/26 · `test_session_restore.py` 22/22 · `tests/js/test_autosave_ui.js` 27/27 · `tests/js/test_restore_calendar.js` 47/47.

## [0.7.0] — 2026-10-21 — 🗓️ "Restaurar" só backups com calendário + ⏱️ autosave a cada 3 min + 🏷️ marca UFVAI na tela de nova sessão

### 🗓️ Menu "Restaurar" reconstruído
- `GET /api/backups` devolve **somente backups** (42 itens = 39 backups + 3 autosaves; `keys_store.json`, `keys.json`, `aakeys.json` e `ufvai_consentimento*.json` ficam de fora) com data/hora/tamanho/título/integridade e 19 datas.
- `POST /api/restore` valida estritamente (`backup_*.json` | `autosave_<n>.json`) → **400** para `keys_store.json` e para `../keys_store.json`.
- Interface com **calendário mensal**, **filtro por data** (`input date` + clique no dia), navegação de mês e lista agrupada por dia, com selos *Autossave* / *corrompido* · i18n em 5 idiomas.

### ⏱️ Autosave corrigido e ligado por padrão
- **Causa-raiz:** `NameError: name 'method' is not defined` no branch `/api/autosave` do `do_POST` (a variável nunca existiu nesse método) → toda gravação morria com "Empty reply from server"; o `GET /api/autosave` estava dentro do `do_POST` → **404**.
- **Fix:** listagem movida para o `do_GET` · **rotação invertida** (rotaciona **antes** de gravar → o slot 1 volta a ser o mais recente) · `autosaveEnabled()` **ligado por padrão** (só desliga se o autor desativar) · rede de segurança nos handlers (exceção → HTTP 500 JSON com a causa).

### 🏷️ Identidade e interface
- Marca **UFVAI** na tela de nova sessão (logo redesenhado + sugestões do prompt com uso UFVAI/agêntico, via patch cirúrgico de mesmo comprimento no motor) · 🇨🇳 Chinês também troca o terminal · 🎨 Manual e Diretrizes no tema claro · 📱 "Idioma" fora do sanduíche e nota da Memória visível no responsivo.

### 🧪 Testes
- `test_restore_backups.py` 19/19 · `test_session_restore.py` 22/22 · `tests/js/test_restore_calendar.js` 40/40 (sobre o HTML **renderizado**) · `tests/js/test_autosave_ui.js` 23/23 (reescrito — o antigo stubava o `fetch` e nunca exercitava o endpoint real) · `node --check` nos 7 `<script>` do HTML servido 7/7.

## [0.6.21] — 2026-10-13 — 🔧 Migração do motor para a **OpenCode V2** · 🍪 Aviso de cookies de terceiros · 🫀 Keep-alive por célula bloqueante

### 🔄 Ajuste de 14/10/2026 (sem bump — a versão continua 0.6.21, por decisão do autor)
- **Sintoma reportado:** ao adicionar uma nova chave de API, o terminal reiniciava e o motor iniciava com o agente **`build`** em vez do **UFVAI**.
- **Causa (doc oficial V2, `opencode.ai/v2/docs/agents` §Selection):** a V2 só usa o `default_agent` de `opencode.json` quando o agente **existe, é visível e aceita `primary`**; caso contrário cai em `build`. A regeneração de `agents/UFVAI.md` + `default_agent` acontecia **apenas no boot** (`setup_dependencies` → `_setup_theme_and_agent`), então reinícios fora do boot (troca de chave via `_apply_opencode_env_change_async`, troca de idioma, `/api/run_terminal`, restore de sessão) podiam rodar sem a config em vigor.
- **Correção:** nova função **`run_fast.ensure_ufvai_agent()`** (idempotente: regenera o agente, remove legados `pesquisai.md`/`ufvai.md` e (re)grava `default_agent: "UFVAI"` preservando as demais chaves) + wrapper **`launch_app._ensure_ufvai_agent_before_spawn()`** chamado **antes de todo (re)spawn do terminal** — `start_ttyd`, `restart_ttyd_with_lang`, `/api/run_terminal` e restart pós-import de sessão. Best-effort: nunca impede o terminal de abrir; falha é logada.
- **Limites honestos:** a inicialização do terminal que leva `opencode -s <id>` restaura a sessão importada **com o agente gravado nela** (comportamento da V2: config não troca o agente de sessão existente). Sessões exportadas do UFVAI gravam UFVAI. Comando do agente em execuções pontuais (`opencode run --agent …`) não é afetado.
- **Versão do motor e do UFVAI:** **mantidas** — `pesquisai` segue 0.6.21 e nada toca no binário do OpenCode.

## Outros itens da v0.6.21 (13/10/2026)

> **Bump para 0.6.21 (decisão do autor, 13/10/2026):** a versão saiu do
> "Não publicado" e ganhou número próprio — a atualização do motor para a
> OpenCode V2 passa a estar registrada **nesta entrada, a 0.6.21**. A promoção
> a **0.7.0** fica reservada para quando houver breaking change de fato.
>
> **Validação de campo:** o ciclo `auth export` → cifragem → `auth import` foi
> **executado de verdade** contra a V2.0.28 nesta release, com uma credencial de
> teste de descarte (ver a seção "Validação de campo do backup de credenciais").
> **Não** foi validado com uma credencial real do autor. O que resta é a
> **retomada de sessão** e a validação com credencial real.

> **Registro corrigido nesta release:** a seção "Não lançado" afirmava que
> README/MANUAL/AGENTS/citação já tinham a seção do motor V2 e do aviso de
> cookies. **Não tinham** — a auditoria de 13/10 encontrou **zero** menções a
> "OpenCode V2" nesses quatro arquivos (as ocorrências de "cookie" existentes
> eram todas sobre telemetria/LGPD, não sobre o proxy). **Corrigido nesta release:**
> README (novidades + tabela de versões), MANUAL (§1.4.1 + tabela de versões),
> AGENTS (§0.1 — motor OpenCode V2) e a citação (metadados) foram escritos de fato,
> com a mesma regra do CHANGELOG: só entra no documento o que foi verificado no
> código ou em execução real.

### 🔧 Motor OpenCode V2 (a mudança de fundo)
- **O que mudou:** o UFVAI passou a rodar sobre o **OpenCode 2.x**. A V2 abandonou `config.json` e `tui.json`; a configuração do motor vive em `~/.config/opencode/opencode.json` e a do cliente de terminal em `~/.config/opencode/cli.json`.
- **Instalador:** `https://opencode.ai/v2/install` (constante `OPENCODE_INSTALL_V2`), com fallback para o pacote npm oficial `@opencode/cli`. O V1 instalado é **atualizado no lugar** (mesmo `~/.opencode/bin`).
- **Detecção de versão:** `opencode_utils` ganhou `opencode_version_string()`, `opencode_major()` e `is_opencode_v2()`. `find_opencode()` passa a **preferir o binário 2.x** entre todos os candidatos — antes, um `opencode` 1.x antigo no PATH era escolhido e o boot tentava atualizar a cada inicialização.
- **`--auto` no lugar de `--yolo`:** é a flag de autoaprovação da V2. Desligar continua possível com `PESQUISAI_YOLO=0` (comportamento padrão inalterado: ligado).
- **Tema do terminal em um arquivo só:** `themes/pesquisai.json` traz **dark e light juntos**; o modo passa a ficar em `cli.json` (`theme.mode`). O tema legado `pesquisai-light.json` é removido quando existe. A interface web continua usando os nomes `pesquisai` / `pesquisai-light`.
- **As 50 chaves do tema:** o conversor da V2 exige as mesmas 50 chaves do tema embutido; a paleta foi convertida papel a papel. A ausência de qualquer uma faria o motor cair no tema padrão.
- **`tui.json` não é mais gravado:** é formato V1; a V2 só o lê para migrar quando `cli.json` ainda não existe.
- **Agente:** `agents/UFVAI.md` com o frontmatter aceito pela V2 (`description`, `mode: primary`, `color`) — **sem `name`**, porque a V2 define o ID pelo caminho do arquivo. O ID gravado é **`UFVAI`**, como pede o autor, e `default_agent: "UFVAI"` vai para `opencode.json`. Validado na V2.0.28 em execução real: `/api/agent` devolve `id: "UFVAI"`, `name: "UFVAI"`, com o prompt do UFVAI; `agents/pesquisai.md` e `agents/ufvai.md` são removidos na migração.
- **Credenciais:** a V2 guarda credenciais em SQLite (`~/.local/share/opencode/opencode.db`). O backup no Drive voltou a ser feito com **`opencode auth export` → JSON cifrado** e restaurado com `opencode auth import`. O banco em si nunca é copiado.

### 🍪 Aviso de cookies de terceiros do proxy do Colab
- **Problema:** a interface abre pelo proxy do Colab (`https://<porta>-<id>.prod.colab.dev`). Se o navegador bloquear cookies de terceiros, **o endereço simplesmente não abre** — sem mensagem de erro útil.
- **Solução:** `colab_cookies.py` sobe um servidor efêmero em `127.0.0.1` e o teste roda num **iframe** apontando para uma página mínima servida pelo próprio kernel. A página tenta gravar um cookie e responde por `postMessage`.
- **O aviso só aparece quando o bloqueio é detectado.** O bloco nasce **invisível** (fundo transparente, sem borda) e só vira cartão no estado `blocked` — isto é, a página carregou e o cookie **não** voltou. Com os cookies liberados **nada aparece**; e como não houve detecção, também ficam em silêncio o timeout, a falha de rede e o erro do próprio teste.
- **Sem duplicar aviso:** `ensure_cookie_check()` é idempotente — o notebook e o `run_fast` pedem o mesmo teste, e o usuário vê **um** bloco.
- **Privacidade:** a página de teste não lê nem grava nada do usuário; só testa o próprio cookie.

### 🫀 Keep-alive como célula bloqueante (corrige a 0.6.20 de 01/10)
- **Problema:** o keep-alive da 0.6.20 era um `subprocess` que imprimia uma linha por minuto. O Colab decide a ociosidade pela **atividade do notebook** — um processo em segundo plano não conta, então a sessão continuava caindo.
- **Solução:** `keepalive.py` roda **na própria célula**, bloqueando o kernel. A cada 60 s verifica as portas 8000 (terminal) e 8001 (interface); **duas falhas seguidas** disparam a recuperação (uma falha isolada não reinicia nada — evita falso positivo), e o estado saudável zera o contador.
- **Limite honesto, declarado no código e no notebook:** nada garante a sessão para sempre — o Colab tem teto (~12 h) e cota. Este módulo **não simula cliques na interface**, o que seria violação dos termos do serviço.
- **Encerrar:** o botão **SAIR** da interface chama `request_stop()` e mata a célula pelo PID file (`/tmp/pesquisai/ufvai_keepalive.pid`).
- **Log local:** `/tmp/pesquisai/ufvai_keepalive.log` — fora do Drive de propósito, para não gerar tráfego a cada minuto.

### 🛡️ Módulo novo `opencode_config.py`
- Toda a manipulação de arquivos do motor ficou num módulo só, **sem efeito colateral na importação**: leitura de JSON/JSONC, escrita atômica (temp + `os.replace`), merge de `cli.json`, merge de `opencode.json`, tema e agente.
- **Regra de ouro:** arquivo do usuário que **não pode ser interpretado** (JSON quebrado) **nunca é sobrescrito** — a carga é descartada e o log avisa. Isso vale para `cli.json` e `opencode.json`.

### 🧪 Testes
- **3 suítes novas**, 3 módulos que estavam sem cobertura nenhuma:
  - `tests/test_opencode_config.py` — JSONC (comentários dentro de string não são cortados), escrita atômica sem temporário órfão, preservação das chaves do usuário, **arquivo corrompido não é sobrescrito**, tema com exatamente 50 chaves todas apontando para `defs` existentes e em hexadecimal válido, round-trip de gravação/leitura;
  - `tests/test_colab_cookies.py` — página servida responde **HTTP 200 real** num servidor efêmero, `Cache-Control: no-store`, thread daemon, porta livre, escape da URL no HTML, idempotência do aviso, `skipped` fora do Colab, truncamento do erro em 200 caracteres;
  - `tests/test_keepalive.py` — laço exercitado **sem espera real** (relógio e evento de parada injetados): `parado` × `limite`, recuperação só após 2 falhas seguidas, contador zerado pelo estado saudável, callback que falha não derruba o laço, log com início/fim, porta aberta/fechada, e uma trava de regressão que garante que o módulo **não volte a usar `subprocess`**.
- `tests/test_run_fast.py` — 12 casos novos: os arquivos que a V2 lê (`themes/pesquisai.json`, `cli.json`, `agents/pesquisai.md`, `opencode.json`), a **não** escrita de `tui.json`/`config.json`/`pesquisai-light.json`, a preservação do tema escolhido pelo usuário, `cli.json`/`opencode.json` corrompidos intactos, e a ligação do teste de cookies em `setup_launch` (inclusive: erro no teste de cookies **não impede** o UFVAI de abrir).
- `tests/test_version_sync.py` — 9 casos novos: o Dockerfile instala o motor **como o usuário `ufvai`** (não root), põe `~/.opencode/bin` no `PATH`, cria os diretórios da V2, instala `ca-certificates` e usa a **mesma URL** de `constants.OPENCODE_INSTALL_V2`.
- **Total da suíte: 217 testes verdes.**

### 🐞 Bugs encontrados pelos próprios testes (corrigidos nesta sessão)
- **`merge_cli_theme` mutava o dicionário do chamador:** a cópia do `theme` era rasa, então escrever `theme["name"]` alterava o `cli.json` recém-lido do disco. Passou a copiar o `theme` também.
- **File handle vazado em `_setup_theme_and_agent`:** `open(agents_md).read()` sem `with` deixava o descritor do `AGENTS.md` aberto a cada boot. Agora usa `with`.

### 📦 Dockerfile
- Instala o **OpenCode V2** durante o build, **como o usuário não-root `ufvai`** (`su -s /bin/bash ufvai -c …`), no mesmo caminho que o Colab usa (`~/.opencode/bin`) — antes a imagem exigia o binário montado por volume.
- `ca-certificates` instalado (o instalador baixa por HTTPS), `PATH` com `~/.opencode/bin`, diretórios `~/.config/opencode/{themes,agents}` e `~/.agents/skills` criados e com dono `ufvai`.
- **Saída para build sem rede:** `UFVAI_NO_OPENCODE_INSTALL=1` pula a etapa e deixa o `run_fast` resolver no boot.
- A imagem **continua terminando em `USER ufvai`** e `HEALTHCHECK` inalterado.

### 📚 Documentação
- `README.md`, `MANUAL.md`, `AGENTS.md` + `agents/AGENTS.{en,es,fr,zh}.md` e `citacao_pesquisai.md`: **escritas nesta release** as seções do motor **OpenCode V2**, do aviso de cookies de terceiros e do keep-alive por célula. Versão propagada para **0.6.21** em todos os arquivos.
- `MANUAL.md` §1.4.1 corrigido: a descrição do keep-alive em **subprocesso** (que era o comportamento da 0.6.20) foi atualizada para a **célula bloqueante** da 0.6.21.
- `PesquisAI.ipynb`: instruções de uso atualizadas (passo 2 = teste de cookies, passo 4 = keep-alive em célula), boot chamando `ensure_cookie_check()`, citação ABNT em v0.6.21.

### 🔗 Ligação do aviso de cookies no `launch_app`
- `launch_app.launch()` agora também chama `ensure_cookie_check()` antes de exibir o botão de abertura. Sem isso, quem chamasse o `launch()` **diretamente** (é o caminho do `__main__` do módulo e de integrações) ficaria **sem** o aviso, porque a chamada vivia só no `run_fast.setup_launch()`.
- A ligação é **idempotente** por construção: `ensure_cookie_check()` tem flag de módulo (`_COOKIE_CHECK_DONE`) e devolve `{'state': 'done'}` sem repetir o aviso. O fluxo do Colab (notebook → `run_fast` → `launch`) **não duplica nada**.
- Falha no teste de cookies é registrada em log e **nunca** interrompe o boot — o aviso é acessório, oUFVAI abre de qualquer forma.

### ✅ Validação de campo do backup de credenciais (13/10/2026, V2.0.28)
- **Ciclo `auth export` → cifragem → `auth import` executado de verdade** contra o motor V2.0.28, com uma **credencial de teste de descarte** (`integration: openrouter`, label "UFVAI Teste Validação"). Resultado: **funciona ponta a ponta**. **Limite honesto do que isso prova:** valida o *caminho* (schema, cifragem, round-trip, idempotência) — **não** valida uma credencial real do autor, nem o uso do modelo.
- **O cofre NÃO volta a `[]` por conta própria — correção em relação a um registro anterior.** Ao final da validação o cofre foi limpo (`auth export` → `[]`), **mas** `restore_opencode_auth_from_drive()` roda **a cada boot** (`launch_app.py:4006`) e o backup no Drive **continha** a credencial de teste. No boot seguinte ela foi **reimportada automaticamente**: a entrada `cred_ufvaiteste0000000000` tem `time_created` = 20:04:15 UTC, e `save_opencode_auth_to_drive()` no encerramento (`launch_app.py:3927`) regrava o backup com o mesmo conteúdo — o teste **se autoperpeta**. Enquanto `backups/opencode_auth.json` contiver a credencial de descarte, todo boot a reinyeta. **Consequência prática: remover a credencial de teste do cofre e o arquivo de backup antes da validação com credencial real**, sob pena de o `restore` recusar por já haver credencial no motor (`launch_app.py:1417`) e mascarar o diagnóstico.
- **O schema que o motor exige foi extraído do próprio binário**, não adivinhado. `Credential.Entry = { id, integrationID, label, active, value }`, e `Credential.Value` é uma **união discriminada por `type`** com três formatos — `oauth` (`methodID`, `refresh`, `access`, `expires?`, `metadata?`), `key` (`key`, `metadata?`, `configuration?`) e `external` (`methodID`, `metadata?`). O `id` é do tipo `Credential.ID` (prefixo `cred_`). Sem esse contrato, o `auth import` rejeita campo a campo (`Missing key at [0]["id"]` → `["integrationID"]` → `["label"]` → `Expected boolean` → `Expected Credential.Value`).
- **Round-trip verificado ponta a ponta:** após importar uma credencial `{type: "key", key: ...}`, o `auth export` devolve **o mesmo segredo intacto** — a criptografia e a decifragem do UFVAI não perdem nada. Reimportar a mesma entrada responde `Imported 1 credential` (idempotente do lado do motor: não duplica).
- **Comportamento seguro confirmado:** uma exportação vazia (`[]`) **nunca sobrescreve** um backup já gravado — `save_opencode_auth_to_drive()` só escreve se trouxer ao menos uma credencial. Testado: com o export vazio a função devolve `False` e o envelope `opencode-auth-export-v2` permanece íntegro.
- **Envelope cifrado conferido:** o arquivo no Drive é `{_ufvai_enc, data, format}` com `format: "opencode-auth-export-v2"`; o segredo **não aparece em claro** no arquivo (273 B para um payload de teste). O arquivo temporário do `auth import` é removido em `finally`, então **segredos não ficam em `/tmp`**.
- **Nota de operação:** `auth logout` em terminal não interativo exige **dois** argumentos — `opencode auth logout <integration> <credential>`; com um só, ou com o ID/label no lugar errado, o motor abre seletor interativo e falha. Afeta apenas a limpeza manual, não o fluxo automático do UFVAI.

### ❗ Pendências (autor)
- **Limpar a credencial de teste antes da validação real** — o cofre ainda contém `cred_ufvaiteste0000000000` (`openrouter`) e `backups/opencode_auth.json` a contém cifrada; como o `restore` roda a cada boot, ela **volta sozinha**. A limpeza exige **os dois**: `opencode auth logout openrouter "UFVAI Teste Validação"` **e** a remoção do arquivo de backup no Drive. (Ver a seção de validação acima.)
- **Validação de campo com credencial REAL** — o caminho está validado com credencial sintética; falta o round-trip com a credencial do autor (login → `auth export` → backup cifrado → `auth import` → retomada de sessão).
- **Retomada de sessão** no Colab com o motor 2.x: subir a interface, reconectar e confirmar que a sessão volta com o histórico — ainda não foi exercitada em execução real.
- **Push para o GitHub** — `git push` segue bloqueado por falta de credencial (`gh auth login` pendente).
- Rebuild do `.deb` offline em 0.6.21 (o pacote atual continua em 0.6.19).

---

## [0.6.20] — 2026-10-01 — 🫀 Keep-alive + botão SAIR na interface · 🌐 Rodapé com o site oficial · 📄 Planilha de contatos em 1 linha
### 🎯 Nova direção (mudança de planos)
- **Descartada** a abordagem da 0.6.20 bugada de 30/09 (supervisor desacoplado `colab_host.py`/`spawn_detached` — travava em "Aguardando a interface ficar pronta…" porque `eval_js(proxyPort)` e `drive.mount` exigem o kernel do Colab e abortavam antes de gravar o `READY_FILE`). **Rollback** foi feito e a base desta release é a **v0.6.19 estável**, sem alteração funcional no pacote de boot — a 0.6.20 vive no `PesquisAI.ipynb` (boot/keep-alive/SAIR) e no pacote (rodapé do site + planilha de contatos, abaixo). Número de versão mantido: **0.6.20**.

### 📦 Novo `PesquisAI.ipynb` (única mudança de código)
- **Célula de boot simplificada:** painel da logomarca (5% → 12% → 20%) → clone/pull do repositório (`git pull --ff-only --depth 1` em `/tmp/pesquisai`) → `from main import run; run()` **direto no kernel do Colab** (fluxo comprovado da v0.6.17/0.6.19, sem supervisor) → painel 100%.
- **🫀 Keep-alive em background (subprocesso):** `subprocess.Popen(sys.executable, start_new_session=True)` imprime 1 linha a cada 60s em `/tmp/pesquisai/ufvai_keepalive.log` (saída em arquivo — mantém a política "painel único", zero texto solto no notebook). Limite honesto documentado na célula: nada impede o Colab de destruir o runtime (~12 h de teto, cota, decisão do backend).
- **🔴 Botão SAIR (novo, card abaixo da barra de carregamento):**
  - Exibido após o boot bem-sucedido **somente no Colab** (registro real de callback via `google.colab.output.register_callback("ufvai.exit", …)`);
  - **Confirmação obrigatória:** clique em SAIR abre painel de confirmação (SIM, SAIR / CANCELAR) com aviso claro — tudo em memória é perdido, arquivos no Drive continuam salvos, não há como desfazer;
  - Ao confirmar: encerra o keep-alive (`terminate` → `wait` → fallback `kill`), atualiza o painel de boot ("Encerrando o ambiente…") e chama **`google.colab.runtime.unassign()`** — desconecta e exclui o runtime (equivalente a *Runtime ▸ Desconectar e excluir ambiente*; colabtools #2568);
  - Fallback honesto: se `invokeFunction` falhar, o card orienta usar o menu **Runtime** manualmente (nenhuma chamada inventada);
  - Fora do Colab o card não é exibido (sem `google.colab` disponível).
- **Documentação:** células markdown do ipynb atualizadas (instruções de uso, keep-alive e SAIR; citação ABNT v0.6.20).

### 🌐 Rodapé com o link do site oficial
- O rodapé da interface ganha o link **"🌐 Site"** (ícone globo em SVG, abre em nova aba) para `https://gustavobraga-byte.github.io/ufvaisite/`, entre o GitHub e o texto "UFV · Viçosa, MG - Brasil".
- **Responsivo:** em telas <480px o texto "UFV · Viçosa, MG - Brasil" sai de cena para o link caber sem quebrar a linha; desktop e tablet mantêm tudo visível.
- Arquivos: `pesquisai/launch_app_responsive_v041.py` + `pesquisai/launch_app_responsive.py` (pacote) e cópias vivas da raiz (4 no total); typo de tag `<span>` corrigido no responsivo do pacote.

### 📄 Planilha de contatos: uma linha por ativação/retorno
- **Contrato novo:** a planilha do desenvolvedor recebe EXATAMENTE UMA linha — a **`usuario_ativo`** (e-mail · nome · IP), gravada **quando o usuário clica no botão** (Continuar/ABRIR da tela de Termos ou "Bem-vindo de volta").
- O primeiro aceite **não grava mais** a linha `novo_contato`: grava somente o perfil do usuário localmente + backup no Drive (e o contador anônimo no GA4).
- Backend (`telemetry.py`): `notify_active_user()` agora é a única fonte de linhas; a flag legada `novo_contato` ainda é aceita no Apps Script (compatibilidade) e o fix "Versão" como texto (evita `0.6.20` virar data no Sheets) está propagado nas cópias.

### 🧪 Testes
- Suítes revalidadas: deduplicação/telemetria atualizada ao contrato da linha única (32/32) · cascata CSS dos 4 arquivos vivos (144/144) · versão/boot (24/24) · SAIR em modo estático.
- **Igual a Zero:** o ambiente Colab em uso nunca foi desligado nos testes (casos que invocariam shutdown/keepalive real foram executados apenas como verificação estática de código).

### 🔢 Versionamento e docs em paridade
- Bump `0.6.19 → 0.6.20` em `pesquisai/__version__.py` (`__version__`, `__release_date__="2026-10-01"`, `__codename__="Boot simplificado + keep-alive em subprocesso + botão SAIR no Colab"`), `pyproject.toml` (versão + descrição), `Dockerfile` (comentário + LABEL), `README.md` (badge, novidades, tabela de versões, citação, BibTeX, rodapé), `MANUAL.md` (cabeçalho, citações, tabela, rodapé), `AGENTS.md` + `agents/AGENTS.{en,es,fr,pt,zh}.md` (frontmatter + rodapé), `citacao_pesquisai.md`, `PesquisAI.ipynb`.
- **Pendente (humano):** publish no GitHub (o ipynb clona de `gustavobraga-byte/PesquisAI`); rebuild do `.deb` não é exigido (o código do pacote é idêntico à v0.6.19 — a mudança vive só no notebook).

---

## [0.6.19] — 2026-09-29 — 📱 Menu mobile sem SVG + hamburger à direita + docs em paridade

### 📐 O menu hamburger aparecia colado no logo, à esquerda
- **Sintoma:** em ≤767px o botão de idioma + hamburguer apareciam logo ao lado da marca "UFVAI", no lado **esquerdo** da topbar — o usuário não os achava.
- **Causa raiz:** o CSS base tem `.sep { flex: 1; }` dentro do `#topbar`. Na resolução do flexbox o `flex-grow` é distribuído **antes** das margens automáticas (§4.5 do spec: "auto margins absorb the remaining free space *after* the flexible lengths have been resolved"). Com o `.sep` absorvendo todo o espaço livre, o `margin-left: auto` do `.tb-icons` recebia 0 e o grupo encostava no logo.
- **Fix CSS:** em `@media (max-width: 767px)` → `#topbar .sep { display: none; }` (especificidade de ID, vence o `.sep` do CSS base). Os `.tb-btn` que o `.sep` separava já estão `display:none` nesse breakpoint, então nada se perde: o espaço livre volta e o `margin-left: auto` do `.tb-icons` empurra idioma + hamburguer para a borda direita.
- **Desktop intacto:** o `.sep` continua `flex:1` como spacer acima de 768px e o `.tb-icons` volta a `margin-left: 6px` (encostado no logo, como sempre).
- **Arquivos:** `pesquisai/launch_app_responsive_v041.py` (produção) + `pesquisai/launch_app_responsive.py` (legado) nos dois projetos (`UFVAI-v0.6.9/`, `ufvai-github/`) **e** as cópias de produção da raiz (`launch_app_responsive_v041.py`, `launch_app_responsive.py`, `launch_app_responsive_versaoteste_CORRIGIDO.py`) — 7 arquivos vivos no total.

### 🧪 Teste de regressão de cascata (não é grep no fonte)
- **Novo:** `tests/test_responsive_hamburger.py` nos dois projetos.
- **Como funciona:** importa o módulo real, chama `create_wrapper_html()`, extrai os `<style>`, parseia o CSS com `tinycss2` e **resolve a cascata de verdade** — especificidade + `!important` + ordem de origem + style inline — para uma largura simulada. Escolhido porque o bug anterior (`display:none` presente mas inefetivo por cascata) **passaria** num grep: a regra antiga tinha especificidade (0,1,0), igual à da regra base.
- **Cobertura:** 7 arquivos vivos × 10 larguras (320/375/414/479/600/767 mobile · 768/900/1024/1440 desktop) — 252 verificações por projeto. Contratos: (a) ≤767px nenhum SVG da topbar fica visível (exceto o do próprio hamburger); (b) ≤767px `.sep` = `none` e `.tb-icons` com `margin-left:auto`; (c) ≥768px o `.sep` volta a ser spacer e `.tb-icons` volta a `6px`; (d) o hamburger e o botão de idioma continuam visíveis no mobile; (e) nenhum SVG dentro do drawer.
- **Resultado:** 252/252 nos dois projetos.
- Versão do release: `0.6.19` em `pesquisai/__version__.py` (`__version__="0.6.19"`, `__release_date__="2026-09-29"`, `__codename__="Menu mobile sem SVG + docs em paridade (skills personalizadas)"`), `pyproject.toml`, `Dockerfile` e `CHANGELOG.md`; docs em paridade: `README.md` (badge, novidades, tabela de versões, citação, BibTeX, rodapé), `MANUAL.md` (cabeçalho, citação, tabela, rodapé), `AGENTS.md` + `agents/AGENTS.{pt,en,es,fr,zh}.md`, `citacao_pesquisai.md`, `PesquisAI.ipynb`.


### 📱 Responsivo: esconder botões SVG quando o hamburger aparece
- **Motivação:** em telas pequenas (≤767px) o menu hamburger aparecia mas os botões-ícone SVG continuavam na topbar, poluindo e duplicando ações.
- **Fix CSS (`launch_app_responsive*.py`):** `@media (max-width:767px)` agora faz `.tb-icon{display:none}`; drawer reexibe botões textuais (`.mobile-menu .tb-btn{display:inline-flex}`) sem SVG (`.mobile-menu .tb-btn svg, .mobile-menu .btn-provider svg{display:none}`). NENHUM SVG aparece com menu reduzido — funções seguem no drawer (Dashboard, Sessões, Atalhos, Diretrizes, Memória, Tema, Idioma, backup/restore/drive).
- **Arquivos:** `pesquisai/launch_app_responsive_v041.py` (produção) + `pesquisai/launch_app_responsive.py` (legado) nos dois projetos (`UFVAI-v0.6.9/` e `ufvai-github/`).

### 📚 Docs em paridade (skills personalizadas)
- **Sincronizados `UFVAI-v0.6.9/` → `ufvai-github/`:** `AGENTS.md` + `agents/AGENTS.{pt,en,es,fr,zh}.md` + `agents/README.md` — todos agora com §2.1.0, linha `cep-ufv`, ética atualizada, cabeçalhos multilíngues com recall 4b.
- **Fix versões incorretas:** frontmatter/rodapés `0.6.17` → `0.6.19` (código já era `0.6.18` no staging); `Dockerfile` estável `0.6.9` → `0.6.19`; `README.md` (badge, novidades, tabela, citação, BibTeX, rodapé), `MANUAL.md` (cabeçalho, tabela, citação, rodapé), `citacao_pesquisai.md`, `PesquisAI.ipynb`, `pyproject.toml` sincronizados.
- Bump `0.6.18 → 0.6.19` em `pesquisai/__version__.py` (`__version__`, `__release_date__="2026-09-29"`, `__codename__="Menu mobile sem SVG + docs em paridade (skills personalizadas)"`), `pyproject.toml`, `Dockerfile`, `CHANGELOG.md`.

### 📦 Rebuild `.deb` 0.6.19-offline (29/09)
- **Base:** `pesquisai_0.6.17-offline10` extraído; `/opt/pesquisai` atualizado com fonte v0.6.19 (docs, `__version__`, `constants.py` com `cep-ufv` + `custom_skills`, responsivo sem SVG, `index.html`, i18n); `run_fast.py` com merge `setup_custom_skills` (v0.6.18) sobre patches offline (tela loading, portas automáticas); `telemetry.py`/`launch_app.py` offline preservados (versão via `__version__`).
- **Pacote:** `pesquisai_0.6.19-offline_amd64.deb` · 1019K · md5 `df7be1672b18395f652ef558696bc946` · sha256 `695a03f3ba130d8e63d55f761945ccc6d47bbedbac7b18168671668a813da05a` · `Version: 0.6.19-offline` · `Installed-Size: 3240` · 0 `__pycache__`/`.pyc` · perms 755/644.
- **Validação:** `py_compile` merged OK; `test_version_sync` 5/5; `dpkg-deb` conteúdo OK (`__version__ 0.6.19`, `custom_skills` 6 refs, responsive `display:none` 2 refs, AGENTS `0.6.19`, offline patches 25+3 refs).
- **Destino:** `UFVAI-v0.6.9/debs/` + `ufvai-github/debs/` (anteriores preservados); `debs/README.md` atualizado (pacote + SHA + tabela + citação).

## [0.6.18] — 2026-09-19 — 🧩 Skills personalizadas do usuário

### 🧩 Nova pasta persistente de skills personalizadas
- **Motivação:** permitir que o usuário estenda o UFVAI com skills próprias, sem precisar editar o código ou os repositórios oficiais, e que o agente saiba onde criar skills novas solicitadas em conversa.
- **Pasta:** `backups/skills-personalizadas/` (Colab: `/content/drive/My Drive/PesquisAI/backups/skills-personalizadas/` · Offline: `~/PesquisAI/backups/skills-personalizadas/`). Criada automaticamente no boot, com `README.md` explicativo.
- **Carga a cada boot:** nova `setup_custom_skills()` em `pesquisai/run_fast.py`, chamada logo após `setup_skills()` — varre a pasta e copia cada subpasta válida (contendo `SKILL.md`) para `SKILLS_DIR` (`~/.agents/skills`), onde o OpenCode a injeta no contexto junto com as oficiais. Subpastas sem `SKILL.md` são ignoradas com log informativo (validação fail-closed); falhas nunca interrompem o boot.
- **Instrução ao agente:** nova seção "🧩 Skills Personalizadas do Usuário" injetada no prompt do `pesquisai.md` (via `_inject` dentro de `setup_launch`) com o caminho real da pasta — ao criar uma nova skill a pedido do usuário, o agente grava-a obrigatoriamente nessa pasta e informa que ela entra em vigor no próximo boot.
- **Documentação:** `AGENTS.md` ganhou seção §2.1.0 com as regras da pasta de skills personalizadas.
- Bump `0.6.17 → 0.6.18` em `pesquisai/__version__.py` (`__version__`, `__codename__="Skills personalizadas do usuário (backups/skills-personalizadas carregadas a cada boot)"`), `pyproject.toml`, `CHANGELOG.md`.

## [0.6.17] — 2026-09-01 — ⚡ Memória abre instantânea via menu (singleton + warm-up + prefetch)

### ⚡ O carregamento da memória demorava muito a cada abertura do menu
- **Causa raiz:** cada request `/api/obsidian*` criava um `ObsidianMemory.from_env()` **novo** (6 pontos em `launch_app.py`) → `Searcher` novo → revalidação `mtime`/`size` de todas as notas via Drive FUSE + re-parse do cache BM25 (3,8 MB) + árvore iterada 2× (`include=tree`) + `LinkIndex` reconstruído a cada `stats()`. Qualquer mudança de arquivo (autopilot grava daily constantemente) invalidava o cache → re-leitura + re-tokenização completa. Cache do frontend: só 5 s.
- **Fix backend `launch_app.py` (singleton stale-while-revalidate):** nova camada module-level `_get_memory()` — 1 instância em RAM compartilhada entre requests (índice BM25/LinkIndex construídos 1×); 1ª construção protegida por lock (sem build duplo do warm-up + request); após `_MEM_TTL=30s` devolve dados correntes imediatamente e dispara `_kick_memory_rebuild()` em background (menu **nunca** bloqueia esperando o Drive). Os 6 endpoints (`/api/obsidian`, `/note` GET+POST, `/tree`, `/search`, `/tags`) agora usam o singleton.
- **Warm-up no boot:** `_warm_memory_async()` em `launch()` pré-aquece o índice em thread daemon assim que o servidor sobe — o 1º clique no menu já encontra o índice em RAM.
- **Escritas convergem em background:** save/create/delete de nota agora disparam `_kick_memory_rebuild()` (antes: `invalidate()` deixava o próximo acesso lento; agora a leitura seguinte serve índice stale e converge em background).
- **Fix frontend `launch_app_responsive_v041.py`:** cache do menu 5 s → **120 s** com stale-while-revalidate (>30 s revalida silenciosamente) + **prefetch fire-and-forget** de `/api/obsidian?include=tree` no `window load` (aquece servidor e popula o cache local) → abertura instantânea do menu.
- **Compatibilidade:** endpoints, payload e behavior inalterados; apenas tempo de resposta (µs vs. segundos). Vault desativado (`DISABLED`/`NO_VAULT`) retorna rápido como antes.

### Outros (bump)
- Bump `0.6.16 → 0.6.17` em `pesquisai/__version__.py` (`__version__`, `__codename__="Memória abre instantânea via menu (singleton + warm-up)"`), `pyproject.toml`, `CHANGELOG.md`.
- **Rebuild `.deb` 0.6.17-offline** (02/09, versão não publicada): fonte 0.6.17 integral (`launch_app.py`, `search.py`, `telemetry.py`, `responsive_v041`), assets corrigidos (`logo-oficial-288.jpg`, `icon.png`, `ufvai-64/128/256.png` — o pacote 0.6.9 só tinha `logo-oficial.jpeg`, quebrando o logo no código novo), `zh_CN.json` + `vendor/marked.min.js` incluídos, `ufvai-app.desktop` + ícones hicolor 64/128/256, docs atualizados (README/MANUAL/CHANGELOG/TELEMETRY/PRIVACY/SECURITY), postinst com reparo ativo de permissões (lição 0.6.9-2) e normalização 755/644. Validado: 14/14 md5 = canônica · py_compile 28 arquivos · bash -n 6 scripts · 0 `__pycache__` · 0 aninhamento · sha256 `9804297a…69f1`.
- **Docs sincronizados em 0.6.17:** `AGENTS.md` + `agents/AGENTS.*.md` ×5 (frontmatter/rodapés 0.6.13→0.6.17, canônica + GitHub), `README.md` (badge, Novidades 0.6.14–0.6.17 + histórico consolidado 0.6.x, BibTeX, citação), `MANUAL.md` (cabeçalho, citação, metadados, histórico 0.6.11–0.6.17), `pyproject.toml` da raiz do Drive (0.6.9→0.6.17).

## [0.6.16] — 2026-09-01 — 🐛 Fix retorno: 1 linha por clique (remove heartbeat duplicado)

### 🐛 No retorno o e-mail era enviado 2-3 vezes (linha duplicada na planilha)
- **Causa raiz (v0.6.14):** ao detectar `prof.accepted && prof.terms_version===_TV` (usuário já registrado), o frontend disparava `_heartbeat()` imediato **+** `setTimeout(_heartbeat, 2500)` (duas linhas `usuario_ativo`) **e** o clique em "Continuar" disparava terceiro `_heartbeat()` — 2-3 linhas por retorno.
- **Fix frontend `launch_app_responsive_v041.py`:** removidos os dois disparos automáticos ao exibir `welcome-overlay`; `POST /api/access` (flag `usuario_ativo` + IP) agora só é chamado no **clique** em "Continuar". Novo guard `var _heartbeatSent=false` em `_heartbeat()` impede duplo clique acidental — exatamente **1 linha por retorno**, conforme solicitado: "basta uma vez quando o usuário clicar no retorno".
- **Backend `launch_app.py` / `telemetry.py`:** inalterados — já aceitam `ip` do cliente (ipify) e gravam `flag=usuario_ativo`; Apps Script `APPS_SCRIPT_PLANILHA_CONTATO.gs` já com 8 colunas.

### Outros (bump)
- Bump `0.6.15 → 0.6.16` em `pesquisai/__version__.py` (`__version__`, `__codename__="Retorno registra 1 linha apenas no clique"`), `pyproject.toml`, `CHANGELOG.md`.

## [0.6.15] — 2026-09-01 — 🐛 Prompt inicial respeita idioma detectado do sistema/navegador

### 🐛 Prompt inicial sempre em português, mesmo com sistema/navegador em inglês
- **Causa raiz:** `_current_lang = "pt_BR"` fixo (truthy) → `_build_ttyd_cmd(lang=None)` fazia `PESQUISAI_LANG or _current_lang or _detect_system_lang()` e **nunca** alcançava `_detect_system_lang()`. `launch()` chamava `start_ttyd()` **antes** de `start_wrapper_server()` que faria a detecção — ordem errada. No Colab `LANG=en_US.UTF-8` (confirmado `env | grep LANG`), mas ttyd iniciava `Olá! (Dica: ...)` em pt.
- **Fix backend `launch_app.py`:** `_current_lang` inicia `""` (vazio) para permitir detecção; novo helper `_ensure_lang_initialized()` (prioridade: `~/.config/pesquisai_lang` > `PESQUISAI_LANG` env > `_detect_system_lang()` > persiste) chamado em `launch()` **antes** do 1º `start_ttyd()` e em `start_wrapper_server()` (idempotente). `_build_ttyd_cmd` agora detecta corretamente quando `_current_lang` vazio. Normalização via `_LANG_MAP` e `print("🌐 Idioma detectado")` mantidos.
- **Fix frontend `launch_app_responsive_v041.py`:** `window.load` compara `GET /api/lang` (backend) com `getCurrentLang()` (navegador: `?lang` > cookie > `localStorage` > `navigator.language`). Se divergir e `LANGS` válido, chama automaticamente `setLang(_currentLang)` uma vez por sessão (`sessionStorage "ufvai_lang_synced"`) — corrige instalações antigas onde backend ficou preso em `pt_BR` por causa do bug. UI já ficava correta (via `applyLang`), mas terminal precisava do restart para saudação.

### Outros (bump)
- Bump `0.6.14 → 0.6.15` em `pesquisai/__version__.py` (`__version__`, `__codename__="Prompt inicial respeita idioma detectado"`), `pyproject.toml`, `AGENTS.md` e `agents/AGENTS.*.md` (5 idiomas), `README.md`/`MANUAL.md` badges.
- Frontend ipify (0.6.14) preservado; detecção de idioma independe de IP.

## [0.6.14] — 2026-09-01 — 🐛 Fix IP localhost (ipify client-side) + todo acesso logado

### 🐛 IP ainda registrava 127.0.0.1 (localhost do Colab)
- **Causa raiz (confirmada em produção 2026-09-01 19:21):** `GET /api/access` e `POST /api/consent` liam `X-Forwarded-For`/`X-Real-IP`/`Forwarded`, mas o proxy do Google Colab **não injeta** esses headers na conexão `localhost:8001` — `candidates=[]` → fallback `handler.client_address[0]` = `127.0.0.1`. O `contato.log` provou: `ip=127.0.0.1` em `novo_contato` e `forward iniciado … ip=127.0.0.1`.
- **Fix `launch_app.py`:** `_get_client_ip(handler, client_ip=None)` agora aceita IP enviado pelo cliente (parâmetro `client_ip`). Quando o IP do cliente for público (`!_is_private_ip()`), é **preferido** sobre a cadeia de headers. `POST /api/access` e `POST /api/consent` extraem `ip`/`client_ip`/`clientIp` do JSON do body e passam a `_get_client_ip(self, client_ip=_body_ip)`. Log de diagnóstico quando IP ainda é privado (`logger.warning` com `candidates`+`headers`+`client_address`).
- **Fix frontend `launch_app_responsive_v041.py`:** captura IP público via `https://api.ipify.org?format=json` (CORS, sem chave) no carregamento (`__UFVAI_CLIENT_IP__`), fallback `https://ipinfo.io/json` após 1,8s. `_post()` (Termos) e `_heartbeat()` (`/api/access`) agora enviam `payload.ip = __UFVAI_CLIENT_IP__` quando disponível. Sem IP, backend ainda usa headers (offline/local).

### 🐛 Todo acesso de usuário já registrado deve ir para a planilha (flag `usuario_ativo`)
- **Causa:** `fetch("/api/access", {body:"{}"})` só era chamado no **clique** do botão "Continuar" do overlay "Bem-vindo de volta". Se o usuário apenas recarregasse a página sem clicar (ou se o JS falhasse), nenhum heartbeat era enviado. Requisito do projeto: **todo acesso** (cada carregamento da UI) deve gerar linha na planilha com `flag=usuario_ativo`.
- **Fix frontend:** `_heartbeat()` extraído (envia `ip` do cliente). No `fetch("/api/consent")` que detecta `prof.accepted && prof.terms_version===_TV` (usuário já ativo), após `_showWelcome()` dispara ` _heartbeat()` imediatamente **e** `setTimeout(_heartbeat, 2500)` (segunda tentativa após ipify resolver). O clique em "Continuar" também chama `_heartbeat()` (idempotente — duas linhas por acesso são aceitáveis; anti-abuso `MAX_ROWS=5000`).
- **Fix backend `launch_app.py`:** `POST /api/access` agora lê `ip` do body e o repassa a `notify_active_user(_cip)`; `POST /api/consent` idem. `telemetry._read_profile()` já cai no backup persistente (fix v0.6.13), então mesmo com `~/.config` efêmero o heartbeat encontra o e-mail.

### Outros (bump)
- Bump `0.6.13 → 0.6.14` em `pesquisai/__version__.py` (`__version__`, `__release_date__="2026-09-01"`, `__codename__="Fix IP localhost + todo acesso logado"`), `pyproject.toml`, `AGENTS.md` e `agents/AGENTS.*.md` (5 idiomas), `README.md`/`MANUAL.md` badges.
- Apps Script `APPS_SCRIPT_PLANILHA_CONTATO.gs` inalterado (já trata `name`+`ip`+`flag`); planilha já tem 8 colunas.

## [0.6.13] — 2026-09-01 — 🐛 IP real do cliente + heartbeat "usuario_ativo" na revisita

### 🐛 IP coletado era 127.0.0.1 (localhost do Colab)
- **Causa:** `_get_client_ip()` lia `X-Forwarded-For` pegando o PRIMEIRO item da cadeia e, sem header, caía em `handler.client_address[0]` = `127.0.0.1` (conexão local do proxy do Google). A planilha registrava sempre `127.0.0.1`.
- **Fix `launch_app.py`:** novo `_get_client_ip()` v0.6.13 percorre a cadeia `X-Forwarded-For` da **DIREITA para a esquerda**, saltando IPs privados/loopback via helper `_is_private_ip()` (prefixos IPv4 privados 10./172.16-31./192.168., link-local 169.254., CGNAT 100.64., reservados + IPv6 `::1`/`fe80:`/ULA `fc`/`fd`), devolvendo o **primeiro IP público** — o proxy do Google Colab injeta o IP real do navegador nessa cadeia.
- **Headers extras:** `X-Real-IP`, `CF-Connecting-IP`, `True-Client-IP`, `X-Forwarded`, `X-Cluster-Client-IP` e `Forwarded` (RFC 7239 `for=`); fallback em cadeia → `client_address`. Nunca retorna vazio (se tudo for privado, devolve o primeiro candidato).

### 🐛 Revisita de usuário já registrado não gravava na planilha
- **Causa:** o e-mail ficava em `~/.config/ufvai_profile.json` (efêmero — reset da VM do Colab apaga). Em sessão nova, o GET `/api/consent` achava o usuário no backup persistente (`backups/ufvai_consentimento.json` no Drive) e mostrava "Bem-vindo de volta", mas o heartbeat `POST /api/access` → `telemetry.notify_active_user()` lia só o perfil efêmero → e-mail vazio → `SKIP` → nada gravado.
- **Fix `telemetry.py`:** novo `_persisted_profile_path()` (espelha `launch_app._consent_backup_file()`: `/content/drive/My Drive/PesquisAI/backups/ufvai_consentimento.json` no Colab · `~/PesquisAI/backups/` offline) e `_read_profile()` agora **cai no backup persistente** quando o perfil local não tem e-mail — preenche `email`, `email_sha256` e `name`. `notify_active_user()` (flag `usuario_ativo`) volta a gravar a revisita na planilha; `_forward_contact` também se beneficia.

### Outros (bump)
- Bump `0.6.12 → 0.6.13` em `pesquisai/__version__.py` (`__version__`, `__release_date__="2026-09-01"`, `__codename__="IP real do cliente + heartbeat usuario_ativo na revisita"`), `pyproject.toml`, `AGENTS.md` e `agents/AGENTS.*.md` (5 idiomas), `README.md`/`MANUAL.md` badges.
- Sem mudanças de frontend (`launch_app_responsive_v041.py` inalterado) nem Apps Script (`webhook-contatos.gs` já trata flag `usuario_ativo`).

## [0.6.12] — 2026-09-01 — 📱 Fix preview responsivo

### 📱 Memória — preview no mobile
- **Bug:** preview markdown não aparecia no responsivo (`max-width: 767px`) — `#memory-preview` tinha `display:none` + `flex:1` mas sem `min-height`/`overflow` adequado no layout `flex-direction: column`, ficando com altura 0 em `#memory-editor-body` (`min-height:0`).
- **Fix CSS `launch_app_responsive_v041.py`:** `@media (max-width:767px)` agora define `#memory-editor-pane {flex:1; min-height:0; display:flex; flex-direction:column}`, `#memory-editor-body {flex:1; min-height:0; overflow:hidden}`, `#memory-editor {min-height:120px; flex:1 1 40%}`, `#memory-preview {min-height:150px; flex:1 1 60% !important; overflow-y:auto !important; display:block !important}` + regras para garantir visibilidade.
- **Fix JS:** `onEditorInput()` agora atualiza live preview também em `preview` (`if (_memoryTab === "split" || _memoryTab === "preview") renderPreview()`), antes só em `split` — digitar no mobile com aba Preview agora reflete instantaneamente.


## [0.6.11] — 2026-09-01 — 🐛 Hotfix memória — isoformat cache BM25

### 🐛 Correção crítica — `AttributeError: 'str' object has no attribute 'isoformat'` (Minha memória não carregava)
- **Causa:** `pesquisai/obsidian/search.py` `Searcher._load_from_cache()` reconstruía `NoteMetadata` com `created=str(...)` / `updated=str(...)` (string) em vez de `date`. Ao exibir a árvore da memória (`GET /api/obsidian/status?include=tree` e `/api/obsidian/tree`/`/note`), `launch_app.py` chamava `note.metadata.updated.isoformat()` e quebrava quando o cache BM25 estava ativo (`cache HIT`).
- **Fix `search.py`:** `import datetime as _dt` + `from .models import _parse_date`; agora `created=_parse_date(...) or _dt.date.today()` e `updated=_parse_date(...) or _dt.date.today()` — converte ISO `YYYY-MM-DD` e também ISO datetime `YYYY-MM-DDTHH:MM:SS±TZ` corretamente.
- **Fix `models.py` `_parse_date`:** robustez para ISO 8601 completo — tenta `date.fromisoformat`, `datetime.fromisoformat`, depois formatos legados `%Y-%m-%d` etc.; aceita `date`, `datetime` e `str`; `datetime` → `.date()`.
- **Fix `launch_app.py` / `pesquisai/launch_app.py` (defensivo):** novo helper `_safe_isoformat(v)` que aceita `str` (cache antigo), `date`, `datetime` e `None`; trocadas 4 ocorrências de `note.metadata.updated.isoformat() if ... else None` por `_safe_isoformat(...)` para nunca mais quebrar mesmo com cache stale.
- **Cache:** `vault/embeddings_cache/bm25_cache.json` (3,9 MB, 248 notas) regenerado com `date` correto; validado `type=date`, `isoformat()` OK, `cache_hit=True` (~0,2s) e inválido stale removido. Hot-patch aplicado no kernel vivo via `jupyter_client` sem reiniciar o Colab.

### Outros (bump)
- Bump `0.6.10 → 0.6.11` em `pesquisai/__version__.py` (`__version__`, `__release_date__="2026-09-01"`, `__codename__="Hotfix memória — isoformat cache BM25 + _parse_date ISO robusto"`), `pyproject.toml`, `AGENTS.md` e `agents/AGENTS.*.md` (5 idiomas), `README.md`/`MANUAL.md` badges.


## [0.6.10] — 2026-09-01 — 🚀 Memória otimizada + nome+IP + responsiva mobile

### Memória — otimização para muitas notas (backend BM25 + cache)
- **Cache em disco** (`vault/embeddings_cache/bm25_cache.json`, JSON atômico, 3,8 MB para 247 notas): `Searcher.rebuild()` tenta `HIT` validando `mtime`+`size` por arquivo com tolerância 1s para FUSE do Drive; `HIT` carrega 247 notas em ~0,2s sem re-tokenizar (~145k tokens) vs `MISS` 1–2s. Stats inclui `cache_hit`.
- **Frontend memória**: paginação (`_memorySearchLimit` 50 → “Mostrar mais (X restantes)”), debounce 150→200 ms, e busca BM25 server-side para `q≥3` (`GET /api/obsidian/search?q=&limit=20` com snippet/score) mesclada ao filtro substring cliente; ranking BM25 (título 3.0 > tag 2.5 > wikilink 2.0 > corpo 1.0) superior ao `includes()` puro.
- **Responsiva mobile** (requisito 2026-09-01): `#memory-overlay` com media `@768px` (sidebar 300px → 100% / 38vh, coluna única, borda inferior), `@479px` (100vw/100vh sem radius), alvos ≥44px, debounce e `visualViewport` para teclado não cobrir campo.

### Tela de Termos — campo Nome ao lado do e-mail + IP
- **Layout** flex row `t-row` (Nome `flex:1 1 160px` + E-mail `flex:1.2 1 180px`, `flex-wrap:wrap`): lado a lado no desktop, coluna no mobile; nota LGPD atualizada para “nome e e-mail + IP”.
- **Validação** `_validName` (2–100, letras acentuadas/espaço/'/-) e `_validMail`; `btn` habilita só com `chk && okMail && okName`; autofill-watch cobre ambos; `visualViewport` revela campo focado; erros separados (`err` vs `errName`).
- **JS** `var _TV="6"` (TV 5→6 força re-consentimento), `_post(accepted,analytics,contactEmail,contactName)` com `contact_name`, `profName` no `fetch /api/consent` (pré-preenche `t-name`+`t-email`), `welcome` exibe “Nome — e-mail” e `Se não é você` devolve ambos; GA `localStorage("ufvai_terms_version")==="6"`.
- **Backend** `telemetry.py`: `contact_status()` expõe `has_name`/`name_masked`, `_valid_name()`, `save_contact(email,name,ip)` grava `name` em `ufvai_profile.json` e encaminha `name`+`ip` via `_forward_contact(...,name,ip)` (+fallback lê perfil), `notify_active_user(ip)`; `launch_app.py`: helper `_get_client_ip` (X-Forwarded-For > X-Real-IP > remote_addr), `_read_consent_profile()` normaliza `name`/`nome`, `/api/access` captura IP, `/api/consent` exige `contact_name` quando `accepted`, valida e grava `name`/`ip` em `backups/ufvai_consentimento.json` (além de `email_sha256`), GET expõe `profile.name/nome/ip`.
- **Planilha** Apps Script v0.6.10: cabeçalho 6→8 cols `Timestamp | Email | Nome | Email SHA-256 | Ambiente | Versão | Flag | IP`; `appendRow` com `name`/`ip`; migração automática (insere col Nome após Email e IP no fim se cabeçalho antigo), freeze + estilo navy #1F3864, `MAX_ROWS` 1000→5000; payload `{name,ip}` no `telemetry._forward_contact`.

### Outros
- `pyproject.toml` / `__version__.py` bump 0.6.9→0.6.10 (codename + release_date 2026-09-01), `__version__` usado no badge da UI.
- `vault/embeddings_cache/bm25_cache.json` já validado (247 notas, 19k df).


## [0.6.9-6] — 2026-08-25 — 🔧 Offline completo: tudo no .deb + porta blindada (só .deb, Colab inalterado)

### Offline — tudo dentro do .deb (100% offline)
- **Wheels bundle**: `wheels/` com 27 wheels (cryptography 50, requests, bs4, pyyaml, google-api-python-client + deps, httplib2, etc. — 22 MB) copiados para `/opt/pesquisai/wheels` no `.deb`; `postinst` tenta `pip install --no-index --find-links=/opt/pesquisai/wheels` primeiro (offline), só então tenta `pip` online como fallback. Adeus `pip` sem rede.
- **Backup dir fix**: `launch_app.start_wrapper_server()` agora detecta `Drive sem escrita` (via `os.access` + `get_default_vault_path()` local) e usa `~/PesquisAI/backups` em vez de `/content/drive/.../backups` (antes ficava no Drive mesmo após fallback do vault). Log agora mostra `~/PesquisAI/backups` offline.

### Offline — porta blindada
- **Bind `0.0.0.0` + `::`**: `UFVAI_BIND_HOST` padrão agora `0.0.0.0` (antes `127.0.0.1` offline) + listener IPv6 em `::` (antes só `::1` quando `127.0.0.1`). Resolve `localhost → 127.0.1.1` (Ubuntu) e `::1` preferido pelo Firefox/Chromium; `ERR_CONNECTION_REFUSED` por binding parcial eliminado. Segurança mantida por token `X-UFVAI-Token` + CORS same-origin; `UFVAI_BIND_HOST=127.0.0.1` restaura modo localhost-only se desejado.
- **Tela 8002 liberada com Drive montado**: `_early_loading_screen()` agora checa `import google.colab` (Colab REAL) em vez de `os.path.isdir("/content/drive")`; com Drive montado via rclone/ocamlfuse no `.deb` a tela 8002 volta a subir em <3s (antes ficava suprimida, usuário via tela morta).

### Empacotamento
- `.deb` **0.6.9-6** (22 MB wheels inclusos, ~23 MB total, Installed-Size ~23000) rebuild com `wheels/` + perms normalizadas + `postinst` offline-first. `__version__` permanece `0.6.9` (Colab inalterado) — pacote `0.6.9-6`.

## [0.6.9-5] — 2026-08-25 — 🔧 Offline harden (só .deb, Colab inalterado)

### Offline — tela instantânea + fast-fail (restaura 0.5.1.9, visual UFVAI)
- **Tela de carregamento instantânea na porta 8002** (papel #f6f5f0, navy #1f2831, dourado #b29149, logo base64, título UFVAI): sobe em <3s antes de qualquer `apt/pip/git`, abre Chrome --app imediatamente, faz polling de `GET /api/health` via proxy (200 ou 403 com token = vivo) e redireciona para `:8001` com carência de 6s. Flag `~/.ui_already_opened` evita segunda janela do launcher. *Só ativa fora do Colab* — Colab mantém painel único.
- **Fast-fail offline** (`_network_ok()` TCP 443 2,5s): sem rede, pula `apt-get`/`curl opencode`/`pip install`/`git clone` de skills (usa cache/bundle do .deb), eliminando timeouts de 60s ×N que causavam “demora muito” e `ERR_CONNECTION_REFUSED` por falta de feedback.

### Offline — ttyd e /tmp
- **`install_ttyd()` checa `which ttyd`/`/usr/local/bin/ttyd` antes**: bundle do .deb já presente → pula `apt`, evita “Instalando ttyd…” desnecessário offline. Fallback para `~/bin/ttyd` se `/usr/local/bin` sem permissão, garante PATH.
- **`_prepare_ttyd_touch_index()` sem `Permission denied`**: candidatos `~/.cache/ufvai/ttyd_touch_<uid>.html` → `~/PesquisAI/tmp/ttyd_touch.html` → `/tmp/ttyd_touch_<uid>.html` → `/tmp/ttyd_touch.html`; remove stale root-owned antes de escrever; loga debug em vez de warning.

### Offline — memória
- **`discovery.get_default_vault_path()` fallback offline**: se `PESQUISAI_OBSIDIAN_VAULT` do Drive estiver sem escrita e não estivermos no Colab, usa `~/PesquisAI/vault` (evita `status=read_only` quando o Drive está desmontado ou montado read-only). Também adiciona `~/PesquisAI/vault` como último candidato local (depois de `~/Obsidian/PesquisAI`). *Colab inalterado* — validação de Drive permanece idêntica.

### Empacotamento
- `.deb` **0.6.9-5** rebuild a partir da fonte com normalização de permissões (dirs 755/files 644/scripts 755) + validação como `nobody`. `__version__` permanece `0.6.9` (Colab inalterado) — versão do pacote é `0.6.9-5`.

## [0.6.9] — 2026-08-25 — 📜 Termos v2.1: telemetria opt-out · e-mail de ativação · perfil persistente · botão Manual

### Termos de Uso v2.1 (re-consentimento — `_TV=5`)
- **Telemetria ativa por padrão (opt-out)**: base legítimo interesse (**LGPD art. 7º, IX**);
  caixa de telemetria vem **marcada** na tela de Termos; oposição a qualquer momento desliga
  (art. 18, §2º) via caixa ou `UFVAI_TELEMETRY=0`.
- **Sem cookies**: gtag carrega com `analytics_storage:'denied'` — nenhum cookie `_ga` é criado.
- **Coleta resumida aos dados padrão do Analytics**: evento custom `ufvai_session` **removido**;
  canal client-side limitado ao `page_view` padrão.
- **E-mail de ativação obrigatório** (base **art. 7º, V** — execução do serviço): backend devolve
  **400** se o aceite vier sem e-mail válido; eliminação (art. 18) mantida e re-solicitada na
  próxima abertura.

### Perfil persistente e pré-preenchimento
- **Novo arquivo**: `backups/ufvai_consentimento.json` (Colab: no Drive; offline:
  `~/PesquisAI/backups/`) com `{email, email_sha256, analytics, terms_version, accepted_at,
  app_version}` — helpers `_consent_backup_file()` / `_read_consent_profile()`.
- **GET /api/consent** agora inclui `"profile"` → frontend pré-preenche e-mail/checkboxes e,
  se a mesma versão dos Termos já foi aceita, **pula a tela diretamente**.
- Fallback local preservado (`~/.config/ufvai_profile.json`).

### Interface
- **Botão 📘 Manual** ao lado do Dashboard de Saúde; nova rota **`GET /api/manual`** serve o
  `MANUAL.md` local (cadeia de candidatos raiz → fallback GitHub); modal com Recarregar +
  Ver fonte; i18n `manual.*` nos 5 idiomas.
- **Ícones distintos**: Diretrizes do Agente = clipboard-list 📋 · Manual = book-open 📘.
- **Tela de Termos responsiva**: card com `max-height:100dvh` + rolagem interna; media queries
  ≤640px (coluna nos botões, logo 64px, input 16px anti-zoom iOS) e landscape ≤600px.

### Correções
- **DebugView (bug da v0.6.2)**: `UFVAI_TELEMETRY_DEBUG` agora envia `"debug_mode": 1` nos params
  do evento — o antigo parâmetro de URL `&debug_view=1` era ignorado pelo GA4.
- **Logs fora do Drive (Colab)**: `ttyd.log` → `/tmp/ufvai-logs/`; a pasta `logs/` não é mais
  criada no Drive do usuário.

### Documentação
- `docs/TERMS_OF_USE.md` → **v2.1** (§7 reescrito: opt-out art. 7º IX sem cookies + e-mail art. 7º V);
  `PRIVACY.md` (tabela de saída de dados + nota sobre cookie/e-mail); `TELEMETRY.md` ("as três
  condições" → duas; canais revisados).

## [0.6.8] — 2026-08-24 — 🧹 Painel único (zero prints) · reordenação LGPD · planilha de contatos

### Interface
- **Política painel único (Colab)**: todo feedback visual vem só do painel de boot (`_BootPanel`);
  prints verbosos suprimidos (`logger.debug`), warnings httplib2 silenciados, "Mounted at..." do
  Drive oculto; offline mantém prints normais.
- **Reordenação LGPD na tela de Termos**: opcionais (estatísticas + e-mail) ANTES do aceite
  obrigatório; `ufvai_terms_version=4`.
- **Versão na tela de Termos corrigida**: placeholders `{__VERSION__}`/`__UFVAI_VERSION__`
  substituídos por 0.6.8; citação ABNT atualizada.

### Novidades
- **Planilha de contatos automática**: criação via Drive/Sheets API (título "UFVAI — Contatos"),
  Apps Script pronto (`APPS_SCRIPT_PLANILHA_CONTATO.gs`), endpoint injetado no painel Admin e em
  `ufvai.env`; fallback manual documentado (`GUIA_PLANILHA_CONTATOS_0.6.8.md`).

### Empacotamento
- **Rebuild `.deb` 0.6.8-2** (24/08): staging por seleção a partir da fonte; launcher estável
  (5.541 B, Chrome --app/curl-wait); validação md5 49 arquivos = fonte; versões 0.6.5-1 e 0.6.8-1
  **vetadas** (launcher regressivo/contaminação por aninhamento).


## [0.6.7] — 2026-08-23 — 🖼️ Tela de carregamento do Colab no tema da logomarca · ✉️ Canal de contato configurável pela UI

### Interface
- **Barra de carregamento desde o primeiro segundo (Colab)**: a antiga barra escura de setup
  (`progress_bar.py`, card `#0d0f10` com spinner colorido) foi APOSENTADA. Agora existe UM ÚNICO
  painel leve no tema da logomarca oficial — papel off-white `#f6f5f0`, wordmark "**UFV**"
  azul-marinho `#2b2d3a` + "**AI**" dourado `#b8912f/#b8912f`, régua fina e tagline
  "INTELIGÊNCIA ARTIFICIAL" — que nasce ainda na fase de clone do repositório (`PesquisAI.ipynb`
  embute uma réplica mínima com o mesmo display_id) e percorre TODA a inicialização sem reiniciar:
  clone → Drive → dependências → skills → núcleo opencode → chaves → ttyd → interface web → 100%.
  **As mensagens aparecem sempre ABAIXO da barra**, linha a linha (spinner dourado na etapa ativa,
  ✓ na concluída, ✕ em falhas sem abortar o boot), com percentual monotônico (nunca regressivo).
- **Arquitetura da barra contínua**: `progress_bar.show()` e o `launch()` alimentam a MESMA
  instância via novo singleton `launch_app.get_boot_panel()` (mesmo display_id
  `ufvai_boot_panel`) — fim de barras duplicadas/sobrepostas; `begin()` tornou-se idempotente
  (não zera % nem histórico) e `active()` conclui automaticamente o checkpoint pendente ao trocar
  de etapa (nunca dois spinners). Percentuais internos do `launch()` remapeados para continuar
  acima dos estágios do setup (82→99→100). Renderização por `display_id`/`update_display`
  (uma única saída atualizada); fora do Colab tudo vira no-op/fallback ASCII legado.
- **Botão de lançamento no tema da marca**: card claro contínuo com a LOGO REAL embutida em
  base64 (`assets/logo-oficial-288.jpg`, offline-safe, com fallback wordmark CSS) NO LUGAR do
  antigo texto "✨ UFVAI pronto"; botão em pílula dourada com tipografia navy "ABRIR O UFVAI".
  O badge verde separado "✨ UFVAI pronto!" não é mais exibido no Colab (o painel finaliza em
  100% dentro do próprio painel); fora do Colab mantém-se o print equivalente. Mantidos a classe
  `.pesquisai-launch` (compat) e cuidados de a11y (`:focus-visible`, `prefers-reduced-motion`).
- **`PesquisAI.ipynb` atualizado**: rebrand UFVAI (título, instruções, citação ABNT v0.6.7),
  removido o antigo aviso textual "⏳ PesquisAI — iniciando..." e o `clear_output()` que apagava
  a saída; o notebook agora abre com o painel da logomarca já na clonagem (~5%) e entrega o
  comando para `main.run()`, que continua a mesma barra até o botão final.

### Telemetria
- **URL de contato no painel 📊 Telemetria (Admin)**: novo campo opcional onde o mantenedor cola
  a URL HTTPS que receberá os e-mails de contato opt-in (ex.: Apps Script → Planilha Google).
  Sem editar arquivos nem variáveis de ambiente; grava em `~/.config/ufvai_telemetry.json`
  (chmod 600) e aplica no processo na hora. Prefill da URL efetiva ao abrir o painel +
  indicador de status/origem (env × painel). Deixar vazio = usuários não são encaminhados.
- **`save_admin_config()` parcial**: cada campo é independente — dá para salvar só o canal de
  contato sem redigir ID/Secret do GA4 (que nunca são devolvidos pela API); campo em branco =
  mantém o valor já salvo (secret não é mais apagado por acidente ao re-salvar).
- **Validações**: URL de contato exige `https://` (localhost liberado para teste); mensagem de
  erro específica quando ID/Secret ficam incompletos numa edição parcial do GA4.
- **Docs**: TELEMETRY.md §Passo 9 reescrito — Opção A recomendada = Planilha + Apps Script
  (Google, grátis, passo a passo de 3 min + dica de e-mail via MailApp) · Opção B avançada =
  webhook self-hosted open-source (Gotify/ntfy/Flask).

### Técnico
- `telemetry.py`: `_contact_endpoint()` (env > arquivo), `contact_status()` com
  `contact_endpoint_source`, `masked_state()` expõe `contact_endpoint_url` só ao painel Admin;
- `launch_app.py`: `/api/admin/telemetry` POST aceita `contact_endpoint`;
- UI (`launch_app_responsive_v041.py`): campo `tel-contact` + status dinâmico + envio no POST.

### Boot visual (v0.6.7, 2026-08-23)
- `launch_app.py`: `_UFVAI_ICO_SVG` + `_UFL_CSS` + classe `_BootPanel` (begin/active/done/fail/
  finish) integrada ao `launch()` com try/except que marca ✕ no checkpoint e re-levanta a exceção;
  `show_launch_button()` reescrito; import de `update_display`; testes em `tests/test_boot_panel.py`.


## [0.6.6] — 2026-08-22 — 🖼️ Favicon UFVAI (incl. Colab) · ✉️ Contato opt-in LGPD

### Interface
- **FAVICON na interface**: `<link rel="icon">` (ico.svg) + PNG 64 fallback + apple-touch-icon no
  `<head>` do wrapper; nova rota `/favicon.ico` (mesma whitelist de assets, offline-safe). No Colab,
  script injeta os favicons com o prefixo do pathname do proxy (`/proxy/8001/`) — links absolutos
  `/assets/…` quebravam sob o proxy; o logo da tela de Termos migrou para caminho relativo (agora
  também aparece no Colab).

### Contato opt-in (e-mail) — para o desenvolvedor, com base legal LGPD
- **Tela de Termos**: campo opcional de e-mail com finalidade declarada (contato/novidades),
  validação client-side e aviso de privacidade inline. Termos v3 → re-consentimento dos usuários.
- **LGPD art. 7º I**: consentimento livre/informado/inequívoco, campo em branco por padrão;
  gravação local em `~/.config/ufvai_profile.json` (chmod 600) com SHA-256 e carimbo do consentimento.
- **GA4 NUNCA recebe o e-mail** (Termos do Google proíbem PII, mesmo com hash): vai apenas o evento
  contador `contact_optin`, sem conteúdo.
- **NOVO `UFVAI_CONTACT_ENDPOINT`** (env/ufvai.env): se o desenvolvedor configurar endpoint próprio
  HTTPS (ex.: Apps Script), o app faz POST `{product, email, email_sha256, environment, sent_at}` —
  canal direto e separado do canal analítico.
- **Direitos do titular**: eliminação via campo esvaziado, remoção do arquivo ou
  `POST /api/contact/delete`; estado mascarado exposto em `GET /api/consent` (`contact.email_masked`)
  e no painel Admin (`masked_state`).

### Docs & versão
- PRIVACY.md: seção "E-mail de contato (v0.6.6)" · TELEMETRY.md: Passo 9 (endpoint Apps Script de
  exemplo, tabela admin vê/nunca vê atualizada) · bump 0.6.5 → 0.6.6 em `__version__.py`,
  `pyproject.toml`, `Dockerfile`, `install-offline.sh`, AGENTS.md + agents (5 idiomas).

### Validação
- `py_compile` OK · pytest completo · smoke dos endpoints `/favicon.ico`, `/api/consent`
  (com/sem contato), `/api/contact/delete` e validação de e-mail inválido.

## [0.6.5] — 2026-08-22 — 🔐 Terminal à prova de travamentos · 🖥️ /api/ttyd_ready · 🚀 Splash de carregamento

### Terminal — kill cirúrgico por árvore
- **CRÍTICO corrigido**: o ttyd agora é o **líder do próprio grupo de processos** (`start_new_session=True`) e é rastreado em `_TTYD_PROC`. `_stop_terminal()` mata a árvore inteira (ttyd + bash + opencode) com **um único `killpg`** — acaba o antigo `pkill -f opencode` **global**, que matava qualquer processo com "opencode" na cmdline (inclusive o agente hospedeiro).
- Fallback determinístico: `pkill -9 -x ttyd` (COMM **exato**; nunca `-f` — o `-f` casava `bash -i -c 'ttyd …'` e processos-host). Órfãos de versões antigas tratados com padrão ancorado (`^-i -c .*opencode`).
- `kill_previous()` do boot migrado para `pkill -x`; o temporário do touch-handler (`--index`) também usa terminate/wait → killpg → `pkill -x`.
- `_build_ttyd_cmd()` extraído de `start_ttyd()` para permitir retry determinístico.

### UI — splash de carregamento + polling de prontidão
- **NOVO endpoint `GET /api/ttyd_ready`** (`_wait_port_open` real, timeout 1,2 s): o frontend faz polling **antes de apontar o iframe** — fim do `ERR_CONNECTION_REFUSED` visível no boot, na troca de idioma e na restauração de sessão.
- **NOVO splash de boot** (`#boot-splash`): logomarca UFVAI (asset local `/assets/logo-oficial-288.jpg`), spinner, status em 3 estados (`boot.starting`/`boot.restarting`/`boot.restoring`), erro com indicação do log (`boot.timeout`) e botão **Recarregar** (`boot.retry`) — **i18n completo nos 5 idiomas** (pt/en/es/fr/zh; antes só pt_BR, com fallback hardcoded).
- Troca de idioma e restauração de sessão agora mostram splash imediato e **retorno honesto**: se a porta não abre, erro visível em vez de reload às cegas (causa do refresco em terminal morto).

### Correções relacionadas
- `launch_app_responsive_v041.py`: splash delay/retry para o iframe; delegação ao boot quando o ttyd está morto.

### Docs & versão
- Bump **0.6.4 → 0.6.5** em `__version__.py`, `pyproject.toml`, `Dockerfile`, `AGENTS.md` + `agents/AGENTS.*.md` (5 idiomas; `AGENTS.zh.md` resgatado do v0.6.0 — titre/rodapé agora v0.6.5), `install-offline.sh`.
- `docs/RELEASE_NOTES_v0.6.5.md` nova.

### Validação
- `py_compile` OK · **pytest completo** (workaround `--override-ini="addopts="`) · smoke do wrapper (i18n do splash nos 5 idiomas + endpoints) · `md5 deb ↔ fonte` conferido.


## [0.6.4] — 2026-08-22 — 🪪 Marca UFVAI completa · 🎨 Temas UFVAI no terminal · 🖼️ Logo oficial · 📜 Termos v2

### Marca (PesquisAI → UFVAI)
- **AGENTS.md + `agents/AGENTS.{pt,en,es,fr,zh}.md`**: o agente agora se apresenta como **UFVAI** — frontmatter (`name`, versão 0.6.4, cor dourada `#b29149`), título, identidade (§1), capacidades, memória, limitações e rodapé. IDs técnicos preservados: `PESQUISAI_OBSIDIAN_VAULT`, caminhos `~/PesquisAI` e `/content/drive/My Drive/PesquisAI/`, tags `pesquisai/*`, pacote Python `pesquisai`.
- Agente gerado pelo OpenCode (`run_fast._setup_theme_and_agent()`): `name: UFVAI` + cor dourada.
- Strings de UI do wrapper (i18n inline em 5 idiomas): "Memória/Memory/Mémoire UFVAI", "Regras e princípios do UFVAI".

### Terminal — temas harmonizados com a identidade UFVAI
- **Temas do TUI regenerados** (`pesquisai.json` / `pesquisai-light.json`): escuro com fundos azul-noite `#141c24/#1f2831` (rail da marca), acento primário **dourado** `#d4b56a/#b29149`, amarelo UFV `#D1A705`, secundário azul-aço dessaturado; claro com papel quente e texto azul-escuro `#1f2831`. Azul antigo do PesquisAI (`#4fc3f7`) eliminado de todos os pontos.
- **Wrapper HTML**: o fallback JS do `applyWrapperTheme()` sobrescrevia o CSS canônico com teal antigo (`#157a73`/`#46a39b`) — agora reflete a paleta UFVAI; tema claro dourado sobre papel quente (antes teal/laranja); anti-flash e `theme-color` em `#141c24`; banner Colab ("ABRIR O UFVAI") em gradiente dourado.

### Abertura — logo oficial + fim do modal antigo
- **REMOVIDO o onboarding antigo do PesquisAI** (`welcome-hint`: logo do GitHub + botão "Começar") que empilhava com a tela de Termos. A tela de **Termos de Uso é a única abertura**.
- **Logomarca oficial** (`logo_8x8cm_300dpi.jpg`, otimizada p/ 288 px / 6,9 KB) exibida na tela de Termos via nova rota **`/assets/*` offline-safe** (whitelist estrita + traversal guard; procura no diretório do código → `/opt/pesquisai/assets` → `~/PesquisAI/assets`; `onerror` esconde graciosamente). Resolve o bug do logo que dependia de `raw.githubusercontent.com`.

### Legal
- **Termos de Uso v2.0** (`docs/TERMS_OF_USE.md`): definições, distinção licença×termos, integridade acadêmica alinhada à **Portaria CNPq nº 2.664/2026** e normas UFV (**POSIC — Resolução Consu/UFV nº 12/2024**, Código de Ética — Res. Consu nº 04/2024), LGPD completa (consentimento art. 7º I, direitos art. 18, transferência internacional arts. 33–36), foro Viçosa/MG, cessação e contato/DPO.
- **PRIVACY.md**: seção "Seus direitos" reescrita com os 9 direitos do art. 18, canal do titular e DPO UFV (`dgi.ufv.br/privacidade`), nota sobre pseudonimização do `client_id` e registro das operações (art. 37).
- **LICENSE**: titular atualizado para "Gustavo Bastos Braga — Universidade Federal de Viçosa (DER/UFV)" + bloco **NOTICE** (marca UFVAI, Termos v2.0, integridade científica).
- **Overlay de Termos** atualizado (menção à Portaria CNPq e LGPD) e **re-consentimento forçado** (`ufvai_terms_version = 2`).

### Telemetria — canal duplo + painel Admin na UI
- **Google tag (gtag.js) client-side** com o ID de medição do admin (`G-CMVTFP2M6F` embutido como default; override por `UFVAI_GA_MEASUREMENT_ID`): rastreia sessões no Colab/local (`page_view`, `ufvai_session` com versão/ambiente/idioma, `anonymize_ip`). **Consent-gate**: só carrega após aceite dos Termos com estatísticas marcadas — sem consentimento não há requisição ao googletagmanager nem cookie `_ga`.
- **Painel 📊 Telemetria (Admin)** na barra superior: estado em tempo real (ativa/inativa/motivo), campos ID de medição + API Secret salvos em `~/.config/ufvai_telemetry.json` (chmod 600, aplicados imediatamente no processo; secret nunca é devolvido pela API). Novos endpoints `GET/POST /api/admin/telemetry` (mesmo token da sessão). Strings i18n nos 5 idiomas.
- `telemetry.py`: `_ga_config()` agora lê env → arquivo local; novas funções `save_admin_config()` e `masked_state()`.
- **TELEMETRY.md §0 — Guia do administrador em 8 passos**: criar propriedade GA4 → fluxo Web → Measurement ID → segredo MP → `~/PesquisAI/config/ufvai.env` (offline) ou `os.environ` (Colab) → validação via DebugView → o que o admin vê × nunca vê → conformidade LGPD operacional.

### Offline
- **install-offline.sh reescrito (v0.6.4)**: marca UFVAI, portas corretas (UI 8001 · terminal 8000), atalho `ufvai` (+ alias `pesquisa` mantido por compatibilidade), modelo comentado de `config/ufvai.env`, verificação de requisitos robusta.

### Validação
- `py_compile` OK · **pytest 202/202** · smoke do wrapper (12 verificações) e dos temas (9) aprovados.


## [0.6.3] — 2026-08-22 — 🔌 Servidor persistente offline · 🎨 Ícone UFVAI no dock

### Correções
- **BUG CRÍTICO (offline) — "conexão recusada" em localhost:8001**: o wrapper HTTP roda em **thread daemon**; ao fim de `run()` a main thread terminava e o interpretador encerrava o processo, matando o servidor segundos depois da inicialização (no Colab não aparecia, pois o kernel permanece vivo). Agora `run_fast._offline_keep_alive()` mantém o processo ativo fora do Colab — encerra com Ctrl+C (foreground) ou `kill $(cat ~/PesquisAI/pesquisai.pid)` (background); `UFVAI_NO_KEEPALIVE=1` desabilita.
- **Regressão restaurada — servidor dual-stack**: o 0.5.x bindava IPv4+IPv6 no loopback justamente porque Chromium/Firefox preferem `::1` ao resolver "localhost"; o hardening v0.6.0 deixou só IPv4. Agora, além do listener principal, sobe um loopback IPv6 (`::1`) adicional quando local.

### Interface
- **Ícone UFVAI no dock**: a janela aberta pelo launcher usa `--class="UFVAI"`, que agora casa com o novo `ufvai-app.desktop` (`StartupWMClass=UFVAI`) e PNGs instalados nos temas hicolor (256/128/64) — a barra/dock mostra a lupa dourada da marca em vez do ícone do navegador. `postinst` instala ícones + desktop entry e atualiza os caches.


## [0.6.2] — 2026-08-22 — ⌨️ Terminal gravável · 🖥️ Launcher app-mode · 📊 Telemetria debug

### Correções
- **BUG CRÍTICO — não dava para digitar no terminal**: o v0.6.0 perdeu a flag `--writable` do ttyd (regressão do hardening) e o terminal ficava **read-only**. Restaurada em `start_ttyd()` e na restauração de sessão (`/api/run_terminal`).
- **Modo offline (.deb) não abria a interface**: o launcher do v0.6.0 apenas imprimia a URL em background, sem feedback. Restaurado o comportamento do launcher v0.5.1.10: espera ativa da porta 8001 via `curl` (até 180 s na 1ª execução), abertura como **app separado** (Chrome `--app` com perfil próprio → Chromium → Firefox → `xdg-open`), PID-file e reabertura da UI se já estiver rodando. Fonte versionada em `debs/launcher/ufvai-launcher.sh`.

### Telemetria
- `UFVAI_TELEMETRY_DEBUG=1` envia os eventos para o **DebugView** do GA4 (tempo real, sem gravar relatórios) — facilita validar a configuração.
- O launcher agora carrega `~/PesquisAI/config/ufvai.env` antes de iniciar: coloque lá `UFVAI_GA_MEASUREMENT_ID` e `UFVAI_GA_API_SECRET` para ativar a telemetria no modo offline.

### Requisitos para a telemetria enviar de verdade (os 3 precisam estar ativos)
1. Credenciais no ambiente: `UFVAI_GA_MEASUREMENT_ID` + `UFVAI_GA_API_SECRET`;
2. Consentimento: checkbox "estatísticas anônimas" marcado na tela de Termos (`~/.config/ufvai_consent.json` → `"analytics": true`);
3. Kill-switch desligado (`UFVAI_TELEMETRY` ≠ `0`).


## [0.6.1] — 2026-08-22 — 🌐 Idioma do sistema · 🔁 Troca de idioma robusta · 🌍 Auto-open offline

### Correções
- **Troca de idioma agora muda a mensagem inicial** (Colab e .deb): o frontend recarregava a página em 700 ms enquanto o backend ainda reiniciava o ttyd (~3–4 s) — o iframe reconectava num terminal morto/antigo e a saudação não mudava. `setLang()` passou a ser `async` (aguarda o POST `/api/lang` com timeout de segurança de 15 s) e o backend só responde depois que a porta do terminal já aceita conexões (`_wait_port_open`, até 12 s).
- **Idioma do SISTEMA detectado na 1ª execução** (`$LANGUAGE` → `$LC_ALL` → `$LC_MESSAGES` → `$LANG` → `locale`): saudação inicial no idioma do usuário (pt/en/es/fr/zh); preferência persistida em `~/.config/pesquisai_lang`. O frontend já usava `navigator.language` como fallback da UI.
- **Modo offline (.deb) abre o navegador sozinho**: launcher roda em background e antes não havia feedback ("parecia não iniciar"). Agora thread daemon espera a porta da UI responder (até 30 s) e abre o navegador (`webbrowser` → fallback `xdg-open`/`open`). Desabilitar com `UFVAI_NO_OPEN=1`.

### Marca
- Banners Colab/console atualizados para UFVAI: "✨ UFVAI pronto!" · "ABRIR O UFVAI".

### Arquivos
- `pesquisai/launch_app.py`: `_detect_system_lang()`, `_persist_lang()`, `_wait_port_open()`, `_auto_open_browser()`; unificação do mapa de idiomas em `_LANG_MAP`; restart do ttyd com espera ativa da porta.
- `pesquisai/launch_app_responsive_v041.py`: `setLang()` assíncrono com await + fallback.
- `pesquisai/__version__.py` / `pyproject.toml`: 0.6.0 → **0.6.1**.


## [0.6.0] — 2026-08-21 — 🏷️ UFVAI · 🔐 Hardening · 📊 Telemetria opt-in · 🇨🇳 zh_CN · 📜 Termos

### Marca
- **Rebrand visual PesquisAI → UFVAI** (wrapper/notebook/assets): paleta dourado `#b29149`/`#D1A705` + azul profundo `#141c24`/`#1f2831`, wordmark **UFV**(700)+**AI**(600) em Montserrat, ícone lupa dourada. Identificadores técnicos preservados (pacote `pesquisai`, pasta Drive `PesquisAI`, endpoints `/api/*`).

### Segurança (auditoria completa — docs/SECURITY_AUDIT_2026-08-21.md)
- **CORS `*` removido** de todos os endpoints; token de sessão obrigatório em `/api/*` (injetado no HTML; patch global de `window.fetch`). Fecha exfiltração de API keys por páginas maliciosas.
- **Sanitização por segmento `&&`**: valida cada comando após `&&` contra a allowlist (fecha RCE pós-&&).
- **`opencode_auth.json` agora é gravado CIFRADO** (Fernet) no Drive; leitura aceita legado plaintext.
- `GET /api/apikey?provider=` retorna chave sempre mascarada; `/api/debug`/`diagnose`/`health` não listam mais nomes de env secrets.
- `/api/restore` com sanitização anti-path-traversal; nome de backup saneado.
- `ThreadingHTTPServer`, cap de corpo (10 MB), rate limit generoso (120/min/IP), headers `nosniff`/`no-referrer`/`SAMEORIGIN`.
- Bind: Colab mantém `0.0.0.0`; local passa a `127.0.0.1` (override `UFVAI_BIND_HOST`).
- `--yolo` **mantido por padrão** (decisão do usuário); desligável com `PESQUISAI_YOLO=0`.
- Bugfix: `/api/run_terminal` aceita `cmd` OU `command` (botão "Restaurar sessão" voltou a funcionar).
- Normalização de 12 escapes JS-regex latentes em strings Python (elimina SyntaxWarning/erro em py≥3.12; saída idêntica).

### Telemetria anônima opt-in
- Novo módulo `pesquisai/telemetry.py` (GA4 Measurement Protocol server-side). Sem consentimento/config não envia nada; kill-switch `UFVAI_TELEMETRY=0`. Zero conteúdo — só contadores. Detalhes: `TELEMETRY.md` e `PRIVACY.md`.

### Termos de Uso
- Tela de aceite obrigatória na 1ª entrada (overlay bloqueante, i18n, links para LICENSE/TERMOS/PRIVACIDADE no GitHub) + endpoint `/api/consent`.

### Internacionalização
- **中文（简体） zh_CN completo**: menu 🇨🇳, detector, saudação do agente, traduções inline + `zh_CN.json`.

### Correções
- Versão sincronizada 0.6.0 (`__version__.py`/`pyproject.toml`/Dockerfile); Dockerfile label corrigido.

---
## [0.5.1.9] - 2026-07-18 - Versão Offline para Linux e atualização do AGENTS.md

### 🚀 Major Changes

-**Instalador offline para Linux**: Instalador em formato .deb para utilização offline do PesquisAI.
- **Reescrita completa do AGENTS.md**: Principal atualização desde a introdução da memória persistente. O documento foi reformulado do zero para maior clareza, consistência normativa, economia de tokens e alinhamento com o código-fonte (`constants.SKILL_REGISTRY`).
- **Nova arquitetura de diretórios**: Introduzida separação oficial entre `vault/` (memória interna do agente) e `outputs-<slug-do-projeto>/` (entregáveis finais organizados por projeto). Isso melhora organização, reprodutibilidade e experiência do usuário final.
- **Fortalecimento de Integridade e Segurança**: 
  - Protocolo completo de defesa contra prompt injection (ignorar, manter tarefa original e avisar usuário).
  - Proteção explícita contra acesso a arquivos de segredos (`keys_store.json` e `keys_encryption_key.bin`).
  - LGPD com "hard stop": interrupção obrigatória de gravação ao detectar dados sensíveis não anonimizados.

### ✨ Improvements

- **Catálogo de Skills**: Totalmente sincronizado com o registry real. Removidas referências infladas ("147+ skills") e adicionados IDs canônicos (`qualitativa`, `grant-finder`, `memorial`, `obsidian-memory`, `BR-DWGD`, `meta-search-br`).
- **Gestão de Memória**: 
  - Frontmatter enriquecido com `updated`, `accessed_at`, `dataset_version`, `evidence_refs` e `source_language`.
  - Atualização automática e obrigatória de `moc/last-state.md` no fim de sessões/tarefas relevantes.
  - Clarificada a condicionalidade do salvamento (obrigatório apenas quando `PESQUISAI_OBSIDIAN_VAULT` está ativa).
- **Regras de Precedência**: Seção dedicada e expandida, blindando integridade (§4.1), proibições de memória (§2.2.1), injeção de prompt e restrições de path traversal.
- **Geração de Arquivos**: PDF agora obrigatório apenas para entregáveis finais (artigos, memoriais, relatórios). Notas internas não geram mais PDF automaticamente.
- **Declaração de Uso de IA**: Agente agora sugere ativamente a inclusão da declaração em entregas acadêmicas finais.
- **Exemplos e Limitações**: Exemplos positivo/negativo mais robustos (incluindo proibição de URLs falsas). Seção de limitações expandida com "Non-goals" explícitos (pareceres médicos/jurídicos, CEP/CONEP, submissão automática, etc.).

### 🛡️ Security & Compliance

- Fechada brecha que permitia edição de notas humanas via `force=True`.
- LGPD reforçada com recusa explícita mesmo diante de insistência do usuário.
- Proteção contra path traversal e vazamento de segredos criptográficos.

### 📋 Documentation

- AGENTS.md agora funciona como fonte canônica de comportamento do agente em runtime.
- Melhoria significativa na legibilidade e na capacidade de manutenção futura.

### 🔄 Outras Alterações

- Alinhamento entre `AGENTS.md`, `docs/INTEGRITY.md`, `docs/OBSIDIAN_MEMORY_MODEL.md` e o código-fonte.
- Redução estimada de ~18–25% no consumo de tokens do prompt do sistema.
- Preparação para futuras features (Workspace de Projetos, Evidence Ledger e Reprodutibilidade) já contempladas na nova estrutura.


---
## [0.5.1.8] — 2026-07-10 — 🐛 3 bugfixes: provider buttons, session restore, backup confirm

### 🔧 Bugfix 1: Provider edit/delete buttons (SyntaxError)

**Problema:** `JSON.stringify(provider)` dentro de `onclick="..."` em uma string Python `"""..."""` gerava SyntaxError. O interpretador Python consumia as aspas escapadas, produzindo JavaScript inválido.

**Correção:**
- Substituído `onclick="editSavedKey(JSON.stringify(provider))"` por `data-provider="..." onclick="editSavedKey(this.dataset.provider)"`
- Mesmo padrão para `deleteSavedKey`
- Sem `JSON.stringify` inline = sem conflito de escapes com a string tripla do Python

**Arquivo:** `launch_app_responsive_v041.py` — função `renderSavedKeys()`

---

### 🔧 Bugfix 2: Session history não atualiza ttyd

**Problema:** O comando `opencode session restore <sessionId>` restaurava os dados da sessão no disco, mas o servidor sempre iniciava um **opencode novo do zero** após o comando (linha 1600 do `launch_app.py`: `bash_cmd = f"{cmd}; {_opencode_bin}; exec bash"`). O terminal nunca refletia a sessão restaurada.

**Correção:**
- Troca do comando para `opencode -s <sessionId>` com `no_fallback: true`
- `no_fallback: true` elimina o `; {_opencode_bin}` — o opencode já inicia **direto na sessão** restaurada
- `setTimeout(() => location.reload(), 2500)` recarrega a página para conectar ao novo ttyd
- Mesmo padrão do endpoint `/api/restore` (backup)

**Arquivo:** `launch_app_responsive_v041.py` — função `_doRestoreSession()`

---

### ✨ Feature 3: Confirmação antes de restaurar backup

**Problema:** `doRestore(file)` executava a importação do backup imediatamente, sem confirmação do usuário.

**Correção:**
- Toda a lógica de `doRestore()` foi envolvida em `pesquisaiConfirm()`
- Usa chave i18n `ui.restore` para o texto do botão
- Cancelar = não executa nada; Confirmar = importa o backup

**Arquivo:** `launch_app_responsive_v041.py` — função `doRestore()`

---

### 🧩 Nova skill: Memorial UFV

- **Nova skill `skill-memorial-ufv`** — Geração automática do Memorial RSC-PCCTAE (Relatório Detalhado → memorial formatado UFV/ABNT)
- Repositório: [github.com/gustavobraga-byte/Memorial_ufv](https://github.com/gustavobraga-byte/Memorial_ufv)
- Fluxo: lê o PDF do Relatório Detalhado RSC emitido pelo sistema oficial da UFV, extrai dados estruturados, gera narrativas longas em linguagem acadêmico-científica e formata conforme normas UFV/ABNT
- Gera saída em `.md` e `.docx` formatado

---

### 🧩 Alterações adicionais no provider flow

- **NOVO `prov-step0`**: Tela inicial do modal de provedores lista as chaves salvas no Drive com botões editar/excluir, antes de mostrar a lista de provedores para adicionar.
- **NOVO botão "Voltar"**: Navegação `prov-step1 → prov-step0` via `provBack()`.
- **NOVO botão "↻ Atualizar"**: No modal de sessões, recarrega a lista sem fechar.
- **Largura do modal de provedores**: 480px → 520px para acomodar os botões de ação das chaves salvas.

---

## [0.5.1.5] — 2026-07-01 — 🧠 Editor de Memória Obsidian no botão 🧠

> **Nota:** v0.5.1.5 foi um hotfix para v0.5.1.4. As versões 0.5.1.6 e 0.5.1.7 foram patches internos não lançados publicamente.

### 🧠 Editor de Memória (Obsidian Memory Editor)

- **Modal split view**: Lista de notas à esquerda + editor markdown com abas Edit / Preview / Split à direita
- **4 endpoints REST novos:**
  - `GET  /api/obsidian/note?path=...` — ler nota crua
  - `GET  /api/obsidian/tree?subdir=...` — árvore agrupada por subdiretório
  - `GET  /api/obsidian/search?q=...` — busca BM25 com debounce 150ms
  - `GET  /api/obsidian/tags` — lista de tags usadas com contagem
- **POST /api/obsidian/note** com 3 ações:
  - `action=save` — sobrescrever nota (force=true para notas humanas)
  - `action=create` — criar nova nota a partir de template
  - `action=delete` — mover para `.trash/` (force=true para notas humanas)
- **Preview markdown** via `marked.js` com destaque de `[[wikilinks]]` e `#tags`
- **Dirty indicator**: Indicador visual de edição não salva
- **20 novas chaves i18n** (`memory.editor.*`) em pt_BR, en_US, es_ES, fr_FR
- **Bugfix**: `from pathlib import Path` faltava — quebrava `tree` endpoint

### 🔧 Hotfix v0.5.1.5

- Botões do editor não funcionavam (SyntaxError JS em string multilinha) — **corrigido**

---

## [0.5.1.3] — 2026-06-30 — 🔌 Conectores de Provedor de IA

- **Bugfix:** `confirmProvider()` crashava com TypeError antes de salvar a API key
- Captura local de `_selProv.id`/`env`/`name` antes de `closeProvider()`
- Verifica `r.ok` e `d.ok` no fetch (antes: sempre exibia "✅ Salvo!")
- `closeProvider()` movido para após o sucesso do salvamento

---

## [0.5.1.2] — 2026-06-30 — 🧠 Botão Memória Obsidian no topbar

- **Overlay de Memória** mostra status (ready/disabled/...) + stats + notas recentes + daily notes
- **Endpoint**: `GET /api/obsidian` (status da memória persistente)

---

## [0.5.1] — 2026-06-29 — 🤖 Obsidian Autopilot (Salvamento Autônomo)

### 🤖 O agente agora SALVA SOZINHO

- **`pesquisai/obsidian/autopilot.py`** (NOVO) — API de alto nível com funções LLM:
  - `recall(query)` — busca no vault antes de responder
  - `save(title, body, tags)` — salva nota após concluir tarefa
  - `save_finding(text, source)` — captura rápida (1 linha)
  - `start_session()` / `end_session(summary)` — log automático
  - `log_skill(id)` / `log_file(path)` — tracking de atividades
  - `auto_init()` — inicializa vault + daily + MOC + sessão
- **`run_fast.py`** (EDITADO) — chama `auto_init()` na inicialização
- **Prompt do agente** injeta instruções de autopilot
- Vault criado automaticamente em `<DRIVE>/PesquisAI/vault/`
- Daily note e MOC raiz criados automaticamente
- **Tudo é no-op** se o vault não estiver disponível
- **Vault SEMPRE no Google Drive** (validação obrigatória)

---

## [0.5.0] — 2026-06-28 — 🧠 Obsidian Second Brain (Long-Term Memory)

- Módulo `pesquisai.obsidian` (8 arquivos, ~1.500 linhas)
- Skill `obsidian-memory` (repositório git separado)
- 10 templates Obsidian (daily, research, literature, session, methodology, datasource, hypothesis, reference, moc, inbox)
- Memória persistente entre sessões via vault no Google Drive
- Busca BM25 offline + backlinks + wikilinks + tags
- Taxonomia de tags `pesquisai/*` (19 tags oficiais)
- **REGRA:** vault SEMPRE no Google Drive (rejeita fora no Colab)
- 71 testes pytest (100% passing) + teste e2e validado

---

## [0.4.2.3] — 2026-06-27 — 🔥 BUGFIX CRÍTICO — Botões do wrapper quebrados

- **🛑 JS BROKEN:** A string tripla `"""..."""` do `launch_app_responsive_v041.py` continha escapes de aspas que Python removia durante a compilação, gerando JavaScript com sintaxe inválida → **TODOS os botões do HTML paravam de funcionar** (SyntaxError no `<script>`)
- ✅ `renderSessions`: `onclick` inline trocado por `data-session-id` + event delegation
- ✅ `restoreSession`: `confirm(...)` com aspas escapadas trocado por `confirm(...chr(34)...)` (concat JS)
- ✅ `escapeHtml`: object literal com aspas trocado por if/else chain
- ✅ Validado: Node.js `--check` passa, 79/79 testes pytest OK

---

## [0.4.2.2] — 2026-06-24 — Ses_10a4+: 6 correções adicionais

- **🖥️ FOOTER PC:** Botão provedor + "Powered by OpenCode" alinhados à direita no desktop (`margin-left: auto`)
- **🧩 SKILLS:** `grant-finder` e `meta-search-br` em `skills/` com links para clonar do GitHub
- **📜 SESSÕES:** `openSessions()` agora faz fetch em `/api/sessions` e popula a lista
- **🌍 LANG:** Ao trocar idioma, ttyd reinicia com saudação no idioma + instrução persistente
- **📦** `__version__.py` movido para `pesquisai/__version__.py`
- **🧹** AGENTS.md: removido `- [link/lien/enlace]` das 4 variantes

---

## [0.4.2.1] — 2026-06-23 — Ses_10a4: 3 correções

- **Tema CLARO:** Contraste corrigido nos 6 modais (`background:#181b1e` fixo → variável CSS `.modal-shell`)
- **Dashboard de Saúde:** `openHealth()` faz fetch em `/api/health` e popula lista com badges de status
- **Modal de Diretrizes:** Renderiza markdown (marked.js + github-markdown-css) ao invés de texto cru

---

## [0.4.2] — 2026-06-22 — Footer Responsivo + AGENTS.md Multilíngue

- Rodapé 100% responsivo (flex-wrap + 2 linhas)
- Modal de Diretrizes com AGENTS.md multilíngue
- Endpoint `GET /api/agents?lang=xx_XX`

---

## [0.4.1] — 2026-06-20 — UI Fixes (Responsivo + Tema + Idioma)

- 6 media queries + hamburger menu
- `toggleTheme()` recarrega iframe ttyd
- Dropdown 4 idiomas (pt_BR, en_US, es_ES, fr_FR)

---

## [0.4.0] — 2026-06-15 — Release Inicial

Primeira release do PesquisAI com:
- Agente de pesquisa científica via OpenCode
- Integração IBGE, DataSUS, dados-brasil, agrobr
- Wrapper HTML com ttyd
- Backup/restore de sessões
- Gerenciamento de provedores de IA
- Tema escuro "pesquisai"
- Suporte a 4 idiomas
