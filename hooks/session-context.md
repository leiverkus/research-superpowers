# Research Superpowers — Skill Index

You have the **research-superpowers** plugin. Below is an index of available
skills with one-line triggers. For full procedural content, load the skill via
the `Skill` tool (e.g. `Skill ingest-source`).

## Workflow phases (sequence)

1. **brainstorming-research** — open question → input/ideas/<slug>-design.md
2. **writing-research-plan** — design doc → pre-registered plan
3. **literature-review** — strategic search, produces literaturguide.md + BibTeX
4. **ingest-source** — one source PDF → wiki content (sources + entities + BibTeX + log)
5. **executing-research-plan** — work plan tasks via subagents with two-stage review
6. **drafting-manuscript** — stable synthesis pages → output/publication/**/*.qmd
7. **requesting-peer-review** — manuscript → constructive + adversarial review
8. **finishing-a-research-project** — closing checklist, archival

## Cross-cutting skills

- **wiki-lint** — run scripts/lint-wiki.py (structural, deterministic)
- **semantic-wiki-review** — LLM content audit (contradictions, stale syntheses)
- **grant-finder** — funding programmes parallel to publication

## Calling convention

When a user message matches a skill's trigger, load the skill via the `Skill`
tool before responding. Skills declare their inputs/outputs in frontmatter
(see `docs/skill-contract.md`).

User instructions in CLAUDE.md or AGENTS.md override skill defaults. If the
user says "skip <phase>", name the skipped phase out loud and proceed.
