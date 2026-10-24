#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# UFVAI v0.7.0-offline (engine PesquisAI) — Instalação local
# ═══════════════════════════════════════════════════════════════
#
# Alternativa ao pacote .deb para quem baixou o código-fonte.
# Instala o UFVAI em modo offline no diretório ~/PesquisAI/
# Sem dependência de Google Colab ou Google Drive.
#
# Uso:
#   chmod +x install-offline.sh
#   ./install-offline.sh
#
# Requisitos:
#   - Python 3.10+
#   - Git
#   - Internet (apenas para download inicial do opencode)
#
# Telemetria (opcional): configure credenciais GA4 em
#   ~/PesquisAI/config/ufvai.env  →  UFVAI_GA_MEASUREMENT_ID / UFVAI_GA_API_SECRET
#   Sem elas a telemetria permanece inerte mesmo com consentimento.
# ═══════════════════════════════════════════════════════════════

set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; GOLD='\033[0;33m'
NC='\033[0m'

info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

VERSION="0.7.5"
UI_PORT="8001"      # interface web (wrapper HTTP)
TERM_PORT="8000"    # terminal ttyd

check_requirements() {
    info "Verificando requisitos..."
    command -v python3 &> /dev/null || error "Python3 não encontrado. Instale: sudo apt install python3 python3-pip"
    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    if (( $(echo "$PYTHON_VERSION < 3.10" | bc -l) )); then
        error "Python $PYTHON_VERSION encontrado. Requerido: 3.10+"
    fi
    success "Python $PYTHON_VERSION"

    if ! command -v git &> /dev/null; then
        warn "Git não encontrado. Instalando..."
        sudo apt update && sudo apt install -y git bc curl
    fi
    success "Dependências base OK"
}

setup_directories() {
    info "Criando estrutura de diretórios..."
    for d in vault outputs backups logs sessions config chrome-profile; do
        mkdir -p "$HOME/PesquisAI/$d"
    done
    success "Diretórios criados em ~/PesquisAI/"
}

install_python_deps() {
    info "Instalando dependências Python..."
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    python3 -m pip install --user --break-system-packages \
        "cryptography>=41.0" "requests>=2.31" "beautifulsoup4>=4.12" "pyyaml>=6.0" 2>/dev/null \
    || python3 -m pip install --user \
        "cryptography>=41.0" "requests>=2.31" "beautifulsoup4>=4.12" "pyyaml>=6.0" 2>/dev/null \
    || warn "Falha ao instalar dependências via pip — instale manualmente."
    # v0.7.4 — instala o pacote `pesquisai` (API do autopilot) a partir
    # desta árvore. Antes o erro era ENGOULDO (`2>/dev/null || true`) e a
    # API do autopilot ficava indisponivel sem ninguem perceber.
    if python3 -m pip install --user --break-system-packages -e "$SCRIPT_DIR" 2>&1 | tail -3 \
       || python3 -m pip install --user -e "$SCRIPT_DIR" 2>&1 | tail -3; then
        success "Pacote `pesquisai` instalado"
    else
        warn "Falha ao instalar o pacote `pesquisai` — a API do autopilot pode nao funcionar."
    fi
    # VERIFICAÇÃO real: importa a API a partir de um diretório NEUTRO
    # (é exatamente assim que o agente a usa).
    if (cd / && python3 -c "from pesquisai.obsidian.autopilot import recall, save" 2>/dev/null); then
        success "API do autopilot verificada (pesquisai.obsidian.autopilot)"
    else
        warn "A API do autopilot nao pode ser importada fora de $SCRIPT_DIR — "
        warn "o PYTHONPATH do launcher cobre o app, mas scripts externos precisam do pacote instalado."
    fi
    success "Dependências Python instaladas"
}

