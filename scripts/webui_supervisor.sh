#!/usr/bin/env bash
# webui_supervisor.sh — mantém a versão web nova em segundo plano.
#
# O runtime do Colab é efêmero: a cada reinício o servidor da web morre.
# Este supervisor o religa automaticamente (e sobrevive a quedas do próprio
# processo). Uso:
#
#   setsid nohup bash scripts/webui_supervisor.sh > /dev/null 2>&1 < /dev/null &
#
# Variáveis: UFVAI_WEBUI_PORT (padrão 8003), UFVAI_WEBUI_SRC (padrão
# /tmp/pesquisai), UFVAI_WEBUI_LOG (padrão /tmp/webui-8003.log).
set -u

SRC="${UFVAI_WEBUI_SRC:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PORT="${UFVAI_WEBUI_PORT:-8003}"
LOG="${UFVAI_WEBUI_LOG:-/tmp/webui-8003.log}"

cd "$SRC" 2>/dev/null || exit 1
export PYTHONPATH="$SRC:${PYTHONPATH:-}"
export PYTHONUNBUFFERED=1

echo "[$(date '+%F %T')] supervisor da web nova (porta $PORT) iniciado" >> "$LOG"
while true; do
  if [ -f "$SRC/pesquisai/webui_server.py" ]; then
    python3 -m pesquisai.webui_server "$PORT" >> "$LOG" 2>&1
    echo "[$(date '+%F %T')] webui_server encerrou — reiniciando em 3 s" >> "$LOG"
  else
    echo "[$(date '+%F %T')] $SRC/pesquisai/webui_server.py ausente — aguardando" >> "$LOG"
  fi
  sleep 3
done
