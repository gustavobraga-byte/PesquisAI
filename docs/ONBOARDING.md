# 🧭 Onboarding de primeiro uso — v0.7.10

> **Pedido do autor (05/11/2026):** *"um novo user, quero que ele use a apikey dele,
> mas de modo simples"* — e, para quem já usa: *"essa tela aparece se não tiverem
> uma apikey no sistema"*.

## 1. Quando a tela aparece

| Situação | Onboarding? |
|---|---|
| Nenhuma chave no `keys_store.json` **e** nenhuma variável de provedor no ambiente | **Sim** |
| Qualquer chave salva (Google, NVIDIA, OpenRouter, Anthropic, OpenAI…) | Não — abre como hoje |
| Usuário antigo que trocou de conta Google / apagou o store | **Sim** (a condição é objetiva, não é flag de "já viu") |
| `UFVAI_SKIP_ONBOARDING=1` | Não |
| Usuário clicou em **✕ (Agora não)** | Não nesta aba (`sessionStorage`); volta na próxima abertura sem chave |

A ordem de abertura é sempre: **Termos → (Bem-vindo de volta) → VPN da UFV
("é aluno?") → Onboarding**. O script do onboarding espera os overlays
anteriores e a resposta da VPN saírem da frente (poll de 500 ms).

## 2. Fluxo

```
┌──────────────────────────────────────────────────────────────┐
│ Para usar o UFVAI você precisa de um provedor de IA          │
│                                                              │
│  [🔑 Já tenho um provedor de IA]        → modal de sempre    │
│  [🆓 Não tenho / não sei o que é isso]  → opções guiadas     │
└──────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┬──────────────────┐
        ▼                     ▼                     ▼                  ▼
  Google Gemini         NVIDIA NIM            OpenRouter         OpenCode Go
  ★ RECOMENDADO         grátis                grátis (:free)     PAGO
        │                     │                     │                  │
        └────────── tutorial + link + campo para colar a chave ────────┘
                              │
                     POST /api/onboarding/key
                              │
        grava cifrado → injeta no serviço → modelo padrão → reinicia
```

### Passo 2 — tutorial de cada provedor

Cada tela tem: **passos numerados**, **link oficial** (abre em nova aba), uma
**reprodução da tela** do provedor (rotulada `reprodução da tela`) e o campo
para colar a chave.

| Provedor | Link | Prefixo | Variável | Modelo padrão |
|---|---|---|---|---|
| Google Gemini | `https://aistudio.google.com/api-keys` | `AIza` | `GOOGLE_GENERATIVE_AI_API_KEY` | `google/gemini-flash-lite-latest` |
| NVIDIA NIM | `https://build.nvidia.com/` | `nvapi-` | `NVIDIA_API_KEY` | — (escolher no seletor) |
| OpenRouter | `https://openrouter.ai/keys` | `sk-or-` | `OPENROUTER_API_KEY` | `openrouter/free` |
| OpenCode Go | `https://opencode.ai/go` | `sk-` | `OPENCODE_API_KEY` | — (pago) |

### Outros provedores (v0.7.11)

Abaixo dos quatro cards principais há **“Outro provedor (OpenAI, Anthropic,
Groq, Mistral…)”**. A lista é curada e cada item leva ao mesmo tutorial com
link oficial + campo da chave:

| Provedor | Variável | Prefixo |
|---|---|---|
| OpenAI | `OPENAI_API_KEY` | `sk-` / `sk-proj-` |
| Anthropic | `ANTHROPIC_API_KEY` | `sk-ant-` |
| Groq | `GROQ_API_KEY` | `gsk_` |
| Mistral | `MISTRAL_API_KEY` | — |
| DeepSeek | `DEEPSEEK_API_KEY` | `sk-` |
| Together AI | `TOGETHER_API_KEY` | — |
| Fireworks AI | `FIREWORKS_API_KEY` | `fw_` |
| xAI | `XAI_API_KEY` | `xai-` |
| Cohere | `COHERE_API_KEY` | — |

Esses provedores **não trocam o modelo padrão automaticamente** (o id do
modelo depende do catálogo do motor): escolha o modelo depois em
**🎛️ Modelo gratuito padrão** (Google, NVIDIA, OpenRouter) ou no seletor do
terminal.

No Google, o texto é explícito: **Criar chave → clicar em Copiar → voltar para esta
janela → colar**. A tela mostra o **print real** do Google AI Studio
(`assets/print-google-apikey.png`). Ao salvar, o modelo padrão vira o
**Gemini Flash-Lite Latest** com esforço **high**.

## 3. Regra do modelo padrão

- `GOOGLE_DEFAULT_MODEL = "google/gemini-flash-lite-latest"` e
  `GOOGLE_DEFAULT_VARIANT = "high"` (em `pesquisai/onboarding.py`).
- Com chave do Google, o boot **sempre** garante esse modelo no
  `~/.config/opencode/opencode.json`, preservando todo o resto:
  - `model` (raiz) = `google/gemini-flash-lite-latest` — o motor V2 **não retém
    variante** no campo raiz;
  - `agents.UFVAI.model` = `google/gemini-flash-lite-latest#high` — é daqui que a
    TUI mostra **“Gemini Flash-Lite Latest Google · high”**.
