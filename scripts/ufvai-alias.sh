#!/usr/bin/env bash
# ============================================================================
# ufvai-alias.sh — UFVAI v0.7.6
# Aliasing do motor estilo Flint: o nome "ufvai" passa a existir por cima do
# motor físico (OpenCode), SEM renomear nada em execução.
#
#   ~/.config/ufvai            -> ~/.config/opencode        (symlink)
#   ~/.config/ufvai/ufvai.json -> opencode.json             (symlink)
#   ~/.local/share/ufvai       -> ~/.local/share/opencode   (symlink)
#   /usr/local/bin/ufvai       -> wrapper (OPENCODE_CONFIG_DIR/OPENCODE_CONFIG)
#
# Idempotente · fail-open · não toca no banco SQLite (banco renomeado com o
# motor em execução corromperia o WAL — por isso OPENCODE_DB NÃO é redefinido).
#
# Overrides: UFVAI_ENGINE_BIN (binário do motor) · UFVAI_BIN_LINK (destino do
#            comando ufvai) · UFVAI_CONFIG_SRC / UFVAI_DATA_SRC (dirs reais)
# ============================================================================
set -euo pipefail

ENGINE_BIN="${UFVAI_ENGINE_BIN:-$(command -v opencode 2>/dev/null || echo /root/.opencode/bin/opencode)}"
CFG_SRC="${UFVAI_CONFIG_SRC:-$HOME/.config/opencode}"
CFG_DST="$HOME/.config/ufvai"
DATA_SRC="${UFVAI_DATA_SRC:-$HOME/.local/share/opencode}"
DATA_DST="$HOME/.local/share/ufvai"
BIN_DST="${UFVAI_BIN_LINK:-/usr/local/bin/ufvai}"

echo "🔧 Motor detectado: $ENGINE_BIN"

# 1) Diretório de config: ufvai aponta para o real ---------------------------
if [ -L "$CFG_DST" ] || [ -e "$CFG_DST" ]; then
  echo "• $CFG_DST já existe — mantido"
else
  if [ -d "$CFG_SRC" ]; then
    ln -s "$CFG_SRC" "$CFG_DST"
    echo "✔ link $CFG_DST -> $CFG_SRC"
  else
    echo "⚠ $CFG_SRC não encontrado — pulando (fail-open)"
  fi
fi

# 2) Arquivo de config: ufvai.json -> opencode.json (fonte única) ------------
if [ -L "$CFG_DST/ufvai.json" ] || [ -e "$CFG_DST/ufvai.json" ]; then
  echo "• ufvai.json já existe — mantido"
elif [ -f "$CFG_SRC/opencode.json" ]; then
  ln -s opencode.json "$CFG_SRC/ufvai.json"
  echo "✔ link ufvai.json -> opencode.json"
else
  echo "⚠ $CFG_SRC/opencode.json não encontrado — pulando (fail-open)"
fi

# 3) Diretório de dados: mesmo banco/crédenciais ----------------------------
if [ -L "$DATA_DST" ] || [ -e "$DATA_DST" ]; then
  echo "• $DATA_DST já existe — mantido"
else
  if [ -d "$DATA_SRC" ]; then
    ln -s "$DATA_SRC" "$DATA_DST"
    echo "✔ link $DATA_DST -> $DATA_SRC"
  else
    echo "⚠ $DATA_SRC não encontrado — pulando (fail-open)"
  fi
fi

# 4) Comando ufvai (wrapper) -------------------------------------------------
if [ ! -d "$(dirname "$BIN_DST")" ]; then
  echo "⚠ $(dirname "$BIN_DST") inexistente — use UFVAI_BIN_LINK para outro destino"
  exit 0
fi
cat > "$BIN_DST" <<EOF
#!/bin/sh
# UFVAI v0.7.6 — wrapper do motor (identidade UFVAI sobre o runtime físico)
export OPENCODE_CONFIG_DIR="\$HOME/.config/ufvai"
export OPENCODE_CONFIG="\$HOME/.config/ufvai/ufvai.json"
exec "$ENGINE_BIN" "\$@"
EOF
chmod +x "$BIN_DST"
echo "✔ comando $BIN_DST"

echo
echo "Pronto. Use 'ufvai' (equivalente a 'opencode', com a identidade UFVAI)."
echo "Conferência: ufvai --version · ufvai auth export"
