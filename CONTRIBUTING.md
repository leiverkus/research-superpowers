# Contributing

Thanks for considering a contribution. This plugin is a small, opinionated piece of research infrastructure; the goal of these notes is to keep it coherent as it grows.

## What we accept

- **Bug fixes** in skills, agents, the template, or the linter.
- **New skills** that fit the research lifecycle and meet the criteria in [`docs/skill-authoring.md`](docs/skill-authoring.md). Authoring a skill that overlaps an existing one is a bigger conversation — open an issue first.
- **MCP integrations** that follow the soft-preference pattern documented in `docs/skill-authoring.md` and `docs/recommended-mcps.md`. The plugin must remain standalone-functional.
- **Documentation improvements** — clarifications, missing cross-references, broken links, example-project polish.

## What we don't accept

- Adding a separate slash-command artefact for an existing skill. Skills are the single source of truth; OpenCode and Claude Code both discover them natively from `skills/<name>/SKILL.md`. See [`docs/skill-contract.md`](docs/skill-contract.md).
- Pre-registration enforced as a HARD-GATE. The SOFT-GATE pattern is intentional; hermeneutic disciplines (theology, interpretive archaeology) cannot reasonably freeze a hypothesis before reading.
- Authority-claim language in skill prose (`YOU MUST`, `EXTREMELY IMPORTANT`, etc.). Sober, peer-to-peer wording wins.

## How to contribute

1. Open an issue describing the change, especially if it touches more than one file.
2. Branch off `main`. Prefix branches: `fix/`, `feat/`, `docs/`, `chore/`.
3. Make the change. Keep diffs scoped — one logical change per PR.
4. Run verification (see below).
5. Open a PR. Describe the **why**, not just the what.

## Language convention

- All skill prose, agent prompts, templates, docs, and example content are in **English**.
- Domain-specific terminology that belongs to the field stays in its native form when standard: *Formgeschichte*, *Quellenkritik*, *Stratum*, *Locus*, *terminus ante quem*, etc. Italicise on first use.
- Frontmatter field names, JSON keys, BibTeX keys, file paths, and slugs are English / kebab-case.

## Verification before a PR

```bash
# 1. Plugin manifest + marketplace.json are valid and pass Claude Code's checks
claude plugin validate .

# 2. JSON schema is well-formed and both mirrors are in sync
python3 -c "import json; json.load(open('schema/knowledge-frontmatter.schema.json'))"
diff -q schema/knowledge-frontmatter.schema.json \
        templates/research-project-template/schema/knowledge-frontmatter.schema.json
diff -q schema/knowledge-frontmatter.schema.json \
        examples/example-project/schema/knowledge-frontmatter.schema.json

# 2b. Script mirrors are byte-identical (canonical source: the template)
#     This list must match .github/workflows/lint.yml ("Script mirrors are in
#     sync") exactly — that job is what actually gates the build.
for rel in scripts/lint-wiki.py scripts/wiki-to-graph.py \
           scripts/graph_mcp.py scripts/wiki-global-graph.py \
           scripts/library.py scripts/bib-subset.py scripts/bib-search.py \
           scripts/check-pdf-version.py scripts/add-to-library.py \
           scripts/optimize-pdf.py \
           scripts/vendor/cytoscape.min.js; do
  diff -q "templates/research-project-template/$rel" "examples/example-project/$rel"
done

# 3. Example project lints clean
cd examples/example-project && python3 scripts/lint-wiki.py
cd -

# 4. Agent contract: every agent references an existing skill
for f in agents/*.md; do
  impl=$(grep '^implements:' "$f" | awk '{print $2}')
  [ -d "skills/$impl" ] || echo "MISSING SKILL: $f → $impl"
done

# 5. Unit + integration tests (install the pinned dev deps first)
python3 -m pip install -r requirements-dev.txt
python3 -m unittest discover -s tests
```

> `requirements-dev.txt` is **dev/CI-only** (PyYAML + `jsonschema`). The runtime
> wiki scripts need only the stdlib + PyYAML; `jsonschema` powers the schema
> conformance cross-check (`tests/test_schema_conformance.py`), which skips
> cleanly if it isn't installed.

`claude plugin validate .` is the same check Anthropic's marketplace submission pipeline runs. Pass it locally before opening the PR. CI also runs a **best-effort** install smoke (`.github/workflows/install-smoke.yml`) that installs the real Claude CLI and runs `claude plugin validate .` plus a local marketplace install; it skips honestly if the CLI can't be obtained in the runner and never gates a release.

### Mirrored files

Two sets of files are duplicated and must stay identical:

