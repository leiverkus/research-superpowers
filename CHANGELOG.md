# Changelog

All notable changes to `research-superpowers` are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.0] — 2026-06-08

Adds dependency-free community detection to the knowledge graph — automatic thematic clustering, in the CLI, the MCP, and a community-grouped HTML layout.

### Added

- **Community detection** (`scripts/wiki-to-graph.py`) — automatic thematic clustering of the wiki, dependency-free and deterministic (greedy modularity, Clauset–Newman–Moore; no `igraph`/`leidenalg`). Surfaces the sub-topics of a literature without any tagging.
  - New `communities [--min-size N]` query sub-command and `graph_communities` MCP tool (`--json` supported); each community reports its size, node-type mix, and members.
  - Every node gets a `community` id in `graph.json` / `graph.graphml`; `graph.html` **groups nodes spatially by community** (compound containers laid out by cose) and gains a **Colour: by type / by community** switch.
  - Robust on dense, hub-heavy wikis where label propagation collapses to one blob; ties broken deterministically so the partition is reproducible.
  - CI smoke-tests the community query + the `community` attribute on the example project.

## [0.7.0] — 2026-06-08

Completes the knowledge-graph Query-Layer: query the wiki live during a session, from the terminal or as native MCP tools.

### Added

- **Live graph query sub-commands** in `scripts/wiki-to-graph.py` — query the wiki *during a session*, recomputed from the `.md` on each call (always current, no stale export), deterministic (real graph traversal, not LLM-eyeballed JSON), stdlib-only:
  - `neighbors <slug> [--depth N] [--relation TYPE]`, `path <a> <b>`, `god-nodes [--top-n N]`, `bridges`, `relations [--type T] [--confidence C] [--node N]`, `search <term>`, `stats`; `--json` on any query for machine-readable output; node tokens may be a unique substring (fuzzy-resolved).
  - Backward compatible: with no sub-command the script builds the exports exactly as before (CI, scaffold and the skill are unchanged).
  - `wiki-graph` skill now queries the live graph for targeted questions (build/HTML reserved for overview and the visual); documented in CLAUDE.md; CI smoke-tests the queries on the example project.
  - This is the CLI half of the deferred Query-Layer.
- **`wiki-graph` MCP server** (`scripts/graph_mcp.py`) — the MCP half of the Query-Layer. A stdlib-only stdio JSON-RPC server (no `pip install mcp`, no network) that exposes the queries as native tools: `graph_neighbors`, `graph_path`, `graph_god_nodes`, `graph_bridges`, `graph_relations`, `graph_search`, `graph_stats`. It is a thin wrapper — each tool shells out to `wiki-to-graph.py --json`, so results are identical and equally live. Registered **per project** via `.mcp.json` (Claude Code reads it at the project root, rooted in that repo, so it auto-knows the right wiki in any session); OpenCode equivalent documented in CLAUDE.md. CI smoke-tests the handshake + a tool call.

## [0.6.0] — 2026-06-07

Two related changes: the knowledge wiki moves to plain Markdown (Quarto reserved for the publication layer), and a dependency-free knowledge-graph export layer is added on top of it.

### Added

- **Knowledge-graph export layer over the Markdown wiki.** The wiki is already a graph (pages linked by wikilinks); this makes it explicit and queryable without a new dependency or any LLM/network calls.
  - `scripts/wiki-to-graph.py` (template + example-project mirror) reads `knowledge/**/*.md` and writes `knowledge/_meta/graph/graph.json` and `knowledge/_meta/graph/graph.graphml` (Gephi/yEd). One node per page (`type` from frontmatter; optional `subtype` derived only from `gnd_id`/`idai_gazetteer_id`); edges from wikilinks (confidence `extracted`) and from the new structured `relations` block. Derived views: **god_nodes** (top-N by degree, `--top-n`, default 15) and **bridges** (entities joining ≥2 otherwise-unconnected source clusters, via union-find). CLI `--knowledge-dir` / `--out-dir`.
  - **Self-contained interactive `graph.html`** — `wiki-to-graph.py` also writes an offline HTML viz (cytoscape.js vendored under `scripts/vendor/`, inlined into one file — no install, no network). Colour by node type, size by degree (capped), gold ring on bridges; short labels (sources shown as "Author Year", not the full title); filter by node type / relation type / confidence; search; click a node to highlight its neighbourhood and list its typed relations. For readability the default view shows only the typed-relation layer (wikilinks are one toggle away) and lays out the visible subgraph. Covers everyday exploration without Gephi/yEd (those remain for heavy layout / community detection). `--no-html` skips it; the script degrades gracefully if the vendored lib is absent.
  - **Optional `relations` frontmatter field** (additive — pages without it stay valid): `target` (page slug), `type` (free vocabulary: cites, contradicts, builds-on, …), `confidence` (`extracted` | `inferred` | `ambiguous`). Documented in `docs/frontmatter-schema.md`; added identically to all three schema copies.
  - **Linter integration:** `lint-wiki.py` validates `relations` (target resolves, confidence enum, required/known keys) and reports an **inference-rate** (share of `inferred`+`ambiguous`), mirroring the SOFT-GATE override-rate as an audit signal.
  - CI builds the graph from the example project and asserts node/edge/relation counts, non-empty god_nodes + bridges, and well-formed GraphML.
  - **`wiki-graph` skill** — the intent-triggered layer over the script: builds the graph and answers structure questions grounded in `graph.json` (god nodes, bridges, relation types/confidence, dangling/orphan signals), with a Python-free fallback. Positioned as the structure-analysis sibling of `wiki-lint` (validation) and `semantic-wiki-review` (content audit). Registered in the skill catalogue (`using-research-powers`, README, `docs/concepts.md`).

