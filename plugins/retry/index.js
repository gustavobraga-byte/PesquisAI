// SPDX-License-Identifier: MIT
// index.js — UFVAI Retry (v0.7.10)
//
// O plano gratuito do Google limita a cota POR MINUTO (ex.: 250k tokens de
// entrada/min). O retry padrão do motor recomeça em poucos segundos e bate na
// mesma janela. Este plugin intercepta o hook `retry` e, para 429/503 ou
// mensagens de cota, espera a janela do provedor antes da próxima tentativa.
//
// Opções (entrada de `plugins` ou ambiente):
//   delayMs      — espera padrão quando a mensagem não informa (62 s)
//   maxAttempts  — tentativa máxima antes de desistir (8)
//   switchAfter  — tentativas no modelo principal antes do fallback (5)
//   fallbackModel— modelo de reserva (google/gemini-3.1-flash-lite)
//
// Ambiente: UFVAI_RETRY_DELAY_MS, UFVAI_RETRY_MAX_ATTEMPTS,
//           UFVAI_RETRY_SWITCH_AFTER, UFVAI_RETRY_FALLBACK.

export const PLUGIN_ID = "ufvai.retry"

// Só a mensagem de cota/limite por minuto merece a espera de 1 minuto.
// Outros 429/503 (ex.: "Too many requests", "overloaded") seguem o retry
// padrão do motor — este plugin não os atrasa.
const QUOTA_RE =
  /quota|RESOURCE_EXHAUSTED|exceeded your current quota|rate.?limit|free_tier|per.?minute/i

// Sobrecarga momentânea (503/"high demand") não é cota: espera curta.
const DEMAND_RE =
  /high demand|overload|temporarily|try again later|service unavailable|capacity/i
const RETRY_IN_RE =
  /(?:retry|try again)[^0-9]{0,48}?([0-9]+(?:\.[0-9]+)?)\s*(ms|s|sec|secs|seconds|m|min)\b/i

function clamp(value, lo, hi) {
  return Math.min(Math.max(value, lo), hi)
}

function selector(ref) {
  const text = String(ref || "").trim()
  const cut = text.indexOf("/")
  if (cut <= 0) return undefined
  return { providerID: text.slice(0, cut), id: text.slice(cut + 1).split("#")[0] }
}

function delayFor(message, fallbackMs) {
  const match = String(message || "").match(RETRY_IN_RE)
  if (!match) return clamp(fallbackMs, 5_000, 180_000)
  const n = Number(match[1])
  const unit = String(match[2] || "s").toLowerCase()
  const ms = unit === "ms" ? n : unit.startsWith("m") ? n * 60_000 : n * 1_000
  // +3 s de folga para a janela virar de fato.
  return clamp(ms + 3_000, 5_000, 180_000)
}

export default {
  id: PLUGIN_ID,
  async setup(ctx) {
    const options = ctx?.options && typeof ctx.options === "object" ? ctx.options : {}
    const fallbackMs = Number(options.delayMs || process.env.UFVAI_RETRY_DELAY_MS || 62_000)
    const maxAttempts = Number(options.maxAttempts || process.env.UFVAI_RETRY_MAX_ATTEMPTS || 8)
    const switchAfter = Number(options.switchAfter || process.env.UFVAI_RETRY_SWITCH_AFTER || 5)
    const demandMs = Number(options.demandDelayMs || process.env.UFVAI_RETRY_DEMAND_MS || 5_000)
    const fallbackRef = String(
      options.fallbackModel ||
        process.env.UFVAI_RETRY_FALLBACK ||
        "google/gemini-3.1-flash-lite",
    )
    const switched = new Map() // sessionID -> timestamp do último fallback

    await ctx.session.hook("retry", async (event) => {
      const message = String((event.error && event.error.message) || "")
      const isQuota = QUOTA_RE.test(message)
      if (!isQuota) {
        // v0.7.10: "high demand"/"overloaded" → espera curta (5 s padrão),
        // nunca os 62 s da cota.
        if (DEMAND_RE.test(message)) {
          event.decision =
            event.attempt >= maxAttempts
              ? { retry: false }
              : { retry: true, delay: clamp(demandMs, 1_000, 30_000) }
        }
        return
      }

      const fallback = selector(fallbackRef)
      const current = event.model ? `${event.model.providerID}/${event.model.id}` : ""
      const target = fallback ? `${fallback.providerID}/${fallback.id}` : ""
      const lastSwitch = switched.get(event.sessionID) || 0
      const canSwitch =
        fallback &&
        current !== target &&
        event.attempt >= switchAfter &&
        Date.now() - lastSwitch > 30 * 60_000

      if (canSwitch) {
        try {
          // v0.7.10: 5 tentativas no principal não resolveram — troca o modelo
          // DESTA sessão para o 3.1 Flash Lite e repete a mesma requisição.
          await ctx.session.switchModel({ sessionID: event.sessionID, model: fallback })
          switched.set(event.sessionID, Date.now())
          event.decision = { retry: true, delay: 1_500 }
          return
        } catch {
          // se a troca falhar, segue o fluxo normal (espera/desiste)
        }
      }

      if (event.attempt >= maxAttempts) {
        event.decision = { retry: false }
        return
      }
      event.decision = { retry: true, delay: delayFor(message, fallbackMs) }
    })
  },
}
