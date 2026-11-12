// research-superpowers.ts — OpenCode plugin
//
// Replicates the SessionStart hook of the research-superpowers *Claude Code*
// plugin. Claude Code injects a compact skill index (hooks/session-context.md)
// at session start via its `SessionStart` hook so the assistant knows which
// research skills exist and when to invoke them. OpenCode has no SessionStart
// hook, so we achieve the same effect through the `session.context` hook: we
// merge the skill index into the system-prompt parts that OpenCode assembles
// for every LLM request.
//
// V2 port (2026-11-12): opencode 2.x no longer loads V1 plugins
// (`{ id, server }` + `experimental.chat.system.transform`). Under V2 the
// index was silently never injected. Now `{ id, setup(ctx) }` with
// `ctx.session.hook("context")`; system parts are `{ type: "text", text }`
// objects instead of strings. Contract: ~/.config/opencode/tests/plugins.test.ts.
//
// Two design constraints, both learned from this machine's setup:
//
//   1. GWDG / Qwen (OpenAI-compatible) reject a SECOND system message
//      ("System message must be at the beginning." → HTTP 400). So we do NOT
//      push a fresh array entry blindly — we merge the index into an existing
//      system entry, keeping it inside the single leading system block.
//
//   2. Installed globally, the plugin must stay quiet outside research projects.
//      It only fires when the working directory looks like a research project
//      (a `knowledge/` directory — the marker every scaffolded project has),
//      or when RESEARCH_SUPERPOWERS_ALWAYS=1 is set.
//
// Content source, in priority order:
//   a) $RESEARCH_SUPERPOWERS_DIR/hooks/session-context.md  (live file — stays in sync)
//   b) the repo this plugin file lives in (resolved through the symlink)
//   c) the current project's .claude/skills symlink → <repo>/hooks/session-context.md
//   d) the EMBEDDED_INDEX fallback below (self-contained; always works)
//
// Two more Claude Code mechanisms the skills rely on, rebuilt here:
//
//   * Plugin root for shell commands. Skills call scripts as
//     `"${CLAUDE_PLUGIN_ROOT:-$RESEARCH_SUPERPOWERS_DIR}/hooks/…"`. Claude Code
//     sets CLAUDE_PLUGIN_ROOT; OpenCode sets nothing, so every shell command
//     gets RESEARCH_SUPERPOWERS_DIR (the repo root) unless the user set it.
//     This hook runs everywhere, not only in research projects, because
//     scaffold-research-project is used before a project exists.
//
//   * The SessionStart drift check (hooks/drift_check.py). It runs once per
//     plugin instance in a research project, in the background, and its
//     findings — if any — join the system prompt of the first session that
//     sees them. State-triggered like in Claude Code: no change, no output.
//     RESEARCH_SUPERPOWERS_NO_DRIFT_CHECK=1 switches it off.

import type { Plugin } from "@opencode/plugin"
import { execFile } from "node:child_process"
import { existsSync, readFileSync, realpathSync } from "node:fs"
import { join, dirname } from "node:path"
import { fileURLToPath } from "node:url"

const MARKER = "<research-superpowers>"
const DRIFT_MARKER = "<research-drift-report>"

// ── Fallback index (verbatim copy of hooks/session-context.md) ──────────────
const EMBEDDED_INDEX = `# Research Superpowers — Skill Index

You have the **research-superpowers** plugin. Below is an index of available
skills with one-line triggers. For full procedural content, load the skill via
the \`Skill\` tool (e.g. \`Skill ingest-source\`).

## Setup & orientation

- **using-research-powers** — orientation: how the skills fit together and when to use which
- **scaffold-research-project** — create a new research project from the template

## Workflow phases (sequence)

1. **brainstorming-research** — open question → input/ideas/<slug>-design.md
2. **writing-research-plan** — design doc → ready plan (status=ready for hermeneutic, status=pre-registered for quantitative/mixed)
3. **literature-review** — strategic search, produces literaturguide.md + BibTeX (search only — downloads nothing)
4. **acquire-sources** — auto-download OA PDFs + write acquisition-todo.md manual worklist for paywalled sources; re-run to reconcile
5. **ingest-source** — one acquired source PDF → wiki content (sources + entities + BibTeX + log)
6. **executing-research-plan** — work plan tasks via subagents with two-stage review
7. **drafting-manuscript** — stable synthesis pages → output/**/*.qmd
8. **requesting-peer-review** — manuscript → constructive + adversarial review
9. **finishing-a-research-project** — closing checklist, archival

## Cross-cutting skills

- **add-to-library** — add one PDF directly to the shared master library (verify metadata + keywords), outside the project ingest flow
- **wiki-lint** — run scripts/lint-wiki.py (structural, deterministic)
- **drift-report** — deterministic maintenance findings across library + all projects (index, scans, bloat, merge drift, bibkey collisions); auto-runs state-triggered at session start
- **wiki-graph** — build/query the knowledge graph (god nodes, bridges, communities; CLI + MCP)
- **semantic-wiki-review** — LLM content audit (contradictions, stale syntheses)
- **grant-finder** — funding programmes parallel to publication

## Calling convention

When a user message matches a skill's trigger, load the skill via the \`Skill\`
tool before responding. A request whose answer lives only in the chat — a
single reference, a definition, what a wiki page says — needs no skill. Skills
declare their inputs/outputs in frontmatter (see \`docs/skill-contract.md\`).

User instructions in CLAUDE.md or AGENTS.md override skill defaults. If the
user says "skip <phase>", name the skipped phase out loud and proceed.`

