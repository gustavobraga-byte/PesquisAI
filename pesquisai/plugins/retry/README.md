# UFVAI Retry

Plugin do servidor (OpenCode V2) que intercepta o hook `retry` e, **somente
quando a mensagem é de cota** (`quota`, `RESOURCE_EXHAUSTED`,
`free_tier`, `per minute`, `rate limit`), troca a espera curta por **~62 s** —
a janela de 1 minuto da cota gratuita do Google.
- **“high demand” / “overloaded” / “temporarily”** (503): espera **curta**
  (5 s padrão; `demandDelayMs`/`UFVAI_RETRY_DEMAND_MS`, teto 30 s).
- Outros 429/503 (ex.: “Too many requests”) seguem o retry padrão do motor.

- Lê `retryDelay`/`retry in 23s` da própria mensagem, quando existir.
- Teto de 3 min por tentativa; desiste após `maxAttempts` (padrão 8).
- **Fallback:** após 5 tentativas no modelo principal, troca a sessão para
  `google/gemini-3.1-flash-lite` e repete (uma vez por sessão a cada 30 min).
- Opções: `{ "delayMs": 62000, "maxAttempts": 8, "switchAfter": 5,
  "fallbackModel": "google/gemini-3.1-flash-lite" }` na entrada de `plugins`,
  ou `UFVAI_RETRY_DELAY_MS` / `UFVAI_RETRY_MAX_ATTEMPTS` /
  `UFVAI_RETRY_SWITCH_AFTER` / `UFVAI_RETRY_FALLBACK`.
- Sem cota: não interfere em mais nada.
