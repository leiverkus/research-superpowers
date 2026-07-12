# Roadmap — maturity & long-term maintainability

As of **v0.10.0** the plugin is *functionally* complete and robust: two
external engineering reviews left no open P1/P2/P3 findings (score 9/10). The
remaining ~0.5 points toward a practical 10/10 are **not bug fixes** — they are
maturity, portability, and release-automation work. This document captures that
work as a prioritised backlog so it isn't lost.

Each item lists: the gap, the proposed approach, a rough effort, whether it
keeps the project **dependency-free** (a standing design principle — scaffolded
projects must run `lint-wiki.py` / `wiki-to-graph.py` with stdlib + PyYAML
only), and concrete acceptance criteria.

Priority is **value ÷ effort**: cheap guards that prevent real regressions
come first; the platform matrix (largest) comes last.

---

## P1 — Reproducible CI (pin versions)  ·  small  ·  dependency-free  ·  ✅ done (v0.11.0 + v0.11.1)

> **Status: done.** v0.11.0 pinned all Actions to commit SHAs and Quarto to
> `1.9.38`. v0.11.1 closed the rest: Python pinned to `3.12.13`, PyYAML to
> `6.0.3` (no moving `pip` upgrade), runners pinned to `ubuntu-24.04` instead
> of `ubuntu-latest`. (Container-by-digest remains a possible future step but
> is not currently warranted.)

**Gap.** `.github/workflows/lint.yml` pins GitHub Actions and Quarto to moving
major tags (`actions/checkout@v4`, `actions/setup-python@v5`,
`quarto-dev/quarto-actions/setup@v2`). A silent upstream change can break or —
worse — *change* a green build without a code change. The render job already
floats whatever Quarto `setup@v2` currently resolves to.

**Approach.**
- Pin actions to a full commit SHA (with the human-readable tag in a trailing
  comment), e.g. `actions/checkout@<sha> # v4.2.2`.
- Pin Quarto explicitly via the action's `version:` input (e.g. `1.6.39`)
  instead of "latest".
- Pin the Python patch line already in use (`3.12`) — fine as-is, optionally
  freeze to `3.12.x`.
- Consider Dependabot (`.github/dependabot.yml`) to bump the pins via PR so they
  stay current *deliberately*, not silently.

**Acceptance.** Re-running an old commit's CI produces the same toolchain
versions. No `uses:` line references a bare major tag.

---

## P2 — Script mirror-drift guard  ·  small  ·  dependency-free  ·  ✅ done (v0.11.0)

> **Status: done.** v0.11.0 added CI `diff -q` of the wiki scripts and the
> vendored cytoscape bundle across template ↔ example (and the example schema
> copy); `CONTRIBUTING.md` documents the canonical source + re-sync command.
> The "stretch" single-source generator was deliberately not done — verbatim
> mirrors guarded by CI are sufficient.

**Gap.** `lint-wiki.py`, `wiki-to-graph.py` and `graph_mcp.py` exist in **two**
copies (`templates/research-project-template/scripts/` and
`examples/example-project/scripts/`) and must stay byte-identical. Only the
**schema** mirror is currently guarded by CI (`diff -q`); the **scripts** are
not — they can drift unnoticed. (The itinera project carries a third copy that
lives outside this repo and is synced by hand.)

**Approach (pragmatic, chosen over a generator).**
- Add a CI step `diff -q` for each script across template ↔ example (mirror of
  the existing schema check). This is the smallest change that closes the gap.
- Document the canonical source (template) and the one-line sync command in
  `CONTRIBUTING.md`.

**Stretch (only if drift keeps happening).** Replace the mirrors with a single
canonical `scripts/` + a `make sync` (or a tiny `scripts/sync-mirrors.py`) that
copies into template/example, with CI asserting the copy is current. A real
code-generator is *not* warranted for verbatim copies.

**Acceptance.** Editing one script copy without the other fails CI with a clear
message pointing at the canonical source.

---

## P3 — Automated release process  ·  medium  ·  dependency-free  ·  ✅ done (v0.12.0)