### Changed

- **Knowledge wiki is now plain Markdown (`.md`), not Quarto (`.qmd`).** The wiki layer (`knowledge/`) is for thinking and steering — it needs no build step and is read directly in Foam/Obsidian or the repository browser. Quarto is now reserved exclusively for the publication layer (`output/publication/`), which genuinely needs formats, CSL, cross-references and figures. This aligns the template and example project with the convention already used in real projects.
  - Renamed every `knowledge/**/*.qmd` page to `.md` in `templates/research-project-template/` and `examples/example-project/`.
  - Removed `knowledge/_quarto.yml` and `knowledge/Makefile` from the template (the wiki has no build step).
  - `scripts/lint-wiki.py` now globs `*.md` (and skips both `_example-` and `_beispiel-` prefixes).
  - Figures in wiki pages use plain Markdown image syntax; the Quarto cross-reference form (`{#fig-…}` + `@fig-…`) is reserved for publication pages.
  - `.gitlab-ci.yml` lints the wiki (`scripts/lint-wiki.py`) instead of rendering it; only the publication is rendered and deployed to GitLab Pages.
  - Updated `.vscode/settings.json` (schema glob → `knowledge/**/*.md`), `.gitignore` (dropped stale `knowledge/_site|.quarto`), the JSON Schema descriptions, `CLAUDE.md`, both READMEs, and all skill/agent/docs references accordingly.

### Fixed

- **Template `knowledge/_meta/index.md` and `log.md` now carry valid YAML frontmatter**, so a freshly scaffolded project passes `scripts/lint-wiki.py` (0 issues) out of the box.

## [0.5.1] — 2026-05-28

Post-release housekeeping for the example project. Brings every file under `examples/example-project/` into alignment with v0.3 (SOFT-GATE / methodology-aware) and v0.5 (focus-driven ingest). No skill or schema changes.

### Changed

