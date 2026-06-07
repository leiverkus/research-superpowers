# Skill Authoring Guide

How to add or change a skill in this plugin.

## When to author a new skill

Author a new skill when a workflow phase is genuinely recurring, has a verifiable completion criterion, and is large enough that a checklist + red-flag table would actually catch mistakes. If it's one prompt's worth of reasoning, it's not a skill.

Strong signals:
- A phase currently gets skipped "because it feels obvious"
- The user has corrected the same mistake twice
- There is a file artifact whose existence can gate the next phase

Weak signals (consider not authoring):
- "It would be nice to remind the agent about X"
- A one-off preference
- A code pattern

## SOT pattern

Workflow logic lives in exactly one file. The Skill is that SOT. Agents and Commands reference the Skill — they do not duplicate its content. See [`skill-contract.md`](skill-contract.md) for the full pattern.

## File layout

```
skills/<skill-name>/SKILL.md           # SOT
agents/<agent-name>.md                 # optional — only if subagent dispatch helps
```

Skill names: `kebab-case`, verb-phrase or noun-phrase describing the activity (`ingest-source`, `writing-research-plan`). Match the folder name to the `name:` field in frontmatter.

Both Claude Code and OpenCode discover skills natively from `skills/<name>/SKILL.md`. No slash-command shims are needed; skills trigger from natural language matching their `description:` frontmatter, or are invoked directly via the `skill` tool.

## Skill template

```markdown
---
name: <skill-name>
description: Use when <trigger>. <What it does in one line>.
inputs:                # only if the skill is dispatchable or has a command
  - name: <input>
    description: <what it is>
    required: true | false
outputs:               # only if the skill produces file artefacts
  - path: <path or glob>
    kind: created | modified | created_or_modified | appended | deleted
agents:                # only if subagent(s) implement this skill
  - <agent-name>
---

<SUBAGENT-STOP>
If dispatched as a subagent for a specific task, skip this skill.
</SUBAGENT-STOP>

# <Title>

One-paragraph framing — what this phase accomplishes and why it is distinct from neighboring phases.

**Announce at start:** "Using <skill-name> to <purpose>."

<SOFT-GATE>
Before <action>, check:
(1) <verifiable condition>

If unmet: tell the user which, ask for a one-line reason, write to
`knowledge/_meta/gate-overrides.log`, continue.
</SOFT-GATE>

## When to use
## Checklist
## Process Flow
## <Phase-specific templates / tables>
## Red Flags
## Key Principles
## Next Skill
```

Section headings are English by convention (they function like keys; tools and authors recognise them). Prose, examples, red flags, and announce-lines are German.

## Agent template

Agents are thin pointers — no duplicated procedural content. See [`skill-contract.md`](skill-contract.md). Typical length: 30–70 lines.

```markdown
---
name: <agent-name>
description: <one-line, when dispatched>
implements: <skill-name>
---

# <Agent Title>

You execute the `<skill-name>` skill as a dispatched subagent. You have NO
memory of the parent conversation. The parent embeds the full
`skills/<skill-name>/SKILL.md` content into your prompt — follow that
checklist exactly. The contract is in that skill's frontmatter.

## Subagent rules
- (dispatch-specific constraints only — no duplicate checklist)

## Output (strict markdown)
(report template)
```

## Design rules

### Checklists

- **Concrete and verifiable.** "Verify that `foo.md` exists and has `status: stable`" is verifiable. "Understand the domain deeply" is not.
- **Ordered when order matters, numbered either way.** If steps commute, say so.
- **Reference files by path.** `input/ideas/<slug>-design.md`, not "the design doc".
- **One artifact per phase, minimum.** A skill should leave something on disk that the next phase can check.

### Gates — SOFT-GATE pattern

A SOFT-GATE names a verifiable precondition. If the condition holds, the skill proceeds. If not, the skill **does not silently block**: it surfaces the missing precondition to the user, requests a one-line written reason for proceeding anyway, and writes the reason to `knowledge/_meta/gate-overrides.log` before continuing. The audit trail is the discipline; the user is the final authority.

Format in the skill (`<SOFT-GATE>` tag wraps the precondition check):

```markdown
<SOFT-GATE>
Before <action>, check:
(1) <condition 1>
(2) <condition 2>
...

If unmet: tell the user which condition is missing, ask for a one-line
reason, write the reason to `knowledge/_meta/gate-overrides.log`, and
continue.
</SOFT-GATE>
```

Log line format (append-only):

