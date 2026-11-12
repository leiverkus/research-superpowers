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
//   b) the current project's .claude/skills symlink → <repo>/hooks/session-context.md
//   c) the EMBEDDED_INDEX fallback below (self-contained; always works)

import type { Plugin } from "@opencode/plugin"
import { existsSync, readFileSync, realpathSync } from "node:fs"
import { join, dirname } from "node:path"

const MARKER = "<research-superpowers>"

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

/** Locate hooks/session-context.md from env, or by following the project's
 *  `.claude/skills` → <repo>/skills symlink back to the repo root. */
function resolveIndexFile(dir: string): string | null {
  const env = process.env.RESEARCH_SUPERPOWERS_DIR
  if (env) {
    const p = join(env, "hooks", "session-context.md")
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

export const id = "research-superpowers"

export default {
  id,
  async setup(ctx) {
    // Resolved once per plugin instance; the location is stable for it.
    const index = loadIndex(ctx.location.directory)
    if (!index) return // outside research projects: register nothing

    const block = `${MARKER}\n${index}\n</research-superpowers>`

    await ctx.session.hook("context", (event) => {
      const system = event.system
      // Idempotent: never inject twice (the hook fires on every request of a
      // tool loop, and the same event may be transformed again).
      if (system.some((part) => part.type === "text" && part.text.includes(MARKER))) return

      // GWDG-safe: merge into the last existing text part instead of adding a
      // part that OpenAI-compatible backends would turn into a second system
      // message ("System message must be at the beginning." → HTTP 400).
      const i = system.length - 1
      const last = system[i]
      if (last && last.type === "text") {
        system[i] = { ...last, text: `${last.text}\n\n${block}` }
      } else {
        system.push({ type: "text", text: block })
      }
    })
  },
} satisfies Plugin.Plugin
