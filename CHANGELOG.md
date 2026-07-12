# Changelog

All notable changes to `research-superpowers` are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.18.0] — 2026-07-12

### Added

- **`GRAPH_REPORT.md` — a deterministic prose summary of the knowledge graph.** `scripts/wiki-to-graph.py` now writes a fourth artefact alongside `graph.json` / `graph.graphml` / `graph.html`: a human-readable Markdown report with an overview (page/link/community counts, node types, inference-rate, dangling-link warning), the god nodes as a degree-ranked table, the bridges, the labelled communities, an **Asserted relations** section grouping the typed `relations:` edges by type (with `(inferred)` / `(ambiguous)` markers and each edge's `because` rationale), and a **Suggested questions** section whose prompts are generated from the structure and name real pages (the most-central hub, each bridge, each contradiction, plus a nudge when the inference-rate is high or links dangle). It is the static, git-diffable sibling of `graph.html` for a no-browser read — and, in keeping with the plugin's grounding discipline, it invents nothing: every line traces back to `graph.json`, every page is emitted as a `[[wikilink]]`, and it carries **no timestamp** so an unchanged wiki reproduces the file byte-for-byte (clean diffs, no churn). Available three ways: written automatically on the default build, printed to stdout via the new `report` sub-command (`python scripts/wiki-to-graph.py report`), and exposed as the `graph_report` MCP tool. Convergent with the report step in [Graphify](https://github.com/Graphify-Labs/graphify), adapted to the wiki's grounded, deterministic model.
- **Deterministic, LLM-free community labels.** `communities` were numbered (`community 3 (7)`); each now carries a `label` = the title of its most-connected member (its local hub, tie-broken by slug, source titles trimmed to their "Author Year" head). The label flows into `graph.json`, the cluster boxes in `graph.html`, the `communities` CLI output, `GRAPH_REPORT.md`, and the `graph_communities` MCP tool — turning anonymous cluster numbers into a readable at-a-glance sense of each theme, without an LLM call. Additive and schema-safe (existing community fields unchanged); the partition stays deterministic across runs.

### Fixed

- **`communities` sub-command help text** said "label propagation"; the implementation is greedy modularity (Clauset–Newman–Moore) — corrected in the CLI help and the module docstring.

## [0.17.0] — 2026-07-03

### Added

- **Single-page review findings as a first-class channel: `review_flags`.** Content-review findings about *one page's own content* (an overstatement, a weakly-supported or stale claim, a missing citation, an open question) now have a dedicated, structured home in that page's frontmatter — a **third axis**, deliberately kept apart from the two that already existed. `status` stays human-owned maturity (`draft → review → stable`, agents never self-promote); `relations: contradicts` records a conflict *between two* pages; `review_flags` records a concern about *this* page. This makes the case that matters representable: a `status: stable` page that a newer source now undercuts keeps its blessing **and** carries an open flag, instead of a review clobbering the user's `stable` decision. Each flag has `kind` (`overstatement | weak-support | stale | missing-citation | open-question`), `state` (`open | resolved`), `raised_by`, `detected`, an optional `detail`, and an optional `resolved` date. Schema-optional; pages without it stay valid (`schema/knowledge-frontmatter.schema.json`, mirrored into template + example; conformance cases added in `tests/test_schema_conformance.py`, stdlib-subset ⇄ jsonschema parity green).
  - **`semantic-wiki-review` now records findings on the pages**, not only in the dated `_meta/` report. The audit stays non-destructive to *content* — it writes `review_flags` (and `relations: contradicts` for page↔page conflicts) as frontmatter metadata, never touches prose, and never changes `status`. The dated report remains the human-readable digest and the sole home of the report-only categories (missing cross-references, suspect/aggregator citations). Findings are resolved in place via `state: resolved`, not by deletion.
  - **`drafting-manuscript` gates on open flags (SOFT-GATE #5).** It will not draft from a synthesis/source page carrying a `state: open` flag without a logged override in `gate-overrides.log` — so a known content concern cannot be silently baked into the manuscript. Preference is to resolve first, then draft.
  - **`wiki-lint` surfaces open flags** in a new `=== Review flags ===` section (script + Python-free fallback). Advisory by design: open flags are reported and gate drafting, but do **not** fail the lint exit code (a wiki with known, open findings is not malformed); a *malformed* flag still fails via schema validation. The example project's chronology-debate synthesis demonstrates one honest open `weak-support` flag (it leans on two stub sources and an inferred contradiction).
- **Acquisition gate inside `executing-research-plan`.** A plan run now guarantees every ingest task's original PDF is on disk *before* the first `source-ingester` is dispatched, instead of letting each ingest hard-stop one source at a time. The gate scans `input/bibliography/`, runs `acquire-sources` (dispatching the `source-acquirer` subagent for ≥ ~8 missing items) on the A+B set, and — when originals remain missing — enters an interactive resume loop: it surfaces the `acquisition-todo.md` worklist, marks the dependent ingest todos `blocked`, pauses, and on resume reconciles newly-added PDFs, offering to search open-access **alternatives** (a different OA source on the same topic, via `literature-review`) or continue with the acquired subset. Non-blocked downstream work (analysis on existing data) is not held up. Reflected in the process-flow diagram, routing table, red flags, and `using-research-powers`.
- **Weighted source table as the head of `literaturguide.md`.** `literature-review` now opens the guide with a required table (`Grade | Autor Jahr | Kurztitel | OA/Zugang | DOI/Link`) before the nine prose sections. This is the canonical weighting `acquire-sources` filters on (by `Grade`, default A+B) to build its download worklist — closing the hand-off between search and acquisition.

### Changed

- **Canonical, flat PDF naming: `autor-jahr-kurztitel.pdf`.** All source PDFs live directly in `input/bibliography/` — flat, no per-source subfolders — under one lowercase-ASCII, hyphen-separated scheme (`autor` = first author's surname with umlaut/ß folding and particles removed; `jahr` = four-digit year + disambiguation letter; `kurztitel` = 1–3 significant title words). This single flat folder is the source of truth `acquire-sources` reconciles against and `ingest-source` reads from; the wiki slug / bibkey is the `autor-jahr` prefix. `acquire-sources` writes downloads straight to this name; manual downloads are renamed to it before ingest. Applied across `acquire-sources`, `ingest-source`, the template `CLAUDE.md` / `README.md` / `input/bibliography/README.md`, `docs/tutorial.md`, and `docs/installation-cowork.md`; the example plans now carry an explicit *Acquire source PDFs* task before ingest.
- **`writing-research-plan` decomposes with an explicit acquisition step.** Plans now enumerate data sources with a status (acquire pending / on disk / already in wiki) and insert an *Acquire-sources* task before ingest tasks, so the Acquire → Ingest → Analysis → Synthesis → Draft chain has no gaps.
- **Template software directory renamed `output/app/` → `output/code/`** (with matching `.gitignore` paths and the tree in `CLAUDE.md` / `README.md`), aligning the folder name with how the skills refer to it.
- **`grant-finder`: reference path made relative** (`research-skills/dao-grant-finder/`), removing a hard-coded absolute machine path from the skill.
- **Manuscript drafting now writes with depth instead of reflowing bullets.** Drafts built straight from the deliberately terse wiki came out dense and compressed — one flat sentence per wiki bullet, no examples, no explanation. `drafting-manuscript` reframes the "wiki is the single source of truth" rule so it governs *what is claimed*, while treating the wiki as a **pointer to the depth, not the depth itself**: when a page is too thin to develop a point, the drafter reaches back to the source — the source page's `### Direct quotes` / `### Examples & illustrations`, or the original PDF in `input/bibliography/` at the cited page anchors (on disk thanks to `acquire-sources`) — and cites what it uses. A new *Writing with depth* section distinguishes grounded elaboration (from the source, cited — encouraged) from expository framing (uncited) and new-claims-from-memory (still forbidden), gives an assertion → grounding → example → significance paragraph pattern, and adds a reach-back checklist step, process-flow branch, red flags, and key principles. The `drafter` subagent contract now receives the source PDF paths and reports which it reached into.
  - **`ingest-source` captures the raw material for that depth.** A new `### Examples & illustrations (for later drafting)` subsection in each focus block records the concrete cases a source uses (artefact, site, dataset, passage) with page anchors, and the `### Direct quotes` guidance now prefers passages that carry an explanation or example. A claim-only page produces dense prose downstream.
  - **Per-project house style.** The template `CLAUDE.md` gains a *Manuscript style (drafting depth)* block — tunable per project (density, examples, register, target length) — which `drafting-manuscript` reads before drafting; the Draft workflow references it.
  - **`writing-research-plan`** now directs Draft tasks to carry a generous word count as a floor for development, since too-tight targets are the main driver of compressed prose.

## [0.16.0] — 2026-06-23

### Added

- **New acquisition phase between search and ingest: `acquire-sources`.** A new skill (with an optional `source-acquirer` subagent) sits between `literature-review` and `ingest-source`. It auto-downloads the Open-Access PDFs for the A+B graded sources into `input/bibliography/` (named `Lastname - Title - Year.pdf`), and for everything paywalled or bot-blocked it writes `input/bibliography/acquisition-todo.md` — a manual-download worklist with DOI/landing links and the exact target filename, so the user can fetch originals via university VPN. Every download is validated (HTTP 200 + `application/pdf` content-type + `%PDF-` magic bytes + size + not an HTML login/Cloudflare page), so a saved "Access Denied" page is never mistaken for a source. Re-running reconciles newly-arrived manual downloads (idempotent); a date-stamped `acquisition-log-*.json` records every resolution. Wired into the phase sequence (`hooks/session-context.md`, `using-research-powers`, README, tutorial, phase-flow).
- **`ingest-source` hard-stops on a missing original.** Previously, when the original PDF was not on disk, the agent improvised — searching for alternatives and silently falling back to a preprint, prior version, or book review (undocumented, and corrupting provenance). Ingest now expects the acquired original in `input/bibliography/` and **hard-stops** if it is missing, pointing the user to `acquisition-todo.md`. A substitute is ingested only with explicit user consent, recorded as provenance: a new optional `based_on` frontmatter field (`original` | `review` | `preprint` | `prior-version`), a `> [!warning] Provenance` callout, and a marked log line.

- **Ingest now writes typed, confidence-tagged graph relations.** `ingest-source` (and the `source-ingester` subagent) build the *typed* graph layer at ingest time: every stance-bearing connection (confirms / contradicts / builds-on / cites) is mirrored from the prose `## Connections` list into a structured `relations:` frontmatter entry — `type` from a controlled vocabulary, `confidence` (`extracted` only with a quote + page, else `inferred` / `ambiguous`), and a one-line `because` rationale. Previously the graph saw only untyped `wikilink` edges and the typed layer had to be added by hand. The block stays schema-optional; a new SOFT-GATE item checks that stance connections have a matching relation. Re-ingest unions the `relations:` block (dedupe by `(target, type)`, keep higher confidence). The example project's three source pages now demonstrate it (lint-green, 6 typed edges).

### Changed

- **Semitic-transcription fonts for PDF output.** The publication templates (`article`, `book`, `presentation`) switched their PDF font stack from Linux Libertine to a free, OFL-licensed set tuned for scholarly transcription of Semitic languages: `mainfont` → **Gentium Plus** (Latin transliteration incl. ʾ/ʿ + polytonic Greek), `sansfont` → **Noto Sans** (headings with transliterated terms), `monofont` → **Fira Code**; native Hebrew (RTL) via **Ezra SIL** through a babel block in the PDF preambles. The PDF build uses XeLaTeX or LuaLaTeX (Quarto picks one). Install + usage notes in `output/README.md` and the root README; the previously-untracked `_preamble.tex` sources are now versioned (a `.gitignore` rule had swallowed them).
- **Publication layout flattened.** `output/publication/article` and `output/publication/book` moved up one level to `output/article` and `output/book`, and the now-empty `output/publication/` wrapper was removed. `article`, `book` and `presentation` are now siblings directly under `output/`. Every path reference was updated to match — template `CLAUDE.md` / `README.md`, `.gitlab-ci.yml`, `.vscode/tasks.json`, `.gitignore`, the skills (`drafting-manuscript`, `executing-research-plan`, `requesting-peer-review`, `finishing-a-research-project`, `writing-research-plan`, `using-research-powers`), `docs/`, `hooks/session-context.md`, the `knowledge-frontmatter` schema, the OpenCode plugin mirror, the example project, and CI (`.github/workflows/lint.yml`). The in-file `bibliography` / `csl` paths in the article and book templates were corrected from `../../bibtex` to `../bibtex` to match the new depth (now consistent with `presentation`).

### Fixed

- **`make all` no longer deletes the earlier formats.** The article, book and presentation Makefiles built each format with a separate `quarto render` call, but Quarto cleans the output directory on every render — so `make all` left only the last format and silently removed the others. The `all` target is now a single `quarto render … --to all` pass that emits every declared format side by side.
- **`make all` made robust for the presentation; `make clean` no longer deletes `_preamble.tex`.** The presentation declares two PDF formats (Beamer slides + A4 handout) that collided on the shared `talk.tex` intermediate under `--to all` and on `talk.pdf` — `make all` failed and left a single half-rendered file. It now renders each format in place (no shared output-dir clean) and collects the artefacts, with distinct `output-file` names (`talk-slides.pdf` / `talk-handout.pdf`). Separately, the `clean` targets ran `rm -f *.tex`, which deleted the hand-authored `_preamble.tex`; they now remove only generated `.tex` and always preserve `_preamble.tex`. Verified by rendering all three formats to PDF (transliteration, polytonic Greek, native Hebrew all glyph-correct).

## [0.15.1] — 2026-06-08

Fixes a fake-green in the v0.15.0 install smoke: the marketplace add / install / list steps were tolerant (`|| echo`), so in the real CI run the CLI and `validate` passed but `marketplace add .` and the install actually **failed** and `list` reported no plugins — yet the job stayed green. This made the "tier 2 done / all P1–P7 complete" claim unsubstantiated.

### Fixed

- **Install smoke is now fail-closed** (`.github/workflows/install-smoke.yml`): once the CLI is available the whole sequence must succeed with no suppressed errors — `claude plugin validate ./` → `claude plugin marketplace add ./ --scope user` → `claude plugin install research-superpowers@leiverkus-research --scope user` → `claude plugin list --json`, then a check that the JSON actually contains `research-superpowers`. The path is `./` (the CLI rejects a bare `.` for `marketplace add`), and an isolated `CLAUDE_CONFIG_DIR` keeps the run self-contained. Only *obtaining* the CLI stays best-effort (honest skip with a notice if it can't be installed). Verified locally end-to-end (plugin installs, `list --json` reports `research-superpowers@leiverkus-research` v0.15.0).

## [0.15.0] — 2026-06-08

Roadmap P6 tier 2 — a best-effort, honest plugin-install smoke test. With this, all roadmap items P1–P7 are complete.

### Added

- **Plugin install smoke (roadmap P6, tier 2)**: `.github/workflows/install-smoke.yml` installs the real Claude CLI and runs `claude plugin validate .` plus a local marketplace add/install/list. Honest by design — if the CLI can't be obtained in the runner the job **skips with a notice** rather than faking success; if the CLI is available, `validate` must pass. It is intentionally **not** part of the release gate (`release.yml`), since tier 2 is environment-dependent and must never block a release.

### Docs

- `docs/ROADMAP.md` marks P6 tier 2 done; all P1–P7 items are now complete. `CONTRIBUTING.md` notes the best-effort install smoke.

## [0.14.0] — 2026-06-08

Roadmap P7: the test suite now runs on Linux, macOS and Windows, with a real hook-dispatch test per OS. This is the last planned maturity item; only the best-effort P6 tier 2 (a real `claude plugin install` in CI) remains open.

### Added

- **Cross-platform CI matrix** (roadmap P7): the unit + integration suite runs as a `tests` job on `ubuntu-24.04`, `macos-latest` and `windows-latest` (the heavy Quarto render stays Linux-only). This proves the Python tooling, the scaffold E2E, the MCP server and path handling work on all three OSes, not just Linux.
- **Hook-dispatch test** (`tests/test_hook_dispatch.py`): exercises the real `hooks/run-hook.cmd session-start` entry point per OS — the polyglot wrapper on POSIX, the cmd.exe → Git-bash path on Windows — and asserts the emitted `additionalContext` is valid JSON carrying the skill index.
- **`.gitattributes`**: forces LF on the shell hooks (`session-start`, `run-hook.cmd`, `*.sh`) so a Windows checkout (`core.autocrlf=true`) can't rewrite them to CRLF and break the bash shebang; marks the vendored cytoscape bundle as binary.

### Fixed

- **Windows UTF-8 output bug** (surfaced by the new matrix): `wiki-to-graph.py` printed JSON containing arrow glyphs (`←`/`→`) to stdout, which crashed with `UnicodeEncodeError` on a Windows cp1252 console. All three scripts now force UTF-8 on stdout/stderr (`sys.stdout.reconfigure`), the MCP server decodes the CLI subprocess as UTF-8, and `scripts/release.py` does the same for `notes`. A real bug for Windows users, not just CI.
- **`release.py bump` is now atomic**: it computes and validates every change (manifests, README badge, CHANGELOG) in memory first and only writes once all succeed — a missing README badge can no longer leave a half-bumped repo. Tested by asserting the worktree is unchanged after a failed bump.
- **Runtime validator now enforces nested `relations[]` rules**: `lint-wiki.py` previously checked only that each `relations` item was an object, so `type: 42`, `because: 42`, a bad `confidence` enum, a missing required key, or an unknown key slipped through while JSON Schema rejected them. The validator is now recursive (object `required` / `properties` / `additionalProperties`, array items), and `tests/test_schema_conformance.py` pins six new nested cases in agreement with `jsonschema`.

### Security

- **Least-privilege release workflow**: `release.yml` now defaults to `contents: read`; only the `release` job that publishes gets `contents: write` (the render/test verify jobs run read-only).

### Changed

- The single-OS `lint` job no longer runs the unit tests itself; they now run in the cross-OS `tests` job (which includes Linux), so the release gate (`release.yml` → `workflow_call`) is verified on all three platforms before a tag can publish.
- The portability matrix pins Python to the minor `3.12` (exact patches aren't built for every OS/arch); the reproducible anchor (the ubuntu `lint` + `release` jobs) keeps the exact `3.12.13` pin.

## [0.13.0] — 2026-06-08

Roadmap P5 + P6 (tier 1): a `jsonschema` golden cross-check of the hand-rolled validator, and an end-to-end test of the shipped template. No runtime dependency added — scaffolded projects still run on stdlib + PyYAML only.

### Added

- **Schema conformance cross-check** (roadmap P5, hybrid): the stdlib validator in `lint-wiki.py` stays the runtime, and `jsonschema` (pinned in the new `requirements-dev.txt`, CI/dev-only) becomes the authoritative golden check. `tests/test_schema_conformance.py` pins the hand-rolled validator and `jsonschema` in agreement on every rule the subset implements (a valid page + one fixture per single-rule violation: required, enum, date, pattern, type, conditional `bibkey`, array-item type) and validates **all shipped example/template wiki pages** with the real engine. The tests skip cleanly when `jsonschema` is absent. If the schema outgrows the stdlib subset, the cross-check fails — the signal to extend the subset or revisit a runtime dependency.
- **Scaffold end-to-end test** (roadmap P6, tier 1): `tests/test_scaffold_e2e.py` materialises a project from the shipped `templates/research-project-template/`, drops in a small connected wiki, and runs the real user path against the *copied* scripts — lint (clean) → graph build (`graph.json`) → a `neighbors` query → the MCP handshake + `graph_stats`. Proves the shipped template (not just the in-repo example) is self-consistent. (Tier 2, a real `claude plugin install` in CI, remains open.)
- **`requirements-dev.txt`** — pinned dev/CI toolchain (PyYAML 6.0.3 + jsonschema 4.25.1); CI installs from it. Documented in `CONTRIBUTING.md`.

## [0.12.0] — 2026-06-08

Roadmap P3 + P4: an automated, self-checking release process and a much broader negative/integration test suite. No user-visible behaviour change.

### Added

- **Automated, fail-closed release process** (roadmap P3): `scripts/release.py` (stdlib) is the single source of truth for the manifest versions, the git tag, and the matching CHANGELOG section — `check` (verify all three agree), `notes` (extract a section), `bump` (bump manifests + README badge + CHANGELOG skeleton; the badge replacement now fails loudly instead of silently no-op'ing). `.github/workflows/release.yml` fires on a `v*` tag and, **before** creating the release, (1) runs the **entire CI suite** on the tagged commit via `workflow_call` and (2) asserts the tagged commit is **contained in `origin/main`** — so an untested or off-main tag cannot publish a release. It then extracts the CHANGELOG section and creates the GitHub Release — no manual `gh release create`. The lint job also runs `check` on every PR, so a version bump without a CHANGELOG entry fails CI. `CONTRIBUTING.md` documents the flow.
- **Negative & integration tests** (roadmap P4): `tests/test_wiki_robustness.py` adds 21 adversarial cases — empty / single-page / all-orphan wikis, malformed wikilinks (empty brackets, aliases, headings, dangling, self-links, duplicate-weight), corrupt frontmatter (unterminated, non-dict root, tabs, BOM), MCP error paths (unknown tool, missing argument, malformed JSON-RPC frame, unknown method, non-existent node, valid call), a **1000-page** scale + determinism check (with a wall-clock budget), and subdir/stem path handling. `tests/test_release.py` covers the release helper end-to-end in a throwaway repo: full bump, idempotency, missing-badge failure, bad-semver rejection, and every `check` mismatch case.

### Changed

- The version bump for this release was produced by `scripts/release.py bump`; the GitHub Release itself is created by `release.yml` when the `v0.12.0` tag is pushed (the dogfooding of P3 is completed by that tag push, not by this commit).

## [0.11.1] — 2026-06-08

Completes the reproducible-CI work from v0.11.0 (roadmap P1) and marks the done items in the roadmap.

### Changed

- **Toolchain fully pinned** (roadmap P1, finish): Python is pinned to `3.12.13` (with `check-latest: false`) instead of the moving `3.12`, PyYAML to `6.0.3` via the Python-bundled pip (dropping the moving `pip install --upgrade pip pyyaml`), and both CI runners to `ubuntu-24.04` instead of `ubuntu-latest`. With the Action SHAs and Quarto `1.9.38` already pinned in v0.11.0, the build toolchain is now deterministic apart from the runner base image (container-by-digest noted as a possible future step).

### Docs

- **Roadmap status** (roadmap P3-doc): `docs/ROADMAP.md` now marks P1 and P2 as ✅ done with a status note, instead of still describing them as open gaps.

## [0.11.0] — 2026-06-08

First maturity pass from the post-v0.10.0 roadmap (`docs/ROADMAP.md`): pure hardening of the build pipeline, no user-visible behaviour change.

### Changed

- **Reproducible CI** (roadmap P1): GitHub Actions are now pinned to immutable commit SHAs (with a human-readable version comment) instead of moving major tags, and Quarto is pinned to an explicit version (`1.9.38`) instead of "latest". This also upgrades `actions/checkout` and `actions/setup-python` to their Node 24 majors, resolving the Node 20 deprecation that would have broken the build after 2026-06-16.

### Added

- **Script mirror-drift guard** (roadmap P2): CI now fails if the wiki scripts (`lint-wiki.py`, `wiki-to-graph.py`, `graph_mcp.py`, `vendor/cytoscape.min.js`) drift between the template and the example — previously only the JSON schema was guarded, and the example schema copy is now checked too. `CONTRIBUTING.md` documents the canonical source (the template) and the one-shot re-sync command.

## [0.10.0] — 2026-06-08

Engineering-robustness pass addressing an external review — the scripts and template were less robust than the concept.

### Fixed

- **Template build config was broken in scaffolded projects** (P1): `.gitlab-ci.yml` and the VS Code tasks referenced `artikel.qmd`/`vortrag.qmd` instead of the actual `article.qmd`/`talk.qmd`, and still tried to Quarto-build the now plain-Markdown wiki. A new CI scaffold-config smoke test guards against recurrence.
- **Invalid dates crashed the tools** (P1): `2026-99-99` raised `ValueError` in PyYAML; `lint-wiki.py` and `wiki-to-graph.py` now parse with a no-timestamp loader (dates stay strings) and catch it.
- **Schema lint was incomplete** (P1): `validate_frontmatter` now checks types, ISO date validity, patterns (wikidata/iDAI/GND IDs) and array item types — not just required fields and enums.
- **Duplicate page slugs silently merged** (P1): both the linter and the graph builder now fail loudly on colliding slugs.
- **Methodology contracts contradicted the hermeneutic default** (P1): `executing-research-plan` and `requesting-peer-review` no longer demand a pre-registered hypothesis for hermeneutic projects (`status: ready` suffices; falsification is reframed as "what would refute the thesis").
- **The gate "override-rate" was not a rate** (P2): it read 100% once ≥10 entries existed; now reports an honest count + recent-window frequency.
- **README / session-index drift** (P2): version badge (was 0.3.0), skill count (was 12), and dead migration links fixed; `hooks/session-context.md` now lists every skill.
- **Article template did not render** (P1): its `bibliography`/`csl` paths were one level too shallow (`../bibtex/` → `../../bibtex/`).
- **Book template did not render** (P1): Quarto requires the homepage at the project root, so `frontmatter/index.qmd` is now `index.qmd`.
- **Remaining doc drift** (P2): `docs/README.md` and `docs/installation.md` said "12 skills" (now 14, and the docs-in-sync check covers `docs/` too); `--strict` removed from `CONTRIBUTING.md` (the installed Claude CLI rejects it).
- **Date validation too lax** (P2): `date.fromisoformat()` also accepts `20260415` and week dates like `2026-W15-3`; a strict `YYYY-MM-DD` check is now applied first.
- **Override recency counted future dates** (P3): a 2099 entry no longer counts as "last 30 days".

### Added

- **CI drift guards & tests**: README version badge must equal `plugin.json`, skill-count mentions across README + `docs/` must equal the actual count, README links must resolve, `session-context.md` must mention every skill — plus stdlib `unittest` tests (`tests/`) for invalid frontmatter, strict dates, duplicate slugs, the override count + future-date guard, bad-YAML robustness, and deterministic communities.
- **Real publication render smoke test in CI**: a dedicated job runs `quarto render` of the article, book and presentation templates to HTML — catching broken bibliography paths / book layout that mere file-existence checks miss.
- **OpenCode integration is now versioned** (`opencode/`): the native OpenCode plugin (`plugin/research-superpowers.ts`) that replicates the SessionStart skill-index injection via `experimental.chat.system.transform` — GWDG-safe, scoped to research projects — plus its setup README are checked in instead of living untracked. Its `EMBEDDED_INDEX` fallback was re-synced to the current `hooks/session-context.md`, and a new CI step (in the docs-in-sync job) fails the build if the two ever drift again.

## [0.9.0] — 2026-06-08

Adds an optional per-relation rationale (`because`) — the lightweight first step toward rationale nodes.

### Added

- **Optional `because` rationale on relations** — a one-line "why A relates to B" attached to each `relations` entry (the lightweight first step toward rationale nodes). Additive and optional; pages without it stay valid.
  - Recorded per edge in `graph.json` / `graph.graphml`; shown in the `graph.html` info panel and in the `relations` query output (CLI + `graph_relations` MCP tool).
  - `lint-wiki.py` accepts `because` and reports the share of relations that carry a rationale (alongside the inference-rate) — the natural place to ground an `inferred` edge when hardening it to `extracted`.
  - Documented in `docs/frontmatter-schema.md` and CLAUDE.md; CI exercises it on the example project.

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

Focus-driven `ingest-source`. Source pages now capture **what this project takes from a source under a specific focus**, not a generic summary. Re-ingest of the same source with a different focus appends a new `## Focus:` block rather than overwriting. Aligns the wiki with how researchers actually read: question-driven, not RAG-style full-text indexing. Existing source pages keep working — lint accepts both old and new structures.

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

Cowork-friendly install path. The plugin now works fully click-only — no terminal, no Python, no Git required for the core workflow. Existing CLI users see no change to their flow. Purely additive; no breaking changes.

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

First public release. Combines an optional MCP integration layer, the removal of the legacy OpenCode-commands shims (OpenCode now reads skills natively from `.claude/skills/`), full English internationalisation of all skill prose and templates, and a complete user-facing manual (README, Quickstart, Tutorial, Concepts). **Additive** for MCP and i18n; the removal of `opencode-commands/` is technically breaking for anyone who relied on the slash shortcuts, but they were never published. See [`docs/recommended-mcps.md`](docs/recommended-mcps.md).

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

Architecture consolidation. **Breaking** — bump major-zero version because public skill/command surface changes.

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
