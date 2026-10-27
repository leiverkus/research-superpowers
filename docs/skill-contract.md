# Skill Contract — SOT Pattern

This document defines how the three artefact types in this plugin relate to each other so that workflow logic lives in exactly one place.

## The two artefact types

| Type | Lives in | Loaded by | Has procedural content? |
|------|----------|-----------|-------------------------|
| **Skill** (`skills/<name>/SKILL.md`) | Plugin | `Skill` tool in main conversation (Claude Code), or OpenCode's native `skill` tool, or preloaded into a subagent via the agent's `skills:` frontmatter (embedded into the prompt on hosts without preloading) | **Yes — this is the SOT.** |
| **Agent** (`agents/<name>.md`) | Plugin | `Agent` tool with `subagent_type` | **No** — dispatch contract only. |

A workflow has exactly one Skill (the SOT). It may additionally have an Agent (when subagent dispatch is useful for context isolation). The Agent never duplicates the procedural content of the Skill.

Slash-command shortcuts (`/ingest`, `/draft`, …) were maintained in `opencode-commands/` through v0.2; they were removed in v0.3 because both Claude Code and OpenCode discover skills natively from `skills/<name>/SKILL.md`. Skills are triggered by natural language matching their `description:` or invoked directly via the `skill` tool.

## Skill frontmatter contract

Skills that are dispatchable (i.e. have an Agent) or that are invoked via Command declare an `inputs:` and `outputs:` block in their frontmatter. This block is the formal contract that Agents and Commands reference.

```yaml
---
name: ingest-source
description: ...
inputs:
  - name: source_path
    description: Absolute path to the source PDF or text in the shared library
    required: true
  - name: project_root
    description: Absolute path to the research project root
    required: true
  - name: existing_entities
    description: Pre-existing entity slugs to deduplicate against
    required: false
outputs:
  - path: knowledge/sources/<slug>.md
    kind: created
  - path: knowledge/entities/<entity-slug>.md
    kind: created_or_modified
  - path: output/bibtex/references.bib
    kind: modified
  - path: knowledge/_meta/log.md
    kind: appended
agents:
  - source-ingester
---
```

Fields:

- `inputs` — what the caller (parent skill, user, or dispatching agent) must supply. Each entry has `name`, `description`, `required` (default `true`).
- `outputs` — files and artefacts the skill produces or modifies. Each entry has `path` (may include placeholders), `kind` (`created` | `modified` | `created_or_modified` | `appended` | `deleted`).
- `agents` — names of subagents that can execute this skill. Optional. Pure-human skills (e.g. `brainstorming-research`) omit this.

## Agent shape (~25-35 lines)

An Agent file declares: which Skill it implements, the dispatch-specific rules (no memory, one message, strict output), and the output report format. It does **not** repeat the Skill's checklist.

```yaml
---
name: source-ingester
description: Dispatched by ingest-source. Reads ONE source thoroughly and produces all wiki artefacts. Fresh context per dispatch.
implements: ingest-source
skills:
  - ingest-source
model: inherit
disallowedTools: Agent
---

# Source Ingester Subagent

You execute the `ingest-source` skill as a dispatched subagent. You have NO memory
of the parent conversation. The full `skills/ingest-source/SKILL.md` is preloaded
into your context; follow that checklist exactly.

## Subagent rules

- No memory of parent — do not assume unstated context
- One source per dispatch — never batch
- Return everything in ONE message
- If a step is ambiguous, make the most defensible choice and flag it under "Notes for reviewer" — do not ask back
- Conservative on inferences — flag uncertainty, do not paper over it

## Output report (strict markdown)

[concrete report template, ~15 lines]
```

That is the whole agent file. The checklist, red flags, templates — all live in the SKILL.md.

## How the skill reaches the subagent

When a parent Skill (or the user triggering `ingest-source` via natural language) dispatches the `source-ingester` subagent:

1. The parent calls the `Agent` tool with `subagent_type: source-ingester` and a `prompt` that contains the concrete input values (source path, project root, focus, etc.).
2. Claude Code starts the subagent with the agent file as its system prompt and **preloads every skill listed in its `skills:` frontmatter** — the full SKILL.md (procedural checklist, red flags, templates) is in the subagent's context before it reads the prompt.
3. The Agent file's own content provides the subagent-specific framing (no memory, output format).

**Fallback — hosts without preloading.** A dispatch to a generic subagent type does not read `skills:`, and neither does a host whose agent loader lacks the field (check before relying on it in OpenCode). There the parent reads `skills/ingest-source/SKILL.md` and embeds its full content in the prompt alongside the inputs, as every version before v0.42 did. The agent body says both, so it reads correctly either way.

**Agent frontmatter beyond the contract.** `model:` routes the work (`inherit` where reading or writing quality is the product — ingest, drafting, analysis, review; `sonnet` for mechanical batch work — search, download, lint). `inherit` is written out rather than omitted so that a user-configured default subagent model cannot silently downgrade a source reading. `disallowedTools: Agent` keeps a worker from dispatching further workers — the preloaded skill describes its own dispatch step, which is the parent's job. `tools:` is deliberately **not** set as an allowlist: an allowlist drops MCP tools (`dao-paper-search`, `dao-searxng`) unless each is named, and the agents use them. Claude Code ignores `hooks`, `mcpServers` and `permissionMode` in plugin agents.

Result: the Skill checklist exists in exactly one file. The Agent file declares contract and dispatch rules.

## Lint check

`scripts/lint-plugin.py` checks these contracts — run in CI (the "Agent ↔ skill
contract" job) and locally before a PR.

**Enforced — a violation fails the build (exit 1):**

- Every Agent has an `implements:` field, referencing an existing Skill.
- Every Skill referenced as `agents:` exists.
- Symmetry: if an Agent implements Skill X, Skill X lists that Agent, and the back-pointer resolves.
- Every Agent preloads the Skill it implements (`skills:` contains the `implements:` value), and every `skills:` entry is an existing Skill by its bare name. Claude Code skips an unresolvable entry with only a debug-log warning, so this is checked here rather than discovered as a subagent that silently lacks its checklist.

**Advisory — reported, but does not fail:**

- Agent files should carry no numbered checklist longer than 3 items — a *heuristic* for "procedural content leaked out of SKILL.md", kept advisory because it can false-positive on a legitimate short enumeration.

The structural rules are enforced, not just editorial — when changing a workflow, change the Skill; the Agent stays untouched.

## When NOT to follow this pattern

Some skills are pure-human guidance (no subagent dispatch, no command shortcut) — e.g. `brainstorming-research`. These declare neither `inputs:` nor `outputs:` nor `agents:`. They are loaded via the `Skill` tool only, and their content is the whole story.
