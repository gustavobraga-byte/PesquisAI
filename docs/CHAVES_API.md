# Chaves de API — leia antes de começar

> 📘 **Guia visual (HTML, com as telas):** [`chaves-api-tutorial.html`](chaves-api-tutorial.html)
> — abre no navegador, funciona offline e pode ser impresso em PDF (Ctrl+P).
> Leva ~5 minutos e cobre OpenRouter, NVIDIA, modelo padrão e autosave.
>
> 🧭 **Primeiro uso (v0.7.10):** sem chave, o UFVAI mostra sozinho a tela de escolha
> do provedor — ver [`ONBOARDING.md`](ONBOARDING.md).

**Responsabilidade:** as chaves de API são **de sua responsabilidade**. Elas são
emitidas diretamente pelo provedor (NVIDIA, OpenRouter, OpenCode Go), e a
plataforma UFVAI **não tem qualquer vínculo** com esses provedores: não emite,
não cobra, não garante limites nem disponibilidade. Não compartilhe sua chave.

## 🆓 Como obter uma chave gratuita

### OpenRouter (modelos com sufixo `:free`)
1. Crie uma conta em https://openrouter.ai.
2. Acesse https://openrouter.ai/keys e clique em **Create key**.
3. Copie a chave (ela começa com `sk-or-`) e cole em **UFVAI → Provedores → OpenRouter**.
4. Escolha um modelo gratuito no seletor (ex.: `openrouter/free`).

### NVIDIA (modelos `nvidia/*`)
1. Crie uma conta em https://build.nvidia.com.
2. Escolha um modelo, abra a opção de API e gere uma chave (**Get API Key**).
3. Cole a chave (começa com `nvapi-`) em **UFVAI → Provedores → NVIDIA**.

Os limites de uso gratuito são definidos pelo provedor e podem mudar.

## 💳 Opções pagas

**OpenCode Go** é pago: https://opencode.ai/go. Use a chave na tela de Provedores.

## 🔒 Onde a chave fica

A chave é gravada **cifrada** na pasta `backups/` do seu Google Drive
(ou em `~/PesquisAI` no modo offline). Não é enviada a terceiros pela UFVAI.

---

# API keys — read before you start (English)

API keys are **your responsibility**. They are issued directly by the provider
(NVIDIA, OpenRouter, OpenCode Go). UFVAI has **no connection** with those
providers: it does not issue, bill, or guarantee limits or availability.
Free-tier limits are set by each provider. Never share your key.

- **OpenRouter:** sign up at openrouter.ai → https://openrouter.ai/keys → Create key → paste in UFVAI → Provedores.
- **NVIDIA:** sign up at build.nvidia.com → pick a model → Get API Key → paste in UFVAI → Provedores.
- **OpenCode Go (paid):** https://opencode.ai/go