- **`examples/example-project/input/ideas/low-chronology-design.md`** — rewritten as a hermeneutic design doc (matches the project's `methodology: hermeneutic` declared in `input/description/project-description.md`). Removes references to a quantitative OxCal re-analysis; reframes as close reading of the foundational positions plus *Forschungsstand* with three plausible interpretive outcomes (regional variation / one-resolution / Forschungsstand reading).
- **`examples/example-project/input/ideas/low-chronology-plan.md`** — `status: pre-registered` → `status: ready`; removed `Hypothesis` and `Falsification Criteria` blocks (not used in hermeneutic projects); added `methodology: hermeneutic` and `Method sketch` / `Iteration expectation` blocks per v0.3 plan template. Task list rewritten around close reading + per-source focus-driven ingest, dropping the Bayesian / OxCal data-analysis tasks.
- **`examples/example-project/knowledge/synthesis/chronology-debate.qmd`** — modernised to v0.5 conventions: references the focus-driven Finkelstein-Piasetzky source page properly (via the `## Focus: 14C reconciliation` block); adds an argument-structure map over the four levels of the debate (data selection / calibration / phase modelling / framework choice); incorporates the new Mazar 2011 and Regev et al. 2020 stubs. Status: `review` (was: `draft`).
- **`examples/example-project/output/publication/article/main.qmd`** — rewritten as a hermeneutic article skeleton (Introduction → State of the Field → Argument Structure → Negev Case → Discussion → Conclusion). Dropped Reproducibility section with OxCal seeds (no quantitative analysis to reproduce).
- **`examples/example-project/knowledge/_meta/log.qmd`** — updated to reflect the new event sequence (plan `status: ready` rather than `pre-registered`; new ingests for Mazar 2011 and Regev et al. 2020; synthesis promoted to `review`).

### Added

- **`examples/example-project/knowledge/sources/mazar-2011.qmd`** — new focus-driven source page with one focus block ("the Modified Conventional Chronology response to the Low Chronology"), demonstrating the v0.5 structure on the Mazar counter-position.
- **`examples/example-project/knowledge/sources/regev-et-al-2020.qmd`** — new focus-driven source page with one focus block ("the current Tel Rehov 14C dataset and re-modelling under IntCal20").
- **BibTeX entries for `mazar-2011` and `regev-et-al-2020`** in `examples/example-project/output/bibtex/references.bib`.

### Removed / Fixed

- Stale "not yet ingested" markers for `mazar-2011` and `regev-et-al-2020` across the example project — these are now real stub source pages.

---

## [0.5.0] — 2026-05-27

Focus-driven `ingest-source`. Source pages now capture **what this project takes from a source under a specific focus**, not a generic summary. Re-ingest of the same source with a different focus appends a new `## Focus:` block rather than overwriting. Aligns the wiki with how researchers actually read: question-driven, not RAG-style full-text indexing. Existing source pages keep working — lint accepts both old and new structures. See [`docs/migration-v0.4-to-v0.5.md`](docs/migration-v0.4-to-v0.5.md).

### Changed

- **`skills/ingest-source/SKILL.md`** — substantial restructure. New `focus` input (smart-default from `input/description/project-description.md`). New Step 1 "Determine focus" (proposes project research question, asks user to confirm or refine; refuses to proceed without confirmed focus). New Step 5 "Check for existing source page" + re-ingest detection branch (append mode preserves prior focus blocks; replaces `## Other content in this source`; unions `## Mentioned entities` and `## Connections`; legacy-wrap option for pre-v0.5 pages). New Source Page Template body (stacked `## Focus:` blocks; explicit `## Boundary: what this source does NOT address`; one-paragraph `## Other content in this source`). Old generic sections (`Core Theses`, `Method`, `Relevant Findings`, `Positioning`) removed from the spec.
- **`agents/source-ingester.md`** — output report extended: `### Focus`, `### Re-ingest mode` (`fresh` | `append-section` | `update-existing-focus` | `legacy-wrap`); `### Claims relevant to focus` replaces `### Core theses`; `### Boundary noted` echoes the explicit boundary statement. Min. 1 verbatim quote *per focus block* (was: min. 2 per ingest).
- **`templates/research-project-template/knowledge/sources/_beispiel-finkelstein-2003.qmd`** — rewritten with two stacked focus blocks demonstrating the append pattern.
- **`examples/example-project/knowledge/sources/finkelstein-piasetzky-2003.qmd`** — rewritten with one realistic focus block aligned to the example project's research question.

### Added

- **`examples/example-project/input/description/project-description.md`** — new file. The example project now has a proper research question file so the smart-default focus elicitation has something to read.
- **`docs/concepts.md` § "Wiki is purpose-built, not a generic archive"** — explains the why behind focus-driven ingest, the append-on-reingest pattern, and how this differs from RAG.
- **`docs/migration-v0.4-to-v0.5.md`** — covers the structural change, the optional re-ingest with legacy-wrap, and what stays unchanged.
- **`docs/tutorial.md` § Phase 4** — walkthrough updated to demonstrate focus elicitation, focus refinement, and re-ingest with a different focus on the same source.

### Removed / Fixed

None (the removal of the generic body sections from the SKILL.md *spec* is a template change, not a removal from existing wiki pages).

---

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

## [0.3.1] — 2026-05-27 (post-release housekeeping, rolled into v0.4.0)

> Documented retroactively. These changes shipped to `main` between the v0.3.0 and v0.4.0 tags (commits `0e884ae`, `5432dda`, `c521d5a`) but were not separately tagged. Anyone installing `@v0.4.0` or later already has them.

### Added

- **`.github/ISSUE_TEMPLATE/`** — four YAML-form issue templates: `bug_report.yml`, `skill_behaviour.yml` (skill-dropdown + kind-of-issue), `new_skill.yml` (with the four skill-authoring criteria as required checkboxes), `docs_issue.yml`; plus `config.yml` disabling blank issues and pointing to docs + GitHub Discussions.
- **`.github/PULL_REQUEST_TEMPLATE.md`** — type-of-change checkbox, verification commands matching `CONTRIBUTING.md`, language-convention + SOFT-GATE-preservation checklist, CHANGELOG and migration-note reminders.
- **`.github/workflows/lint.yml`** — CI on every push to `main` and on every PR. 13 steps: plugin + marketplace manifests valid JSON; plugin and marketplace versions match; schema valid + mirror in sync; `python scripts/lint-wiki.py` exits 0 on `examples/example-project/`; every `agents/*.md` `implements:` references an existing skill; every `skills/*/SKILL.md` has valid YAML frontmatter with `name` + `description`; every `.github/ISSUE_TEMPLATE/*.yml` valid YAML; every internal Markdown link in `docs/*.md` resolves on disk.
- **README Lint status badge** (`actions/workflows/lint.yml/badge.svg`).
- **15 GitHub repository topics** for discoverability: `claude-code`, `claude-plugin`, `opencode`, `mcp`, `research`, `academic-writing`, `literature-review`, `peer-review`, `digital-humanities`, `biblical-archaeology`, `theology`, `ancient-history`, `hermeneutics`, `quarto`, `wiki`.

### Fixed

- **`.claude-plugin/marketplace.json`** — `claude plugin validate` (v2.1.132) rejected two fields. Removed root `displayName` (unrecognized). Changed `"source": "."` to `"source": "./"` (validator requires the explicit relative-path form).
- **`.claude-plugin/plugin.json`** — removed `displayName` and `bugs` (both unrecognized by the validator on 2.1.132). Bug reporting still discoverable via the `repository` URL.
- End-to-end install flow verified: `claude plugin marketplace add ./` → `claude plugin install research-superpowers@leiverkus-research` loads at v0.3.0 cleanly.

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