install_opencode() {
    info "Verificando instalação do opencode..."
    if command -v opencode &> /dev/null; then
        success "opencode já instalado: $(which opencode)"
        return
    fi
    OPENCODE_DIR="$HOME/.local/bin"; mkdir -p "$OPENCODE_DIR"
    [[ ":$PATH:" != *":$OPENCODE_DIR:"* ]] && {
        export PATH="$OPENCODE_DIR:$PATH"
        grep -q '.local/bin' "$HOME/.bashrc" 2>/dev/null || echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
    }
    if command -v npm &> /dev/null; then
        npm install -g opencode@latest 2>/dev/null && { success "opencode instalado via npm"; return; }
    fi
    ARCH=$(uname -m); case "$ARCH" in x86_64|amd64) A=linux_amd64;; aarch64|arm64) A=linux_arm64;; *) error "Arquitetura não suportada: $ARCH";; esac
    if curl -fsSL "https://github.com/opencode-ai/opencode/releases/latest/download/opencode_${A}.tar.gz" -o /tmp/opencode.tgz 2>/dev/null; then
        tar -xzf /tmp/opencode.tgz -C "$OPENCODE_DIR" && chmod +x "$OPENCODE_DIR/opencode" && rm -f /tmp/opencode.tgz
        success "opencode instalado em $OPENCODE_DIR"
    else
        warn "Não foi possível baixar o opencode. Instale manualmente: https://github.com/opencode-ai/opencode"
    fi
}

create_shortcut() {
    BIN_DIR="$HOME/.local/bin"; mkdir -p "$BIN_DIR"
    cat > "$BIN_DIR/ufvai" << EOF
#!/bin/bash
# UFVAI v${VERSION} launcher (fonte)
SCRIPT_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="${INSTALL_ROOT}:\$PYTHONPATH"
exec python3 -m pesquisai.run_fast "\$@"
EOF
    chmod +x "$BIN_DIR/ufvai"
    ln -sf "$BIN_DIR/ufvai" "$BIN_DIR/pesquisai" 2>/dev/null || true
    [[ ":$PATH:" != *":$BIN_DIR:"* ]] && { export PATH="$BIN_DIR:$PATH"; grep -q '.local/bin' "$HOME/.bashrc" 2>/dev/null || echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"; }
    success "Atalho criado: ufvai (alias pesquisai mantido)"
}

create_launcher() {
    cat > "$HOME/PesquisAI/start.sh" << EOF
#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# UFVAI v${VERSION}-offline — Iniciador
# ═══════════════════════════════════════════════════════════════
cd "\$(dirname "\$0")"
echo "🔎 UFVAI v${VERSION}-offline"
echo "─────────────────────────────────────────────────────────────"
[ -f "\$PWD/config/ufvai.env" ] && set -a && source "\$PWD/config/ufvai.env" && set +a
export PESQUISAI_LANG="\${PESQUISAI_LANG:-\${LANG%%.*}}"
python3 -m pesquisai.run_fast
EOF
    chmod +x "$HOME/PesquisAI/start.sh"
    # Modelo de env para telemetria opt-in (comentado = inerte)
    [ -f "$HOME/PesquisAI/config/ufvai.env" ] || cat > "$HOME/PesquisAI/config/ufvai.env" << 'EOF'
# ── Configuração do UFVAI ──────────────────────────────────────
# Telemetria anônima OPT-IN (GA4 Measurement Protocol).
# Descomente e preencha APENAS se você é o administrador/produtor:
# UFVAI_GA_MEASUREMENT_ID=G-XXXXXXXXXX
# UFVAI_GA_API_SECRET=xxxxxxxxxxxxxxxxxxxx
# Kill-switch global (desliga telemetria mesmo com consentimento):
# UFVAI_TELEMETRY=0
EOF
    success "Iniciador criado: ~/PesquisAI/start.sh (+ modelo config/ufvai.env)"
}

main() {
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "🔎 UFVAI v${VERSION}-offline — Instalador"
    echo "═══════════════════════════════════════════════════════════════"
    INSTALL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    check_requirements
    setup_directories
    install_python_deps
    install_opencode
    create_shortcut
    create_launcher
    echo ""
    echo "✅ Instalação concluída!"
    echo ""
    echo "Para iniciar:"
    echo "  ~/PesquisAI/start.sh   · ou ·   ufvai"
    echo ""
    echo "Interface:  http://localhost:${UI_PORT}"
    echo "Terminal :  http://localhost:${TERM_PORT}"
    echo ""
    echo "Estrutura:"
    echo "  ~/PesquisAI/vault/     memória Obsidian"
    echo "  ~/PesquisAI/outputs/   entregáveis"
    echo "  ~/PesquisAI/config/    ufvai.env (telemetria opt-in)"
    echo ""
}

main "$@"