- Ajustes sem código:
  - `UFVAI_GOOGLE_MODEL=google/gemini-x` — troca o id;
  - `UFVAI_GOOGLE_VARIANT=max` — troca o esforço (padrão `high`);
  - `UFVAI_GOOGLE_MODEL_LOCK=0` — não força o padrão (respeita a escolha manual).
- Se o catálogo do motor estiver disponível, o id é conferido contra a lista real
  (`google_model_from_catalog`) e cai nos fallbacks declarados. **Nada é inventado.**

## 4. API

### `GET /api/onboarding`

```json
{
  "needs": true,
  "has_key": false,
  "google_model": "google/gemini-flash-lite-latest",
  "providers": [
    {"id": "google", "label": "Google Gemini", "env": "GOOGLE_GENERATIVE_AI_API_KEY",
     "url": "https://aistudio.google.com/api-keys", "paid": false,
     "recommended": true, "tagline": "Grátis no Google AI Studio · recomendado",
     "model": "google/gemini-flash-lite-latest"}
  ],
  "docs": "https://github.com/.../docs/CHAVES_API.md",
  "guide": "https://github.com/.../docs/chaves-api-tutorial.html"
}
```

### `POST /api/onboarding/key`

```json
{"provider": "google", "apikey": "AIza…"}
```

1. normaliza (espaços, aspas, quebras) e valida o **formato**;
2. grava **cifrado** em `backups/keys_store.json` (`save_encrypted_keys`);
3. injeta a variável em `os.environ` e no `_env` do serviço;
4. grava o modelo padrão (Google → Gemini Flash-Lite Latest; OpenRouter → `openrouter/free`);
5. chama `_apply_opencode_env_change_async()` (reergue o serviço e reinicia o terminal);
6. responde `{"ok": true, "provider": "...", "masked": "AIzaSy…cdef", "model": "..."}`.

**Nunca** registra a chave em log; a resposta traz só `masked`.
Erros: `400` provedor não suportado / formato inválido; `500` falha ao gravar o store.

> ⚠️ O endpoint **não** faz chamada de rede ao provedor. A validação é de formato;
> uma chave sintaticamente válida mas revogada só aparece como erro no terminal.
> (Validar online ficou fora do escopo para não travar o onboarding offline.)

## 5. Arquivos

| Arquivo | Papel |
|---|---|
| `pesquisai/onboarding.py` | regras puras: prefixos, validação, máscara, condição, modelo, merge |
| `pesquisai/launch_app.py` | `GET /api/onboarding`, `POST /api/onboarding/key`, `_ensure_google_default_model`, hook no `load_keys_from_drive` |
| `pesquisai/launch_app_responsive_v041.py` | overlay `#onboard-overlay` (3 passos + sucesso), CSS e JS |
| `tests/test_v0710_onboarding.py` | 25 verificações (funções puras + contrato de UI/HTTP) |

## 6. Testes

```bash
pytest -o addopts="" tests/test_v0710_onboarding.py tests/test_version_sync.py -q
# 32 passed
```

> A suíte completa **não** foi executada neste runtime (o ambiente reinicia sob
> carga). Rode-a numa máquina estável antes de publicar.

## 7. Limitações conhecidas

- **As imagens são reproduções** em HTML/CSS, não capturas: as páginas de Google,
  NVIDIA e OpenRouter exigem login. Estão rotuladas como reprodução; o guia completo
  fica em [`chaves-api-tutorial.html`](chaves-api-tutorial.html).
- **Não há criação automática de chave** — o Google não expõe API pública para emitir
  chave em nome do usuário. O fluxo é: um clique no link + um colar.
- **Modelo `gemini-3.5-flash`:** o id é o pedido do autor; se o catálogo do provedor
  usar outro nome, ajuste `UFVAI_GOOGLE_MODEL` (ou o fallback pega o primeiro
  `gemini-*-flash` disponível).


## 8. Boot: espera a chave; ao salvar, reinício duro (v0.7.10)

- **Sem chave, o motor não nasce.** No boot, `needs_onboarding_now()` é avaliado
  antes do serviço (`run_fast.run`) e do terminal (`launch_app.launch`): o wrapper
  sobe (para servir a UI e a API), mas `opencode serve` e o ttyd ficam parados até
  existir uma chave.
- **Ao salvar a chave**, `_apply_opencode_env_change_async()` chama
  `_hard_restart_engine()`:
  1. encerra o terminal (ttyd + bash + TUI — árvore inteira);
  2. derruba o serviço do motor (todas as sessões em memória);
  3. sobe o serviço já com as chaves decifradas e o modelo/variante corretos;
  4. abre um terminal novo.
- Se a chave entrar por outro caminho (modal de Provedores), o onboarding
  detecta em até 3 s (`GET /api/onboarding` → `needs: false`) e recarrega a página.


### 8.1 Retry e fallback (v0.7.10)

- `ufvai-retry` espera ~62 s **só em mensagem de cota** (lê `retry in …s` quando existir); “high demand”/“overloaded” espera **5 s**; outros 429/503 não são atrasados.
- Na **5ª** falha do modelo principal, troca a sessão para
  `google/gemini-3.1-flash-lite` e repete; se o 3.1 também estourar, segue o
  fluxo normal (espera e desiste após 8).
- Configurável: `UFVAI_RETRY_SWITCH_AFTER`, `UFVAI_RETRY_FALLBACK`,
  `UFVAI_RETRY_DELAY_MS`, `UFVAI_RETRY_MAX_ATTEMPTS`.
