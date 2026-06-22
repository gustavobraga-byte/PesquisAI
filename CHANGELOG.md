# Changelog

## v0.2.3 (2026-06-18) — Backup Integrity Fix

### Bug Crítico: Backups Quebrados (corrupção intermitente)
- **Causa raiz identificada**: Google Drive FUSE trunca a escrita em limites de buffer interno (64KB/256KB/512KB) mas `os.path.getsize()` reporta o tamanho alvo (metadata cache adiantada). Resultado: arquivo corrompido passa pela validação de tamanho mas JSON está truncado no meio de uma string.
- **`launch_app.py /api/backup` (corrigido)**:
  - **Validação JSON do `/tmp/` ANTES de copiar** (rejeita se `opencode export` gerar truncado)
  - **Validação JSON lendo de VOLTA do Drive** após `shutil.copy2()` — detecta truncamento FUSE mesmo quando `getsize` reporta tamanho certo
  - **`os.fsync()` + `os.sync()`** no arquivo destino para forçar sincronização FUSE antes de verificar
  - **Backoff exponencial** entre tentativas (0.8s, 1.3s, 1.8s) em vez de fixo 0.5s
  - **Lock de arquivo** (`fcntl.flock`) em `.backup.lock` para impedir concorrência entre cliques rápidos
  - **Heurística potência-de-2** como alerta diagnostico (log warning se tamanho for 2^N)
  - Resposta agora inclui `"validated": true` confirmando integridade
- **`launch_app.py /api/restore` (corrigido)**: valida JSON do backup ANTES de copiar para `/tmp/` e importar (antes só checava `size >= 100`). Detecta backups corrompidos e sugere remover + gerar novo. Mensagem de erro menciona truncamento FUSE se tamanho for potência de 2.
- **`tests/test_launch_app.py`**: 4 novos testes em `TestBackupIntegrity` (JSON válido detectado, truncamento 64KB detectado, truncamento 256KB detectado, `fcntl.flock` disponível)

### Cobertura
- **192 testes** (antes: 188 → agora: 192, +4 novos de integridade)

## v0.2.2 (2026-06-18) — Stable Base Integration + Novas Funcionalidades

###   Cobertura de Testes (FASE 2 — refeita)
- **188 testes** (antes: 103 → agora: 188, +85 novos)
- **Cobertura total: 29% → 57%**
- **`tests/test_security.py`** (79 testes): criptografia round-trip (9), `_FernetFallback` XOR (7: roundtrip raw/base64/string key, chave errada, HMAC corrompido, token curto), geração de chaves (3), save/load (7), migração old→new (6: keyfile/keysfile nomes antigos vs novos), `_load_or_create_encryption_key` (3), sanitização válidos (15), injection bloqueados (20), edge cases (6), `_check_injection` direto (4)
- **`tests/test_launch_app.py`** (25 testes): funções puras (set_drive_info, load_keys, sanitize integrado), `create_wrapper_html` (4 features, URLs, providers, botões), **servidor HTTP real** com 13 endpoints testados: `/api/health` (2), `/api/theme` GET/POST (4, incluindo inválido), `/api/backups` (2), `/api/apikey` GET/POST (4), `/api/run_terminal` (3: válido, malicioso 403, vazio 400), `/api/apikey/apply` (1)
- **`tests/test_run_fast.py`** (NOVO, 16 testes): `_check_bin` (5: existente, ausente, path customizado), `_run` (3: echo, false, capture), `_clone_or_pull` (4: clone novo, falha, pull existente, pull falha→clone), `SKILL_REGISTRY` consistência (4)
- **`tests/test_opencode_utils.py`** (refeito, 19 testes): `find_opencode` (7: cache, env, env inexistente, which, candidato, search, não encontrado), `ensure_opencode_in_path` (2), `build_env` (5), `_search` (3) — **cobertura 30% → 100%**
- **`tests/test_progress_bar.py`** (refeito, 22 testes): `_html` (10: básico, percentual, zero total, step negativo, >100%, spinner, cor, último estágio, além dos estágios), `show` modo terminal (3), `show` modo Colab (2: cria/atualiza handle), `finish` (3) — **cobertura 51% → 92%**
- **`tests/test_version_sync.py`** (5 testes): `__version__` == `constants` == `pyproject` == `Dockerfile`, semver, CHANGELOG

| Módulo | Cobertura antes | Cobertura agora |
|--------|----------------|-----------------|
| `opencode_utils.py` | 30% | **100%** |
| `progress_bar.py` | 51% | **92%** |
| `security.py` | 62% | **79%** |
| `launch_app.py` | 9% | **45%** |
| `run_fast.py` | 0% | **22%** |
| `constants.py` | 100% | 100% |
| `jokes.py` | 100% | 100% |
| **TOTAL** | **29%** | **57%** |

