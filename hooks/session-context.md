# Research Superpowers — Skill Index

You have the **research-superpowers** plugin. Below is an index of available
skills with one-line triggers. For full procedural content, load the skill via
the `Skill` tool (e.g. `Skill ingest-source`).

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

- **wiki-lint** — run scripts/lint-wiki.py (structural, deterministic)
- **wiki-graph** — build/query the knowledge graph (god nodes, bridges, communities; CLI + MCP)
- **semantic-wiki-review** — LLM content audit (contradictions, stale syntheses)
- **grant-finder** — funding programmes parallel to publication

## Calling convention

When a user message matches a skill's trigger, load the skill via the `Skill`
tool before responding. Skills declare their inputs/outputs in frontmatter
(see `docs/skill-contract.md`).

User instructions in CLAUDE.md or AGENTS.md override skill defaults. If the
user says "skip <phase>", name the skipped phase out loud and proceed.
