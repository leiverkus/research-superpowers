// research-superpowers.ts — OpenCode plugin
//
// Replicates the SessionStart hook of the research-superpowers *Claude Code*
// plugin. Claude Code injects a compact skill index (hooks/session-context.md)
// at session start via its `SessionStart` hook so the assistant knows which
// research skills exist and when to invoke them. OpenCode has no SessionStart
// hook, so we achieve the same effect through `experimental.chat.system.transform`:
// we append the skill index to the system-prompt array that OpenCode assembles
// for every LLM call.
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

import type { Plugin } from "@opencode-ai/plugin"
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
tool before responding. Skills declare their inputs/outputs in frontmatter
(see \`docs/skill-contract.md\`).

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

const researchSuperpowers: Plugin = async ({ directory }) => {
  // Resolve the index once per session. The plugin function runs per project,
  // so `directory` is stable for this instance.
  const active = isResearchProject(directory)
  let index: string | null = null
  if (active) {
    const file = resolveIndexFile(directory)
    if (file) {
      try {
        index = readFileSync(file, "utf8")
      } catch {
        index = EMBEDDED_INDEX
      }
    } else {
      index = EMBEDDED_INDEX
    }
  }

  return {
    "experimental.chat.system.transform": async (_input, output) => {
      if (!index) return
      const system = output.system
      if (!Array.isArray(system)) return
      // Idempotent: never inject twice (e.g. if the array is re-transformed).
      if (system.some((s) => typeof s === "string" && s.includes(MARKER))) return

      const block = `${MARKER}\n${index}\n</research-superpowers>`

      // GWDG-safe: merge into the existing leading system block rather than
      // appending a new entry that some OpenAI-compatible backends turn into a
      // second system message.
      if (system.length > 0 && typeof system[system.length - 1] === "string") {
        system[system.length - 1] += `\n\n${block}`
      } else {
        system.push(block)
      }
    },
  }
}

export const id = "research-superpowers"
export default { id, server: researchSuperpowers }
