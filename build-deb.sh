#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# build-deb.sh — empacotamento Debian/Ubuntu do UFVAI (engine PesquisAI)
# ═══════════════════════════════════════════════════════════════════════════
# Gera o .deb offline a partir DESTA árvore de código, com:
#   • código do app + agentes + i18n + docs em /opt/pesquisai
#   • ttyd empacotado (sem sudo no boot)
#   • launcher /usr/bin/ufvai (+ alias /usr/bin/pesquisai)
#   • ufvai-engine: instalador do motor OpenCode V2
#   • .pth para `import pesquisai` funcionar fora de /opt (autopilot do agente)
#   • postinst idempotente, sem pip e sem rede
#
# Uso:
#   ./build-deb.sh                 # amd64 (arquitetura da máquina, se suportada)
#   ./build-deb.sh amd64
#   ./build-deb.sh arm64
#   ./build-deb.sh both            # amd64 + arm64
#   ./build-deb.sh --no-ttyd amd64 # sem binário ttyd (o boot tenta apt/curl)
#   ./build-deb.sh --rev offline1  # revisão Debian (padrão: offline1)
#   ./build-deb.sh --keep          # preserva o staging em /tmp para inspeção
#
# Requisitos de build: dpkg-deb, tar, gzip, xz, curl (para o ttyd).
# O resultado vai para ./debs/.
# ═══════════════════════════════════════════════════════════════════════════
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG="pesquisai"
REV="offline1"
WITH_TTYD=1
KEEP=0
TARGET=""

TTYD_VERSION="${TTYD_VERSION:-1.7.7}"
ENGINE_REFERENCE="${UFVAI_ENGINE_VERSION:-2.2.5}"
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/ufvai-build"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
die()   { echo -e "${RED}[ERRO]${NC} $*" >&2; exit 1; }

usage() { sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'; exit 0; }

while [ $# -gt 0 ]; do
    case "$1" in
        --no-ttyd) WITH_TTYD=0 ;;
        --keep)    KEEP=1 ;;
        --rev)     REV="${2:?--rev exige um valor}"; shift ;;
        --rev=*)   REV="${1#*=}" ;;
        -h|--help) usage ;;
        amd64|arm64|both) TARGET="$1" ;;
        *) die "Argumento desconhecido: $1 (use --help)" ;;
    esac
    shift
done

[ -n "$TARGET" ] || TARGET="$(dpkg --print-architecture)"
[ "$TARGET" = "both" ] && TARGETS=(amd64 arm64) || TARGETS=("$TARGET")

VERSION="$(sed -n 's/^__version__: *str *= *"\([^"]*\)".*/\1/p' \
    "$ROOT/pesquisai/__version__.py" | head -n1)"
[ -n "$VERSION" ] || die "Não foi possível ler a versão em pesquisai/__version__.py"
FULL_VERSION="${VERSION}-${REV}"

command -v dpkg-deb >/dev/null || die "dpkg-deb não encontrado (sudo apt install dpkg)"
command -v tar >/dev/null || die "tar não encontrado"
command -v gzip >/dev/null || die "gzip não encontrado"

# Data reprodutível: último commit, se houver git; senão, data fixa.
SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-$(git -C "$ROOT" log -1 --format=%ct 2>/dev/null || echo 1762000000)}"
export SOURCE_DATE_EPOCH
BUILD_DATE="$(date -R)"

# ── ttyd ────────────────────────────────────────────────────────────────────
ttyd_cache_path() {
    local arch="$1" bin
    case "$arch" in
        amd64) bin="x86_64" ;;
        arm64) bin="aarch64" ;;
        *) die "Arquitetura sem ttyd pré-compilado: $arch" ;;
    esac
    echo "$CACHE_DIR/ttyd-${TTYD_VERSION}-${bin}"
}

