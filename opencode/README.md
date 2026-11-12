# research-superpowers in OpenCode

[OpenCode](https://opencode.ai/) 2.x runs the research-superpowers workflow with
three pieces, all from this repo:

| Piece | What OpenCode gets | Source |
| --- | --- | --- |
| **Skills** | all `skills/<name>/SKILL.md`, loaded natively by the `skill` tool | `skills/` |
| **Subagents** | `source-ingester`, `drafter`, `literature-scout`, … for the `subagent` tool | `opencode/agents/` (generated) |
| **Plugin** | skill index + drift check at session start, plugin root for shell commands | `opencode/plugin/research-superpowers.ts` |

> **Two meanings of "plugin".** A *Claude Code* plugin (this repo) is a bundle of
> `SKILL.md`, agents and `hooks.json`. An *OpenCode* plugin is a TypeScript
> module that hooks into events. OpenCode reads the skills by file discovery; the
> one OpenCode plugin here rebuilds what Claude Code's hooks do.

## Install

```bash
/path/to/research-superpowers/opencode/install.sh
opencode service restart   # or quit and reopen the OpenCode app
```

The script creates symlinks only, so `git pull` updates everything in place:

- `~/.config/opencode/skills/research-superpowers` → `skills/` — one grouping
  link; skill names stay plain (`ingest-source`, not `research-superpowers/…`).
  Global on purpose: `scaffold-research-project` is needed before a project exists.
- `~/.config/opencode/agents/<name>.md` → `opencode/agents/<name>.md` — one link
  per agent, because OpenCode names an agent in a sub-directory `<dir>/<name>`
  and the skills dispatch them by bare name. Re-run the script after a new agent.
- `~/.config/opencode/plugin/research-superpowers.ts` → the plugin.

It never replaces a real file or a link to somewhere else (it reports a
`CONFLICT` and exits 1), honours `OPENCODE_CONFIG_DIR`, and
`install.sh --uninstall` removes exactly its own links.

A per-project alternative for the skills alone is `.claude/skills` →
`skills/`; OpenCode searches `.claude/skills` and `.agents/skills` too. Agents have
no such path: OpenCode reads them only from `.opencode/agents/` and
`~/.config/opencode/agents/`.

## Why the agents are generated

OpenCode does not read Claude Code agent files, and their frontmatter does not
carry over: without `mode:` an agent becomes a *primary* agent the `subagent`
tool cannot launch; `disallowedTools` is not an OpenCode field, so a read-only
agent such as `peer-reviewer` could write; `model: sonnet`/`inherit` are Claude
aliases. `scripts/build-opencode-agents.py` therefore writes `opencode/agents/`
from `agents/` — same name, description and instructions, plus `mode: subagent`
and a `permission:` block (`Agent` → `subagent: deny`, `Write`/`Edit` →
`edit: deny`). `agents/` stays the only source; CI fails if the two drift:

```bash
python scripts/build-opencode-agents.py          # after editing agents/
python scripts/build-opencode-agents.py --check  # what CI runs
```

The generated agents name no model, so they run on the model of the session
that launches them (the counterpart of `inherit`). To pin one, set it in
`opencode.jsonc`, e.g. `"agent": { "literature-scout": { "model": "provider/model" } }`.

## The plugin

- **Skill index.** `setup(ctx)` registers `ctx.session.hook("context")` and
  merges `hooks/session-context.md` into the system prompt of every request —
  what Claude Code's `SessionStart` hook does. Only in research projects (a
  `knowledge/` or `input/` directory); `RESEARCH_SUPERPOWERS_ALWAYS=1` lifts that.
- **Drift check.** In a research project it runs `hooks/drift_check.py` once, in
  the background, as Claude Code's second `SessionStart` hook does. Findings, if
  any, join the system prompt of the first session that sees them; no change
  means no output. `RESEARCH_SUPERPOWERS_NO_DRIFT_CHECK=1` switches it off.
- **Plugin root for shell commands.** Skills call plugin scripts as
  `"${CLAUDE_PLUGIN_ROOT:-$RESEARCH_SUPERPOWERS_DIR}/…"`. Claude Code sets the
  first; the plugin sets `RESEARCH_SUPERPOWERS_DIR` (the repo it lives in) for
  every shell command, in every directory.
- **GWDG / Qwen safe.** Everything is merged into the existing system block, never
  added as a second system message (OpenAI-compatible backends such as GWDG
  reject that with `HTTP 400 "System message must be at the beginning."`).
- **OpenCode 2.x API.** OpenCode 2.x no longer loads the 1.x plugin format
  (`experimental.chat.system.transform`); with the old plugin the index silently
  never arrived. Tests: `bun test opencode/tests`.

> **Keeping the embedded fallback in sync.** The `EMBEDDED_INDEX` literal in
> `plugin/research-superpowers.ts` is a copy of `hooks/session-context.md` for
> the no-configuration case. When you edit `session-context.md`, re-sync it
> (escaping backticks) and CI will verify the two match:
>
> ```bash
> python3 - <<'PY'
> import pathlib
> ts = pathlib.Path("opencode/plugin/research-superpowers.ts")
> src = ts.read_text(); md = pathlib.Path("hooks/session-context.md").read_text().rstrip("\n")
> esc = md.replace("`", "\\`").replace("${", "\\${")
> head = "const EMBEDDED_INDEX = `"; tail = "`\n\n// ── Helpers"
> i = src.index(head) + len(head); j = src.index(tail)
> ts.write_text(src[:i] + esc + src[j:]); print("synced")
> PY
> ```

### Configuration (optional)

| Env var | Effect |
| --- | --- |
| `RESEARCH_SUPERPOWERS_DIR` | Repo root. Defaults to the repo the plugin file lives in (through the symlink); set it for a copied plugin. |
| `RESEARCH_SUPERPOWERS_ALWAYS=1` | Inject the index in every project, not just research projects. |
| `RESEARCH_SUPERPOWERS_NO_DRIFT_CHECK=1` | Skip the session-start drift check (same switch as in Claude Code). |

## Differences that remain

- **No task tool.** OpenCode 2.x has no `TodoWrite`/`TaskCreate`; where a skill
  says "task-list item", keep the list in your reply or in the plan file.
- **Skill names have no `research-superpowers:` prefix** in OpenCode.
- **Model choice per agent** is yours (see above); Claude Code's `sonnet` hints
  for the cheaper agents do not translate.

## Why not just AGENTS.md?

You can mention the skills in your project's `AGENTS.md` and OpenCode will load
them on demand — that's the zero-code path. This plugin is the higher-fidelity
option: it injects the *same* curated index Claude Code uses, automatically, in
every research project, without editing each project's `AGENTS.md`.
