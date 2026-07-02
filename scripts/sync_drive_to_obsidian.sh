#!/usr/bin/env bash
# sync_drive_to_obsidian.sh — Sincroniza o vault entre o Drive e o Obsidian local.
#
# Estratégia: rsync bidirecional com proteção de notas humanas.
#
# Uso:
#   ./sync_drive_to_obsidian.sh                          # direção padrão: push
#   ./sync_drive_to_obsidian.sh pull                     # Drive → Obsidian
#   ./sync_drive_to_obsidian.sh both                     # bidirecional
#
# Requisitos: rsync 3+, bash 4+.

set -euo pipefail

DRIVE_VAULT="${PESQUISAI_DRIVE_PATH:-/content/drive/My Drive/PesquisAI}/vault"
LOCAL_VAULT="${PESQUISAI_OBSIDIAN_LOCAL:-${HOME}/Obsidian/PesquisAI}"
DIRECTION="${1:-push}"
BACKUP_DIR="$DRIVE_VAULT/.backups/$(date +%Y-%m-%d)"

if [ ! -d "$DRIVE_VAULT" ]; then
  echo "❌ Vault no Drive não encontrado: $DRIVE_VAULT"
  echo "   Rode ./init_vault.sh primeiro."
  exit 1
fi

echo "🔄 Sincronizando: $DIRECTION"
echo "   📂 origem: $DRIVE_VAULT"
echo "   📂 destino: $LOCAL_VAULT"
echo ""

# Backup antes de qualquer operação
echo "💾 Backup pré-sync em $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"
rsync -a --delete \
  --exclude=".trash/" \
  --exclude=".backups/" \
  --exclude=".pesquisai-audit.log" \
  "$DRIVE_VAULT/" "$BACKUP_DIR/" > /dev/null 2>&1 || true

# ── Push: Drive → Local ────────────────────────────────────────
if [ "$DIRECTION" = "push" ] || [ "$DIRECTION" = "both" ]; then
  echo "📤 Push: Drive → Local"
  mkdir -p "$LOCAL_VAULT"
  rsync -a --update \
    --exclude=".trash/" \
    --exclude=".backups/" \
    --exclude=".obsidian/" \
    --exclude=".pesquisai-audit.log" \
    "$DRIVE_VAULT/" "$LOCAL_VAULT/"
  echo "   ✅ Concluído."
fi

# ── Pull: Local → Drive (com proteção) ─────────────────────────
if [ "$DIRECTION" = "pull" ] || [ "$DIRECTION" = "both" ]; then
  echo "📥 Pull: Local → Drive (com proteção de notas humanas)"
  if [ ! -d "$LOCAL_VAULT" ]; then
    echo "   ⚠️  Vault local não existe, pulando pull."
  else
    # Para cada .md local, copia para o Drive, mas:
    #   - Se já existe no Drive E é humano (created_by vazio), NÃO sobrescreve
    #   - Caso contrário, copia
    find "$LOCAL_VAULT" -name "*.md" | while read -r local_file; do
      rel="${local_file#$LOCAL_VAULT/}"
      drive_file="$DRIVE_VAULT/$rel"
      if [ -f "$drive_file" ]; then
        # Existe no Drive — checa se é humano
        if grep -q "^created_by: *pesquisai" "$drive_file" 2>/dev/null; then
          # É do PesquisAI, pode sobrescrever
          cp "$local_file" "$drive_file"
        elif grep -q "^created_by: *$" "$drive_file" 2>/dev/null || \
             ! grep -q "^created_by:" "$drive_file" 2>/dev/null; then
          # É humana (created_by vazio OU ausente) — pula
          echo "   🔒 $rel (humana — pulando)"
        fi
      else
        # Não existe no Drive — cria (provavelmente nova)
        mkdir -p "$(dirname "$drive_file")"
        cp "$local_file" "$drive_file"
      fi
    done
    echo "   ✅ Concluído."
  fi
fi

# ── Estatísticas ────────────────────────────────────────────────
echo ""
echo "📊 Estatísticas:"
echo "   Notas no Drive: $(find "$DRIVE_VAULT" -name "*.md" -not -path "*/.trash/*" -not -path "*/.backups/*" | wc -l)"
if [ -d "$LOCAL_VAULT" ]; then
  echo "   Notas no Local: $(find "$LOCAL_VAULT" -name "*.md" | wc -l)"
fi
echo "   Backup em: $BACKUP_DIR"
echo ""
echo "✅ Sincronização finalizada."
