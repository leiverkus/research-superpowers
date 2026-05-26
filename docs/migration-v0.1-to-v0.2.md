# Migration v0.1 → v0.2

This guide walks you through migrating an existing research project that was scaffolded against `research-superpowers` v0.1.

If you have NO existing project, skip this file and scaffold fresh from `templates/research-project-template/`.

## TL;DR (~5 minutes)

1. Update the plugin: `claude plugins update research-superpowers`
2. Add `schema/knowledge-frontmatter.schema.json` to your project (copy from the template — see step 2 below).
3. Add the methodology frontmatter to your `CLAUDE.md` (step 3).
4. Run `python scripts/lint-wiki.py` and verify exit 0 (or address legitimate issues).

Optional but recommended: steps 4–6 below.

## Step 1 — Update the plugin

```bash
claude plugins update research-superpowers
```

If you installed from a local path, `git pull` in that directory.

## Step 2 — Add the schema to your project

v0.2 expects `schema/knowledge-frontmatter.schema.json` at the project root. The lint script looks there.

```bash
mkdir -p schema
cp ~/.claude/plugins/research-superpowers/templates/research-project-template/schema/knowledge-frontmatter.schema.json schema/
```

(Adjust the source path to wherever the plugin lives on your system.)

This file is the project-local mirror of the canonical schema in the plugin. Keep them in sync when the plugin updates — `schema/README.md` documents the sync convention.

## Step 3 — Add methodology frontmatter to `CLAUDE.md`

Open your project's `CLAUDE.md`. At the very top, add a YAML frontmatter block:

```yaml
---
methodology: hermeneutic   # hermeneutic | quantitative | mixed
discipline: ""             # e.g. "Biblische Archäologie", "Theologie", "Digital Humanities"
languages: [de, en]
---
```

Pick the methodology that matches your project. **Default is `hermeneutic`**, which preserves v0.1 behaviour minus the pre-registration requirement. If your project genuinely centres on quantitative methods (geostatistics, Bayesian 14C, quantitative DH), set `quantitative`. For mixed-methods, set `mixed` and mark individual plan tasks as `pre-registered: true` where appropriate.

If your existing research plan has a frontmatter `status: pre-registered`, you can keep it; it now corresponds to `methodology: quantitative` semantics.

If your plan was operating implicitly under hermeneutic norms (most theology / interpretive archaeology projects), change the plan's frontmatter to `status: ready` and add an `Iterations-Erwartung` section to the plan body. Templates for both variants are in `skills/writing-research-plan/SKILL.md`.

## Step 4 — Replace deleted commands

These OpenCode commands no longer exist. Use the underlying skill instead — the skill loads exactly the same logic.

| Removed command | Replacement |
|---|---|
| `/execute-plan` | invoke skill `executing-research-plan` (auto-triggers on "Plan ausführen" / "execute the plan") |
| `/finish-project` | invoke skill `finishing-a-research-project` ("Projekt abschließen") |
| `/grant-finder` | invoke skill `grant-finder` ("Fördermittel suchen") |
| `/research-plan` | invoke skill `writing-research-plan` ("Plan schreiben") |
| `/wiki-lint` | run `python scripts/lint-wiki.py` directly, or invoke skill `wiki-lint` |

The 5 remaining commands (`/ingest`, `/draft`, `/peer-review`, `/lit-review`, `/research-brainstorm`) were unchanged in behaviour at v0.2 but shrunk to ≤ 10 lines. **v0.3 removes them entirely** — OpenCode now reads skills natively from `.claude/skills/`; the slash shortcuts added no real UX value. Trigger skills via natural language or the `skill` tool.

## Step 5 — Replace `critical-thinking` invocations

The standalone `critical-thinking` skill is gone. Its content is now a cross-cutting checklist inside two skills:

- **During analysis / method selection** — `executing-research-plan` has a new "Critical Thinking — Querschnitts-Checkliste" section. Invoke that skill instead.
- **During peer review** — `requesting-peer-review` has a "Critical Thinking — Evidenz-Audit für Reviewer" section. Already included in the standard review flow.

If you previously invoked `critical-thinking` via a slash command or skill trigger, route those requests to one of these two skills.

## Step 6 — Optional: enable VS Code live validation

Copy the new `.vscode/settings.json` snippet from the template:

```bash
# In your project root:
cp ~/.claude/plugins/research-superpowers/templates/research-project-template/.vscode/settings.json .vscode/settings.json
```

Or merge the relevant snippet into your existing `settings.json`:

```jsonc
{
  "yaml.schemas": {
    "./schema/knowledge-frontmatter.schema.json": "knowledge/**/*.qmd"
  }
}
```

With the YAML extension installed, VS Code now marks frontmatter errors live as you type.

## Step 7 — Re-run lint to verify

```bash
python scripts/lint-wiki.py
```

Expected: exit 0 (or only pre-existing structural issues unrelated to the migration).

The new lint shows an additional `=== Gate-Overrides ===` section. With no `knowledge/_meta/gate-overrides.log` yet, it reports "Keine gate-overrides.log".

## What you DON'T have to do

- You do **not** have to rewrite existing pages. The schema is backward-compatible (no fields removed, `bibliography` became optional).
- You do **not** have to convert your in-progress research plan immediately. The plan continues to work; the methodology distinction kicks in next time `writing-research-plan` runs.
- You do **not** have to translate skill prose into German. The plugin's skills are bilingual; the language convention in `docs/skill-authoring.md` applies to new skills.

## If something breaks

- **Lint complains about missing `bibliography` field** — you're on the v0.1 lint. Re-copy `scripts/lint-wiki.py` from the template.
- **Hook injects 7 KB of skill content at session start** — you're on the v0.1 hook. `git pull` the plugin, restart Claude Code.
- **A SOFT-GATE seems to block silently** — it shouldn't. SOFT-GATEs prompt for an override reason. If you see blocking, the skill text is outdated; update from the plugin.

Open an issue at the plugin repo with the project's `_meta/log.qmd` excerpt and the failing command.

## See also

- [`../CHANGELOG.md`](../CHANGELOG.md) — full list of changes
- [`skill-contract.md`](skill-contract.md) — the new SOT pattern
- [`phase-flow.md`](phase-flow.md) — updated workflow graph with back-edges
- [`skill-authoring.md`](skill-authoring.md) — for authoring new skills under v0.2 conventions