> **Status: done.** `scripts/release.py` (stdlib) is the single source of truth
> for the manifest versions, the tag, and the matching CHANGELOG section
> (`check` / `notes` / `bump`). `.github/workflows/release.yml` fires on a `v*`
> tag and is **fail-closed**: before cutting the release it runs the entire CI
> suite on the tagged commit (`workflow_call`) and asserts the commit is on
> `origin/main`, then extracts the CHANGELOG section and creates the GitHub
> Release — no manual `gh release create`, no untested/off-main publish. The
> lint job also runs `check` on every PR. Covered end-to-end by
> `tests/test_release.py` (full bump, idempotency, missing-badge, every
> mismatch case).

**Gap.** Releases are manual today: bump `plugin.json` + `marketplace.json`,
edit `CHANGELOG.md`, `git tag -a`, `gh release create`. Each step is a place to
forget something (the version-match CI check catches *some* of it after the
fact).

**Approach.** A tag-triggered `release.yml` workflow:
- On `push` of a `v*` tag: assert `plugin.json` == `marketplace.json` == tag
  (reuse the existing check), assert `CHANGELOG.md` has a section for that
  version, then create the GitHub Release with the extracted changelog section
  as the body.
- Optionally attach a packaged plugin artefact (zip of the plugin tree) to the
  release.
- A `prepare-release` helper (script or `workflow_dispatch`) that bumps both
  manifests and opens the changelog section, so the human only writes notes.

**Acceptance.** Pushing a correctly-prepared tag produces a Release with the
right notes and a fail-closed check on any version/changelog mismatch — no
manual `gh release create`.

---

## P4 — More negative & integration tests  ·  medium  ·  dependency-free  ·  ✅ done (v0.12.0)

> **Status: done.** `tests/test_wiki_robustness.py` adds 21 adversarial cases:
> empty / single-page / all-orphan wikis, malformed wikilinks (empty brackets,
> aliases, headings, dangling, self-links, weight on duplicates), corrupt
> frontmatter (unterminated, non-dict root, tabs, BOM), MCP error paths
> (unknown tool, missing arg, malformed frame, unknown method, non-existent
> node, plus a valid call), a **1000-page** scale + determinism check (with a
> wall-clock budget; ≈0.5s locally), and subdir/stem path handling. The release
> helper is covered end-to-end by `tests/test_release.py`. (Windows path
> separators are deferred to P7; a 2000-page run is possible but 1000 already
> exercises the same code paths well under budget.)

**Gap.** The stdlib `unittest` suite covers the review's robustness cases but is
thin on adversarial inputs. The reviewer named: MCP error paths, corrupt graph
data, unusual wikilinks, empty wikis, Windows-style paths, and large wikis.

**Approach (extend `tests/`).**
- **Empty / degenerate wiki**: zero pages, one page no links, all-orphan wiki —
  graph build and every query must return cleanly, not crash.
- **Malformed wikilinks**: `[[ ]]`, `[[a|b]]` aliases, nested brackets, links to
  non-existent slugs, self-links, duplicate links — edges resolved sanely.
- **Corrupt / partial frontmatter**: missing `---` close, tabs, BOM, non-dict
  YAML root, lists where maps expected — parsers degrade, never raise.
- **MCP error paths**: unknown tool name, bad params, malformed JSON-RPC frame,
  query for a non-existent slug → proper JSON-RPC error objects, `isError`.
- **Scale**: a generated ~1–2k-page fixture — build + community detection finish
  within a time budget and stay deterministic.
- **Path handling**: backslash-style and mixed separators in slugs/paths (feeds
  into P6).

**Acceptance.** Each class has at least one test; coverage of the parser and
graph builder error branches is meaningfully higher.

---

## P5 — Schema validation: full Draft-07 coverage  ·  medium  ·  CI/dev dependency  ·  ✅ done (v0.13.0)

> **Status: done (hybrid, as recommended).** The stdlib validator stays the
> runtime (scaffolded projects need no `pip install`). `jsonschema` (pinned in
> `requirements-dev.txt`) is a CI/dev golden cross-check:
> `tests/test_schema_conformance.py` pins the hand-rolled validator and
> `jsonschema` in agreement on every rule the subset implements (valid + each
> single-rule violation, **including the nested `relations[]` object rules** —
> type, enum, required and `additionalProperties`) and validates all shipped
> example/template pages with the real engine. The tests skip cleanly when `jsonschema` is absent. If the
> schema ever grows a feature the subset can't express, the cross-check fails —
> the signal to extend the subset or revisit a runtime dependency.

