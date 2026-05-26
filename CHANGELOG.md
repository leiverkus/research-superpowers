# Changelog

All notable changes to `research-superpowers` are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] — 2026-05-27

Cowork-friendly install path. The plugin now works fully click-only — no terminal, no Python, no Git required for the core workflow. Existing CLI users see no change to their flow. Purely additive; no breaking changes. See [`docs/migration-v0.3-to-v0.4.md`](docs/migration-v0.3-to-v0.4.md).

### Added

- **`skills/scaffold-research-project/SKILL.md`** — conversational project scaffolding. Asks for project name, parent directory, methodology, discipline, and languages; copies the template tree via Claude's Read+Write tools (no `cp -r`); patches CLAUDE.md frontmatter with the user's answers; optionally initialises git via Bash if available. Designed for Cowork (no shell) and as a friendlier setup for any first-time user. Skill total: 12 → 13.
- **Python-free fallback in `skills/wiki-lint/SKILL.md`** — when `scripts/lint-wiki.py`, `python3`, or `pyyaml` are missing, the skill validates frontmatter inline. Tells the user explicitly that wikilink resolution and orphan detection require the Python script (those checks are O(N²) in tokens for a full-wiki scan).
- **`docs/installation-cowork.md`** — click-only install path. What you need (just Claude), install via `/plugin marketplace add`, scaffold via natural language, what each "give up" actually costs (Python / Git / Quarto), troubleshooting, when to upgrade to the full setup.
- **`docs/migration-v0.3-to-v0.4.md`** — short note: purely additive, existing users keep their CLI flow.
- **README and `docs/installation.md` and `docs/README.md`** — cross-pointers to the Cowork install path.

### Changed

- `.claude-plugin/plugin.json` — version 0.3.0 → 0.4.0; description appended: "Works in Claude Code and Cowork — no terminal required for the core workflow."
- `.claude-plugin/marketplace.json` — version 0.4.0 (sync); description appended; new `cowork` tag added.

### Removed / Fixed

None.

---

## [0.3.0] — 2026-05-27

First public release. Combines an optional MCP integration layer, the removal of the legacy OpenCode-commands shims (OpenCode now reads skills natively from `.claude/skills/`), full English internationalisation of all skill prose and templates, and a complete user-facing manual (README, Quickstart, Tutorial, Concepts). **Additive** for MCP and i18n; the removal of `opencode-commands/` is technically breaking for anyone who relied on the slash shortcuts, but they were never published. See [`docs/recommended-mcps.md`](docs/recommended-mcps.md) and [`docs/migration-v0.2-to-v0.3.md`](docs/migration-v0.2-to-v0.3.md).

### Added

- **`docs/recommended-mcps.md`** — setup guide for both MCPs (install, env vars, Docker stack for SearXNG, version pinning).
- **`docs/migration-v0.2-to-v0.3.md`** — short migration note (no required steps, optional MCP setup, optional new frontmatter fields).
- **Schema entity fields** in `schema/knowledge-frontmatter.schema.json` (and template mirror): `wikidata_qid`, `idai_gazetteer_id`, `gnd_id` — all optional, with regex patterns. Resolvable via `dao-paper-search-mcp.resolve_author` / `resolve_site`.
- **"MCP-Optimierung (recommended)" sections** in 5 skills (`literature-review`, `semantic-wiki-review`, `requesting-peer-review`, `ingest-source`, `drafting-manuscript`) and 1 agent (`literature-scout`). Each follows the soft-preference pattern: name the MCP, point to the manual fallback, never require the MCP.
- **`agents/literature-scout.md` output schema** extended with optional `source_class`, `inline_citation_markdown`, `authoritative_bibliography_line`, `wikidata_qid`, `idai_gazetteer_id` fields.
- **Authority IDs in entity template** — `_beispiel-tel-megiddo.qmd` now shows `wikidata_qid: Q173799` and `idai_gazetteer_id: "2048473"` as examples.
- **"Suspect / aggregator citations" audit category** in `semantic-wiki-review`, plus matching table column in the report format.
- **Cited Evidence Audit with `source_class`** column in `requesting-peer-review` report template.
- **Web-citation form** `[(domain — title)](url)` documented in `drafting-manuscript` Citation Rules.

### Changed

