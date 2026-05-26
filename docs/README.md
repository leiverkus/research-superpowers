# research-superpowers

A meta-workflow plugin for LLM-assisted scientific research. Inspired by [obra/superpowers](https://github.com/obra/superpowers), adapted to the research lifecycle: **Idee → Plan → Literatur → Ingest → Analyse → Draft → Peer-Review → Publikation**.

Target domains: Theology, Biblical Archaeology, Digital Humanities. Methodology-aware: hermeneutic projects are the default; quantitative and mixed sub-studies opt in to pre-registration.

Works with the [research-project-template](./../templates/research-project-template/).

## What it does

- **SOFT-GATE pattern** — skills check verifiable preconditions and request a written override reason instead of silently blocking. Overrides are logged to `knowledge/_meta/gate-overrides.log`; the linter warns when override rate exceeds 30 %.
- **Methodology branching** — `methodology: hermeneutic` skips pre-registration in favor of research question + method sketch; `quantitative` requires a frozen hypothesis with falsification criteria; `mixed` handles per-sub-study.
- **SOT pattern** — workflow logic lives in exactly one file per workflow (the Skill). Agents and Commands are thin pointers (`implements:` field on agents, ≤ 10-line commands). See [`skill-contract.md`](skill-contract.md).
- **Centralized frontmatter schema** in [`schema/knowledge-frontmatter.schema.json`](../schema/knowledge-frontmatter.schema.json) — consumed by `scripts/lint-wiki.py`, VS Code `yaml.schemas`, and skills (by reference, not duplicate).
- **SessionStart hook** injects a ~25-line skill index (~80 % smaller than v0.1's full SKILL.md inject). Skill details are loaded on-demand via the `Skill` tool.
- **12 skills + 6 subagents** mirror the workflow. Both Claude Code and OpenCode discover skills natively from the `skills/` directory; no separate slash-command shims are needed.
- **Optional: Recommended MCPs** (v0.3) — [`dao-paper-search-mcp`](https://github.com/leiverkus/dao-paper-search-mcp) for verified academic citations across Zenon DAI / IAA / ADAJ / IxTheo / OpenAlex / Crossref etc. plus Wikidata / iDAI.gazetteer entity resolution; [`dao-searxng-mcp`](https://github.com/leiverkus/dao-searxng-mcp) for web search with `source_class` detection (primary / aggregator / suspect). Both are optional — skills fall back to manual API calls if absent. See [`recommended-mcps.md`](recommended-mcps.md).

## Install (Claude Code)

```bash
claude plugins install /path/to/research-superpowers
```

After install, start a session inside a research project (scaffold one from `templates/research-project-template/` first). The assistant gets a compact skill index at SessionStart and loads individual skills on demand.

## Install (OpenCode)

OpenCode v1.x reads `SKILL.md` files natively from `.claude/skills/<name>/SKILL.md` ([OpenCode docs](https://opencode.ai/docs/skills/)). Symlink or copy the plugin's `skills/` directory under your project's `.claude/`:

```bash
ln -s /path/to/research-superpowers/skills .claude/skills
```

Agents discover skills via OpenCode's built-in `skill` tool and load them on demand. No separate slash-commands needed.

## Skill topology

**Workflow phases (sequential, with legitimate back-edges):**

```
brainstorming-research        (SOFT-GATE: design doc signed off)
   ↓
writing-research-plan         (SOFT-GATE: methodology-aware —
                               quant: pre-registered hypothesis;
                               herm: status=ready)
   ↓
literature-review  →  ingest-source (loop)
   ↓                     (SOFT-GATE: 5 artefacts + lint green)
executing-research-plan       (review mode methodology-aware —
                               quant: two-stage spec+quality;
                               herm: synthesis-review)
   ↓
drafting-manuscript           (SOFT-GATE: ≥1 stable synthesis + lint green)
   ↓
requesting-peer-review        (constructive + adversarial)
   ↓
finishing-a-research-project  (closing checklist)
```

**Cross-cutting skills** (context-triggered, no phase binding):
- `wiki-lint` — structural, deterministic, runs the Python linter
- `semantic-wiki-review` — LLM content audit (contradictions, stale syntheses); separate from `wiki-lint`
- `grant-finder` — funding programmes parallel to publication

**Phase-flow graph** with hermeneutic back-edges and SOFT-GATE semantics: see [`phase-flow.md`](phase-flow.md).

## Methodology

The project's `CLAUDE.md` declares `methodology` in its frontmatter:

- `hermeneutic` (default) — theology, exegesis, source criticism, interpretive archaeology. No frozen hypothesis. Plan documents research question + method sketch + expected sources; hypothesis revision through new reading is legitimate and goes into `_meta/log.qmd`.
- `quantitative` — geostatistics, 14C Bayesian, quantitative DH. Full pre-registration (hypothesis, operationalisation, stop criterion). Deviations are logged and results marked exploratory.
- `mixed` — per-sub-study. Quantitative tasks mark `pre-registered: true`; hermeneutic tasks do not.

## Repository layout

```
research-superpowers/
├── .claude-plugin/plugin.json
├── schema/                       # SOT — JSON Schema (mirrored into template)
├── hooks/                        # SessionStart injects session-context.md
├── skills/                       # 12 SKILL.md files (SOT for workflows)
├── agents/                       # 6 thin-pointer subagents
├── templates/research-project-template/
│   ├── CLAUDE.md                 # frontmatter declares methodology + discipline
│   ├── schema/                   # mirror of plugin schema
│   ├── scripts/lint-wiki.py      # consumes schema; reports gate-overrides rate
│   └── .vscode/settings.json     # yaml.schemas → live frontmatter validation
├── examples/example-project/
└── docs/
    ├── README.md                 # this file
    ├── frontmatter-schema.md     # narrative pointer to schema/
    ├── phase-flow.md             # graph with hermeneutic back-edges
    ├── skill-authoring.md        # how to add or change a skill
    ├── skill-contract.md         # SOT pattern + inputs/outputs format
    └── migration-v0.1-to-v0.2.md
```

## Authoring new skills

See [`skill-authoring.md`](skill-authoring.md) — template, language convention with DE/EN glossary, agent/command shape, lint expectations.

## Frontmatter

Every `knowledge/**/*.qmd` page follows the central schema. See [`frontmatter-schema.md`](frontmatter-schema.md) for the narrative pointer; [`schema/knowledge-frontmatter.schema.json`](../schema/knowledge-frontmatter.schema.json) for the normative definition.

## Migrating from v0.1

See [`migration-v0.1-to-v0.2.md`](migration-v0.1-to-v0.2.md) and [`../CHANGELOG.md`](../CHANGELOG.md).

## License

Patrick Leiverkus, MIT, 2026.