**Gap.** The hand-rolled `validate_frontmatter` implements only the slice of
JSON-Schema Draft-07 the current schema uses (required, enum, type, a few
patterns, ISO dates, array item types). A future schema feature (`oneOf`,
`if/then`, `$ref`, `dependentRequired`, numeric bounds, `format`) would silently
**not** be enforced — the validator would pass frontmatter the schema forbids.

**Recommendation (see decision note below): hybrid.**
- **Keep the stdlib validator as the runtime** in `lint-wiki.py`, so scaffolded
  research projects stay installable with **no `pip install`** — this is the
  whole point of the dependency-free principle and must not regress for end
  users.
- **Add `jsonschema` as a CI/dev-only dependency** and a CI step that validates
  the example wiki (and the `_example-*` templates) against the schema with the
  *real* engine. This becomes the authoritative cross-check: if the hand-rolled
  validator and `jsonschema` ever disagree on a fixture, CI fails — which both
  catches validator bugs *and* tells you when the schema has outgrown the
  stdlib subset.
- Add a small **conformance fixture set** (valid + each-rule-violating pages)
  asserted identically by both validators.

This gives full Draft-07 coverage where correctness is verified (CI) without
forcing the dependency on researchers' machines.

**Acceptance.** `jsonschema` validates all example/template wiki pages in CI;
a conformance suite pins both validators in agreement; `requirements-dev.txt`
(or equivalent) documents the dev dependency; runtime lint still works with
stdlib + PyYAML only.

---

## P6 — End-to-end install & scaffold test  ·  medium  ·  dependency-free  ·  ✅ done (tier 1 v0.13.0, tier 2 v0.15.0)

