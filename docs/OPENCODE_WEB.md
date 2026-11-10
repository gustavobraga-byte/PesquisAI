# 🖥️ UFVAI v0.7.11-web — interface web do OpenCode no lugar do ttyd

> **Variante da v0.7.11.** A janela principal do UFVAI deixa de exibir o
> terminal `ttyd` e passa a exibir a **SPA oficial do OpenCode**, servida pelo
> próprio motor (`opencode serve`), com a **identidade visual do UFVAI**
> (navy + dourado + creme) injetada por um proxy local.

---

## 1. O que muda

| Antes (v0.7.11) | Agora (v0.7.11-web) |
|---|---|
| iframe aponta para `ttyd` na porta 8000 | iframe aponta para o **proxy da SPA** na porta **8002** |
| interface = TUI dentro do terminal | interface = **web app do OpenCode** (chat, sessões, arquivos) |
| tema = `pesquisai` no ttyd | tema **UFVAI** injetado no web app (`--v2-*`) |
| login = terminal | **Basic auth injetada pelo proxy** (o navegador nunca vê a senha) |

O `ttyd` continua sendo iniciado em segundo plano (porta 8000) como
**fallback** e para os recursos que dependem dele (`/api/run_terminal`,
reinício de idioma, etc.), mas **não aparece** na janela principal.

---

## 2. Arquitetura

```
Navegador
  │  https://<colab>/proxy/8001/        (wrapper UFVAI: topbar, rodapé, modais)
  │      └── iframe https://<colab>/proxy/8002/
  ▼
Proxy UFVAI (pesquisai/ocweb.py, 0.0.0.0:8002)
  │  • injeta Authorization: Basic opencode:<service.json.password>
  │  • repassa /_assets, /icons, /api/* e SSE /api/event
  │  • injeta <style> com a paleta UFVAI + badge
  ▼
OpenCode web (127.0.0.1:<porta do service.json>, só loopback)
```

O proxy lê `~/.local/state/opencode/service.json` a cada requisição. Se o
motor reiniciar (nova porta/senha), ele se adapta sem reiniciar o wrapper.

---

## 3. Como executar

Nada muda no fluxo do Colab: rode a célula de boot da árvore
`UFVAI-v0.7.11-web/` e abra a interface na **porta 8001**. A janela já abre
com a SPA do OpenCode.

No `.deb` (Linux com TUN/NET_ADMIN), o mesmo vale:

```bash
sudo apt install ./debs/pesquisai_0.7.11-web1_amd64.deb
ufvai
```

Se o serviço ainda não estiver pronto (onboarding sem chave), o proxy devolve
uma página “O motor do OpenCode ainda não está disponível” que recarrega a
cada 3 s — em vez de um JSON de erro.

---

## 4. Tema UFVAI

O CSS injetado sobrescreve os tokens `--v2-*` do motor:

| Token | Claro | Escuro |
|---|---|---|
| `--v2-background-bg-deep` | `#efece4` | `#0d0f10` |
| `--v2-background-bg-base` | `#f6f5f0` | `#111518` |
| `--v2-background-bg-layer-01` | `#ffffff` | `#161b1e` |
| `--v2-text-text-base` | `#23282c` | `#f2f1ea` |
| `--v2-text-text-muted` | `#5f6468` | `#a8a49a` |
| `--v2-border-border-base` | `#ddd8cc` | `#2a3136` |
| `--v2-text-text-accent` | `#8a6d33` | `#d9b45c` |
| `--v2-background-bg-accent` | `#8a6d33` | `#b29149` |

Além dos tokens:

* barra superior de 3 px em degradê **navy → dourado**;
* badge fixo **UFV·AI** no canto inferior esquerdo;
* tipografia do sistema (`Segoe UI`/system-ui);
* título da aba = **UFVAI · OpenCode**.

O tema claro/escuro acompanha o `localStorage` do próprio OpenCode
(`opencode-color-scheme`), então o botão de tema do web app continua valendo.

---

## 5. Segurança