###  Bugs Corrigidos (detectados pela FASE 2)
- **`security.py` _FernetFallback XOR**: `encrypt` modificava o iv (`b"XOR" + iv[3:]`) APÓS computar o xor_key, mas `decrypt` usava o iv modificado para recomputar o xor_key → chaves diferentes → roundtrip impossível. Corrigido: iv não é mais modificado (o version byte 0x81 já indica XOR)
- **`security.py:556`**: `opencode -s <session_id>` com caracteres inválidos (espaço, etc.) passava pela sanitização porque o prefixo genérico `"opencode"` validava antes do bloco específico. Agora o bloco `opencode -s` valida explicitamente o session_id (apenas alfanuméricos + `_-.`)
- **`launch_app.py:1441`**: segunda sanitização (`sanitize_command(bash_cmd)`) pegava o `;` que o próprio código adicionava (`f"{cmd}; exec bash"`), bloqueando TODOS os comandos via `/api/run_terminal` com erro 500. Corrigido: segunda sanitização removida (o comando do usuário já foi validado; o sufixo `; exec bash` é controlado pelo código)

###  Novas Funcionalidades (FASE 3)
- **3.2 Dashboard de Saúde**: endpoint `GET /api/health` consolidando `/api/diagnose` + `/api/debug`; botão 🩺 na topbar abre modal com checklist visual (Drive montado, ttyd ativo, OpenCode encontrado, keys carregadas, skills instaladas, ffmpeg, espaço em disco, versão)
- **3.3 Busca/Histórico de Sessões**: botão 📜 na topbar abre modal listando sessões (via `/api/sessions` existente); campo de busca filtra por id/conteúdo em tempo real; botão "abrir" por sessão reinicia terminal com `opencode -s <id>`
- **3.6 Atalhos de Teclado Visíveis**: botão ⌨️ na topbar + tecla `?` abrem modal com 8 atalhos (Ctrl+Shift+C copiar, Ctrl+C interromper, Ctrl+L limpar, Ctrl+Shift+V colar, Tab autocompletar, ↑↓ histórico, ? este painel); `Esc` fecha todos os modais
- **3.8 Tema Claro (acessibilidade)**: `pesquisai-light.json` gerado em `run_fast.py` (paleta clara #f5f6f7/#0288d1); toggle ◑ na topbar persiste em `tui.json` via `POST /api/theme`; `GET /api/theme` retorna tema atual; CSS vars do wrapper atualizadas dinamicamente; tema carregado no startup

###  Integração com Base Estável
- **Docs sincronizadas do GitHub estável (v0.2)**: AGENTS.md, README.md, MANUAL.md, PesquisAI.ipynb, LICENSE, citacao_pesquisai.md, declaracao_uso_ia.md, disclaimer_pesquisai.md, IntructionsCEO_paperclip.md
- **Versão atualizada em todas as docs**: v0.2 → v0.2.1 (16 referências em 7 arquivos)
- **`pyproject.toml`**: `readme = "README.md"` re-adicionado; LICENSE, AGENTS.md, MANUAL.md incluídos no build

###  Package (continuação FASE 1)
- **`pesquisai/`**: módulos movidos para package real (git mv preservando histórico)
- **`__init__.py`**: criado como entry-point do package
- **Imports relativos**: `.constants`, `.__version__`, `.jokes`, `.progress_bar`, `.opencode_utils`, `.security`
- **`main.py`**: entry-point atualizado para `from pesquisai.run_fast import run`
- **Testes**: imports atualizados para `pesquisai.X` + strings `@patch` corrigidas
- **`Dockerfile`**: CMD aponta para `pesquisai.run_fast`

###  Bugs Corrigidos (FASE 1)
- **Bug 1.1**: `test_constants.py` assert versão aceita X.Y e X.Y.Z (antes só X.Y)
- **Bug 1.2**: `launch_app.py` logo `v0.2` hardcodeado → `v{VERSION}` dinâmico
- **Bug 1.3**: `Dockerfile` version `0.2` → `0.2.1`
- **Bug 1.5**: `.coverage` removido do git + `.gitignore`
- **Bug 1.6**: `launch_app.install_ttyd` `shell=True` → lista de args
- **Bug 1.7**: `run_fast._install_system_deps`/`_install_python_deps` `shell=True` → args

## v0.2.1 (2026-06-16) — Secure Keys

###  Segurança (Novo)
- **`security.py`**: Módulo de segurança completo com:
  - Criptografia AES-128-CBC + HMAC-SHA256 via Fernet (`cryptography`) para chaves de API
  - Fallback seguro para ambientes sem `cryptography`
  - Geração e gerenciamento de chave de criptografia no Google Drive (`.keys_encryption_key`)
  - Sanitização de comandos com whitelist de prefixos e bloqueio de injection (`; & | \` $() ${} > < \0`)
  - `save_encrypted_keys()` / `load_encrypted_keys()` — salvamento e carga criptografados
  - `sanitize_command()` — validação de comandos com 18 cenários de teste
- **`launch_app.py`**: Endpoint `/api/run_terminal` agora usa `sanitize_command()` antes de executar (bloqueia command injection)
- **`launch_app.py`**: `POST /api/apikey` salva chaves CRIPTOGRAFADAS (não mais em texto puro)
- **`launch_app.py`**: `GET /api/apikey` descriptografa e mascara valores (exibe só 4 primeiros caracteres)
- **`launch_app.py`**: `kill_previous()` e `start_ttyd` migrados de `shell=True` para lista de argumentos
- **`launch_app.py`**: Chave de criptografia armazenada em arquivo SEPARADO (`.keys_encryption_key`) — defesa em profundidade

###  Versão Centralizada
- **`__version__.py`**: Novo arquivo como fonte ÚNICA para versão, autor, repositório, licença
- **`constants.py`**: `VERSION` agora importa de `__version__` (antes era string hardcoded)
- **`pyproject.toml`**: Versão sincronizada com `__version__.py`; adicionada dependência `cryptography>=41.0`
- **`pyproject.toml`**: Seção `[project.optional-dependencies]` adicionada com `crypto = ["pycryptodome>=3.20"]`
- **`run_fast.py`**: Instala `cryptography` durante `_install_python_deps()`
- **Testes automatizados**: 18 testes de sanitização, testes de ciclo completo de criptografia

### Correções de Bugs
- **`constants.py`**: Versão unificada para `VERSION = "0.2"` (estava `"1.0"` — inconsistente com o resto do projeto)
- **`progress_bar.py`**: Correção do bug na declaração de `IN_COLAB` — agora a variável é corretamente detectada via import do IPython

### Qualidade de Código
- **`pyproject.toml`**: Build backend modernizado para `hatchling` (substitui `setuptools.backends._legacy`)
- **Type hints**: Adicionados em `constants.py`, `opencode_utils.py`, `progress_bar.py`, `run_fast.py` e funções principais de `launch_app.py`
- **Configuração Ruff**: Linter e formatador configurados no `pyproject.toml`
- **Configuração Mypy**: Type checker configurado para validação opcional

### CI/CD
- **`.github/workflows/ci.yml`**: Pipeline de integração contínua com 3 jobs:
  - Lint (Ruff) + Format check + Type check (Mypy)
  - Testes (pytest + coverage) em Python 3.10, 3.11, 3.12
  - Gate de qualidade: testes só rodam se lint passar

### Testes
- **`tests/`**: Estrutura de testes com pytest criada (3 suites iniciais):
  - `test_constants.py` — 12 testes: versão, autor, skills, portas, consistência pyproject.toml
  - `test_jokes.py` — 9 testes: categorias, rotação, fallback, 10 piadas por categoria
  - `test_progress_bar.py` — 7 testes: HTML, estágios, cores, edge cases
  - `test_opencode_utils.py` — 3 testes: candidatos, busca, fallback

### Arquitetura
- **`constants.py`**: Skills centralizadas em `SKILL_REGISTRY` com flag `requerida` para fallback inteligente
- **`constants.py`**: `ESSENTIAL_SKILLS` como conjunto derivado para validação
- **`run_fast.py`**: Importa `SKILL_REGISTRY` e `ESSENTIAL_SKILLS` de `constants.py` (antes estava hardcoded)

### Segurança
- **`SECURITY.md`**: Política de segurança, reporte de vulnerabilidades e boas práticas

### Deploy
- **`Dockerfile`**: Imagem Docker para execução local (fora do Colab)

### Infraestrutura
- **`.gitignore`**: Aprimorado com entradas para Python, IDE, OpenCode, Colab, cache
- **`pyproject.toml`**: Seções `[project.optional-dependencies]` para `dev` e `test`

## v0.2 (2026-06-10)

### Otimizações de Performance
- Clonagem de skills paralelizada com `ThreadPoolExecutor(max_workers=8)` — 8 repositórios clonados simultaneamente
- Cache de repositórios: skills já em `/tmp/` fazem `git pull --depth 1 --ff-only` em vez de clonar do zero
- `--single-branch --depth 1` em todos os clones (baixa só o branch padrão)
- Detecção de binários existentes: pula opencode, uv, ttyd se já instalados
- `apt-get update` executado uma única vez (antes rodava em duas etapas separadas)
- `pip install` com `--no-cache-dir` para evitar overhead de cache
- `_check_bin()` aprimorado: busca também em `~/.local/bin`, `~/.npm-global/bin`, `~/.opencode/bin`

### Correções
- **Item 2** — Versão do AGENTS.md corrigida de `v0.01` para `v0.2`
- **Item 4** — `.gitignore` criado com `__pycache__/`, `*.pyc`, `*.pyo`, etc.
- **Item 6** — Numeração duplicada no MANUAL.md corrigida (seção `## 1. Primeiros Passos` removida; seções 1–10 renumeradas)
- **Item 7** — Lógica de carregamento de chaves extraída para `load_keys_from_drive()`, eliminando 3 ocorrências duplicadas

### Interface
- **Item 30** — Barra de progresso com `display_id=True` (sem acumular HTML)
- `clear_output(wait=True)` ao final para limpar textos de setup, restando apenas o botão de launch
- `show_ready_message()` e `show_launch_button()` reexibidos após limpeza
- `Ctrl+Shift+C` no ttyd para copiar (atalho padrão, funciona no Chrome)
- `Ctrl+C` mantém SIGINT (interromper comandos)
- Footer alterado para "UFV · Viçosa, MG - Brasil"

### Provedores
- Lista de provedores ordenada alfabeticamente
- Adicionados **OpenCode Zen** (`OPENCODE_ZEN_API_KEY`) e **OpenCode Go** (`OPENCODE_GO_API_KEY`)

### Registro SisPPG/UFV
- Badge SisPPG com nº **10356285004** adicionado ao README
- Citações ABNT atualizadas com nº de registro em README, MANUAL, citacao_pesquisai, declaracao_uso_ia
- Rodapé do AGENTS.md com nº SisPPG
- Notebooks atualizados com citação e badge
- URL corrigida: `https://www.sisppg.ufv.br` → `http://sisppg.ufv.br`

### Notebook
- Loading animado via `IPython.display`
- Repositório usa `git pull` se já existe (não recria toda execução)
- `clear_output()` antes de rodar (interface mais limpa)
- Markdown simplificado e reorganizado

### Arquivos Novos
- `run_fast.py` — Versão otimizada com paralelismo e cache, substitui o fluxo do `main.py`
- `CHANGELOG.md` — Este arquivo
- `SisPPG - Sistema de Pesquisa e Pós-Graduação.pdf` — Comprovante de registro

### Integridade de Referências
- AGENTS.md — Nova seção `3.1 Sub-fluxo de Verificação de Referências` com 4 subpassos (rastreamento, confirmação de 3 campos, link/DOI obrigatório, inclusão) e regra de ouro contra fabricação
- `run_fast.py` — Descrição do agente atualizada para incluir "verificação obrigatória de referências"

### Alterações em Arquivos Existentes
- `AGENTS.md` — Versão `v0.01` → `v0.2`; seção 3.1 adicionada
- `.gitignore` — Criado
- `MANUAL.md` — Numeração corrigida + citações com SisPPG
- `launch_app.py` — Função `load_keys_from_drive()` extraída; provedores ordenados + Zen/Go
- `progress_bar.py` — `finish()` com `clear_output(wait=True)`
- `main.py` — Simplificado para delegar a `run_fast.py`
- `README.md` — Badge SisPPG + citação atualizada
- `citacao_pesquisai.md` — Citação com SisPPG
- `declaracao_uso_ia.md` — Citação com SisPPG
- `PesquisAI.ipynb` — Loading animado, git pull, markdown simplificado
- `PesquisAI_Colab.ipynb` — Badge SisPPG

## v0.001 (2026-06-10)

### Funções Iniciais
- **setup_drive.py** — Montagem do Google Drive, autenticação Google API, criação do diretório de trabalho
- **setup_dependencies.py** — Instalação do opencode (curl/pip/npm), uv, xclip/xsel, tema e agente
- **setup_skills.py** — Clonagem sequencial de 8 skills (ibge, datasus, scientific, pesquisai, ufv-abnt, qualitativa, dados-brasil, agrobr)
- **launch_app.py** — Instalação do ttyd, servidor web wrapper com backup/restore de sessão e gerenciamento de provedores de IA
- **main.py** — Orquestrador chamando drive → dependências → skills → launch
- **constants.py** — Constantes de caminhos e configuração
- **opencode_utils.py** — Busca do binário opencode e construção de environment
- **jokes.py** — Piagens temáticas exibidas durante o loading
- **PesquisAI.ipynb** — Notebook Colab principal
- Fluxo sequencial de inicialização (sem paralelismo)
- Numeração duplicada no MANUAL.md
- Código duplicado de carregamento de chaves em 3 locais
- Sem barra de progresso
- Sem `.gitignore`
