#!/usr/bin/env bash
# init_vault.sh — Cria a estrutura do vault do Obsidian no Google Drive.
#
# REGRA: o vault DEVE ficar no Google Drive do usuário (não em /content/
# ou /tmp/, que são efêmeros no Colab). O caminho padrão é
# /content/drive/My Drive/PesquisAI/vault, que é o FUSE mount do Drive.
#
# Uso:
#   ./init_vault.sh                              # usa Drive (padrão)
#   ./init_vault.sh /content/drive/.../vault    # usa path explícito no Drive
#   PESQUISAI_DRIVE_PATH=/outro/path \
#     ./init_vault.sh                            # usa outro local no Drive
#
# Requisitos: bash 4+, find, mkdir.

set -euo pipefail

DEFAULT_VAULT="/content/drive/My Drive/PesquisAI/vault"
VAULT_PATH="${1:-${PESQUISAI_DRIVE_PATH:-$DEFAULT_VAULT}/vault}"

# ── Validação: o caminho DEVE estar no Google Drive ─────────────
# O FUSE mount do Drive no Colab aparece como /content/drive/.
# Aceitar também "Shared drives/" e "Sharedwithme/" do Drive.
case "$VAULT_PATH" in
  /content/drive/*|/content/drive/.colab/*)
    # OK: dentro do FUSE mount do Drive
    ;;
  /content/*|/tmp/*|/home/*)
    echo "❌ ERRO: o caminho '$VAULT_PATH' NÃO está no Google Drive."
    echo ""
    echo "O PesquisAI exige que o vault fique no Google Drive do"
    echo "usuário, pois o Colab é efêmero (/content/ e /tmp/ são"
    echo "perdidos quando a sessão termina)."
    echo ""
    echo "Use um dos caminhos abaixo:"
    echo "  1. Padrão:      /content/drive/My Drive/PesquisAI/vault"
    echo "  2. Outro Drive: /content/drive/Shared drives/<nome>/vault"
    echo "  3. Variável:    PESQUISAI_DRIVE_PATH=/content/drive/Meu\ Drive/Meu\ Dir"
    echo ""
    echo "Para forçar uso fora do Drive (NÃO recomendado), edite o script"
    echo "e comente o bloco de validação."
    exit 1
    ;;
  *)
    # Caminho customizado — avisar mas permitir
    echo "⚠️  AVISO: o caminho '$VAULT_PATH' não está no FUSE mount do Drive."
    echo "   Se você está no Colab, o vault será PERDIDO ao fim da sessão."
    read -p "   Continuar mesmo assim? (s/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Ss]$ ]]; then
      echo "Abortado. Use o caminho padrão do Drive."
      exit 1
    fi
    ;;
esac

echo "🧠 Inicializando vault do Obsidian em: $VAULT_PATH"
echo "   (caminho validado como dentro do Google Drive ✓)"
mkdir -p "$VAULT_PATH"

# Verifica que o Drive está montado (no Colab)
if [[ "$VAULT_PATH" == /content/drive/* ]] && [ ! -d "/content/drive/My Drive" ]; then
  echo ""
  echo "❌ ERRO: o Google Drive não está montado em /content/drive/"
  echo "   No Colab, execute antes:"
  echo "     from google.colab import drive"
  echo "     drive.mount('/content/drive')"
  exit 1
fi

# Estrutura padrão de pastas
for sub in \
  daily \
  research \
  literature \
  methodology \
  hypothesis \
  reference \
  sessions \
  moc \
  inbox \
  datasource \
  ".obsidian" \
  ".trash" \
  ".backups"
do
  mkdir -p "$VAULT_PATH/$sub"
done

# .obsidian/pesquisai.json — config do PesquisAI no Obsidian
cat > "$VAULT_PATH/.obsidian/pesquisai.json" << 'JSON'
{
  "vault_version": "0.5.0",
  "agent": "pesquisai",
  "auto_daily": true,
  "auto_session_log": true,
  "protect_human_notes": true,
  "taxonomy": {
    "pesquisai/ibge": "Dados do IBGE",
    "pesquisai/datasus": "Dados do DataSUS",
    "pesquisai/agrobr": "Dados do agrobr",
    "pesquisai/dados-brasil": "Outros dados BR",
    "pesquisai/capes": "Dados da CAPES",
    "pesquisai/sucupira": "Sucupira (CAPES)",
    "pesquisai/daily": "Daily note",
    "pesquisai/research": "Projeto de pesquisa",
    "pesquisai/literature": "Revisão de literatura",
    "pesquisai/session": "Log de sessão",
    "pesquisai/methodology": "Método",
    "pesquisai/datasource": "Fonte de dados",
    "pesquisai/hypothesis": "Hipótese",
    "pesquisai/reference": "Citação / referência",
    "pesquisai/moc": "Map of Content",
    "pesquisai/inbox": "Captura rápida",
    "pesquisai/draft": "Rascunho",
    "pesquisai/review": "Em revisão",
    "pesquisai/published": "Finalizado",
    "pesquisai/archived": "Arquivado"
  }
}
JSON

# .obsidian/app.json — config mínima do Obsidian
cat > "$VAULT_PATH/.obsidian/app.json" << 'JSON'
{
  "alwaysUpdateLinks": true,
  "newLinkFormat": "shortest",
  "useMarkdownLinks": false,
  "showInlineTitle": true,
  "readableLineLength": true
}
JSON

# .obsidian/appearance.json — tema escuro por padrão
cat > "$VAULT_PATH/.obsidian/appearance.json" << 'JSON'
{
  "baseFontSize": 16,
  "translucency": false,
  "theme": "obsidian",
  "cssTheme": "minimal"
}
JSON

# .gitignore — não versionar backups e trash
cat > "$VAULT_PATH/.gitignore" << 'GI'
.trash/
.backups/
.pesquisai-audit.log
*.tmp
GI

# Cria uma daily inicial como exemplo
DAILY_PATH="$VAULT_PATH/daily/$(date +%Y-%m-%d).md"
if [ ! -f "$DAILY_PATH" ]; then
  cat > "$DAILY_PATH" << MD
---
title: "$(date +%Y-%m-%d)"
created: $(date +%Y-%m-%d)
updated: $(date +%Y-%m-%d)
tags:
  - pesquisai/daily
  - pesquisai/draft
author: ""
created_by: ""
status: draft
source: ""
project: ""
---

# $(date +%Y-%m-%d)

> **Data:** $(date +%Y-%m-%d)
> **Vault:** PesquisAI v0.5.0+

Bem-vindo ao seu segundo cérebro! 🎉

Esta daily foi criada automaticamente pelo \`init_vault.sh\`. Edite
livremente — o PesquisAI **não** vai sobrescrever notas humanas (apenas
notas com \`created_by: pesquisai\` no frontmatter).

## 🎯 Foco do dia

- [ ]

## 💡 Insights

-

## 📌 Próximos passos

- [ ]
MD
fi

# Cria MOC raiz
MOC_PATH="$VAULT_PATH/moc/index.md"
if [ ! -f "$MOC_PATH" ]; then
  cat > "$MOC_PATH" << 'MD'
---
title: "📚 MOC raiz — Índice do Vault"
created: $(date +%Y-%m-%d)
updated: $(date +%Y-%m-%d)
tags:
  - pesquisai/moc
author: ""
created_by: ""
status: published
---

# 📚 MOC raiz

> **Vault:** PesquisAI v0.5.0+

Este é o MOC (Map of Content) raiz do seu vault. Use-o como ponto de
entrada para navegar por todos os projetos.

## Projetos ativos

```dataview
LIST
FROM "moc"
WHERE file.name != "index"
SORT file.ctime DESC
```

## Daily notes recentes

```dataview
LIST
FROM "daily"
SORT file.name DESC
LIMIT 7
```

## Pesquisas em andamento

```dataview
LIST
FROM "research"
WHERE contains(tags, "pesquisai/research")
SORT file.mtime DESC
```

## Literatura revisada

```dataview
LIST
FROM "literature"
SORT file.mtime DESC
LIMIT 20
```
MD
fi

echo ""
echo "✅ Vault criado em: $VAULT_PATH"
echo ""
echo "📋 Estrutura:"
find "$VAULT_PATH" -maxdepth 2 -type d | sort
echo ""
echo "🔧 Próximos passos:"
echo "   1. Abra o Obsidian e aponte para esta pasta (que está no Drive)"
echo "   2. Instale os plugins: Dataview, Remotely Save (ou Obsidian Git)"
echo "   3. Defina a variável de ambiente:"
echo "      export PESQUISAI_OBSIDIAN_VAULT=\"$VAULT_PATH\""
echo "   4. Sincronize com: ./scripts/sync_drive_to_obsidian.sh"
echo ""
echo "💾 Tudo está no Google Drive em: $VAULT_PATH"
echo "   (nada foi escrito em /content/ efêmero ou em /tmp/)"