- A senha do serviço (`service.json`) **nunca** chega ao navegador: o proxy a
  converte em `Authorization: Basic` no servidor.
- O proxy escuta em `0.0.0.0:8002` (necessário para o proxy do Colab), mas o
  upstream é sempre `127.0.0.1:<porta>`; não há exposição direta do motor.
- O CSP do próprio OpenCode é preservado (`style-src 'unsafe-inline'` já
  permite o CSS injetado; nenhum script inline é adicionado).
- O token de sessão do wrapper (`X-UFVAI-Token`) continua valendo para as
  rotas `/api/*` do **wrapper** (8001), não para o proxy.

---

## 6. Limitações

- **É a UI do OpenCode**, não uma tela feita pelo UFVAI: menus, atalhos e
  fluxos são os do motor. A customização é visual (cores, tipografia, badge).
- O **chat** usa SSE (`/api/event`); o proxy repassa em chunks. WebSocket é
  suportado por túnel, mas o PTY persistente pode variar conforme a versão do
  OpenCode.
- O `ttyd` continua rodando (fallback). Para desativá-lo de vez, remova a
  chamada `start_ttyd()` em `launch_app.launch()` — não recomendado, pois
  recursos do wrapper dependem dele.
- Sem navegador real neste ambiente, a validação foi por HTTP: HTML, assets,
  `/api/session` e SSE responderam 200/streaming; o teste visual fica com o
  usuário.

---

## 7. Testes

```bash
python -m pytest tests/test_v0711_ocweb.py -q -o addopts=""
# 9 passed
```

Cobrem: leitura do `service.json`, Basic auth, injeção de tema/badge/título,
`ready()` sem serviço, status e a troca de `/api/ttyd_ready` por
`/api/ocweb_ready` no HTML do wrapper.

---

## 8. Arquivos

- `pesquisai/ocweb.py` — proxy + tema (novo)
- `pesquisai/constants.py` — `OCWEB_PORT = 8002`
- `pesquisai/launch_app.py` — inicia o proxy e aponta o iframe para 8002;
  `GET /api/ocweb_ready`
- `pesquisai/launch_app_responsive_v041.py` — `create_wrapper_html(..., web_mode=True)`
- `tests/test_v0711_ocweb.py`

---

## 9. Diagnóstico: “continua abrindo o ttyd”

Se a janela principal ainda mostra o terminal, verifique nesta ordem:

1. **Célula de boot errada (causa mais comum até a revisão `web2`).**
   A célula copiava sempre `UFVAI-v0.7.11/` para `/tmp/pesquisai`, mesmo
   aberta dentro de `UFVAI-v0.7.11-web/`. A versão corrigida resolve a
   origem pela pasta do próprio arquivo (ou pela pasta atual que contenha
   `pesquisai/ocweb.py`).
2. **Sessão sem restart.** O servidor antigo continua na porta 8001 e o bind
   novo falha dentro de uma thread (sem erro visível). A célula corrigida
   detecta a porta ocupada e manda reiniciar o runtime.
3. **Confirmação rápida:**

   ```bash
   curl -s http://127.0.0.1:8002/__ufvai_ready        # {"ready": true, ...}
   curl -s http://127.0.0.1:8001/ | grep -o 'data-terminal-url="[^"]*"'
   # deve conter 8002, não 8000
   ```

4. Se `data-terminal-url` ainda apontar para 8000, o HTML em
   `/tmp/pesquisai-wrapper/index.html` é antigo: rode o boot de novo após
   **Runtime → Restart session**.

---

## 10. Abrir na sessão do projeto (revisão `web3`)

O UFVAI grava a sessão em uso em `/tmp/ufvai-current-session` (assim que o
terminal/engine a cria). O proxy expõe:

| Rota | Uso |
|---|---|
| `GET /__ufvai/boot.js` | script (mesma origem, permitido pelo CSP) que instala o `fetch` com credenciais e, na home, navega para a sessão |
| `GET /__ufvai/session` | `{"sid": "ses_…"}` — vazio se a sessão não existir mais |

