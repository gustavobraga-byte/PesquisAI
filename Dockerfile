# Dockerfile — PesquisAI
#
# Imagem para execução local (fora do Google Colab).
# Requer binário opencode instalado separadamente ou montado como volume.
#
# Uso:
#   docker build -t pesquisai .
#   docker run -p 8000:8000 -p 8001:8001 pesquisai

FROM python:3.11-slim

LABEL org.opencontainers.image.title="PesquisAI"
LABEL org.opencontainers.image.description="Agente de IA para Pesquisa Científica com foco em dados brasileiros"
LABEL org.opencontainers.image.version="0.5.1"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.source="https://github.com/gustavobraga-byte/PesquisAI"

# Evitar prompts interativos
ENV DEBIAN_FRONTEND=noninteractive

# Instalar dependências de sistema
RUN apt-get update -qq && \
    apt-get install -y -qq \
        ttyd \
        git \
        curl \
        xclip \
        xsel \
    && rm -rf /var/lib/apt/lists/*

# Copiar o projeto
WORKDIR /app
COPY . .

# Instalar dependências Python
RUN pip install --no-cache-dir -e .

# Portas: terminal web (8000) e wrapper (8001)
EXPOSE 8000 8001

# Por padrão, apenas imprime ajuda.
# Para uso real, montar opencode e executar via run_fast.py.
CMD ["python", "-c", "from pesquisai.run_fast import run; run()"]