```
- YYYY-MM-DD · <skill-name> · <condition-skipped> · <user reason>
```

`scripts/lint-wiki.py` surfaces the override rate of the last 10 entries and warns if it exceeds 30 % — overrides should be exceptional, not routine.

Use SOFT-GATEs for:
- Artifact existence (design doc, plan, synthesis page)
- Tool outputs (`lint-wiki.py` exits 0, `make render` succeeds)
- Pre-registration (only when `methodology: quantitative` or `mixed` for the relevant sub-study)

Do NOT use gates for subjective judgments ("the draft is good enough"). That is a review, not a gate.

### Red Flags

| Thought | Reality |
|---------|----------|
| "Quote the agent's literal thought" | "Name the reality crisply" |

Two rules:
- **Quote the thought literally.** The agent recognises verbatim, not paraphrase.
- **Name the reality, do not moralise.** "Later = never" is stronger than "Please don't defer".

### Subagent boundaries

If a skill dispatches subagents:
- Fresh context — no conversation history.
- Concrete output contract (file path, format, schema).
- Two-stage review (spec + quality) on the returned artefact.
- The subagent prompt file (`agents/<name>.md`) only declares contract + report format — never duplicates the checklist.

### Optional MCP integration

When a skill benefits from external structured data (verified citations, source-class detection, authority IDs), add an `## MCP Optimisation (recommended)` section after the manual procedure. Follow the soft-preference pattern: name the MCP and the tools used, link to [`recommended-mcps.md`](recommended-mcps.md), keep the manual path fully functional as fallback. The plugin must never *require* an MCP to function. See existing usages in `literature-review`, `ingest-source`, `requesting-peer-review`, `drafting-manuscript`, `semantic-wiki-review` as templates.

## Rigid vs flexible

Mark the skill in its opening paragraph:

- **Rigid** (e.g. `ingest-source`, `drafting-manuscript`, `requesting-peer-review`): checklist is a protocol. Skipping steps breaks downstream gates.
- **Flexible** (e.g. `wiki-lint`, `grant-finder`, `semantic-wiki-review`): principles adapted to context. No phase binding.

## Language convention

- **Everything** — skill prose, headings, frontmatter `description`, agent prompts, templates, examples, red-flag entries, the announce-line: **English**.
- **Frontmatter field names** (`name`, `description`, `inputs`, `outputs`, `agents`, `implements`): English.
- **Code, file paths, JSON keys, BibTeX keys, CLI commands**: as-is (typically English).
- **Domain-specific German (or Latin / Hebrew / Greek) terms of art** stay in their native form when standard: *Quellenkritik*, *Formgeschichte*, *Forschungsstand*, *Stratum*, *Locus*, *terminus ante quem*. Italicise on first use.

### Domain glossary

The German terms below are common in the source material a researcher will be working with. The plugin uses the English equivalents in code, paths, and skill content; the German originals are noted here so authors of new skills know which terms can stay italicised as standard.

| German term in source material | English used in plugin |
|---|---|
| Quelle | source |
| Seite | page |
| Wissensseite | wiki page |
| Entität | entity |
| Konzept | concept |
| Synthese | synthesis |
| Bibliographie | bibliography |
| Zitierschlüssel | bibkey / citation key |
| Forschungsfrage | research question |
| Forschungsplan | research plan |
| Pre-Registrierung | pre-registration |
| Hypothese | hypothesis |
| Falsifikationskriterium | falsification criterion |
| Manuskript | manuscript |
| Begutachtung | peer review |
| Methodologie | methodology |
| Forschungsstand | *Forschungsstand* (kept; "state of the field" is the closest English) |
| Quellenkritik | *Quellenkritik* (kept; "source criticism" is reasonable but the term of art is the German) |

## Registering a new skill

- Add folder + `SKILL.md` under `skills/`.
- Add agent prompt under `agents/` only if subagent dispatch helps.
- Add entry to `docs/phase-flow.md` if phase-bound.
- Add a one-line entry under the right section in `hooks/session-context.md`.
- Mention in `docs/README.md` if it changes the top-level workflow.

## Testing a new skill

1. Start a fresh Claude Code session in a demo research project.
2. Give a prompt that should trigger the skill.
3. Verify: skill is invoked before any tool call; announce-line appears; checklist tracked via TodoWrite; SOFT-GATE respected.
4. Try to bypass the gate — it must prompt for an override reason and log it to `knowledge/_meta/gate-overrides.log`.
5. Run the full phase-flow end-to-end once with a toy example.
