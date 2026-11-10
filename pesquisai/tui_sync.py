"""pesquisai/tui_sync.py — sincronização em tempo real TUI ↔ web (v0.8.0 / web14).

Modelo: o proxy (``ocweb``) decide uma ORDEM para as trocas de sessão (``seq``).
Batimentos da TUI — a mesma sessão repetida — não são trocas e não são
publicados: por isso não revertem uma navegação recente da web.

* TUI → web: o plugin faz ``POST /__ufvai/focus`` (``source: "tui"``) só quando
  a rota muda; o proxy publica no SSE ``/__ufvai/live`` na hora.
* web → TUI: o plugin mantém o stream ``/__ufvai/focus/stream`` (SSE, só eventos
  da web) e navega a TUI para a sessão escolhida no navegador. Sem o stream,
  lê ``/tmp/ufvai-web-focus.json`` a cada 100 ms.
* Batimento: a cada 2 s o arquivo de reserva é reescrito (sem evento).

Nada aqui inventa estado: a sessão publicada é ``context.ui.router.current()``.
Se a API não existir na versão do motor, o plugin não publica nada e a TUI
segue normal.
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
 * UFVAI — sincronização em tempo real TUI <-> web (v0.8.0 / web14).
 *
 * Regra única: só uma TROCA de sessão é publicada; batimentos não. A web e a
 * TUI aplicam apenas eventos mais novos (seq do servidor) e nunca "trocam" para
 * a sessão que já estão mostrando. Assim um batimento antigo não reverte uma
 * escolha recente.
 *
 *   TUI -> web:  POST /__ufvai/focus (source "tui") ao mudar de rota.
 *   web -> TUI:  stream SSE /__ufvai/focus/stream (só eventos da web). O proxy
 *                empurra na hora; se o stream cair, lê o arquivo de reserva.
 *
 * A rota vem de context.ui.router.current(). Se a API não existir na versão do
 * motor, o plugin fica silencioso e a TUI segue normal.
 */

const FOCUS = process.env.UFVAI_FOCUS_FILE || "/tmp/ufvai-focus.json"
const WEB = process.env.UFVAI_WEB_FOCUS_FILE || "/tmp/ufvai-web-focus.json"
const BASE = process.env.UFVAI_PROXY_URL || "http://127.0.0.1:8002"
const FOCUS_URL = process.env.UFVAI_FOCUS_URL || `${BASE}/__ufvai/focus`
const STREAM_URL = process.env.UFVAI_FOCUS_STREAM_URL || `${BASE}/__ufvai/focus/stream`
const PUBLISH_MS = 100
const HEARTBEAT_MS = 2000
const FILE_FOLLOW_MS = 100
const RECONNECT_MS = 1000

/** Entrega o foco ao proxy por HTTP (não bloqueia a TUI se falhar). */
function postFocus(sid: string, route: string) {
  try {
    const f = (globalThis as any).fetch
    if (typeof f !== "function") return
    const p = f(FOCUS_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sid, ts: Date.now(), route: route || "session", source: "tui" }),
    })
    if (p && typeof p.catch === "function") p.catch(() => {})
  } catch {}
}

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

/**
 * Acompanha o stream de foco da web (SSE via fetch). Reconecta sozinho.
 * `isUp()` diz se o stream está recebendo; a reserva por arquivo só age sem ele.
 */
function openStream(onEvent: (ev: any) => void, stopped: () => boolean) {
  let up = false
  let controller: any = null
  let timer: any = null
  const connect = async () => {
    timer = null
    if (stopped()) return
    try {
      const AC = (globalThis as any).AbortController
      controller = AC ? new AC() : null
      const f = (globalThis as any).fetch
      if (typeof f !== "function") throw new Error("sem fetch")
      const res = await f(STREAM_URL, {
        headers: { Accept: "text/event-stream" },
        signal: controller ? controller.signal : undefined,
      })
      if (!res || !res.ok || !res.body) throw new Error("status")
      up = true
      const reader = res.body.getReader()
      const dec = new TextDecoder()
      let buf = ""
      while (!stopped()) {
        const chunk = await reader.read()
        if (chunk.done) break
        buf += dec.decode(chunk.value, { stream: true })
        let idx = buf.indexOf("\n\n")
        while (idx >= 0) {
          const block = buf.slice(0, idx)
          buf = buf.slice(idx + 2)
          idx = buf.indexOf("\n\n")
          const line = block.split("\n").find((l: string) => l.startsWith("data: "))
          if (!line) continue
          try {
            onEvent(JSON.parse(line.slice(6)))
          } catch {}
        }
      }
    } catch {
      // sem stream (proxy reiniciando ou versão antiga): a reserva cobre
    }
    up = false
    if (!stopped()) timer = setTimeout(connect, RECONNECT_MS)
  }
  void connect()
  return {
    isUp: () => up,
    close: () => {
      try {
        if (controller) controller.abort()
      } catch {}
      if (timer) clearTimeout(timer)
    },
  }
}

export default Plugin.define({
  id: "ufvai.sync",
  setup(context: any) {
    let stopped = false
    let lastSid = ""     // última sessão PUBLICADA (troca real)
    let lastWrite = 0    // última escrita do arquivo de reserva
    let webSeq = -1      // último seq da web já aplicado
    let seeded = false   // a primeira leitura da web só serve de referência

    const writeFocus = (now: { sid: string; route: string }) => {
      lastWrite = Date.now()
      try {
        atomicWrite(
          FOCUS,
          JSON.stringify({ sid: now.sid, ts: Date.now(), route: now.route || "session", source: "tui" }),
        )
      } catch {
        // melhor esforço: nunca derruba a TUI por causa do arquivo
      }
    }

    const publish = () => {
      if (stopped) return
      const now = current(context)
      if (!now.sid) return
      if (now.sid === lastSid) {
        // batimento: mantém o arquivo de reserva fresco — não é troca
        if (Date.now() - lastWrite >= 2000) writeFocus(now)
        return
      }
      lastSid = now.sid
      writeFocus(now)
      postFocus(now.sid, now.route)
    }

    const applyWeb = (sid: string, seq: number) => {
      if (!sid || !(seq > webSeq)) return
      webSeq = seq
      if (current(context).sid === sid) return
      try {
        context.ui.router.navigate({ type: "session", sessionID: sid })
      } catch {}
    }

    const onStream = (ev: any) => {
      if (!ev) return
      if (ev.type === "snapshot") {
        const seq = Number(ev.seq) || 0
        if (!seeded) {
          seeded = true
          webSeq = Math.max(webSeq, seq)
          return
        }
        if (ev.source === "web") applyWeb(String(ev.sid || ""), seq)
        return
      }
      if (ev.type === "focus" && ev.source === "web") {
        seeded = true
        applyWeb(String(ev.sid || ""), Number(ev.seq) || 0)
      }
    }

    const followFile = () => {
      if (stopped) return
      // v0.8.0 (web15): o arquivo é SEMPRE acompanhado. Antes, um SSE
      // "aberto" mas bufferizado (proxy do Colab) desligava esta reserva:
      // o stream dizia isUp()=true e nenhum evento chegava — a TUI ficava
      // parada. O seq abaixo torna a leitura idempotente e barata.
      let data: any
      try {
        data = JSON.parse(readFileSync(WEB, "utf8"))
      } catch {
        return
      }
      const sid = String((data && data.sid) || "")
      const seq = Number((data && data.seq) || 0)
      if (!sid || !seq) return
      if (!seeded) {
        seeded = true
        webSeq = Math.max(webSeq, seq)
        return
      }
      applyWeb(sid, seq)
    }

    const stream = openStream(onStream, () => stopped)
    const offs: any[] = []
    for (const evt of ["session.execution.started", "session.viewed", "session.created"]) {
      try {
        const fn = context.data.on(evt, () => publish())
        if (typeof fn === "function") offs.push(fn)
      } catch {}
    }
    publish()
    const t1 = setInterval(() => publish(), PUBLISH_MS)
    const t2 = setInterval(() => followFile(), FILE_FOLLOW_MS)

    return () => {
      stopped = true
      clearInterval(t1)
      clearInterval(t2)
      stream.close()
      for (const fn of offs) {
        try {
          fn()
        } catch {}
      }
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