download_ttyd() {
    local arch="$1" dest="$2" tmp
    tmp="$(ttyd_cache_path "$arch")"
    mkdir -p "$CACHE_DIR"
    if [ ! -s "$tmp" ]; then
        info "Baixando ttyd ${TTYD_VERSION} para ${arch}…"
        local asset
        case "$arch" in amd64) asset="x86_64" ;; arm64) asset="aarch64" ;; esac
        curl -fsSL --retry 3 --connect-timeout 15 \
            "https://github.com/tsl0922/ttyd/releases/download/${TTYD_VERSION}/ttyd.${asset}" \
            -o "$tmp.part" || die "Falha ao baixar ttyd (use --no-ttyd para empacotar sem ele)"
        mv "$tmp.part" "$tmp"
    fi
    # Sanidade: precisa ser ELF e ter tamanho plausível.
    local size; size="$(stat -c %s "$tmp")"
    [ "$size" -gt 500000 ] || die "ttyd baixado parece inválido (${size} bytes)"
    head -c 4 "$tmp" | grep -q $'\x7fELF' || die "ttyd baixado não é um ELF"
    install -m 755 "$tmp" "$dest"
}

# ── staging ─────────────────────────────────────────────────────────────────
build_arch() {
    local arch="$1"
    local stage out size
    stage="$(mktemp -d "${TMPDIR:-/tmp}/${PKG}-${FULL_VERSION}-${arch}.XXXXXX")"
    out="$ROOT/debs/${PKG}_${FULL_VERSION}_${arch}.deb"

    info "Preparando ${PKG} ${FULL_VERSION} para ${arch}…"
    mkdir -p "$stage/DEBIAN" "$stage/opt/pesquisai" \
             "$stage/usr/bin" "$stage/usr/share/applications" \
             "$stage/usr/share/icons/hicolor/scalable/apps" \
             "$stage/usr/share/icons/hicolor/256x256/apps" \
             "$stage/usr/share/icons/hicolor/64x64/apps" \
             "$stage/usr/share/doc/pesquisai" \
             "$stage/usr/share/man/man1" \
             "$stage/usr/lib/python3/dist-packages"

    # ── Código do aplicativo ───────────────────────────────────
    # Cópia seletiva: nada de .git, caches, backups .bak-*, notebooks,
    # tests/ (não são necessários em runtime) nem artefatos de build.
    ( cd "$ROOT" && tar -cf - \
        --exclude='.git' \
        --exclude='.pytest_cache' \
        --exclude='__pycache__' --exclude='*/__pycache__' \
        --exclude='*.pyc' --exclude='*.pyo' \
        --exclude='*.bak-*' --exclude='*.orig-ufvai*' \
        --exclude='*.docx' --exclude='PesquisAI.ipynb*' \
        --exclude='deliverable' --exclude='tests' --exclude='debs' \
        --exclude='packaging' \
        AGENTS.md main.py pyproject.toml README.md MANUAL.md CHANGELOG.md \
        LICENSE PRIVACY.md SECURITY.md TELEMETRY.md \
        disclaimer_pesquisai.md declaracao_uso_ia.md citacao_pesquisai.md \
        pesquisai agents i18n assets docs scripts install-offline.sh \
    ) | tar -xf - -C "$stage/opt/pesquisai"

    # Limpeza defensiva (caso algum cache tenha passado pelo tar)
    find "$stage/opt/pesquisai" -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
    find "$stage/opt/pesquisai" -name '*.pyc' -delete 2>/dev/null || true

    # ── Metadados do pacote ────────────────────────────────────
    printf '%s\n' "$FULL_VERSION" > "$stage/opt/pesquisai/VERSION"
    cat > "$stage/opt/pesquisai/ENGINE.txt" <<EOF
Motor: OpenCode V2
Versão de referência validada: ${ENGINE_REFERENCE}
Validação: 2026-11-02 (opencode v2.2.5)
Instalação: ufvai --engine-install
EOF

    # ── ttyd empacotado ────────────────────────────────────────
    if [ "$WITH_TTYD" = "1" ]; then
        mkdir -p "$stage/opt/pesquisai/bin"
        download_ttyd "$arch" "$stage/opt/pesquisai/bin/ttyd"
        ok "ttyd ${TTYD_VERSION} empacotado"
    else
        warn "Pacote sem ttyd (o boot tentará apt/curl)"
    fi

    # ── Launchers ──────────────────────────────────────────────
    install -m 755 "$ROOT/packaging/ufvai"        "$stage/usr/bin/pesquisai"
    ln -sf pesquisai                              "$stage/usr/bin/ufvai"
    install -m 755 "$ROOT/packaging/ufvai-engine" "$stage/usr/bin/ufvai-engine"

    # ── Import do pacote fora de /opt (autopilot do agente) ────
    printf '/opt/pesquisai\n' > "$stage/usr/lib/python3/dist-packages/ufvai.pth"

    # ── Desktop e ícones ───────────────────────────────────────
    install -m 644 "$ROOT/packaging/ufvai.desktop" "$stage/usr/share/applications/ufvai.desktop"
    install -m 644 "$ROOT/assets/ico.svg"          "$stage/usr/share/icons/hicolor/scalable/apps/ufvai.svg"
    install -m 644 "$ROOT/assets/ufvai-256.png"    "$stage/usr/share/icons/hicolor/256x256/apps/ufvai.png"
    install -m 644 "$ROOT/assets/ufvai-64.png"     "$stage/usr/share/icons/hicolor/64x64/apps/ufvai.png"
    ln -sf ufvai.svg "$stage/usr/share/icons/hicolor/scalable/apps/pesquisai.svg"

    # ── Man page ───────────────────────────────────────────────
    sed "s/@VERSION@/${FULL_VERSION}/g" "$ROOT/packaging/ufvai.1" > "$stage/usr/share/man/man1/ufvai.1"
    gzip -9n "$stage/usr/share/man/man1/ufvai.1"
    ln -sf ufvai.1.gz "$stage/usr/share/man/man1/pesquisai.1.gz"

    # ── Documentação ───────────────────────────────────────────
    sed "s/@VERSION@/${FULL_VERSION}/g" "$ROOT/packaging/README.Debian" \
        > "$stage/usr/share/doc/pesquisai/README.Debian"
    {
        cat <<EOF
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: UFVAI (PesquisAI)
Upstream-Contact: Gustavo Bastos Braga <gustavo.braga@ufv.br>
Source: https://github.com/gustavobraga-byte/PesquisAI
License: MIT

Files: *
Copyright: $(date -u -d "@$SOURCE_DATE_EPOCH" +%Y) Gustavo Bastos Braga
License: MIT

EOF
        cat "$ROOT/LICENSE"
    } > "$stage/usr/share/doc/pesquisai/copyright"

    {
        echo "$PKG ($FULL_VERSION) unstable; urgency=medium"
        echo
        echo "  * Empacotamento offline a partir da árvore ${VERSION}."
        echo "  * Compatível com o motor OpenCode 2.2.x (validado em ${ENGINE_REFERENCE})."
        echo "  * ttyd ${TTYD_VERSION} empacotado (sem sudo no boot)."
        echo "  * Launcher ufvai/pesquisai com --version, --status, --doctor e --stop."
        echo "  * .pth torna 'import pesquisai' disponível para o autopilot do agente."
        echo
        echo " -- Gustavo Bastos Braga <gustavo.braga@ufv.br>  $BUILD_DATE"
    } > "$stage/usr/share/doc/pesquisai/changelog.Debian"
    gzip -9n "$stage/usr/share/doc/pesquisai/changelog.Debian"

    # ── Scripts de manutenção ──────────────────────────────────
    for script in postinst prerm postrm; do
        sed "s/@VERSION@/${FULL_VERSION}/g" "$ROOT/packaging/$script" \
            > "$stage/DEBIAN/$script"
        chmod 755 "$stage/DEBIAN/$script"
    done

    # ── Permissões (origem pode ser Drive FUSE 600/700) ────────
    find "$stage" -type d -exec chmod 755 {} +
    find "$stage" -type f -exec chmod 644 {} +
    chmod 755 "$stage/DEBIAN/postinst" "$stage/DEBIAN/prerm" "$stage/DEBIAN/postrm"
    chmod 755 "$stage/usr/bin/pesquisai" "$stage/usr/bin/ufvai-engine"
    [ -f "$stage/opt/pesquisai/install-offline.sh" ] && chmod 755 "$stage/opt/pesquisai/install-offline.sh"
    chmod 755 "$stage/opt/pesquisai/scripts/"*.sh 2>/dev/null || true
    [ -f "$stage/opt/pesquisai/bin/ttyd" ] && chmod 755 "$stage/opt/pesquisai/bin/ttyd"

    # ── Control ────────────────────────────────────────────────
    size="$(du -sk "$stage" | cut -f1)"
    cat > "$stage/DEBIAN/control" <<EOF
Package: $PKG
Version: $FULL_VERSION
Section: science
Priority: optional
Architecture: $arch
Provides: ufvai
Depends: python3 (>= 3.10), python3-cryptography, python3-requests, python3-bs4, python3-yaml, curl, ca-certificates, git, unzip, xz-utils
Recommends: tmux, xclip, xsel, openvpn, slirp4netns
Suggests: nodejs, npm
Installed-Size: $size
Maintainer: Gustavo Bastos Braga <gustavo.braga@ufv.br>
Homepage: https://github.com/gustavobraga-byte/PesquisAI
Description: UFVAI - agente de pesquisa científica offline (engine PesquisAI)
 UFVAI é um agente de pesquisa científica com foco em dados
 brasileiros (IBGE, DataSUS, agroBR), normas UFV/ABNT e integridade
 científica. A interface sobe em http://localhost:8001 e exibe a
 interface web do OpenCode (proxy local na porta 8002); o terminal
 ttyd continua na porta 8000 como reserva.
 .
 Versão offline: os dados ficam em ~/PesquisAI/ (vault Obsidian,
 outputs, backups, logs). Nada é sincronizado com a nuvem.
 .
 Compatível com o motor OpenCode V2 (2.2.x). O motor não é embutido
 no pacote; instale com "ufvai --engine-install" (sem sudo).
 .
 Recursos:
  - Agente UFVAI com memória persistente (Obsidian)
  - Dados oficiais brasileiros (IBGE, DataSUS, agroBR)
  - Normas UFV/ABNT, CEP/UFV e memorial RSC
  - Interface em 5 idiomas (PT/EN/ES/FR/ZH)
  - Drive Guard e salvamento autônomo de descobertas
EOF

    # ── md5sums ────────────────────────────────────────────────
    ( cd "$stage" && find . -type f ! -path './DEBIAN/*' -print0 \
        | sort -z | xargs -0 md5sum | sed 's#  \./#  #' ) > "$stage/DEBIAN/md5sums"

    # ── Datas reprodutíveis ────────────────────────────────────
    find "$stage" -exec touch -h -d "@$SOURCE_DATE_EPOCH" {} + 2>/dev/null || true

    # ── Build ──────────────────────────────────────────────────
    mkdir -p "$ROOT/debs"
    rm -f "$out"
    info "Empacotando ${out##*/}…"
    dpkg-deb --root-owner-group -Zxz -z6 --build "$stage" "$out" >/dev/null
    ok "Gerado: debs/${out##*/} ($(du -h "$out" | cut -f1))"

    [ "$KEEP" = "1" ] && info "Staging preservado em $stage" || rm -rf "$stage"
}

for arch in "${TARGETS[@]}"; do
    build_arch "$arch"
done

# ── Checksums ───────────────────────────────────────────────────────────────
( cd "$ROOT/debs" && sha256sum "${PKG}_${FULL_VERSION}"_*.deb > SHA256SUMS 2>/dev/null ) || true
ok "Checksums: debs/SHA256SUMS"
echo
info "Instalar:  sudo apt install ./debs/${PKG}_${FULL_VERSION}_${TARGETS[0]}.deb"
info "Testar:    ufvai --version && ufvai --doctor"