- `.claude-plugin/plugin.json` — version 0.2.0 → 0.3.0; description amended with "MCP-aware".
- `templates/research-project-template/CLAUDE.md` — added "Recommended MCPs für DAO-Workflow" subsection after the Zotero-MCP block.
- `docs/README.md` — bullet added under "What it does" naming both MCPs.
- `docs/skill-authoring.md` — new "Optional MCP integration" subsection documenting the soft-preference pattern.
- `docs/README.md`, `docs/skill-contract.md`, `docs/skill-authoring.md`, `docs/migration-v0.1-to-v0.2.md` — note that both Claude Code and OpenCode discover skills natively from `skills/<name>/SKILL.md`. OpenCode install instruction updated to symlink `skills/` under `.claude/skills/`.

### Removed

- **`opencode-commands/` directory** (all 5 remaining commands: `/ingest`, `/draft`, `/peer-review`, `/lit-review`, `/research-brainstorm`). [OpenCode v1.x](https://opencode.ai/docs/skills/) reads `SKILL.md` files natively from `.claude/skills/<name>/SKILL.md` and exposes a built-in `skill` tool. The slash-shortcut shims added no UX value over natural-language triggering or `skill({ name: ... })`. The Command artefact type is gone from the SOT pattern (`docs/skill-contract.md` now describes two types: Skill + Agent).

### Internationalisation & Manual

- **All skill prose, template content, and example project translated to English.** Domain-specific German terms (`*Quellenkritik*`, `*Formgeschichte*`, `*Forschungsstand*`) kept italicised on first use where they are standard. Frontmatter field names, JSON keys, BibTeX keys, and slugs are English.
- **New top-level `README.md`** — GitHub frontpage with hero, Why / Who / Install, 30-second example, skill topology table, docs wayfinder.
- **`LICENSE`** — MIT, Patrick Leiverkus, 2026 (the manifest already declared MIT; this is the canonical file).
- **`.gitignore`** — Python / Node / OS / Quarto outputs.
- **`CONTRIBUTING.md`** — language convention, PR verification commands (including `claude plugin validate --strict`), release procedure, skill-authoring quick reference.
- **`docs/installation.md`** — comprehensive step-by-step installation guide for non-technical users: prerequisites with version checks, three install paths (marketplace, GitHub URL, local clone), OpenCode path, verification, troubleshooting, uninstall.
- **`docs/quickstart.md`** — five-minute onboarding from install to first ingest.
- **`docs/tutorial.md`** — end-to-end walkthrough on a realistic mini-project (Iron Age IIA chronology), every phase narrated, methodology branching demonstrated.
- **`docs/concepts.md`** — narrative explainer of SOFT-GATE, methodology branching, SOT pattern, structural vs semantic review, MCP soft preference.

### Marketplace preparation

- **`.claude-plugin/marketplace.json`** — self-hosted marketplace manifest. End users can register the marketplace with `/plugin marketplace add leiverkus/research-superpowers`, then `/plugin install research-superpowers@leiverkus-research`. Same path used for community-marketplace submission.
- **`.claude-plugin/plugin.json` extended** with `displayName`, `homepage`, `repository`, `bugs` URLs and additional keywords (`ancient-history`, `hermeneutics`, `pre-registration`, `soft-gate`, `mcp`) for marketplace discovery.
- **README install section rewritten** for first-time Claude Code plugin users: leads with the `/plugin marketplace add` flow, lists prerequisites, points to the comprehensive guide.

### Fixed

None.

---

## [0.2.0] — 2026-05-27

Architecture consolidation. **Breaking** — bump major-zero version because public skill/command surface changes. See [`docs/migration-v0.1-to-v0.2.md`](docs/migration-v0.1-to-v0.2.md) for project-level migration steps.

### Breaking changes

- **HARD-GATE → SOFT-GATE.** All `<HARD-GATE>` blocks in skills are replaced by `<SOFT-GATE>` blocks that prompt the user for a written override reason and log it to `knowledge/_meta/gate-overrides.log` instead of blocking. Affected skills: `brainstorming-research`, `writing-research-plan`, `literature-review`, `ingest-source`, `executing-research-plan`, `drafting-manuscript`, `requesting-peer-review`, `finishing-a-research-project`, `wiki-lint`.
- **`critical-thinking` skill removed.** Cross-cutting content folded into `executing-research-plan` (method selection) and `requesting-peer-review` (evidence audit). Remove direct invocations.
- **5 OpenCode commands deleted:** `/execute-plan`, `/finish-project`, `/grant-finder`, `/research-plan`, `/wiki-lint`. The underlying skills remain available via the `Skill` tool; the slash shortcuts added no value over the natural skill trigger.
- **Pre-registration no longer universal.** With `methodology: hermeneutic` (default), `writing-research-plan` produces a `status: ready` plan with research question + method sketch + expected sources — no frozen hypothesis. Only `methodology: quantitative` (or quantitative tasks within `mixed`) require full pre-registration.
- **Wiki lint `bibliography` no longer required.** `scripts/lint-wiki.py` previously required `bibliography` in every page's frontmatter, contradicting the docs. The field is now correctly optional. Pre-existing pages that omitted it will now pass.

### Added

- **`schema/knowledge-frontmatter.schema.json`** — central JSON Schema Draft-07. Single source of truth, mirrored into `templates/research-project-template/schema/` for project-level use.
- **`schema/README.md`** documenting consumers and sync.
- **`docs/skill-contract.md`** formalising the Skill-as-SOT pattern: Skills declare `inputs:` / `outputs:` / `agents:` in frontmatter; Agents and Commands are thin pointers.
- **`docs/migration-v0.1-to-v0.2.md`** — step-by-step project migration guide.
- **`skills/semantic-wiki-review/SKILL.md`** — new skill for the LLM content audit previously promised (but never implemented) by `wiki-lint`. Manual trigger, no CI gate.
- **`hooks/session-context.md`** — compact skill index (~25 lines) injected at SessionStart. Replaces the full SKILL.md inject from v0.1.
- **`templates/research-project-template/.vscode/settings.json` `yaml.schemas`** mapping for live frontmatter validation in VS Code.
- **`templates/research-project-template/CLAUDE.md` frontmatter** declaring project-level `methodology`, `discipline`, `languages`.
- **Gate-override reporting** in `scripts/lint-wiki.py`. New `=== Gate-Overrides ===` block surfaces the override rate over the last 10 entries; warns above 30 %.
- **Phase-flow back-edges** in `docs/phase-flow.md`: `ingest → plan`, `draft → execute`, `peer → draft` as legitimate hermeneutic iteration.
- **Sharp boundary documentation** between `literature-review` (search → `input/bibliography/`) and `ingest-source` (intake → `knowledge/`).

### Changed

- **Agents reduced** from ~82 to ~60 lines average. All 6 agents declare `implements: <skill-name>`; procedural content lives in the implemented skill.
- **OpenCode commands reduced** from 10 (avg ~55 lines) to 5 (≤ 10 lines each).
- **`hooks/session-start`** now loads `hooks/session-context.md` (~1.5 KB) instead of `using-research-powers/SKILL.md` (~7.6 KB). 80 % reduction in per-session token cost.
- **`skills/using-research-powers/SKILL.md`** — authoritarian language (`<EXTREMELY-IMPORTANT>`, "YOU DO NOT HAVE A CHOICE") replaced with sober discipline guidance.
- **`docs/frontmatter-schema.md`** slimmed from 122 to ~30 lines; narrative pointer only.
- **`templates/research-project-template/CLAUDE.md`** — inline frontmatter schema replaced with pointer to `schema/`.
- **`docs/skill-authoring.md`** — SOT-pattern documented; SOFT-GATE template; language convention with DE/EN glossary.
- **`docs/phase-flow.md`** — SOFT-GATE diamonds, methodology-aware gate labels, hermeneutic back-edges.
- **`templates/research-project-template/scripts/lint-wiki.py`** — loads `schema/knowledge-frontmatter.schema.json` instead of hardcoded constants; minimal stdlib Draft-07 validator (no `jsonschema` dep). Removed claims about semantic checks (those live in `semantic-wiki-review` now).
- **5 SOT skills** (`ingest-source`, `drafting-manuscript`, `requesting-peer-review`, `executing-research-plan`, `literature-review`) — added `inputs:`, `outputs:`, `agents:` frontmatter so agents/commands can reference them.

### Removed

- `skills/critical-thinking/` — content dissolved into `executing-research-plan` and `requesting-peer-review` as cross-cutting checklists.
- `opencode-commands/execute-plan.md`
- `opencode-commands/finish-project.md`
- `opencode-commands/grant-finder.md`
- `opencode-commands/research-plan.md`
- `opencode-commands/wiki-lint.md`
- `<EXTREMELY-IMPORTANT>` block in `using-research-powers/SKILL.md`
- Hardcoded `TYPES`, `STATUS_VALUES`, `REQUIRED_FIELDS` constants in `lint-wiki.py`
- Inline YAML frontmatter template in `ingest-source/SKILL.md` (replaced with schema reference + minimal example)

### Fixed

- `lint-wiki.py` `bibliography`-required bug — pages in `examples/example-project/` now pass frontmatter validation (they always should have).

## [0.1.0] — 2026-04-20

Initial release.
