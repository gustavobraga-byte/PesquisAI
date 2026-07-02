# 🚀 Como Subir o PesquisAI v0.4.1 no GitHub

> **Versão:** 0.4.1
> **Data:** 2026-06-23
> **Tamanho:** ~620KB · 64 arquivos

## 📋 Estrutura da Pasta

```
pesquisai-v0.4.1-github/             ⬅️ Esta pasta (pronta para GitHub)
├── README.md                        # ⭐ Documentação principal
├── LICENSE                          # MIT
├── pyproject.toml                   # Configuração do pacote
├── .gitignore                       # Exclusões para Git
├── .github/workflows/ci.yml         # CI/CD (lint + tests + i18n)
├── __version__.py                   # 0.4.1 + __default_theme__
├── GITHUB_SETUP.md                  # Este arquivo
│
├── 🤖 agents/                       # AGENTS.md multilíngues
│   ├── AGENTS.pt.md (🇧🇷)
│   ├── AGENTS.en.md (🇺🇸)
│   ├── AGENTS.es.md (🇪🇸)
│   └── AGENTS.fr.md (🇫🇷)
│
├── 📚 docs/                         # Documentação
│   ├── CHANGELOG.md
│   ├── CHANGELOG.pdf
│   ├── ENTREGAS_JUNHO_2026.md
│   ├── INTEGRITY.md
│   ├── MOBILE_RESPONSIVE_PATCH.md
│   └── gerar_pdf.py
│
├── 🔍 grant_finder/                 # Skill de busca de fomento
│   ├── matcher.py · budget.py · proposal.py
│   ├── sources/  (13 agências)
│   ├── data/     (5 caches JSON)
│   └── tests/    (48 testes ✅)
│
├── 🌐 i18n/                         # Módulo multilíngue
│   ├── translator.py · detector.py
│   ├── translations/ (pt_BR, en_US, es_ES, fr_FR)
│   └── tests/     (31 testes ✅)
│
└── 🔬 pesquisai/                    # Wrapper HTML (v0.4.1)
    ├── launch_app.py                # ⭐ EDITADO (usa _v041)
    ├── launch_app_responsive_v041.py # Patch v0.4.1 (HTML)
    ├── launch_app_responsive.py     # Standalone (também v0.4.1)
    ├── __init__.py
    └── LAUNCH_APP_EDIT_LOG.md       # Log da edição do launch_app.py
```

## ⭐ Destaque: `launch_app.py` já está editado!

Esta versão inclui o **`launch_app.py` já modificado** com o patch v0.4.1 integrado:

- A função `create_wrapper_html` (904 linhas) foi **substituída** por `from .launch_app_responsive_v041 import create_wrapper_html`
- O resto do servidor (rotas, ttyd, opencode, segurança) foi **preservado integralmente**
- Redução: **−871 linhas (−44%)** no `launch_app.py`
- **Não precisa editar mais nada** — basta subir!

## 🚀 Passo a Passo

### Opção 1 — Fork + PR contra o PesquisAI principal (Recomendado)

```bash
# 1. Fork do repositório principal
#    https://github.com/gustavobraga-byte/PesquisAI

# 2. Clone seu fork
git clone https://github.com/SEU_USUARIO/PesquisAI.git
cd PesquisAI

# 3. Criar branch
git checkout -b feature/v0.4.1-additions

# 4. Copiar arquivos desta pasta para o fork
cp -r /caminho/pesquisai-v0.4.1-github/agents ./
cp -r /caminho/pesquisai-v0.4.1-github/grant_finder ./
cp -r /caminho/pesquisai-v0.4.1-github/i18n ./
cp /caminho/pesquisai-v0.4.1-github/pesquisai/launch_app.py ./pesquisai/
cp /caminho/pesquisai-v0.4.1-github/pesquisai/launch_app_responsive_v041.py ./pesquisai/

# 5. Commit
git add .
git commit -m "feat: v0.4.1 — UI Fixes (Responsive + Theme + Language)

- 6 media queries + hamburger menu (responsivo completo)
- toggleTheme() recarrega iframe do ttyd (tema padrão escuro)
- Seletor de idioma na topbar (4 idiomas, cookie, query param)
- Anti-flash CSS (tema escuro sem flash no load)
- launch_app.py editado (create_wrapper_html substituída por import)
- 79 testes (48 grant_finder + 31 i18n) · 71.58% cobertura
- CI workflow (lint + tests + i18n)"

git push origin feature/v0.4.1-additions

# 6. Abrir PR
#    https://github.com/gustavobraga-byte/PesquisAI/compare
```