> **Status: done (both tiers).**
> **Tier 1** — `tests/test_scaffold_e2e.py` materialises a project from the
> shipped `templates/research-project-template/`, drops in a small connected
> wiki, and runs the real user path against the *copied* scripts: lint (clean)
> → graph build (`graph.json` with nodes/edges/communities) → a `neighbors`
> query → the MCP handshake + a `graph_stats` call. Proves the shipped template
> (not just the in-repo example) is self-consistent.
> **Tier 2** — `.github/workflows/install-smoke.yml` installs the real Claude
> CLI and **actually installs this plugin from its own marketplace**: validate →
> `marketplace add ./` → `install research-superpowers@leiverkus-research` →
> `list --json`, then asserts the JSON contains `research-superpowers`.
> **Fail-closed, not fake-green:** only *obtaining* the CLI is best-effort (if it
> can't be installed the job skips with a notice); once the CLI is present the
> whole sequence must succeed with no suppressed errors. It is intentionally
> **not** part of the release gate, since CLI availability is environment-
> dependent and must never block a release.

**Gap.** No test exercises the *user's* path: install the plugin, scaffold a
project, trigger a skill, validate the generated project.

**Approach (two tiers — the second only if feasible).**
1. **Scaffold smoke test (no Claude CLI):** in CI, materialise a project from
   `templates/research-project-template/` into a temp dir, then run
   `lint-wiki.py`, `wiki-to-graph.py` (build + a query), and the MCP smoke
   handshake against it. This proves the *shipped template* is self-consistent,
   not just the in-repo example. Largely reuses existing steps.
2. **Real install test (if the Claude CLI is runnable in CI):** `claude plugin
   install` from the marketplace/tag and assert the plugin loads + skills are
   listed. Treat as best-effort / allowed-to-skip if the CLI isn't available in
   the runner.

**Acceptance.** CI fails if a freshly-scaffolded project doesn't lint clean and
build a graph. Tier 2 runs when the CLI is present.

---

## P7 — Platform matrix (Linux / macOS / Windows)  ·  large  ·  dependency-free  ·  ✅ done (v0.14.0)

> **Status: done.** The unit + integration suite runs as a `tests` matrix job
> on `ubuntu-24.04`, `macos-latest` and `windows-latest` (the heavy Quarto
> render stays Linux-only). `tests/test_hook_dispatch.py` exercises the real
> `run-hook.cmd session-start` entry point per OS — the polyglot wrapper on
> POSIX, the cmd.exe → Git-bash path on Windows — and asserts valid
> session-context JSON. `.gitattributes` forces LF on the shell hooks so a
> Windows checkout can't break the bash shebang. The scaffold E2E + MCP +
> graph tests now also prove the Python tooling and path handling work on all
> three OSes. (Windows symlink behaviour for `.claude/skills` is documented in
> the OpenCode/install docs; the tooling itself uses no symlinks.)

**Gap.** CI runs Linux only. The hooks ship a Windows entry point
(`hooks/run-hook.cmd`) and the project relies on symlinks (`.claude/skills`,
Nextcloud data) and POSIX paths — none of which are exercised on macOS or
Windows.

**Approach.**
- `strategy.matrix.os: [ubuntu-latest, macos-latest, windows-latest]` on the
  lint/test job (the heavy Quarto render job can stay Linux-only).
- Make the test/lint steps OS-agnostic: invoke Python scripts directly (already
  the case), avoid bash-only one-liners on the Windows leg, normalise path
  separators in the tools where slugs/paths are compared.
- Add a focused **hook-dispatch test**: `run-hook.cmd` on Windows and
  `session-start` on POSIX both emit the expected session-context payload.
- Decide and document the **symlink story on Windows** (developer mode / `core.
  symlinks`, or a copy fallback for `.claude/skills`).

**Acceptance.** The lint/test job is green on all three OSes; hook dispatch and
path handling are verified per-OS; Windows symlink behaviour is documented.

---

## Suggested sequencing

A natural order (cheap guards first, biggest last), shippable incrementally:

1. ✅ **v0.11.0 / v0.11.1** — P1 (pin CI) + P2 (script mirror guard). *Done.*
2. ✅ **v0.12.0** — P3 (release automation) + P4 (negative tests). *Done.*
3. ✅ **v0.13.0** — P5 (jsonschema cross-check) + P6 tier 1 (scaffold E2E). *Done.*
4. ✅ **v0.14.0** — P7 (platform matrix). *Done.*
5. ✅ **v0.15.0** — P6 tier 2 (best-effort real `claude plugin install` smoke). *Done.*

**All roadmap items P1–P7 are now complete** (P6 across both tiers). None were
blocking — v0.10.0 was already production-ready; this sequence took the package
from "robust" to "mature". Further hardening (e.g. container-by-digest CI, a
single-source generator for the script mirrors) is noted inline as optional and
not currently warranted.

---

## Decision note — P5 (#4): why hybrid rather than "replace with jsonschema"

Patrick leaned toward introducing `jsonschema`. The recommendation refines that
rather than rejecting it:

- **Adopting `jsonschema` outright as the runtime validator** would force every
  scaffolded research project to `pip install jsonschema` before
  `lint-wiki.py` works — breaking the dependency-free promise that makes the
  template friendly to non-technical researchers (Theology / DH).
- **Keeping only the hand-rolled validator** leaves future schema features
  silently unenforced.
- **Hybrid** (stdlib at runtime, `jsonschema` as the CI/dev golden check + a
  conformance suite) gets full Draft-07 correctness *where it's verified* and
  keeps installs dependency-free *where it matters*. If the runtime ever needs a
  feature the stdlib subset can't express, the CI cross-check is exactly the
  signal to either extend the subset or revisit making `jsonschema` a runtime
  dependency — a decision made on evidence, not pre-emptively.

---

# Feature track — Cross-project graph (global graph)

Distinct from the P1–P7 *maturity* backlog above: this is a **new capability**,
not hardening. `wiki-to-graph.py` maps one project. A researcher running several
`research-project` instances (e.g. Theology / Biblical Archaeology / DH) has the
same real-world entities and sources recurring across projects — "Tel Megiddo",
"Israel Finkelstein", a shared DOI. A *global* graph would surface those
cross-project connections (the same concept developed in two works; two projects
leaning on the same source toward opposite conclusions).

**Why it is hard / lower priority.** The core problem is **identity resolution
across projects**, a data-quality problem more than a code problem. Within a
project identity is the slug (unique, enforced). Across projects slugs both
collide (`tel-megiddo.md` twice) and drift (`entity-tel-megiddo` vs
`tel-megiddo`). It also breaks clean invariants: unique slugs, the per-project
output dir, the CI-Pages publish (no single project's CI can publish a
cross-project artefact), and the single-project MCP.

**The robust join key already exists** in the frontmatter — matched *exactly*,
never by fuzzy title (which would invent false links): `orcid` (living
researchers — the key that actually covers working scientists, where GND /
Wikidata frequently do not), `gnd_id` (persons), `idai_gazetteer_id` (places),
`wikidata_qid` (also used for shared software), and `bibkey` (sources). Concepts
have no authority ID — the known blind spot, reported as such, never guessed;
see *Concept vocabulary* below for the lever that would close it.

**Three relationships, not one path.** Field-testing on a real portfolio (see
*Evidentia field-test* below) showed the original linear `overlap → merge →
serve` picture is only one of three ways projects relate. Pick by one question:

> **Will these wikis become *one* published artefact?**
> - **No — separate works that occasionally overlap** → *federate*: draw
>   `same_as` edges, keep the projects separate (Branch A).
> - **Yes, but they were fragmented by accident** → *consolidate*: merge into
>   one wiki, a one-time migration (Branch B).
> - **Yes, as a synthesis on top of many** (a book / portfolio grant drawing
>   from module wikis) → *portfolio synthesis*: a super-project that references
>   the leaves without merging them (Branch C).

**Honest trigger.** Build the branch you need only once you have the data for it:
≥2 projects with *overlapping, authority-ID-tagged* entities. Step 1 (the shared
foundation) is the cheap way to check that empirically first — and its companion,
the `wiki-lint` authority-coverage report (v0.20.1), keeps the tagging honest (a
real audit found 0 of 135 entities tagged — no tissue to connect until that gap
is worked).

## Shared foundation — `authority-overlap` report  ·  small  ·  dependency-free  ·  ✅ shipped

> **Status: done (v0.20.0; `orcid` join key added v0.21.0), verified end-to-end
> and on a real portfolio.**
> `scripts/wiki-global-graph.py overlap <root> <root> …` reports which
> `orcid` / `gnd_id` / `idai_gazetteer_id` / `wikidata_qid` / `bibkey` occur in
> ≥2 projects — the exact set of `same_as` edges a global graph would draw — and
> states the concept/entity-without-ID blind spot. Deterministic, `--json`,
> stdlib+PyYAML. It is the **detection layer under all three branches** below.
> Tests in `tests/test_global_graph.py`.

**Acceptance (met).** Given N project roots, lists every shared authority id
with the projects and pages it appears in; ids in only one project, or with
differing values, are not reported; missing `knowledge/` dirs are skipped, not
fatal; output is byte-stable across runs.

**Real-scaffold verification.** Beyond the unit tests, the shipped script was
run on two *real* scaffolds, each with a different genuine source ingested
(Toffolo et al. 2014 in one, Fantalkin/Finkelstein/Piasetzky 2011 in the other)
but sharing the same site and scholar, using authority IDs resolved live via
`dao-paper-search` (Tel Megiddo → iDAI.gazetteer `2132671`; Israel Finkelstein →
Wikidata `Q717237`). Both wikis linted clean; the report correctly surfaced the
two shared entity IDs as cross-project `same_as` edges and correctly did **not**
report the two projects' differing `bibkey`s — confirming the entity-level
cross-project link (the "same person/place in two works" case) fires while
distinct sources stay separate. Deterministic across re-runs.

## Branch A — Federate (keep separate, cross-reference)

For peer projects that stay separate. Two steps on top of the shared foundation.

### `merge`  ·  medium  ·  dependency-free
Reuse `wiki-to-graph.py`'s per-project graph, namespace every node by project
(`projA::slug`), and add a `same_as` edge for each overlap-report match. Emit a
combined `graph.json` / `graph.html` outside any single project (a chosen output
dir or a small `~/.research-projects` registry). Keep nodes separate + linked
(not merged) to preserve per-project provenance.
**Acceptance.** A merged `graph.html` where shared entities visibly bridge two
projects' sub-graphs; every `same_as` edge traces back to a shared authority id;
no fuzzy matches; deterministic.

### `serve`  ·  medium  ·  dependency-free
A cross-project variant of `graph_mcp.py` so `neighbors` / `path` span projects
("where else have I used Finkelstein?"). Optional; only worth it once `merge`
is in real use.

## Branch B — Consolidate (fragments → one wiki)  ·  large  ·  LLM-assisted skill

For a *single* work accidentally split into per-chapter wikis. **Not** the
Evidentia case (its modules are genuinely separate works). Distinct from
federate: you want *one* canonical page per entity, not two linked by `same_as`.
It is a **skill, not a script** — content merge and conflict resolution need
judgment — built on the shared foundation as its deterministic detection layer:

- dedup by authority id / bibkey (definite) or slug/title (propose, human confirms);
- **generative, not destructive** — emit a *new* unified project, leave the
  chapter wikis intact (a one-way migration: after it, work in the unified wiki);
- surface genuine content conflicts as `review_flags: open-question` for a human,
  never silently pick a side;
- rewrite wikilinks / `sources:` / `relations:` to the canonical slug; union BibTeX;
- **concepts never auto-merged** (no authority id) — always proposed.

**Acceptance.** N chapter wikis → one `knowledge/` + an `output/book/` skeleton;
every merge traceable to an authority id or a logged human decision; conflicts
surfaced not resolved; source wikis untouched.

## Branch C — Portfolio / synthesis (leaves → a book)  ·  large  ·  the Evidentia case

For a book or portfolio grant that *synthesises across* many leaf projects
without merging them (Evidentia's ~25 module wikis → one book; grants for parts
or the whole). The super-project holds cross-cutting syntheses and **references**
the leaves; `drafting-manuscript` and `grant-finder` would need to **source
across multiple project wikis** — a cross-project *read*, not a merge. The shared
foundation's overlap is the connective tissue that suggests the synthesis
structure. The hard part: a portfolio's deepest connections are usually
*concepts / methods* shared across leaves — the authority-ID blind spot — so this
branch leans on the concept-vocabulary lever below and on human synthesis, with
tooling helping only at the entity / source layer.

**Acceptance.** A super-project whose drafts pull cited content from named leaf
wikis; overlap-derived shared entities form the spine of the synthesis; nothing
in the leaves is merged or mutated.

## Concept vocabulary — closing the blind spot  ·  medium

Concepts carry no authority ID, so cross-project *concept* overlap is invisible —
yet a methods portfolio's deepest links are conceptual (point process,
visibility, least-cost path recurring across modules). The platform-clean fix: a
shared concept vocabulary / glossary (e.g. in a docs repo) that module concept
pages reference by a stable id, giving concepts a project-internal join key — no
fuzzy matching. This is the lever that would make Branch C's synthesis mechanical
rather than purely manual.