// ── Helpers ─────────────────────────────────────────────────────────────────

/** A research project is identifiable by its scaffolded `knowledge/` directory. */
function isResearchProject(dir: string): boolean {
  if (process.env.RESEARCH_SUPERPOWERS_ALWAYS === "1") return true
  if (!dir) return false
  return existsSync(join(dir, "knowledge")) || existsSync(join(dir, "input"))
}

/** The research-superpowers repo this file belongs to: <repo>/opencode/plugin/
 *  research-superpowers.ts, usually reached through a symlink in
 *  ~/.config/opencode/plugin/. Null for a copied plugin with no repo around it. */
function pluginRoot(): string | null {
  try {
    const file = realpathSync(fileURLToPath(import.meta.url))
    const root = dirname(dirname(dirname(file)))
    return existsSync(join(root, "hooks", "session-context.md")) ? root : null
  } catch {
    return null
  }
}

/** Repo root for scripts: the user's RESEARCH_SUPERPOWERS_DIR wins. */
function repoRoot(): string | null {
  return process.env.RESEARCH_SUPERPOWERS_DIR || pluginRoot()
}

/** Locate hooks/session-context.md from env, the plugin's own repo, or by
 *  following the project's `.claude/skills` → <repo>/skills symlink. */
function resolveIndexFile(dir: string): string | null {
  for (const root of [process.env.RESEARCH_SUPERPOWERS_DIR, pluginRoot()]) {
    if (!root) continue
    const p = join(root, "hooks", "session-context.md")
    if (existsSync(p)) return p
  }
  try {
    const skillsLink = join(dir, ".claude", "skills")
    if (existsSync(skillsLink)) {
      const realSkills = realpathSync(skillsLink) // <repo>/skills
      const p = join(dirname(realSkills), "hooks", "session-context.md")
      if (existsSync(p)) return p
    }
  } catch {
    // ignore broken symlinks / permission errors → fall through to embedded
  }
  return null
}

// ── Plugin ──────────────────────────────────────────────────────────────────

function loadIndex(directory: string): string | null {
  if (!isResearchProject(directory)) return null
  const file = resolveIndexFile(directory)
  if (!file) return EMBEDDED_INDEX
  try {
    return readFileSync(file, "utf8")
  } catch {
    return EMBEDDED_INDEX
  }
}

const DRIFT_TIMEOUT_MS = 180_000 // drift_check.py budgets 45 s per check

/** Run hooks/drift_check.py the way Claude Code's SessionStart hook does and
 *  return its additionalContext, or null (no findings, no Python, any error —
 *  a failing drift check must never break a session). */
function runDriftCheck(root: string, directory: string): Promise<string | null> {
  const script = join(root, "hooks", "drift_check.py")
  if (!existsSync(script)) return Promise.resolve(null)
  // Without CLAUDE_PLUGIN_ROOT the script prints the generic
  // {"additionalContext": …} shape instead of Claude Code's hookSpecificOutput.
  const env = { ...process.env, RESEARCH_SUPERPOWERS_DIR: root }
  delete env.CLAUDE_PLUGIN_ROOT
  return new Promise((resolve) => {
    execFile("python3", [script], { cwd: directory, env, timeout: DRIFT_TIMEOUT_MS },
      (err, stdout) => {
        if (err || !stdout.trim()) return resolve(null)
        try {
          const ctx = JSON.parse(stdout).additionalContext
          resolve(typeof ctx === "string" && ctx.trim() ? ctx : null)
        } catch {
          resolve(null)
        }
      })
  })
}

/** Append text to the last system text part (GWDG-safe, see header). */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function appendSystem(system: any[], text: string) {
  const i = system.length - 1
  const last = system[i]
  if (last && last.type === "text") {
    system[i] = { ...last, text: `${last.text}\n\n${text}` }
  } else {
    system.push({ type: "text", text })
  }
}

export const id = "research-superpowers"

export default {
  id,
  async setup(ctx) {
    const root = repoRoot()

    // Plugin root for every shell command (all directories — see header).
    if (root && ctx.shell) {
      await ctx.shell.hook("create.before", (event) => {
        event.env.RESEARCH_SUPERPOWERS_DIR ??= root
      })
    }

    // Resolved once per plugin instance; the location is stable for it.
    const directory = ctx.location.directory
    const index = loadIndex(directory)
    if (!index) return // outside research projects: nothing else to do

    const block = `${MARKER}\n${index}\n</research-superpowers>`

    // Drift check in the background; the session that first sees a result keeps it.
    let drift: string | null = null
    let driftSession: string | null = null
    if (root && process.env.RESEARCH_SUPERPOWERS_NO_DRIFT_CHECK !== "1") {
      void runDriftCheck(root, directory).then((report) => {
        drift = report
      })
    }

    await ctx.session.hook("context", (event) => {
      const system = event.system
      const has = (marker: string) =>
        system.some((part) => part.type === "text" && part.text.includes(marker))

      // Idempotent: never inject twice (the hook fires on every request of a
      // tool loop, and the same event may be transformed again).
      // GWDG-safe: merge into the last existing text part instead of adding a
      // part that OpenAI-compatible backends would turn into a second system
      // message ("System message must be at the beginning." → HTTP 400).
      if (!has(MARKER)) appendSystem(system, block)

      if (drift && !driftSession) driftSession = event.sessionID
      if (drift && driftSession === event.sessionID && !has(DRIFT_MARKER)) {
        appendSystem(system, drift)
      }
    })
  },
} satisfies Plugin.Plugin