### Opção 2 — Repositório independente (pesquisai-additions)

```bash
# 1. Criar novo repositório no GitHub
#    https://github.com/new
#    NÃO inicialize com README/LICENSE/.gitignore

# 2. Navegar até a pasta github-ready
cd /caminho/pesquisai-v0.4.1-github

# 3. Inicializar Git
git init
git add .
git commit -m "Initial release: PesquisAI v0.4.1

🎯 3 correções críticas:
1. Site responsivo (6 media queries + hamburger menu)
2. Tema claro/escuro com reload do terminal (tema padrão escuro)
3. Seletor de idioma na UI (4 idiomas: pt_BR, en_US, es_ES, fr_FR)

📦 Inclui:
- Skill grant_finder (13 agências, 48 testes)
- Módulo i18n (4 idiomas, 31 testes)
- Wrapper HTML responsivo (v0.4.1 corrigido)
- launch_app.py EDITADO (patch v0.4.1 integrado)
- AGENTS.md multilíngues
- 79 testes · 71.58% cobertura
- CI workflow (Python 3.10/3.11/3.12)"

# 4. Conectar ao GitHub
git remote add origin https://github.com/SEU_USUARIO/pesquisai-additions.git
git branch -M main
git push -u origin main

# 5. Criar release/tag
git tag -a v0.4.1 -m "UI Fixes (Responsive + Theme + Language)"
git push origin v0.4.1
```

### Opção 3 — Upload via zip (mais fácil)

```bash
# Use o zip já gerado
pesquisai-v0.4.1-github.zip

# GitHub → Releases → "Draft a new release" → Attach binaries
```

## 🔒 Arquivos que NÃO devem ir para o GitHub

O `.gitignore` já cuida disso:

| ❌ Não comitar | Por quê |
|----------------|---------|
| `__pycache__/` | Cache Python |
| `.pytest_cache/` | Cache de testes |
| `*.pyc` | Bytecode Python |
| `.coverage` | Relatório de cobertura |
| `htmlcov/` | HTML de cobertura |
| `secrets/`, `*.key`, `*.pem` | Credenciais |
| `backups/`, `sessions/`, `sandbox/` | Pessoal |

## ✅ Checklist Antes do Push

- [x] `README.md` com documentação completa
- [x] `LICENSE` (MIT)
- [x] `pyproject.toml` configurado
- [x] `.gitignore` com exclusões
- [x] `.github/workflows/ci.yml` (CI/CD)
- [x] `__version__.py` (fonte única de versão)
- [x] `launch_app.py` EDITADO (patch v0.4.1 integrado)
- [x] `launch_app_responsive_v041.py` (HTML com 3 correções)
- [x] Testes passando (79/79, 71.58% cobertura)
- [x] Sem caches/arquivos temporários
- [x] Sem credenciais
- [x] Tema padrão: 🌙 ESCURO (anti-flash)

## 🧪 Validar Antes do Push

```bash
cd /caminho/pesquisai-v0.4.1-github

# 1. Testes
python3 -m pytest grant_finder/tests/ i18n/tests/ --tb=short

# 2. Validar launch_app.py
python3 -c "
import sys
sys.path.insert(0, '.')
from pesquisai.launch_app_responsive_v041 import create_wrapper_html
html = create_wrapper_html('http://localhost:8000', 'https://drive.google.com')
assert 'data-theme=\"pesquisai\"' in html, 'Tema padrão deve ser escuro'
assert 'ANTI-FLASH' in html, 'Anti-flash deve estar presente'
print('✅ Wrapper HTML OK (tema escuro, anti-flash)')
"

# 3. Limpar artefatos
rm -rf htmlcov coverage.xml .pytest_cache __pycache__
find . -name "__pycache__" -type d -exec rm -rf {} +
find . -name "*.pyc" -delete
```

## 📊 Estatísticas da Release

| Métrica | Valor |
|---------|-------|
| Versão | 0.4.1 |
| Codinome | UI Fixes (Responsive + Theme + Language) |
| Tamanho | ~620KB |
| Arquivos | 64 |
| Linguagem | Python 3.10+ |
| Testes | 79 (48 grant_finder + 31 i18n) |
| Cobertura | 71.58% |
| Idiomas | 4 (pt_BR, en_US, es_ES, fr_FR) |
| Agências de fomento | 13 |
| Media queries | 6 |
| Licença | MIT |
| Tema padrão | 🌙 Escuro (anti-flash) |

---

**PesquisAI · v0.4.1 · "UI Fixes (Responsive + Theme + Language)" · Junho 2026**
