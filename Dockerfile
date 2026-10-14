# Dockerfile — UFVAI v0.6.20
#
# Imagem para execução offline (fora do Google Colab), já com o motor
# **OpenCode V2** instalado para o usuário não-root `ufvai`.
#
# Uso:
#   docker build -t ufvai .
#   docker run -p 8001:8001 -p 8000:8000 ufvai
#
# Com volumes (para persistir vault e config):
#   docker run -p 8001:8001 -p 8000:8000 \
#     -v ufvai-vault:/home/ufvai/PesquisAI/vault \
#     -v ufvai-config:/home/ufvai/PesquisAI/config \
#     ufvai
#
# Sem buildkit/sem rede, o binário pode ser montado como volume — neste caso
# defina UFVAI_NO_OPENCODE_INSTALL=1 para pular a etapa de instalação.

FROM python:3.12-slim AS base

LABEL org.opencontainers.image.title="UFVAI"
LABEL org.opencontainers.image.description="Agente de IA para Pesquisa Científica com foco em dados brasileiros"
LABEL org.opencontainers.image.version="0.6.20"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.source="https://github.com/gustavobraga-byte/PesquisAI"
LABEL org.opencontainers.image.vendor="Universidade Federal de Viçosa (UFV)"

# ── Variáveis de ambiente ─────────────────────────────────────
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UFVAI_NO_OPEN=1 \
    UFVAI_NO_KEEPALIVE=1 \
    PATH=/home/ufvai/.opencode/bin:$PATH \
    PESQUISAI_OBSIDIAN_VAULT=/home/ufvai/PesquisAI/vault

# ── Dependências de sistema ───────────────────────────────────
RUN apt-get update -qq && \
    apt-get install -y -qq --no-install-recommends \
        ttyd \
        git \
        curl \
        ca-certificates \
        xclip \
        xsel \
        procps \
    && rm -rf /var/lib/apt/lists/*

# ── Usuário não-root ──────────────────────────────────────────
RUN groupadd -r ufvai && useradd -r -g ufvai -d /home/ufvai -m ufvai

# ── Copiar apenas dependências primeiro (cache de camadas) ────
WORKDIR /app
COPY pyproject.toml LICENSE README.md CHANGELOG.md ./
COPY pesquisai/__version__.py pesquisai/__version__.py

# ── Instalar dependências Python ──────────────────────────────
RUN pip install --no-cache-dir -e . 2>/dev/null || \
    pip install --no-cache-dir \
        google-api-python-client \
        google-auth-httplib2 \
        google-auth-oauthlib \
        "cryptography>=41.0" \
        "requests>=2.31" \
        "beautifulsoup4>=4.12" \
        pyyaml>=6.0

# ── Copiar código completo ────────────────────────────────────
COPY . .

# ── Motor OpenCode V2 (instalado como o usuário ufvai) ────────
# Mesmo instalador oficial usado no Colab por run_fast._install_opencode_if_missing
# (OPENCODE_INSTALL_V2). O binário fica em ~/.opencode/bin do usuário, que é o
# caminho que opencode_utils procura — nada precisa rodar como root.
ENV OPENCODE_INSTALL_V2=https://opencode.ai/v2/install \
    OPENCODE_MIN_MAJOR=2
RUN set -eu; \
    if [ "${UFVAI_NO_OPENCODE_INSTALL:-0}" = "1" ]; then \
        echo "UFVAI_NO_OPENCODE_INSTALL=1 — pulando a instalação do OpenCode."; \
        exit 0; \
    fi; \
    su -s /bin/bash ufvai -c "curl -fsSL ${OPENCODE_INSTALL_V2} | bash" || \
    su -s /bin/bash ufvai -c "npm install -g @opencode/cli"; \
    su -s /bin/bash ufvai -c 'export PATH="$HOME/.opencode/bin:$PATH"; opencode --version' \
        || echo "AVISO: opencode não respondeu a --version (o run_fast tentará de novo no boot)."

# ── Criar estrutura de diretórios do usuário ──────────────────
RUN mkdir -p /home/ufvai/PesquisAI/vault \
             /home/ufvai/PesquisAI/config \
             /home/ufvai/PesquisAI/outputs \
             /home/ufvai/.config/opencode/themes \
             /home/ufvai/.config/opencode/agents \
             /home/ufvai/.agents/skills \
    && chown -R ufvai:ufvai /home/ufvai/PesquisAI \
             /home/ufvai/.config \
             /home/ufvai/.agents \
             /home/ufvai/.opencode \
             /home/ufvai/.local \
    && chown -R ufvai:ufvai /app

# ── Portas ────────────────────────────────────────────────────
# 8000 = terminal web (ttyd)
# 8001 = wrapper HTTP (UI principal)
EXPOSE 8000 8001

# ── Health check ──────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -sf http://localhost:8001/ || exit 1

# ── Usuário não-root para execução ────────────────────────────
USER ufvai
WORKDIR /home/ufvai

# ── Entry point ───────────────────────────────────────────────
CMD ["python", "-c", "from pesquisai.run_fast import run; run()"]