## Evidentia field-test (2026-07) — what a real portfolio taught

Run on a real ~25-module computational-archaeology platform (10 wikis, 668 pages).
These findings drove the reframing above and shipped `orcid` (v0.21.0):

- **The tissue is people + software, not sites / DOIs.** The theology framing at
  the top (Tel Megiddo, a shared DOI) did not hold: the genuinely shared entities
  were *working researchers* (Crema, Bevan, Lake, Verhagen, spanning the temporal
  / visibility / connectivity modules) and *shared software* (GRASS GIS) — under
  drifted slugs (`enrico-crema` vs `crema`), which is exactly why the match must
  be on the authority id, not the slug.
- **Resolver coverage is the bottleneck, not the tool.** `dao-paper-search`'s
  `resolve_author` (GND / Wikidata) returned nothing for those working
  researchers; the iDAI gazetteer missed real sites (Tel Qasile). Automated
  tagging covers well-known sites + famous scholars; the rest is a manual tail.
  This drove **`orcid`** — the key that *does* cover living researchers — and
  shared software → `wikidata_qid`.
- **Authority-ID coverage is a data-discipline gate.** An audit found **0 of 135
  entities tagged** across the ten wikis — the connective tissue simply wasn't in
  the data. The `wiki-lint` authority-coverage report (v0.20.1) makes that gap
  visible and doubles as the tagging worklist.
- **Payoff, once tagged.** With 5 shared entities tagged (4 ORCID + 1 Wikidata),
  `overlap` surfaced 5 real cross-module `same_as` edges across drifted slugs —
  the first mechanical view of the portfolio's actual connections.
