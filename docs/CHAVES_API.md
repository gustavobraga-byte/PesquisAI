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

### Google Gemini (free tier no AI Studio)
1. Acesse https://aistudio.google.com/api-keys.
2. Clique em **Criar chave de API** e copie (começa com `AIza`).
3. Cole em **UFVAI → Provedores → Google Gemini**.
4. O modelo padrão vira **Gemini Flash-Lite Latest · high**; outros modelos
   Google aparecem no seletor **🎛️ Modelo gratuito padrão**.

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

### Outros provedores (chave própria)
No onboarding, abra **“Outro provedor (OpenAI, Anthropic, Groq, Mistral…)”**.
A lista inclui OpenAI, Anthropic, Groq, Mistral, DeepSeek, Together,
Fireworks, xAI e Cohere; cada um tem link oficial e campo para colar a chave.
A chave é salva cifrada na variável padrão do provedor (ex.:
`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`).

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
