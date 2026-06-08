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

## P5 — Schema validation: full Draft-07 coverage  ·  medium  ·  introduces a CI/dev dependency

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

## P6 — End-to-end install & scaffold test  ·  medium  ·  dependency-free

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

## P7 — Platform matrix (Linux / macOS / Windows)  ·  large  ·  dependency-free

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
3. **v0.13.0** — P5 (jsonschema cross-check) + P6 tier 1 (scaffold E2E).
4. **v0.14.0** — P7 (platform matrix) + P6 tier 2 (real install, if feasible).

None of these are blocking; v0.10.0 is production-ready. This is the path from
"robust" to "mature".

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
