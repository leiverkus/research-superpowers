// Contract tests for the OpenCode plugin (opencode/plugin/research-superpowers.ts).
// Run with: bun test opencode/tests
//
// The plugin is driven through a fake OpenCode 2.x context. RESEARCH_SUPERPOWERS_DIR
// points at a throwaway repo root whose hooks/drift_check.py is a stub, so no test
// touches the real drift state in ~/.cache or the project registry.
import { afterEach, beforeEach, describe, expect, test } from "bun:test"
import fs from "node:fs"
import os from "node:os"
import path from "node:path"
import plugin from "../plugin/research-superpowers"

type Hook = (event: any) => unknown

function fakeContext(directory: string) {
  const hooks: Record<string, Hook[]> = {}
  const register = (domain: string) => async (name: string, cb: Hook) => {
    ;(hooks[`${domain}.${name}`] ??= []).push(cb)
    return { dispose: async () => {} }
  }
  const ctx = {
    location: { directory },
    session: { hook: register("session") },
    shell: { hook: register("shell") },
  }
  const fire = async (name: string, event: any) => {
    for (const cb of hooks[name] ?? []) await cb(event)
    return event
  }
  return { ctx: ctx as any, fire, hooks }
}

const contextEvent = (sessionID = "ses_a") => ({
  sessionID,
  agent: "build",
  system: [{ type: "text", text: "BASE" }],
  messages: [{ role: "user", content: [{ type: "text", text: "hi" }] }],
  options: {},
  tools: {},
})

let tmp: string
let project: string
let root: string
const saved = { ...process.env }

beforeEach(() => {
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), "rs-plugin-"))
  project = path.join(tmp, "project")
  root = path.join(tmp, "repo")
  fs.mkdirSync(project)
  fs.mkdirSync(path.join(root, "hooks"), { recursive: true })
  fs.writeFileSync(path.join(root, "hooks", "session-context.md"), "LIVE INDEX")
  process.env.RESEARCH_SUPERPOWERS_DIR = root
  delete process.env.RESEARCH_SUPERPOWERS_NO_DRIFT_CHECK
  delete process.env.RESEARCH_SUPERPOWERS_ALWAYS
})

afterEach(() => {
  process.env = { ...saved }
  fs.rmSync(tmp, { recursive: true, force: true })
})

/** Stub drift check: records that it ran, prints the given hook JSON. */
function stubDrift(stdout: string) {
  const ran = path.join(tmp, "drift-ran")
  fs.writeFileSync(
    path.join(root, "hooks", "drift_check.py"),
    `import pathlib, sys\npathlib.Path(${JSON.stringify(ran)}).write_text("x")\n` +
      `sys.stdout.write(${JSON.stringify(stdout)})\n`,
  )
  return ran
}

const settle = () => new Promise((r) => setTimeout(r, 1500))

describe("skill index", () => {
  test("merges the live index into the last system part, once", async () => {
    fs.mkdirSync(path.join(project, "knowledge"))
    process.env.RESEARCH_SUPERPOWERS_NO_DRIFT_CHECK = "1"
    const f = fakeContext(project)
    await plugin.setup(f.ctx)
    const event = await f.fire("session.context", contextEvent())
    await f.fire("session.context", event)
    expect(event.system).toHaveLength(1)
    expect(event.system[0].text).toStartWith("BASE")
    expect(event.system[0].text).toContain("LIVE INDEX")
    expect(event.system[0].text.match(/<research-superpowers>/g)).toHaveLength(1)
  })

  test("stays quiet outside research projects", async () => {
    const ran = stubDrift("")
    const f = fakeContext(project)
    await plugin.setup(f.ctx)
    const event = await f.fire("session.context", contextEvent())
    expect(event.system[0].text).toBe("BASE")
    await settle()
    expect(fs.existsSync(ran)).toBe(false)
  })
})

describe("plugin root for shell commands", () => {
  test("sets RESEARCH_SUPERPOWERS_DIR, also outside research projects", async () => {
    const f = fakeContext(project)
    await plugin.setup(f.ctx)
    const event = await f.fire("shell.create.before", { command: "ls", env: {} })
    expect(event.env.RESEARCH_SUPERPOWERS_DIR).toBe(root)
  })

  test("keeps a value the command already carries", async () => {
    const f = fakeContext(project)
    await plugin.setup(f.ctx)
    const event = await f.fire("shell.create.before", {
      command: "ls",
      env: { RESEARCH_SUPERPOWERS_DIR: "/elsewhere" },
    })
    expect(event.env.RESEARCH_SUPERPOWERS_DIR).toBe("/elsewhere")
  })
})

describe("drift check", () => {
  const report = "<research-drift-report>\nNEW PDF\n</research-drift-report>"

  test("findings join the first session's system prompt, and only that session's", async () => {
    fs.mkdirSync(path.join(project, "knowledge"))
    stubDrift(JSON.stringify({ additionalContext: report }))
    const f = fakeContext(project)
    await plugin.setup(f.ctx)
    await settle()
    const first = await f.fire("session.context", contextEvent("ses_a"))
    expect(first.system[0].text).toContain("NEW PDF")
    const again = await f.fire("session.context", contextEvent("ses_a"))
    expect(again.system[0].text.match(/research-drift-report>/g)).toHaveLength(2)
    const other = await f.fire("session.context", contextEvent("ses_b"))
    expect(other.system[0].text).not.toContain("NEW PDF")
  })

  test("no findings, no text", async () => {
    fs.mkdirSync(path.join(project, "knowledge"))
    const ran = stubDrift("")
    const f = fakeContext(project)
    await plugin.setup(f.ctx)
    await settle()
    expect(fs.existsSync(ran)).toBe(true)
    const event = await f.fire("session.context", contextEvent())
    expect(event.system[0].text).not.toContain("research-drift-report")
  })

  test("RESEARCH_SUPERPOWERS_NO_DRIFT_CHECK=1 keeps it from running", async () => {
    fs.mkdirSync(path.join(project, "knowledge"))
    process.env.RESEARCH_SUPERPOWERS_NO_DRIFT_CHECK = "1"
    const ran = stubDrift(JSON.stringify({ additionalContext: report }))
    const f = fakeContext(project)
    await plugin.setup(f.ctx)
    await settle()
    expect(fs.existsSync(ran)).toBe(false)
  })
})
