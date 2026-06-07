# Skill Contract — SOT Pattern

This document defines how the three artefact types in this plugin relate to each other so that workflow logic lives in exactly one place.

## The two artefact types

| Type | Lives in | Loaded by | Has procedural content? |
|------|----------|-----------|-------------------------|
| **Skill** (`skills/<name>/SKILL.md`) | Plugin | `Skill` tool in main conversation (Claude Code), or OpenCode's native `skill` tool, or embedded into a subagent prompt | **Yes — this is the SOT.** |
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
    description: Absolute path to the source PDF or text in input/bibliography/
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
---

# Source Ingester Subagent

You execute the `ingest-source` skill as a dispatched subagent. You have NO memory
of the parent conversation. The parent embeds the full `ingest-source` SKILL.md
content into your prompt; follow that checklist exactly.

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

## How the embedding works at dispatch

When a parent Skill (or the user triggering `ingest-source` via natural language) dispatches the `source-ingester` subagent:

1. The parent reads `skills/ingest-source/SKILL.md`.
2. The parent calls the `Agent` tool with `subagent_type: source-ingester` and a `prompt` that contains:
   - The full SKILL.md content (procedural checklist, red flags, templates), AND
   - The concrete input values (source path, project root, etc.).
3. The Agent file's own content (the system prompt loaded from `agents/source-ingester.md`) provides the subagent-specific framing (no memory, output format).

Result: the Skill checklist exists in exactly one file. The Agent file declares contract and dispatch rules. The Command file is a one-line UI shortcut.

## Lint check

A future `scripts/lint-plugin.py` (not part of the first cut) will verify:

- Every Agent's `implements:` field references an existing Skill.
- Agent files do not contain a numbered checklist of more than 3 items (heuristic for "duplicates SKILL.md").
- Every Skill referenced as `agents:` exists.

For now, the constraint is editorial — when changing a workflow, change the Skill; the Agent stays untouched.

## When NOT to follow this pattern

Some skills are pure-human guidance (no subagent dispatch, no command shortcut) — e.g. `brainstorming-research`. These declare neither `inputs:` nor `outputs:` nor `agents:`. They are loaded via the `Skill` tool only, and their content is the whole story.
