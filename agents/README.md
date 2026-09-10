# 🌍 UFVAI (PesquisAI) — Agents Multilíngues

> Suporte oficial para **5 idiomas** via variantes do `AGENTS.md`.

## 📁 Arquivos

| Arquivo | Idioma | Quando Usar |
|---|---|---|
| `AGENTS.md` (raiz) | 🇧🇷 Português (Brasil) | Padrão (default) — **canônico** (não duplicado em `agents/`) |
| `AGENTS.en.md` | 🇺🇸 English (United States) | Pesquisadores internacionais |
| `AGENTS.es.md` | 🇪🇸 Español (España) | Hispanofalantes, América Latina |
| `AGENTS.fr.md` | 🇫🇷 Français (France) | Francofonia, cooperação internacional |
| `AGENTS.zh.md` | 🇨🇳 简体中文 (Chinês) | Pesquisadores sinofalantes |

> Em divergências entre variantes, prevalece o original em português (`AGENTS.md`).

## 🔧 Como Funciona

O PesquisAI detecta o idioma preferido do usuário e carrega a variante apropriada. A detecção usa o módulo `pesquisai/i18n/` que considera:

1. **Variável de ambiente** `PESQUISAI_LANG`
2. **Headers HTTP** `Accept-Language`
3. **Variáveis de sistema** `LANG`, `LC_ALL`
4. **Fallback** `pt_BR` (Português)

## 📋 Configuração

### Via variável de ambiente (Linux/macOS)

```bash
export PESQUISAI_LANG=en_US
```

### Via Python

```python
from pesquisai.i18n import set_language, get_language

set_language("en_US")
print(get_language())  # "en_US"
```

### Via interface web

Clique no ícone de globo (🌐) no topo da interface para selecionar o idioma.
As **Diretrizes do Agente** (botão 📋 na topbar) mudam automaticamente
para o idioma selecionado — endpoint `GET /api/agents?lang=xx_XX`.

## 🧪 Conteúdo de Cada Variante

Cada `AGENTS.<lang>.md` mantém **100% das regras originais**, com:

- ✅ Mesmas regras de integridade científica
- ✅ Mesmos skills e capacidades
- ✅ Mesmo fluxo de trabalho (pipeline de 6 etapas)
- ✅ Marcadores de evidência traduzidos
- ✅ Citações em formato apropriado para cada idioma

### Traduções dos Marcadores de Evidência

| 🇧🇷 pt_BR | 🇺🇸 en_US | 🇪🇸 es_ES | 🇫🇷 fr_FR | 🇨🇳 zh_CN |
|---|---|---|---|---|
| `[DADO CONFIRMADO]` | `[CONFIRMED DATA]` | `[DATO CONFIRMADO]` | `[DONNÉE CONFIRMÉE]` | `[DADO CONFIRMADO]`* |
| `[ESTIMATIVA FUNDAMENTADA]` | `[FUNDAMENTED ESTIMATE]` | `[ESTIMACIÓN FUNDAMENTADA]` | `[ESTIMATION FONDÉE]` | `[ESTIMATIVA FUNDAMENTADA]`* |
| `[SEM DADOS SUFICIENTES]` | `[INSUFFICIENT DATA]` | `[DATOS INSUFICIENTES]` | `[DONNÉES INSUFFISANTES]` | `[SEM DADOS SUFICIENTES]`* |

\* A variante chinesa (`AGENTS.zh.md`) mantém os marcadores **no original em português** (strings canônicas, acompanhadas de glossário em chinês no corpo do texto) — não traduza nem altere essas strings.

## ➕ Adicionar Novo Idioma

Para adicionar, por exemplo, Alemão (de_DE):

1. Crie `agents/AGENTS.de.md` traduzindo o conteúdo
2. Adicione `"de_DE"` em `i18n/translator.py → SUPPORTED_LANGUAGES`
3. Adicione mapeamento em `i18n/detector.py → _normalize`
4. Crie `i18n/translations/de_DE.json`
5. Atualize a interface para incluir o novo idioma em
   `launch_app_responsive_v041.py → SUPPORTED_LANGUAGES`

## 🧪 Testes de Consistência

```bash
# Verifica que todas as variantes existem e têm a mesma estrutura
python -c "
import yaml
from pathlib import Path

required_sections = ['name', 'description', 'color', 'language']
frontmatter_keys = {}

for f in Path('agents').glob('AGENTS.*.md'):
    content = f.read_text()
    parts = content.split('---', 2)
    if len(parts) >= 3:
        fm = yaml.safe_load(parts[1])
        keys = set(fm.keys())
        frontmatter_keys[f.name] = keys

# Verifica que todos têm as mesmas chaves
all_keys = set.union(*frontmatter_keys.values())
for name, keys in frontmatter_keys.items():
    missing = all_keys - keys
    if missing:
        print(f'{name} está faltando: {missing}')
    else:
        print(f'{name} OK')
"
```

## 📄 Licença

MIT — Copyright (c) 2026 Gustavo Bastos Braga (UFV)
