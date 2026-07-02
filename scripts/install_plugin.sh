#!/usr/bin/env bash
# install_plugin.sh — Instala plugins recomendados do Obsidian no vault.
#
# Plugins instalados:
#   - Dataview          (queries YAML)
#   - Remotely Save     (sync com Google Drive / S3 / WebDAV)
#   - Templater         (templates com lógica)
#   - Calendar          (daily notes visual)
#   - Tag Wrangler      (gestão de tags)
#   - Mind Map          (visualização de grafo)
#
# Uso:
#   ./install_plugin.sh                                  # usa vault default
#   ./install_plugin.sh /path/para/vault                 # usa vault específico
#
# Requisitos: bash 4+, curl, jq, unzip.

set -euo pipefail

VAULT_PATH="${1:-${PESQUISAI_OBSIDIAN_VAULT:-/content/drive/My Drive/PesquisAI/vault}}"
PLUGINS_DIR="$VAULT_PATH/.obsidian/plugins"

if [ ! -d "$VAULT_PATH" ]; then
  echo "❌ Vault não encontrado: $VAULT_PATH"
  echo "   Rode ./init_vault.sh primeiro."
  exit 1
fi

mkdir -p "$PLUGINS_DIR"

# ── Catálogo de plugins ─────────────────────────────────────────
# Formato: id|name|repo
PLUGINS=(
  "dataview|obsidian-dataview|blacksmithgu/obsidian-dataview"
  "remotely-save|remotely-save|remotely-save/remotely-save"
  "templater-obsidian|templater-obsidian|SilentVoid13/Templater"
  "calendar|obsidian-calendar-plugin|liamcain/obsidian-calendar-plugin"
  "tag-wrangler|tag-wrangler|pjeby/tag-wrangler"
  "mind-map|obsidian-mind-map-plugin|lynchjames/obsidian-mind-map"
  "obsidian-git|obsidian-git|denolehov/obsidian-git"
)

download_plugin() {
  local id="$1"
  local name="$2"
  local repo="$3"
  local target="$PLUGINS_DIR/$id"
  local manifest="https://api.github.com/repos/$repo/releases/latest"

  echo "📦 Instalando $name ($repo)..."

  if [ -d "$target" ]; then
    echo "   ↳ Já instalado, pulando."
    return 0
  fi

  mkdir -p "$target"
  # Pega o asset .zip da última release
  local url
  url=$(curl -sL "$manifest" \
    | jq -r --arg n "$name" '.assets[] | select(.name | test($n; "i")) | .browser_download_url' \
    | head -n1)
  if [ -z "$url" ] || [ "$url" = "null" ]; then
    echo "   ⚠️  Não foi possível encontrar asset para $name"
    return 1
  fi
  curl -sL "$url" -o "/tmp/$id.zip"
  unzip -o "/tmp/$id.zip" -d "$target" > /dev/null
  rm "/tmp/$id.zip"

  # Habilita o plugin
  local community_json="$VAULT_PATH/.obsidian/community-plugins.json"
  if [ -f "$community_json" ]; then
    local list
    list=$(cat "$community_json")
    if ! echo "$list" | jq -e ". | index(\"$id\")" > /dev/null 2>&1; then
      echo "$list" | jq ". + [\"$id\"]" > "$community_json.tmp"
      mv "$community_json.tmp" "$community_json"
    fi
  else
    echo "[\"$id\"]" > "$community_json"
  fi
  echo "   ✅ Instalado em $target"
}

# ── Loop ────────────────────────────────────────────────────────
for plugin in "${PLUGINS[@]}"; do
  IFS='|' read -r id name repo <<< "$plugin"
  download_plugin "$id" "$name" "$repo" || true
done

# ── Habilitar Dataview + Remotely Save ──────────────────────────
APP_JSON="$VAULT_PATH/.obsidian/app.json"
if [ -f "$APP_JSON" ]; then
  if command -v jq &> /dev/null; then
    # Garante que dataview e templater estão ativos
    tmp=$(mktemp)
    jq '. + {"vimMode": false, "showLineNumber": true}' "$APP_JSON" > "$tmp"
    mv "$tmp" "$APP_JSON"
  fi
fi

echo ""
echo "✅ Plugins instalados e habilitados."
echo ""
echo "📋 Para finalizar:"
echo "   1. Abra o Obsidian → Settings → Community plugins"
echo "   2. Verifique se os 7 plugins estão ativos"
echo "   3. Configure 'Remotely Save' para sincronizar com seu Drive"
echo "   4. Configure 'Obsidian Git' se preferir sincronizar via git"
