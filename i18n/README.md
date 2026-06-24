# 🌐 PesquisAI i18n — Suporte Multilíngue

> **Idiomas suportados:** pt_BR (padrão), en_US, es_ES
> **Detecção automática:** variável de ambiente, header HTTP, fallback

## 🚀 Uso Rápido

```python
from pesquisai.i18n import t, set_language, get_language, detect

# Definir idioma manualmente
set_language("en_US")
print(t("ui.backup"))      # "Save backup"
print(t("ui.restore"))     # "Restore"

# Detectar do ambiente
set_language(detect())

# Traduzir para um idioma específico sem mudar o atual
print(t_for("es_ES", "ui.backup"))  # "Guardar copia"
```

## 📋 Chaves disponíveis

### `ui.*` — Interface geral
- `ui.backup`, `ui.restore`, `ui.drive`, `ui.settings`
- `ui.save`, `ui.cancel`, `ui.close`, `ui.open`
- `ui.search`, `ui.loading`, `ui.error`, `ui.success`

### `dashboard.*` — Dashboard de Saúde
- `dashboard.title`, `dashboard.drive_mounted`, `dashboard.opencode_found`

### `providers.*` — Conexão de Provedor de IA
- `providers.title`, `providers.api_key`, `providers.save_connect`

### `sessions.*` — Histórico de Sessões
- `sessions.title`, `sessions.search_placeholder`, `sessions.no_sessions`

### `shortcuts.*` — Atalhos de Teclado
- `shortcuts.title`, `shortcuts.copy`, `shortcuts.interrupt`

### `theme.*` — Tema claro/escuro
- `theme.light`, `theme.dark`, `theme.toggle`

### `agents.*` — Regras do Agente
- `agents.rules_title`, `agents.rule1`, `agents.rule2`, etc.

### `errors.*` — Mensagens de erro
- `errors.no_data` (marcador `[SEM DADOS SUFICIENTES]`)
- `errors.connection_failed`, `errors.invalid_key`

### `success_messages.*` — Mensagens de sucesso
- `success_messages.backup_saved`, `success_messages.key_saved`

## 🔧 Detecção de Idioma

### Por variável de ambiente

```bash
export PESQUISAI_LANG=en_US
export LANG=es_ES.UTF-8
```

### Por header HTTP (em servidor)

```python
from pesquisai.i18n import detect_from_accept_language

lang = detect_from_accept_language("en-US,pt-BR;q=0.8")
# → "en_US"
```

### Por código explícito

```python
from pesquisai.i18n import set_language
set_language("es_ES")
```

## 🧪 Testes

```bash
cd /content/drive/My\ Drive/PesquisAI
python -m pytest i18n/tests/ -v
```

## ➕ Adicionar Novo Idioma

1. Crie `translations/<novo_idioma>.json` com a mesma estrutura de `pt_BR.json`
2. Adicione o código em `translator.py` → `SUPPORTED_LANGUAGES`
3. Adicione o mapeamento em `detector.py` → `_normalize`
4. Adicione o nome em `__init__.py` → `available_languages()`
5. Crie os testes

Exemplo para adicionar `fr_FR` (Francês):

```json
// translations/fr_FR.json
{
  "ui": {
    "backup": "Sauvegarder",
    "restore": "Restaurer",
    ...
  }
}
```

## 📦 Integração com Interface Web

O `launch_app.py` agora suporta um seletor de idioma. Use o helper:

```python
from pesquisai.i18n import t_for

# No endpoint /api/languages
@app.get("/api/languages")
def list_languages():
    return {
        "current": get_language(),
        "available": available_languages(),
    }
```

E no JavaScript:

```javascript
async function setLanguage(code) {
  await fetch("/api/language", {
    method: "POST",
    body: JSON.stringify({ language: code }),
  });
  location.reload();
}
```

## 📄 Licença

MIT — Copyright (c) 2026 Gustavo Bastos Braga (UFV)
