# research-superpowers in OpenCode

[OpenCode](https://opencode.ai/) reads `SKILL.md` files natively, so the skills
and agents of this plugin work there too. What OpenCode does **not** have is
Claude Code's `SessionStart` hook — the thing that injects the compact skill
index at the start of a conversation so the assistant knows which research
skills exist.

This directory provides that missing piece as a native **OpenCode plugin**.

> **Note on the two "plugin" meanings.** A *Claude Code* plugin (this repo) is a
> bundle of `SKILL.md`, agents and a `hooks.json`. An *OpenCode* plugin is a
> JavaScript/TypeScript module that hooks into events. They are not
> interchangeable: you load the **skills** via file discovery (symlink), and you
> load **this one plugin** via OpenCode's plugin system to restore the
> session-start index injection.

## 1. Skills + agents (file discovery)

In your research project root:

```bash
mkdir -p .claude
ln -s /path/to/research-superpowers/skills .claude/skills
```

OpenCode (and the global `~/.config/opencode/skills/` directory, if you prefer a
global install) then discovers every skill and agent.

## 2. The session-start plugin

OpenCode auto-loads every `.ts` file in `~/.config/opencode/plugin/`. Symlink
this plugin in:

```bash
ln -s /path/to/research-superpowers/opencode/plugin/research-superpowers.ts \
      ~/.config/opencode/plugin/research-superpowers.ts
```

(Or copy it if you'd rather not symlink. No `opencode.jsonc` edit is needed —
the directory is auto-scanned.)

Restart OpenCode. In any research project the assistant now sees the skill index
in its system context, exactly as in Claude Code.

### How it works

- Hook: `experimental.chat.system.transform` — appends the index to the
  system-prompt array OpenCode builds for each request.
- **GWDG / Qwen safe:** it merges the index into the existing leading system
  block instead of adding a second system message (which OpenAI-compatible
  backends like GWDG reject with `HTTP 400 "System message must be at the
  beginning."`).
- **Scoped:** fires only when the working directory looks like a research
  project (a `knowledge/` or `input/` directory). It stays silent in your other
  projects. Override with `RESEARCH_SUPERPOWERS_ALWAYS=1`.
- **Index source:** prefers the live file at
  `$RESEARCH_SUPERPOWERS_DIR/hooks/session-context.md`, then follows the project's
  `.claude/skills` symlink back to the repo, and finally falls back to an
  embedded copy — so it works even with no configuration.

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
| `RESEARCH_SUPERPOWERS_DIR` | Absolute path to this repo; lets the plugin read the live `hooks/session-context.md` so the index stays in sync. |
| `RESEARCH_SUPERPOWERS_ALWAYS=1` | Inject in every project, not just research projects. |

## Why not just AGENTS.md?

You can mention the skills in your project's `AGENTS.md` and OpenCode will load
them on demand — that's the zero-code path. This plugin is the higher-fidelity
option: it injects the *same* curated index Claude Code uses, automatically, in
every research project, without editing each project's `AGENTS.md`.
