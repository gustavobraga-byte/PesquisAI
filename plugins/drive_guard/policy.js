// SPDX-License-Identifier: MIT
// policy.js — política de caminhos do UFVAI Drive Guard (v0.7.7).
//
// Módulo PURO (só `node:path`, `node:fs`, `node:os`): não importa nada do
// motor, para poder ser testado isoladamente com Node puro.
//
// REGRA DO AUTOR (27/10/2026):
//   "não deixe acessar a pasta My Drive exceto a subpasta PesquisAI e todas
//    suas subpastas — mesmo estando em auto".
//
// Política: tudo sob a RAIZ VIGIADA (por padrão `/content/drive`) é proibido,
// EXCETO o que estiver sob a RAIZ PERMITIDA (por padrão
// `/content/drive/My Drive/PesquisAI`). Nada aqui depende de aprovação do
// usuário, então a flag `--auto` do motor não afeta a decisão.

import fs from "node:fs"
import os from "node:os"
import path from "node:path"

export const DEFAULT_MOUNT = "/content/drive"
export const DEFAULT_ALLOWED = "/content/drive/My Drive/PesquisAI"

// Chaves de entrada de ferramentas que carregam caminho.
const PATH_KEYS = new Set([
  "path",
  "filepath",
  "file_path",
  "file",
  "files",
  "directory",
  "dir",
  "cwd",
  "target",
  "source",
  "destination",
  "output",
  "outputpath",
  "output_path",
  "workdir",
  "workingdirectory",
])

const MAX_DEPTH = 6

// Sentinela para proteger o espaço de "My Drive" durante a tokenização.
const MYDRIVE_SENTINEL = "__UFVAI_MY_DRIVE__"

/** Troca `/content/drive/My Drive` por um token sem espaço. */
export function maskMyDrive(text) {
  return String(text)
    .replace(/\/content\/drive\/My\\?\s+Drive/gi, `/content/drive/${MYDRIVE_SENTINEL}`)
    .replace(/\/content\/drive\/MyDrive/gi, `/content/drive/${MYDRIVE_SENTINEL}`)
}

/** Desfaz maskMyDrive. */
export function unmask(text) {
  return String(text).split(MYDRIVE_SENTINEL).join("My Drive")
}

/** Normaliza um caminho para comparação (NFC + minúsculas + barras).
 *
 *  O Colab expõe a MESMA pasta do Drive com dois nomes — `My Drive` e
 *  `MyDrive` (mesmo inode, sem symlink). Como são o mesmo diretório, os dois
 *  nomes são reduzidos a `my drive`; sem isso, um caminho legítimo como
 *  `/content/drive/MyDrive/PesquisAI/x` seria bloqueado por ser apenas outra
 *  grafia da pasta permitida. */
function key(value) {
  return value
    .normalize("NFC")
    .replace(/\\/g, "/")
    .replace(/\/+/g, "/")
    .toLowerCase()
    .replace(/^\/content\/drive\/mydrive(?=\/|$)/, "/content/drive/my drive")
}

/** `child` está dentro de `root` (inclusive quando é o próprio root)? */
export function isInside(root, child) {
  const r = key(root).replace(/\/+$/, "")
  const c = key(child).replace(/\/+$/, "")
  return c === r || c.startsWith(r + "/")
}

