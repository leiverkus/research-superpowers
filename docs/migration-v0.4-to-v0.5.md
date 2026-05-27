# Migration v0.4 → v0.5

**TL;DR — your old source pages still work.** v0.5 restructures the `ingest-source` Source Page Template to be focus-driven (claims relevant to a specific question, not a generic summary) and adds the `## Focus:` append pattern for re-ingests. Existing source pages from v0.4 and earlier are still valid wiki content; the linter accepts both old and new structures. The new behaviour kicks in on the next ingest.

## What changed

- **Focus is now a required input to `ingest-source`.** The skill asks for a single-sentence focus before reading the source. If `input/description/project-description.md` exists, the project's research question is proposed as the default — the user confirms or refines.
- **Source Page Template restructured.** The old generic sections (`Core Theses`, `Method`, `Relevant Findings`, `Positioning`) are gone. New structure: one `## Bibliographic Details` header, one or more `## Focus: <focus> — <date>` blocks (each with claims, direct quotes, explicit boundary), one `## Other content in this source` paragraph, one `## Mentioned entities` section, one `## Connections` section.
- **Re-ingest appends, doesn't overwrite.** When the skill is invoked on a source whose `knowledge/sources/<slug>.qmd` already exists, it appends a new `## Focus:` block rather than rewriting the page. One bibkey, one wiki page, multiple lenses stacked over the project's life.
- **`agents/source-ingester.md` output report** updated: new `### Focus` line, `### Re-ingest mode` line, `### Claims relevant to focus` replacing `### Core theses`.
- **`docs/concepts.md`** has a new section "Wiki is purpose-built, not a generic archive" explaining the why.
- **`examples/example-project/input/description/project-description.md`** is new — populates the example with a real research question so the smart-default has something to read.
- **`examples/example-project/knowledge/sources/finkelstein-piasetzky-2003.qmd`** rewritten to demonstrate the new structure.
- **`templates/research-project-template/knowledge/sources/_beispiel-finkelstein-2003.qmd`** rewritten to demonstrate two stacked focus blocks (the append pattern).
- **`docs/tutorial.md`** Phase 4 walkthrough now shows focus elicitation, refinement, and re-ingest.

## What you can optionally do

### 1. Re-ingest old sources to get the new structure

Existing source pages keep working as-is. If you want one of them in the new structure, just re-ingest:

> "Re-ingest the Cohen 1979 source under focus: <new focus>."

The skill detects the old-format page (no `## Focus:` headings) and offers:

> Wrap the existing content as `## Focus: (legacy — full summary) — <original updated date>` before appending the new focus block?

If yes, the old generic summary becomes a labelled legacy focus block and the new focus block is appended below. If no, the new focus block is just added alongside the old structure — both stay readable.

### 2. Add `input/description/project-description.md` to existing projects

If your project doesn't have this file yet, create it. Use the template at `templates/research-project-template/input/description/project-description.md` as a starting point. The smart-default focus elicitation reads from this file.

Without it, the skill just asks for the focus explicitly on every ingest — also fine, just slightly more typing.

### 3. Read `docs/concepts.md` § "Wiki is purpose-built, not a generic archive"

This is the conceptual change behind v0.5. Worth ~3 minutes to understand the principle, especially if you're used to summary-style note-taking.

## What you don't have to do

- No batch migration of existing source pages.
- No re-running every old ingest.
- No frontmatter changes (the schema is unchanged).
- No changes to existing wikilinks or BibTeX entries.

## Skills unaffected

`brainstorming-research`, `writing-research-plan`, `literature-review`, `executing-research-plan`, `drafting-manuscript`, `requesting-peer-review`, `finishing-a-research-project`, `wiki-lint`, `semantic-wiki-review`, `grant-finder`, `scaffold-research-project`, `using-research-powers` — no behaviour change.

## If you've installed the example project

Pull the latest plugin (or re-clone), and look at:

- `examples/example-project/input/description/project-description.md` (new)
- `examples/example-project/knowledge/sources/finkelstein-piasetzky-2003.qmd` (restructured — single focus block)
- `templates/research-project-template/knowledge/sources/_beispiel-finkelstein-2003.qmd` (restructured — two stacked focus blocks demonstrating the append pattern)

These are the canonical references for the new structure.

## See also

- [`concepts.md`](concepts.md) § "Wiki is purpose-built, not a generic archive" — the principle
- [`tutorial.md`](tutorial.md) § Phase 4 — focus elicitation + re-ingest walkthrough
- [`../skills/ingest-source/SKILL.md`](../skills/ingest-source/SKILL.md) — full new skill spec
- [`../CHANGELOG.md`](../CHANGELOG.md) — full change list
- [`migration-v0.3-to-v0.4.md`](migration-v0.3-to-v0.4.md) — previous release migration
