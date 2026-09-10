# Changelog — PesquisAI

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
