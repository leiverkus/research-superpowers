# Quickstart

Five minutes from "I just installed this" to "my first source is in the wiki."

## Prerequisites

- Claude Code (or OpenCode) installed and working
- Python 3.10+ for the wiki linter (`pyyaml` only — no other dependencies)
- A PDF of a scholarly source you want to ingest (any field — the example uses Levantine archaeology)

Optional but recommended: see [`recommended-mcps.md`](recommended-mcps.md) for `dao-paper-search-mcp` (verified citations) and `dao-searxng-mcp` (web-source classification). Skip these for the quickstart; the plugin works without them.

## 1. Install the plugin

Open Claude Code in any directory, then:

```
/plugin marketplace add leiverkus/research-superpowers
/plugin install research-superpowers@leiverkus-research
```

Restart Claude Code (`exit`, then `claude` again). You should see a "Research Superpowers" notice on session start.

**OpenCode users:** symlink the skills into your project's `.claude/skills/`:

```bash
git clone https://github.com/leiverkus/research-superpowers ~/code/research-superpowers
cd /path/to/your-research-project
ln -s ~/code/research-superpowers/skills .claude/skills
```

(OpenCode reads SKILL.md files natively from `.claude/skills/<name>/SKILL.md`.)

Need more detail or hit a snag? See [`installation.md`](installation.md) — all three install paths, prerequisites, and troubleshooting.

## 2. Scaffold a research project

Open Claude Code in any directory and say:

> Scaffold a new research project.

The `scaffold-research-project` skill takes over and asks you four questions (project name, parent directory, methodology, discipline). After you confirm, it copies the template tree, patches `CLAUDE.md` with your answers, and optionally initialises git — no terminal commands needed.

(`hermeneutic` is the default methodology and right for most theology / archaeology / DH projects. See [`concepts.md`](concepts.md) for when to choose `quantitative` or `mixed`.)

## 3. Drop a source PDF

Navigate to the project the scaffold created, then copy a PDF into `input/bibliography/`:

```bash
cd ~/Documents/my-first-research-project   # adjust to your actual project path
cp ~/Downloads/finkelstein-2003-low-chronology.pdf input/bibliography/
```

The `ingest-source` skill handles PDFs and falls back to OCR for scanned pages.

## 4. Open Claude Code in the project and trigger ingest

```bash
claude
```

Say:

> Ingest the Finkelstein 2003 PDF from input/bibliography/.

The skill will ask for a **focus** — a single sentence saying what angle this project takes on the source (e.g. "Low Chronology arguments relevant to Iron Age IIA stratigraphy"). If you skip it, the skill proposes your research question as the default and asks you to confirm.

After ingest the assistant will have:

1. Created `knowledge/sources/finkelstein-2003.md` — a focus-driven source page (claims relevant to your project, not a generic summary)
2. Created `knowledge/entities/<entity>.md` for each new person, site, or concept found
3. Appended one BibTeX entry to `output/bibtex/references.bib`
4. Logged the ingest in `knowledge/_meta/log.md`

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

- **More sources?** Repeat step 3 + 4. The wiki builds up incrementally — each ingest appends, never overwrites.
- **Ready to synthesise?** Ask "let's plan the research on X" — that triggers `brainstorming-research`, then `writing-research-plan`, then `executing-research-plan`, which dispatches synthesis, analysis, and draft tasks from the plan.
- **Informal synthesis?** For a quick cross-source question without a formal plan, just ask it — Claude reads the relevant source pages and answers from the wiki.
- **Drafting?** Once at least one synthesis page is `status: stable`, ask "draft chapter on X" — that triggers `drafting-manuscript`.
- **Full walkthrough?** Read [`tutorial.md`](tutorial.md) — same workflow, larger example, every phase narrated.
- **Concepts?** [`concepts.md`](concepts.md) explains the SOFT-GATE pattern, methodology branching, SOT pattern.

## If something looks wrong

- **The assistant tried to draft from memory instead of the wiki.** Push back; the discipline is "every claim cites a source page." If it persists, your project's `CLAUDE.md` may have been overwritten — check the frontmatter and project methodology.
- **Lint complains about a missing field.** The frontmatter schema is in `schema/knowledge-frontmatter.schema.json`. The error message names the field.
- **The skill seemed to block silently.** It shouldn't — SOFT-GATEs ask for a one-line reason and continue. Restart the conversation; share the gate message if it persists.
- **Skill didn't fire when you expected it to.** State the skill name explicitly: "Use the `ingest-source` skill on this PDF."
