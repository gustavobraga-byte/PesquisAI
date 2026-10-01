#!/bin/bash
set -e
echo "🔬 PesquisAI v0.6.0 (WEBCLI Mode) — Instalação"
echo "================================================"

if ! command -v python3 &> /dev/null; then
  echo "❌ Python 3 não encontrado"
  exit 1
fi
PYTHON_VERSION=$(python3 --version | grep -oP '\d+\.\d+')
if [ "$(printf '%s\n' "3.10" "$PYTHON_VERSION" | sort -V | head -n1)" != "3.10" ]; then
  echo "❌ Python >= 3.10 necessário (encontrado: $PYTHON_VERSION)"
  exit 1
fi
echo "✅ Python $PYTHON_VERSION"

# OpenCode CLI
if command -v opencode &> /dev/null; then
  echo "✅ OpenCode $(opencode --version 2>/dev/null || echo 'instalado')"
else
  echo "📦 Instalando OpenCode CLI..."
  curl -fsSL https://opencode.ai/install | bash
  export PATH="$HOME/.local/bin:$HOME/.opencode/bin:$PATH"
fi

# Verifica que `opencode web` funciona
echo ""
echo "Verificando 'opencode web'..."
opencode web --help 2>&1 | head -3
echo ""

# Instala pacote Python
echo "[1/2] Instalando pacote..."
if command -v uv &> /dev/null; then
  uv sync
else
  pip install -e ".[colab]"
fi

echo ""
echo "================================================"
echo "✅ Instalação completa!"
echo ""
echo "Uso:"
echo "  python main.py                  # Inicia opencode web (porta 8000)"
echo "  python main.py --port 8080      # Customiza porta"
echo "  python main.py --background     # Background (retorna PID)"
echo "  python main.py --check          # Verifica opencode"
echo ""
echo "Acesse: http://localhost:8000"
echo ""
