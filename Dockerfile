# Dockerfile — UFVAI v0.6.9
#
# Imagem para execução offline (fora do Google Colab).
# Requer binário opencode instalado separadamente ou montado como volume.
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

FROM python:3.12-slim AS base

LABEL org.opencontainers.image.title="UFVAI"
LABEL org.opencontainers.image.description="Agente de IA para Pesquisa Científica com foco em dados brasileiros"
LABEL org.opencontainers.image.version="0.6.9"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.source="https://github.com/gustavobraga-byte/PesquisAI"
LABEL org.opencontainers.image.vendor="Universidade Federal de Viçosa (UFV)"

# ── Variáveis de ambiente ─────────────────────────────────────
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UFVAI_NO_OPEN=1 \
    UFVAI_NO_KEEPALIVE=1 \
    PESQUISAI_OBSIDIAN_VAULT=/home/ufvai/PesquisAI/vault

# ── Dependências de sistema ───────────────────────────────────
RUN apt-get update -qq && \
    apt-get install -y -qq --no-install-recommends \
        ttyd \
        git \
        curl \
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

# ── Criar estrutura de diretórios do usuário ──────────────────
RUN mkdir -p /home/ufvai/PesquisAI/vault \
             /home/ufvai/PesquisAI/config \
             /home/ufvai/PesquisAI/outputs \
    && chown -R ufvai:ufvai /home/ufvai/PesquisAI \
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
