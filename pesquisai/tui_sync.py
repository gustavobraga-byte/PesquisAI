"""pesquisai/tui_sync.py — v0.7.11-web9: sincronização em tempo real TUI ↔ web.

O problema de sincronizar as duas interfaces não é de transporte (as duas já
falam com o mesmo motor), é de **intenção**: o motor não sabe qual sessão a
TUI está *exibindo* — só sabe qual sessão recebeu mensagem. Inferir isso por
eventos (`session.execution.started`) erra sempre que o usuário apenas troca
de aba/sessão no terminal, e o polling de 2,5 s na web adiciona até 2,5 s de
atraso.

A TUI do OpenCode V2 expõe a rota atual ao plugin (`context.ui.router`), então
o próprio terminal **publica** a sessão que está na tela:

* a cada 400 ms (barato: leitura em memória) e imediatamente no evento
  `session.execution.started`, grava ``/tmp/ufvai-focus.json``;
* o proxy da web (``ocweb``) observa o arquivo a cada 250 ms e faz *push*
  para as páginas abertas por ``/__ufvai/live`` (SSE) — a troca acontece em
  milissegundos, não em segundos;
* no sentido inverso, a web grava ``/tmp/ufvai-web-focus.json`` ao navegar e
  este plugin navega a TUI para a mesma sessão (se o foco tiver < 5 s).

Nada aqui inventa estado: o valor publicado é ``context.ui.router.current()``
— exatamente a sessão que o terminal mostra. Se a API não existir na versão do
motor, o plugin não publica nada e o proxy cai no comportamento anterior
(eventos + polling), sem quebrar a TUI.
"""

from __future__ import annotations

import json
import os

SYNC_PLUGIN_DIR: str = os.path.expanduser("~/.config/opencode/tui/ufvai-sync")
SYNC_PLUGIN_NAME: str = "ufvai-sync"

SYNC_PLUGIN_PACKAGE_JSON: dict = {
    "name": SYNC_PLUGIN_NAME,
    "version": "1.0.0",
    "private": True,
    "type": "module",
    "description": "UFVAI — sincronização em tempo real entre a TUI e a interface web",
    "exports": {"./tui": "./tui.tsx"},
}

SYNC_PLUGIN_TUI_TS: str = r'''import { Plugin } from "@opencode/plugin/tui"
import { readFileSync, renameSync, writeFileSync } from "node:fs"

/**
 * UFVAI — sincronização em tempo real TUI <-> web (v0.7.11-web9).
 *
 * Publica em FOCUS_FILE a sessão que a TUI está exibindo (a cada 400 ms e
 * imediatamente em `session.execution.started`). O proxy da web lê o arquivo
 * e faz push por SSE para as páginas abertas — a web troca de sessão em
 * milissegundos, sem polling.
 *
 * No sentido inverso, lê WEB_FOCUS_FILE (gravado pela web) e navega para a
 * sessão escolhida no navegador, desde que o foco seja recente.
 */

const FOCUS = process.env.UFVAI_FOCUS_FILE || "/tmp/ufvai-focus.json"
const WEB = process.env.UFVAI_WEB_FOCUS_FILE || "/tmp/ufvai-web-focus.json"
const PUBLISH_MS = 250
const FOLLOW_MS = 400
const FOLLOW_MAX_AGE = 5000

function atomicWrite(path: string, text: string) {
  const tmp = `${path}.${process.pid}.tmp`
  writeFileSync(tmp, text)
  renameSync(tmp, path)
}

function current(context: any): { sid: string; route: string } {
  try {
    let raw = context && context.ui && context.ui.router && context.ui.router.current
    if (typeof raw === "function") raw = raw()
    if (!raw || typeof raw !== "object") return { sid: "", route: "" }
    const sid =
      raw.sessionID ||
      (raw.session && raw.session.id) ||
      (raw.params && raw.params.sessionID) ||
      (raw.data && raw.data.sessionID) ||
      ""
    return { sid: String(sid || ""), route: String(raw.type || raw.name || "") }
  } catch {
    return { sid: "", route: "" }
  }
}

export default Plugin.define({
  id: "ufvai.sync",
  setup(context: any) {
    let lastSid = ""
    let lastWebTs = 0
    let lastWrite = 0
    let stopped = false

    const publish = () => {
      if (stopped) return
      const now = current(context)
      if (!now.sid) return
      const t = Date.now()
      // reescreve a cada 2 s mesmo sem trocar de sessão: mantém o arquivo
      // fresco para páginas web que conectam depois e para o /tmp limpo.
      if (now.sid === lastSid && t - lastWrite < 2000) return
      lastSid = now.sid
      lastWrite = t
      try {
        atomicWrite(
          FOCUS,
          JSON.stringify({
            sid: now.sid,
            ts: Date.now(),
            route: now.route || "session",
            source: "tui",
          }),
        )
      } catch {
        // melhor esforço: nunca derruba a TUI por causa do arquivo
      }
    }

    const follow = () => {
      if (stopped) return
      let data: any
      try {
        data = JSON.parse(readFileSync(WEB, "utf8"))
      } catch {
        return
      }
      const ts = Number((data && data.ts) || 0)
      const sid = String((data && data.sid) || "")
      if (!sid || ts <= lastWebTs) return
      lastWebTs = ts
      if (Date.now() - ts > FOLLOW_MAX_AGE) return
      if (current(context).sid === sid) return
      try {
        context.ui.router.navigate({ type: "session", sessionID: sid })
      } catch {}
    }

    let off: any
    try {
      off = context.data.on("session.execution.started", () => publish())
    } catch {}
    publish()
    const t1 = setInterval(() => publish(), PUBLISH_MS)
    const t2 = setInterval(() => follow(), FOLLOW_MS)

    return () => {
      stopped = true
      clearInterval(t1)
      clearInterval(t2)
      try {
        if (typeof off === "function") off()
      } catch {}
    }
  },
})
'''


def install_sync_plugin(plugin_dir: str | None = None) -> str:
    """Grava o pacote do plugin de sincronização e devolve o diretório.

    Idempotente: só reescreve ``tui.tsx`` e ``package.json`` (conteúdo
    determinístico, sem estado do usuário). O ``tui.tsx`` é gravado ANTES do
    ``package.json`` para o motor nunca apontar para um arquivo inexistente
    durante um reload.
    """
    root = plugin_dir or SYNC_PLUGIN_DIR
    os.makedirs(root, exist_ok=True)
    with open(os.path.join(root, "tui.tsx"), "w", encoding="utf-8") as fh:
        fh.write(SYNC_PLUGIN_TUI_TS)
    with open(os.path.join(root, "package.json"), "w", encoding="utf-8") as fh:
        json.dump(SYNC_PLUGIN_PACKAGE_JSON, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return root