A rota interna da SPA é `/server/<chave>/session/<id>`, com
`chave = base64url(origem)` (a home também expõe a chave nos links; o script
prefere o link e só cai no base64 se necessário).

Consequência: ao abrir a interface, a conversa do projeto
(`/content/drive/My Drive/PesquisAI`) já aparece com a saudação — sem clique.
O `ttyd` e a SPA usam o **mesmo serviço**, então o que é criado no terminal
aparece no web (e vice-versa).

---

## 11. Sincronização e catálogo (revisão `web5`)

| Rota | Uso |
|---|---|
| `GET /__ufvai/catalog` | `{ready, models, providers}` — o `boot.js` espera `ready` antes de abrir a sessão |
| `GET /__ufvai/session?fallback=1` | sessão persistida; se não existir, a ativa/mais recente |

- O relay de `/api/event` grava a sessão vista em `/tmp/ufvai-current-session`
  (`session.created`, `session.viewed`, `session.execution.started`,
  `session.model.selected`). O terminal e a SPA compartilham o mesmo motor, e
  o próximo reload abre a mesma conversa.
- `/api/*` sai com `Cache-Control: no-store`: respostas vazias de um motor
  ainda subindo não ficam presas no cache.
- O servidor usa `request_queue_size = 128`; o valor padrão (5) recusava parte
  do pico de ~20 requisições da SPA (“Can't reach this server”).
- No boot, `launch_app` interrompe sessões órfãs (`busy > idle` há 15 min) e
  aquece `/api/provider` + `/api/model` antes de liberar a interface.

---

## 12. Tema e nome da sessão (revisão `web6`)

- **Tema**: o wrapper e o iframe são origens diferentes; a troca vai por
  `postMessage({type:"ufvai-theme", theme:"light"|"dark"})`. O `boot.js`
  aplica em `documentElement[data-color-scheme]`, grava
  `localStorage["opencode-color-scheme"]` e dispara `StorageEvent` (a SPA
  ouve essa chave). O `?theme=` cobre o primeiro carregamento. Em modo web o
  iframe não é recarregado ao trocar o tema.
- **Nome**: a SPA usa o título da sessão; sem título, mostra `opencode`.
  O proxy reescreve títulos nulos/`opencode` para `UFVAI` no
  `POST /api/session` e no evento `session.created`; o boot normaliza as
  sessões antigas. Títulos escolhidos pelo usuário são preservados.

---

## 13. Fallback do catálogo (revisão `web7`)

A SPA não busca `/api/model` e `/api/provider` “crus”: ela guarda o resultado
por `location[directory]`. Se o recorte do projeto vier `[]`, `null`, inválido
ou com erro, `provider.list`/`model.list` ficam indefinidos e o seletor e a
lista de provedores desaparecem.

O proxy agora:
- devolve o catálogo **global** quando o escopo do projeto está vazio/inválido;
- cacheia o global por ~15–30 s;
- expõe `GET /__ufvai/diag` com `project`, contagens `scoped/global` e
  `fallback` (abrir `.../proxy/8002/__ufvai/diag`).
---

## 14. Handshake, cache e sessão ativa (revisão `web8`)

- **Handshake**: a SPA só dispara `provider.sync`/`model.sync` depois de um
  `server.connected`. No Colab o bundle pode carregar depois do primeiro
  evento. O proxy fecha a 1ª conexão SSE **a cada page load** (1 s); a
  reconexão entrega o handshake real ao listener já pronto.
- **Cache**: `/api/model` e `/api/provider` (escopo do projeto e global) são
  pré-buscados no boot; a SPA recebe do cache com `X-UFVAI-Cache: hit`
  (gzip quando grande). Evita o timeout de 15 s do sync.
- **Sessão ativa**: `session.execution.started` grava
  `/tmp/ufvai-active-session` (sid + timestamp). O `boot.js` consulta
  `/__ufvai/session` a cada 2,5 s e segue a sessão do terminal se o início
  for recente (< 30 s), sem trocar quando há texto no composer ou “Working”.

---

## 15. Boot offline e chave Google (revisão `web9`)

- O boot é **fail-open**: falha em Drive/dependências/skills/vault não impede a
  interface de subir.
- Sem o motor OpenCode 2.x, o terminal é pulado e a página 503 orienta
  `ufvai --engine-install`; o app tenta o instalador `ufvai-engine` antes do
  `curl | bash`.
- O `.deb` inclui `unzip`/`xz-utils` nas dependências e põe
  `/opt/pesquisai/bin` no `PATH` para o `ttyd` empacotado.
- A chave do Google **não precisa** começar com `AIza`; o prefixo é apenas
  heurística de reconhecimento e não bloqueia o salvamento.

---

## 16. Foco TUI ↔ web em tempo real (revisão `web10`)

- O plugin de TUI `ufvai-sync` (instalado em
  `~/.config/opencode/tui/ufvai-sync`) publica `context.ui.router.current()`
  em `/tmp/ufvai-focus.json` a cada 250 ms.
- O proxy observa o arquivo a cada 150 ms e faz push em `/__ufvai/live`
  (SSE). A web navega para a sessão exibida no terminal em ~0,3 s.
- No sentido inverso, a web grava `/tmp/ufvai-web-focus.json` ao trocar de
  sessão (400 ms); o plugin navega a TUI (~0,4 s), se o foco tiver < 5 s.
- Ao abrir uma URL de sessão, o **primeiro** foco do live é ignorado e a web
  reporta a própria sessão ao terminal: a URL escolhida manda na abertura;
  depois, as trocas da TUI mandam.
- Sem o plugin (motor antigo), o proxy cai no fallback de eventos/polling.

---

## 17. Sincronização em tempo real — correções da `web11`

A revisão `web10` criou o canal, mas três defeitos impediam o uso real:

### 17.1 A rota usava a chave errada

`/server/<key>/session/<id>` exige `key = base64url(location.origin)` — é
assim que a SPA registra o servidor em que está rodando. O `boot.js` montava a
rota com a URL do **motor**; a SPA não encontrava servidor algum e a sessão
abria em branco (só o badge). Verificação rápida no console:

```js
btoa(location.origin)           // deve ser o <key> da URL
```

Agora `originKey()` calcula a chave e `routeBase()` reaproveita o prefixo da
URL atual; a navegação nunca inventa um `/server/` novo.

### 17.2 Trocar de sessão recarregava a página

`navTo()` faz `history.pushState` + `PopStateEvent` e, se em 700 ms o texto de
`<main>` não mudou (a SPA ignorou o evento), cai para `location.replace`.
Em navegação normal a troca é instantânea e o estado do editor sobrevive.

### 17.3 O push do terminal voltava como foco (ping-pong)

Toda navegação era publicada em `POST /__ufvai/focus`; o push recebido do
terminal era republicado de volta. Agora a navegação vinda de push é marcada
(`sessionStorage["ufvai-pushed"]`, com `_pushedSid` em memória) e **não** é
publicada. O foco inicial de uma página aberta manualmente continua sendo
publicado (`first=!_reported`), para o terminal seguir o navegador.

### 17.4 Tempos observados (Chromium headless, proxy isolado)

| Cenário | Antes | Agora |
|---|---|---|
| home → sessão empurrada pela TUI | ~2,6 s / recarga | 0,23–0,35 s, sem recarga |
| sessão → sessão empurrada pela TUI | ~2,7 s | 0,15 s, marcador de estado vivo |
| clique do usuário → arquivo da web | 0,7–4,3 s | 0,2–0,8 s |

O polling de 1,2 s permanece apenas como reserva quando o `EventSource` não
está conectado (`readyState !== 1` ou sem mensagem há 5 s).

---

## 18. Pergunta da UFV uma vez só e foco instantâneo (revisão `web12`)

### 18.1 Onde a decisão fica

| Arquivo | Escopo | Observação |
|---|---|---|
| `~/.config/ufvai/vpn/prefs.json` | sessão | efêmero no Colab (some no restart) |
| `backups/ufvai_vpn_prefs.json` | **Drive** | decisão definitiva (“sou aluno” / “não”) |
| `keys_store.json` | Drive (cifrado) | CPF + senha, só com “lembrar” |

`load_prefs()` lê os dois e combina: `ask_dismissed` e `auto_connect` são OU
lógico; as demais chaves vêm do local (mais recente). `save_prefs()` grava nos
dois e **mescla** com o que já existe, para que uma escrita parcial não apague a
decisão.

`should_ask()` só retorna `True` quando **nenhum** dos dois registrou a resposta
e não há credenciais salvas. Ou seja: a pergunta aparece uma vez por Drive.

### 18.2 Reconexão automática

- Escolher “sou aluno(a) da UFV” marca a caixa “Lembrar neste Drive (cifrado)”
  por padrão (pode ser desmarcada).
- `_finish_connect()` chama `set_auto_connect(True)` depois de uma conexão
  **bem-sucedida** com `remember=True`.
- No boot, `_vpn_autoconnect_startup()` espera 4 s e chama
  `vpn.connect(use_saved=True)` numa thread — sem modal, sem bloquear a UI.
- `disconnect()` e `forget_credentials()` chamam `set_auto_connect(False)`:
  quem desconectou de propósito não é reconectado sozinho.
- O painel 🛡 mostra “reconecta sozinho ao abrir” quando está armado
  (`auto_connect_ready`).

### 18.3 Latência do foco

| Caminho | Antes (`web11`) | Agora (`web12`) |
|---|---|---|
| TUI → proxy | arquivo + polling 150 ms | `POST /__ufvai/focus` (source `tui`) → SSE |
| TUI → web (medido) | 150–350 ms | **14 ms** no proxy; ~230 ms no teste de ponta |
| web → TUI (medido) | 720 ms | **90 ms** |
| polling de reserva | 800 ms (web) / 150 ms (proxy) | 1.200 ms (web) / 50 ms (proxy) |

O plugin continua gravando `/tmp/ufvai-focus.json` como reserva — plugins
antigos e escritas manuais seguem funcionando.

---

## 19. “Working” preso e botão Parar (revisão `web13`)

### 19.1 Por que ficava “Working”

O status da sessão na SPA é um **conjunto alimentado por evento**:
`session.execution.started` entra, `session.execution.succeeded|failed|
interrupted` sai. Se o evento final não chega (SSE bufferizado no proxy do
Colab, reconexão no meio), o rodapé nunca limpa — mesmo com o turno encerrado
no motor.

`session.time.busy > time.idle` **não** serve para decidir: quando um turno
morre no meio, o motor mantém `outcome` do turno anterior e `idle` velho.

### 19.2 O sinal correto

`GET /__ufvai/run-state?sid=<id>` inspeciona a **última mensagem do
assistente**:

| Situação | `running` | `stale` |
|---|---|---|
| `time.completed` presente | `false` | `false` |
| sem `completed`, atividade < 120 s | `true` | `false` |
| sem `completed`, parada ≥ 120 s | `false` | `true` |

Com isso o `boot.js` faz duas coisas:

1. **destrava** — se a UI mostra “Working” e `running=false`, revalida e
   recarrega uma vez (máx. 1×/30 s por sessão, via `sessionStorage`);
2. **Parar** — se a chamada da SPA não sair em 600 ms, o fallback consulta o
   estado: `running` → manda `POST /api/session/<id>/interrupt?resume=true`;
   já terminado → apenas limpa a UI.

### 19.3 Validação (proxy isolado + Chromium headless)

- turno real de 30 s: **não** recarrega (sem falso positivo);
- “Working” forjado com turno concluído: recarrega em ~8–12 s e limpa;
- Parar em turno concluído: limpa em vez de interrupt inócuo;
- Parar em turno real: `outcome = interrupted` no servidor;
- `pytest`: **113 passed**.

