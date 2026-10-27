// Teste do UFVAI Drive Guard (v0.7.7) — Node puro, sem dependências.
//   node tests/js/test_drive_guard.mjs
//
// Cobre a política de caminhos, a análise de comandos de shell, a entrada das
// ferramentas e o hook de permissão. O ponto central: "My Drive" só é
// acessível dentro de PesquisAI — e a decisão não depende de aprovação
// (portanto vale em --auto).

import assert from "node:assert/strict"
import fs from "node:fs"
import os from "node:os"
import path from "node:path"

import { evaluatePermission, makeGuard } from "../../pesquisai/plugins/drive_guard/policy.js"

let passed = 0
function ok(name, fn) {
  const done = (error) => {
    if (error) {
      console.error(`FAIL  ${name}`)
      console.error(`      ${error.message}`)
      process.exitCode = 1
      return
    }
    passed += 1
    console.log(`  ok  ${name}`)
  }
  try {
    const result = fn()
    if (result && typeof result.then === "function") return result.then(() => done(), done)
    done()
  } catch (error) {
    done(error)
  }
}

const CWD = "/content/drive/My Drive/PesquisAI"
const guard = makeGuard({ cwd: CWD })

console.log("Drive Guard — caminhos")
ok("PesquisAI e subpastas liberados", () => {
  assert.equal(guard.checkPath(`${CWD}/vault/nota.md`).allow, true)
  assert.equal(guard.checkPath(CWD).allow, true)
})
ok("raiz de My Drive bloqueada", () => {
  assert.equal(guard.checkPath("/content/drive/My Drive").allow, false)
  assert.equal(guard.checkPath("/content/drive/My Drive/").allow, false)
})
ok("arquivo fora de PesquisAI bloqueado", () => {
  assert.equal(guard.checkPath("/content/drive/My Drive/Artigo.docx").allow, false)
})
ok("alias MyDrive: fora de PesquisAI bloqueado", () => {
  assert.equal(guard.checkPath("/content/drive/MyDrive/Artigo.docx").allow, false)
  assert.equal(guard.checkPath("/content/drive/MyDrive").allow, false)
})
ok("alias MyDrive: PesquisAI liberado (é a mesma pasta de My Drive)", () => {
  // No Colab, MyDrive e "My Drive" são o MESMO diretório (mesmo inode).
  assert.equal(guard.checkPath("/content/drive/MyDrive/PesquisAI").allow, true)
  assert.equal(guard.checkPath("/content/drive/MyDrive/PesquisAI/vault/x.md").allow, true)
  assert.equal(guard.checkCommand("cat /content/drive/MyDrive/PesquisAI/dados.csv").allow, true)
  assert.equal(guard.checkCommand("cat /content/drive/MyDrive/segredo.pdf").allow, false)
  // vizinho com prefixo parecido NÃO é o alias
  assert.equal(guard.checkPath("/content/drive/MyDriveX/PesquisAI/x").allow, false)
})
ok("escape com .. bloqueado", () => {
  assert.equal(guard.checkPath("../Artigo.docx").allow, false)
  assert.equal(guard.checkPath("../../My Drive/x.pdf").allow, false)
})
ok("fora do Drive não é afetado", () => {
  assert.equal(guard.checkPath("/tmp/ufvai/x.md").allow, true)
  assert.equal(guard.checkPath("~/PesquisAI/x.md").allow, true)
})
ok("caixa e normalização não burlam", () => {
  assert.equal(guard.checkPath("/content/drive/my drive/x.pdf").allow, false)
  assert.equal(guard.checkPath(`${CWD}/vault/`).allow, true)
})
ok("symlink real para My Drive é resolvido", () => {
  const link = path.join(os.tmpdir(), `ufvai-dg-${process.pid}`)
  try {
    fs.symlinkSync("/content/drive/My Drive", link, "dir")
  } catch {
    return // sem permissão para criar symlink: nada a testar
  }
  try {
    assert.equal(guard.checkPath(`${link}/x.pdf`).allow, false)
  } finally {
    fs.unlinkSync(link)
  }
})

console.log("Drive Guard — comandos")
const commands = [
  ['ls "/content/drive/My Drive/PesquisAI/vault"', true],
  ['cat "/content/drive/My Drive/segredo.pdf"', false],
  ["cd /content/drive/My Drive && ls", false],
  ['python3 -c "open(\\"/content/drive/My Drive/x\\")"', false],
  ["find /content/drive -maxdepth 2", false],
  ["cat ../Artigo.docx", false],
  ['D=/content/drive/My\\ Drive; cat "$D/x"', false],
  ["echo ola", true],
  ['echo "My Drive"', true],
  ["python3 script.py /content/drive/MyDrive/PesquisAI/dados.csv", true],
  ["HEADLESS=1 python3 x.py", true],
]
for (const [command, expected] of commands) {
  ok(`shell: ${command}`, () => {
    assert.equal(guard.checkCommand(command).allow, expected)
  })
}

