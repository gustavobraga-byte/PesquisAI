#!/usr/bin/env bash
# Inicia o assistente de voz LFM3-Omni integrado ao UFVAI.
set -e
cd "$(dirname "$0")"

echo "🎙️  Iniciando UFVAI Voz (LFM3-Omni-2B)..."
echo "   Porta: 8010"
echo "   Modelo: ./model (baixado automaticamente se ausente)"
echo ""

# Garante dependências mínimas
python3 -c "import torch, transformers, fastapi, uvicorn, librosa, soundfile" 2>/dev/null || {
  echo "Instalando dependências..."
  pip install -q "transformers>=5.20.2" fastapi uvicorn librosa soundfile peft accelerate
}

exec python3 server.py