- **Frontmatter schema** — three copies: repo root `schema/`,
  `templates/research-project-template/schema/`, and
  `examples/example-project/schema/`.
- **Wiki `scripts/`** — two copies: `templates/research-project-template/scripts/`
  and `examples/example-project/scripts/`. Ten paths, and the authoritative list
  is the loop in `.github/workflows/lint.yml` ("Script mirrors are in sync") —
  **that** is what gates the build; this prose is a copy and copies drift:
  `lint-wiki.py`, `wiki-to-graph.py`, `graph_mcp.py`, `wiki-global-graph.py`,
  `library.py`, `bib-subset.py`, `bib-search.py`, `check-pdf-version.py`,
  `add-to-library.py`, `vendor/cytoscape.min.js`.

  The repo-root `scripts/` is a **different thing**: maintainer tools
  (`build-library.py`, `lint-plugin.py`, `merge-bibs.py`, `migrate-citekeys.py`,
  `release.py`, `rename-source-pdfs.py`, `suggest-authority-ids.py`,
  `zotero-to-bib.py`). They are plugin-internal, never scaffolded into a
  project, and **not** mirrored.

> **Adding a mirrored script? Add it to the lint.yml loop in the same commit.**
> The loop is an allowlist, so a new script that nobody enters **fails open** —
> CI stays green while the mirror rots. That is the one failure this check exists
> to prevent, and the only way to hit it.

**The template is the canonical source.** After editing a script or the schema,
re-sync the copies, e.g.:

```bash
src=templates/research-project-template
cp "$src"/schema/knowledge-frontmatter.schema.json schema/
cp "$src"/schema/knowledge-frontmatter.schema.json examples/example-project/schema/
for rel in scripts/lint-wiki.py scripts/wiki-to-graph.py \
           scripts/graph_mcp.py scripts/wiki-global-graph.py \
           scripts/library.py scripts/bib-subset.py scripts/bib-search.py \
           scripts/check-pdf-version.py scripts/add-to-library.py \
           scripts/optimize-pdf.py \
           scripts/vendor/cytoscape.min.js; do
  cp "$src/$rel" "examples/example-project/$rel"
done
```

CI fails the build if any mirror drifts (steps "Schema mirror is in sync" and
"Script mirrors are in sync").

## Releasing a new version

The release is automated by `scripts/release.py` + `.github/workflows/release.yml`.

1. **Bump** both manifests + the README badge (and get a CHANGELOG skeleton if
   none exists):
   ```bash
   python scripts/release.py bump --version 0.12.0
   ```
2. **Write the CHANGELOG** notes under the `## [0.12.0]` heading.
3. **Open a PR and merge it.** CI's "Release metadata is consistent" step fails
   the build if the manifests disagree or the CHANGELOG section is missing, so a
   half-done bump can't land.
4. **Tag and push** from `main` after the merge:
   ```bash
   git tag -a v0.12.0 -m "research-superpowers v0.12.0" && git push origin v0.12.0
   ```
   The `Release` workflow then verifies the tag matches the manifests + a
   CHANGELOG section exists, extracts that section as the notes, and creates the
   GitHub Release automatically — no manual `gh release create`.
5. For marketplace publication: see [`docs/installation.md`](docs/installation.md)
   and submit at <https://claude.ai/settings/plugins/submit> for
   community-marketplace listing.

> You can dry-run the gate locally: `python scripts/release.py check --tag v0.12.0`
> and preview the notes with `python scripts/release.py notes --version 0.12.0`.

## Skill authoring quick reference

Full guide: [`docs/skill-authoring.md`](docs/skill-authoring.md).

- Skill files live in `skills/<name>/SKILL.md`; folder name matches the `name:` frontmatter field.
- Skill is the SOT. Agents (`agents/<name>.md`) are thin pointers with an `implements:` field; they declare dispatch rules and output format only — never duplicate the skill checklist.
- Gates are SOFT — they prompt for a written override reason and log it to `knowledge/_meta/gate-overrides.log` rather than blocking.
- Pre-registration logic branches on the project-level `methodology` (`hermeneutic` | `quantitative` | `mixed`).
- Add an `## MCP-Optimierung (recommended)` section if your skill benefits from an external MCP. Follow the soft-preference pattern; keep the manual fallback intact.

## Versioning

Semantic Versioning (`MAJOR.MINOR.PATCH`). At `0.x.y`, MINOR may include breaking changes when they buy real architectural clarity; PATCH stays additive. Once we reach `1.0.0`, strict semver applies.

## License

By contributing you agree that your work is released under the MIT License (see [`LICENSE`](LICENSE)).