/** Remove aspas, escapes e `file://` de um candidato a caminho. */
function clean(raw) {
  let s = String(raw).trim()
  if (!s) return ""
  if (/^file:\/\//i.test(s)) s = s.replace(/^file:\/\//i, "")
  s = s.replace(/^[`"']+/, "").replace(/[`"']+$/, "")
  // `\/content\/drive\/My\ Drive` → `/content/drive/My Drive`
  s = s.replace(/\\(["'` ])/g, "$1")
  if (s === "~") s = os.homedir()
  else if (s.startsWith("~/")) s = path.join(os.homedir(), s.slice(2))
  s = s.replace(/^\$HOME(?=\/|$)/, os.homedir())
  return s
}

/** Resolve o caminho real mesmo quando o alvo ainda não existe (realpath do
 *  ancestral mais próximo) — é o que desarma o symlink `MyDrive`. */
function realish(absolute) {
  let current = absolute
  const rest = []
  for (let i = 0; i < 40; i += 1) {
    try {
      const real = fs.realpathSync.native
        ? fs.realpathSync.native(current)
        : fs.realpathSync(current)
      return rest.length ? path.join(real, ...rest.reverse()) : real
    } catch {
      const parent = path.dirname(current)
      if (parent === current) break
      rest.push(path.basename(current))
      current = parent
    }
  }
  return absolute
}

function looksLikePath(value) {
  const s = String(value).trim()
  if (!s) return false
  return (
    s.startsWith("/") ||
    s.startsWith("~") ||
    s.startsWith("./") ||
    s.startsWith("../") ||
    s === "." ||
    s === ".." ||
    /^[A-Za-z]:[\\/]/.test(s) ||
    /(^|\/)My\s*Drive(\/|$)/i.test(s) ||
    /^file:\/\//i.test(s)
  )
}

/**
 * Cria a guarda.
 *
 * @param {object} [options]
 * @param {string} [options.mount]    raiz vigiada (default `/content/drive`)
 * @param {string} [options.allowed]  raiz permitida (default `.../My Drive/PesquisAI`)
 * @param {string} [options.cwd]      diretório de trabalho para caminhos relativos
 * @param {(line: string) => void} [options.log]
 */
export function makeGuard(options = {}) {
  const mount = path.normalize(options.mount || DEFAULT_MOUNT)
  const allowed = path.normalize(options.allowed || DEFAULT_ALLOWED)
  const cwd = options.cwd || process.cwd()
  const log = typeof options.log === "function" ? options.log : () => {}

  /** Converte qualquer entrada em caminho absoluto canônico (ou ""). */
  function canonical(raw, base) {
    const cleaned = clean(raw)
    if (!cleaned) return ""
    let absolute
    if (path.isAbsolute(cleaned)) absolute = path.normalize(cleaned)
    else absolute = path.resolve(base || cwd, cleaned)
    return realish(absolute)
  }

  function decide(raw, base) {
    const canonicalPath = canonical(raw, base)
    if (!canonicalPath) return { allow: true, reason: "", path: "" }
    if (!isInside(mount, canonicalPath)) return { allow: true, reason: "", path: canonicalPath }
    if (isInside(allowed, canonicalPath)) return { allow: true, reason: "", path: canonicalPath }
    const reason =
      `Acesso bloqueado pelo UFVAI Drive Guard (v0.7.7): "${canonicalPath}" está em ` +
      `"My Drive" fora de "${allowed}". Só a pasta PesquisAI (e subpastas) é acessível — ` +
      `esta regra vale também em modo automático (--auto).`
    log(reason)
    return { allow: false, reason, path: canonicalPath }
  }

  /** Verifica um caminho (aceita relativo ao cwd/base informado). */
  function checkPath(raw, base) {
    return decide(raw, base)
  }

  /** Verifica o texto de um comando de shell. */
  function checkCommand(raw) {
    if (typeof raw !== "string" || !raw.trim()) return { allow: true, reason: "" }
    const masked = maskMyDrive(raw)
    const findings = []

    // 1) Caminhos absolutos do Drive em qualquer posição do comando
    //    (`cat /content/drive/My Drive/x`, `python3 -c "open(...)"` etc.).
    const drivePath = /\/content\/drive\/[^\s"'`;|&<>)]*/g
    let match
    while ((match = drivePath.exec(masked)) !== null) {
      const candidate = unmask(match[0])
      if (!findings.includes(candidate)) findings.push(candidate)
    }

    // 2) Tokens (caminhos relativos que escapam, `file://`, `~`).
    for (const token of tokenize(masked)) {
      const candidate = unmask(token)
      if (!looksLikePath(candidate)) continue
      if (!findings.includes(candidate)) findings.push(candidate)
    }

    let touchedMount = 0
    for (const candidate of findings) {
      const verdict = decide(candidate, cwd)
      if (isInside(mount, verdict.path || candidate)) touchedMount += 1
      if (!verdict.allow) return verdict
    }
    // Referência opaca: o comando cita o Drive, mas nenhum caminho pôde ser
    // resolvido (ex.: concatenação de variáveis). Falha fechada.
    const mentionsDrive = /\/content\/drive/i.test(unmask(masked))
    if (mentionsDrive && touchedMount === 0) {
      const reason =
        "Acesso bloqueado pelo UFVAI Drive Guard (v0.7.7): o comando referencia " +
        '"My Drive"/`/content/drive` de forma que não pôde ser verificada. ' +
        `Só "${allowed}" (e subpastas) é acessível.`
      log(reason)
      return { allow: false, reason, path: "" }
    }
    return { allow: true, reason: "" }
  }

  /** Verifica uma entrada de ferramenta (read/write/edit/glob/grep/bash...). */
  function checkToolInput(tool, input) {
    const name = String(tool || "").toLowerCase()
    if (name === "bash" || name === "shell" || name === "sh" || name === "terminal") {
      const command =
        input && typeof input === "object"
          ? input.command || input.cmd || input.script || ""
          : input
      return checkCommand(command)
    }
    const base = input && typeof input === "object" && typeof input.cwd === "string" ? input.cwd : cwd
    for (const candidate of collectStrings(input, "", 0)) {
      const byKey = PATH_KEYS.has(candidate.key)
      if (!byKey && !looksLikePath(candidate.value)) continue
      const verdict = decide(candidate.value, base)
      if (!verdict.allow) return verdict
    }
    return { allow: true, reason: "" }
  }

  /** Verifica um padrão de busca (glob) ou expressão (grep).
   *
   *  Só um padrão ABSOLUTO pode alcançar o Drive por si; um padrão textual
   *  (`grep "My Drive"`) não é caminho — o `path` da ferramenta é verificado
   *  em `checkToolInput`. */
  function checkPattern(pattern) {
    if (typeof pattern !== "string") return { allow: true, reason: "" }
    if (!pattern.startsWith("/") && !pattern.startsWith("~")) {
      return { allow: true, reason: "" }
    }
    return decide(pattern)
  }

  return { mount, allowed, cwd, checkPath, checkCommand, checkToolInput, checkPattern }
}

/** Percorre as strings de uma entrada, guardando a chave de origem. */
function collectStrings(value, keyName, depth, out = []) {
  if (depth > MAX_DEPTH || value == null) return out
  if (typeof value === "string") {
    out.push({ key: String(keyName || "").toLowerCase(), value })
    return out
  }
  if (Array.isArray(value)) {
    for (const item of value) collectStrings(item, keyName, depth + 1, out)
    return out
  }
  if (typeof value === "object") {
    for (const [k, v] of Object.entries(value)) collectStrings(v, k, depth + 1, out)
  }
  return out
}

/** Tokeniza um comando de shell respeitando aspas e escapes. */
export function tokenize(command) {
  const tokens = []
  let current = ""
  let quote = null
  const push = () => {
    if (current) {
      tokens.push(current)
      current = ""
    }
  }
  for (let i = 0; i < command.length; i += 1) {
    const ch = command[i]
    if (quote) {
      if (ch === "\\" && quote === '"' && i + 1 < command.length) {
        current += command[(i += 1)]
        continue
      }
      if (ch === quote) {
        quote = null
        continue
      }
      current += ch
      continue
    }
    if (ch === "\\" && i + 1 < command.length) {
      current += command[(i += 1)]
      continue
    }
    if (ch === '"' || ch === "'") {
      quote = ch
      continue
    }
    if (/[\s;|&<>(){}[\]`,=]/.test(ch)) {
      push()
      continue
    }
    current += ch
  }
  push()
  return tokens
}

/**
 * Avalia um evento do hook `permission.evaluate` do motor.
 * Devolve a razão do bloqueio ou `null` (sem opinião).
 */
export function evaluatePermission(guard, event, cwd) {
  const action = String(event?.action || "")
  const resources = Array.isArray(event?.resources) ? event.resources : []
  if (action === "read" || action === "edit" || action === "external_directory") {
    for (const resource of resources) {
      const verdict = guard.checkPath(resource, cwd)
      if (!verdict.allow) return verdict.reason
    }
    return null
  }
  if (action === "shell") {
    for (const resource of resources) {
      const verdict = guard.checkCommand(resource)
      if (!verdict.allow) return verdict.reason
    }
    return null
  }
  if (action === "glob" || action === "grep") {
    for (const resource of resources) {
      const verdict = guard.checkPattern(resource)
      if (!verdict.allow) return verdict.reason
    }
  }
  return null
}
