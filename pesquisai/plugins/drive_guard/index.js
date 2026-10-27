// SPDX-License-Identifier: MIT
// index.js — UFVAI Drive Guard (v0.7.7)
//
// Plugin do servidor UFVAI V2 (OpenCode 2.x) que impede o agente de acessar
// "My Drive" fora da pasta PesquisAI — inclusive com `--auto`.
//
// Como funciona (duas camadas independentes de aprovação):
//   1. hook `permission.evaluate` — reescreve a decisão para `deny` antes de
//      qualquer execução. Regras `deny` são finais e não dependem do cliente,
//      portanto `--auto` não as contorna.
//   2. hook `tool.execute.before` — inspeciona a entrada da ferramenta
//      (read/write/edit/glob/grep/bash) e lança erro antes de tocar no disco.
//
// Opções (via `plugins: [{ package, options }]` em opencode.json/ufvai.json)
// ou ambiente:
//   mount    — raiz vigiada          (default `/content/drive`)
//   allowed  — raiz permitida        (default `/content/drive/My Drive/PesquisAI`)
//   logFile  — arquivo de auditoria  (default `~/.local/state/ufvai/drive-guard.log`)
//
// Variáveis de ambiente equivalentes: UFVAI_DRIVE_GUARD_ROOT,
// UFVAI_DRIVE_GUARD_ALLOWED, UFVAI_DRIVE_GUARD_LOG.

import fs from "node:fs"
import os from "node:os"
import path from "node:path"

import { evaluatePermission, makeGuard } from "./policy.js"

export const PLUGIN_ID = "ufvai.drive-guard"

function openLog(file) {
  const target =
    file ||
    process.env.UFVAI_DRIVE_GUARD_LOG ||
    path.join(
      process.env.XDG_STATE_HOME || path.join(os.homedir(), ".local", "state"),
      "ufvai",
      "drive-guard.log",
    )
  return (line) => {
    try {
      fs.mkdirSync(path.dirname(target), { recursive: true })
      fs.appendFileSync(target, `${new Date().toISOString()}\t${line}\n`, "utf8")
    } catch {
      /* auditoria é best-effort: nunca derruba o motor */
    }
  }
}

export default {
  id: PLUGIN_ID,
  async setup(ctx) {
    const options = ctx?.options && typeof ctx.options === "object" ? ctx.options : {}
    const cwd = ctx?.location?.directory || process.cwd()
    const log = openLog(options.logFile)

    const guard = makeGuard({
      mount: options.mount || process.env.UFVAI_DRIVE_GUARD_ROOT,
      allowed: options.allowed || process.env.UFVAI_DRIVE_GUARD_ALLOWED,
      cwd,
      log,
    })

    // Camada 1 — decisão de permissão (vale para allow/ask; `deny` é final).
    await ctx.permission.hook("evaluate", (event) => {
      const reason = evaluatePermission(guard, event, cwd)
      if (!reason) return
      event.effect = "deny"
      event.message = reason
    })

    // Camada 2 — antes de a ferramenta tocar no disco.
    await ctx.tool.hook("execute.before", (event) => {
      const verdict = guard.checkToolInput(event.tool, event.input)
      if (verdict.allow) return
      throw new Error(verdict.reason)
    })

    log(`plugin carregado (mount=${guard.mount}; allowed=${guard.allowed})`)

    return () => {
      log("plugin descarregado")
    }
  },
}
