# Quickstart

Five minutes from "I just installed this" to "my first source is in the wiki."

## Prerequisites

- Claude Code (or OpenCode) installed and working
- Python 3.10+ for the wiki linter (`pyyaml` only — no other dependencies)
- A PDF of a scholarly source you want to ingest (any field — the example uses Levantine archaeology)

Optional but recommended: see [`recommended-mcps.md`](recommended-mcps.md) for `dao-paper-search-mcp` (verified citations) and `dao-searxng-mcp` (web-source classification). Skip these for the quickstart; the plugin works without them.

## 1. Install the plugin

```bash
# Claude Code
claude plugins install /path/to/research-superpowers
```

OpenCode users: symlink the skills into your project's `.claude/skills/`:

```bash
ln -s /path/to/research-superpowers/skills .claude/skills
```

(OpenCode reads SKILL.md files natively from `.claude/skills/<name>/SKILL.md`.)

## 2. Scaffold a research project

Copy the template anywhere on disk:

```bash
cp -r /path/to/research-superpowers/templates/research-project-template my-project
cd my-project
```

Edit the frontmatter at the top of `CLAUDE.md` — set `methodology`, `discipline`, and `languages` to match your project:

```yaml
---
methodology: hermeneutic   # hermeneutic | quantitative | mixed
discipline: "Biblical Archaeology"
languages: [en, de]
---
```

(`hermeneutic` is the default and right for most theology / archaeology / DH projects. See [`concepts.md`](concepts.md) for when to choose `quantitative` or `mixed`.)

Initialise git and create the bibliography directory:

```bash
git init
mkdir -p input/bibliography output/bibtex
touch output/bibtex/references.bib
```

## 3. Drop a source PDF

Put a scholarly PDF you want to read into `input/bibliography/`. The plugin's `ingest-source` skill knows how to handle PDFs (and uses OCR if scanned).

```bash
cp ~/Downloads/finkelstein-2003-low-chronology.pdf input/bibliography/
```

## 4. Open Claude Code in the project and trigger ingest

```bash
cd my-project
claude
```

In Claude Code, say:

> Ingest the Finkelstein 2003 PDF from input/bibliography/.

The assistant will:

1. Recognise this as a source-ingest task and invoke the `ingest-source` skill.
2. Read the PDF in full.
3. Derive a slug (`finkelstein-2003`), extract bibliographic data, identify entities (people, places, concepts).
4. Create:
   - `knowledge/sources/finkelstein-2003.qmd` — the source page (frontmatter + theses + methodology + entities + verbatim quotes)
   - `knowledge/entities/<entity>.qmd` — one per new entity (stubs you can expand later)
   - one entry appended to `output/bibtex/references.bib`
   - one line in `knowledge/_meta/log.qmd`
5. Run `scripts/lint-wiki.py` and show you any issues.

You review the diff, accept or revise, commit.

## 5. Verify

```bash
ls knowledge/sources/
ls knowledge/entities/
cat output/bibtex/references.bib
python3 scripts/lint-wiki.py
```

The lint script should exit 0 (all frontmatter valid, all wikilinks resolve).

## What to do next

- **More sources?** Repeat step 3 + 4. After ~5 sources you'll want to start a synthesis page — ask Claude to "create a synthesis page on `<topic>` from the ingested sources" (this triggers `executing-research-plan`'s synthesis routing).
- **Bigger project?** Start formally: ask "let's research X" — that triggers `brainstorming-research`, which produces a design doc and (after your approval) a research plan. Then `executing-research-plan` runs the plan.
- **Drafting?** Once at least one synthesis page is `status: stable`, ask "draft chapter on X" — that triggers `drafting-manuscript`.
- **Full walkthrough?** Read [`tutorial.md`](tutorial.md) — same workflow, larger example, every phase narrated.
- **Concepts?** [`concepts.md`](concepts.md) explains the SOFT-GATE pattern, methodology branching, SOT pattern.

## If something looks wrong

- **The assistant tried to draft from memory instead of the wiki.** Push back; the discipline is "every claim cites a source page." If it persists, your project's `CLAUDE.md` may have been overwritten — check the frontmatter and project methodology.
- **Lint complains about a missing field.** The frontmatter schema is in `schema/knowledge-frontmatter.schema.json`. The error message names the field.
- **The skill seemed to block silently.** It shouldn't — SOFT-GATEs ask for a one-line reason and continue. Restart the conversation; share the gate message if it persists.
- **Skill didn't fire when you expected it to.** State the skill name explicitly: "Use the `ingest-source` skill on this PDF."