console.log("Drive Guard — entrada das ferramentas")
ok("read fora de PesquisAI", () => {
  assert.equal(guard.checkToolInput("read", { path: "/content/drive/My Drive/x.pdf" }).allow, false)
})
ok("read dentro de PesquisAI", () => {
  assert.equal(guard.checkToolInput("read", { path: `${CWD}/vault/x.md` }).allow, true)
})
ok("write/glob com path externo", () => {
  assert.equal(guard.checkToolInput("write", { path: "/content/drive/My Drive/x.md" }).allow, false)
  assert.equal(guard.checkToolInput("glob", { pattern: "*.md", path: "/content/drive/My Drive" }).allow, false)
})
ok("bash com comando proibido", () => {
  assert.equal(guard.checkToolInput("bash", { command: 'ls "/content/drive/My Drive"' }).allow, false)
  assert.equal(guard.checkToolInput("bash", { command: "ls ." }).allow, true)
})
ok("entrada aninhada também é inspecionada", () => {
  const input = { requests: [{ file: "/content/drive/My Drive/x.txt" }] }
  assert.equal(guard.checkToolInput("batch", input).allow, false)
})
ok("grep com padrão textual não é falso positivo", () => {
  assert.equal(guard.checkToolInput("grep", { pattern: "My Drive" }).allow, true)
  assert.equal(guard.checkPattern("My Drive").allow, true)
  assert.equal(guard.checkPattern("/content/drive/My Drive/**").allow, false)
})

console.log("Drive Guard — hook de permissão")
ok("read em My Drive vira deny", () => {
  const event = {
    action: "read",
    resources: ["/content/drive/My Drive/x.pdf"],
    effect: "allow",
  }
  const reason = evaluatePermission(guard, event)
  assert.ok(reason && reason.includes("Drive Guard"))
})
ok("read em PesquisAI não tem opinião", () => {
  const event = { action: "read", resources: [`${CWD}/x.md`], effect: "allow" }
  assert.equal(evaluatePermission(guard, event), null)
})
ok("shell alcançando My Drive vira deny", () => {
  const event = { action: "shell", resources: ["cat /content/drive/My Drive/x"], effect: "allow" }
  assert.ok(evaluatePermission(guard, event))
})
ok("glob absoluto em My Drive vira deny", () => {
  const event = { action: "glob", resources: ["/content/drive/My Drive/**"], effect: "allow" }
  assert.ok(evaluatePermission(guard, event))
})

// ── Contrato do motor: setup() registra os hooks e o `--auto` não fura ──────
// Aqui se exercita o MESMO objeto exportado pelo plugin, com um contexto falso
// que imita `ctx.permission.hook` / `ctx.tool.hook` do OpenCode 2.x. O ponto
// central: um evento que chega como `allow` (é o que a auto-aprovação faz) é
// reescrito para `deny`.
console.log("Drive Guard — contrato do motor (setup)")

const registered = { permission: {}, tool: {} }
const fakeCtx = {
  options: { logFile: path.join(os.tmpdir(), `ufvai-dg-test-${process.pid}.log`) },
  location: { directory: CWD },
  permission: {
    hook: async (name, callback) => {
      registered.permission[name] = callback
      return { dispose: async () => {} }
    },
  },
  tool: {
    hook: async (name, callback) => {
      registered.tool[name] = callback
      return { dispose: async () => {} }
    },
  },
}

const plugin = (await import("../../pesquisai/plugins/drive_guard/index.js")).default

await ok("setup() registra evaluate + execute.before", async () => {
  const cleanup = await plugin.setup(fakeCtx)
  assert.equal(typeof registered.permission.evaluate, "function")
  assert.equal(typeof registered.tool["execute.before"], "function")
  assert.equal(typeof cleanup, "function")
})

await ok("--auto: allow vindo do motor vira deny para fora de PesquisAI", async () => {
  const event = { action: "read", resources: ["/content/drive/My Drive/segredo.pdf"], effect: "allow" }
  await registered.permission.evaluate(event)
  assert.equal(event.effect, "deny")
  assert.match(String(event.message), /Drive Guard/)
})

await ok("--auto: allow dentro de PesquisAI é preservado", async () => {
  const event = { action: "read", resources: [`${CWD}/vault/nota.md`], effect: "allow" }
  await registered.permission.evaluate(event)
  assert.equal(event.effect, "allow")
})

// O hook do plugin é síncrono (lança na hora); o wrapper async garante que
// `assert.rejects` veja uma rejeição, como o motor veria.
const callTool = async (event) => registered.tool["execute.before"](event)

await ok("execute.before barra antes do disco", async () => {
  await assert.rejects(() => callTool({ tool: "read", input: { path: "/content/drive/My Drive/x.pdf" } }), /Drive Guard/)
  await assert.rejects(
    () => callTool({ tool: "bash", input: { command: 'cat "/content/drive/My Drive/x"' } }),
    /Drive Guard/,
  )
})

await ok("execute.before deixa passar o permitido", async () => {
  await callTool({ tool: "read", input: { path: `${CWD}/vault/nota.md` } })
  await callTool({ tool: "bash", input: { command: "ls -la" } })
})

console.log(`\n${passed} verificações ok${process.exitCode ? " (com falhas)" : ""}.`)
