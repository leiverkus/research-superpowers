---
name: drafting-manuscript
description: Use to draft a book chapter, article section, or grant exposé from synthesized wiki content. Pulls from stable synthesis pages and source pages, writes to `output/publication/**/*.qmd` with proper citations. Never drafts from memory — always from the wiki.
inputs:
  - name: plan_task_id
    description: Reference to the explicit Draft task in input/ideas/<slug>-plan.md
    required: true
  - name: target_section
    description: Section title and chapter position (e.g. "3.2 The Low Chronology — Core Arguments")
    required: true
  - name: output_path
    description: Target QMD file path (e.g. output/publication/book/text/03-methods.qmd)
    required: true
  - name: synthesis_pages
    description: Paths to knowledge/synthesis/*.qmd to draw from (must include at least one status=stable)
    required: true
  - name: source_pages
    description: Paths to knowledge/sources/*.qmd whose bibkeys are allowed for citation
    required: true
  - name: target_language
    description: de or en
    required: false
  - name: target_word_count
    description: Target prose length (±15%)
    required: false
outputs:
  - path: output/publication/**/*.qmd
    kind: created_or_modified
  - path: knowledge/_meta/log.qmd
    kind: appended
agents:
  - drafter
---

# Drafting a Manuscript

Turn stable synthesis pages into publishable prose. Every claim gets a citation. Every citation resolves in `output/bibtex/references.bib`. No inventing, no paraphrasing from memory — the wiki is the single source of truth.

**Announce at start:** "Using drafting-manuscript to draft <chapter/section> into `<path>`."

<SOFT-GATE>
Before drafting, check:
(1) At least one `knowledge/synthesis/*.qmd` with `status: stable` exists AND is referenced by the draft task
(2) Every source cited in the target section exists as `knowledge/sources/*.qmd` AND has a BibTeX entry
(3) `wiki-lint` is green on the knowledge tree
(4) The research plan `<slug>-plan.md` contains an explicit Draft task for this output file

If a condition is unmet: tell the user which (e.g. "no stable synthesis yet"),
ask for a short reason to draft anyway, write it into
`knowledge/_meta/gate-overrides.log`, and start the draft. Repeated overrides
on (3) are a maintenance signal.
</SOFT-GATE>

## When to use

- A plan Draft task is current (`executing-research-plan` routes here)
- Synthesis page(s) are stable and user asks for chapter/article draft
- Rewriting a chapter after peer-review revisions (iterate via same skill)

**NOT for:** first-draft brainstorming (use `brainstorming-research`), unsynthesized material (go back and synthesize first), grant research narratives from scratch (use `grant-finder`).

## Checklist

1. **Confirm plan task** — find the exact entry in `<slug>-plan.md`; confirm output file path
2. **Pre-flight checks (SOFT-GATE)** — stable synthesis pages? BibTeX complete? wiki-lint green?
3. **Read all referenced synthesis pages** fully
4. **Read all cited source pages** — especially the "Verbatim quotes (with page)" sections
5. **Determine target length** from the plan (words / pages / chapter size)
6. **Produce a section skeleton** — introduction, main parts, conclusion; confirm with user before prose
7. **Draft prose** — one section at a time, citations inline as `[@bibkey]` or `[@bibkey, p. 152]`
8. **Verify every citation** — each `[@bibkey]` has a matching entry in `output/bibtex/references.bib`
9. **Write to target file** — `output/publication/book/text/<nn-slug>.qmd` or `output/publication/article/main.qmd`
10. **Render check** — run `make render` (or `quarto render`) in the target `output/publication/<book|article>/` directory; fix any errors
11. **Log** — entry in `knowledge/_meta/log.qmd`: date, draft, target file, word count, source count

## Process Flow

```dot
digraph drafting {
    "Confirm plan task" [shape=box];
    "Pre-flight (SOFT-GATE)" [shape=box];
    "Gate passes?" [shape=diamond];
    "Back to synthesis / ingest / lint" [shape=box];
    "Read synthesis pages" [shape=box];
    "Read source pages" [shape=box];
    "Determine length" [shape=box];
    "Section skeleton" [shape=box];
    "User approves skeleton?" [shape=diamond];
    "Draft prose section by section" [shape=box];
    "Verify citations" [shape=box];
    "Citations complete?" [shape=diamond];
    "Write target file" [shape=box];
    "Render check" [shape=box];
    "Render OK?" [shape=diamond];
    "Fix render errors" [shape=box];
    "Log entry" [shape=box];
    "Done" [shape=doublecircle];

    "Confirm plan task" -> "Pre-flight (SOFT-GATE)";
    "Pre-flight (SOFT-GATE)" -> "Gate passes?";
    "Gate passes?" -> "Back to synthesis / ingest / lint" [label="no"];
    "Gate passes?" -> "Read synthesis pages" [label="yes"];
    "Read synthesis pages" -> "Read source pages";
    "Read source pages" -> "Determine length";
    "Determine length" -> "Section skeleton";
    "Section skeleton" -> "User approves skeleton?";
    "User approves skeleton?" -> "Section skeleton" [label="no"];
    "User approves skeleton?" -> "Draft prose section by section" [label="yes"];
    "Draft prose section by section" -> "Verify citations";
    "Verify citations" -> "Citations complete?";
    "Citations complete?" -> "Draft prose section by section" [label="no"];
    "Citations complete?" -> "Write target file" [label="yes"];
    "Write target file" -> "Render check";
    "Render check" -> "Render OK?";
    "Render OK?" -> "Fix render errors" [label="no"];
    "Fix render errors" -> "Render check";
    "Render OK?" -> "Log entry" [label="yes"];
    "Log entry" -> "Done";
}
```

## Citation Rules

- Inline citations: `[@finkelstein-2003]` or `[@finkelstein-2003, p. 152]`
- Multiple: `[@finkelstein-2003; @mazar-2011]`
- Every citation key MUST exist in `output/bibtex/references.bib`
- Direct quotes: inline with `>` or an em-dash, always with page number
- No uncited claims in argumentative sections (exception: common knowledge, clearly marked)
- **Web citations** (online databases, digital editions, research blogs without a BibTeX entry): use the `(domain — title)` form as an inline link, e.g. `[(idai.gazetteer.de — Tel Megiddo)](https://gazetteer.dainst.org/place/2048473)`. Use sparingly; group separately as "Web resources" in the references list.

## MCP Optimisation (recommended)

> If `dao-paper-search-mcp` and `dao-searxng-mcp` (see [`docs/recommended-mcps.md`](../../docs/recommended-mcps.md)) are available, verify citations through the MCPs instead of reconstructing them from memory. Otherwise, copy strictly from the source page's "Verbatim quotes" sections.

- **Book / article citations**: `dao-paper-search-mcp.search_crossref(doi=...)` returns `inline_citation.markdown` (a ready Author-Year link) and `authoritative_bibliography_line` (the full references-list line). Paste both verbatim instead of formatting Author-Year yourself.
- **Web citations**: `dao-searxng-mcp.fetch_url(url=...)` returns `source_class`. If `aggregator` or `suspect`, either find the primary source or name the aggregator status transparently in the text.

## Subagent Dispatch (optional, for long chapters)

For chapters > 3000 words, dispatch `drafter` subagent (see `agents/drafter.md`) per section. The subagent receives:
- The section outline
- List of synthesis pages (paths) to pull from
- List of source pages (paths) with allowed citation keys
- Target word count

Main conversation composes the final draft from section outputs.

## Quarto Template Hooks

The template's `output/publication/book/` uses a Quarto book structure (see `templates/research-project-template/output/publication/book/`):

- `_quarto.yml` defines the chapter list — update when adding a new chapter file
- `text/<nn-slug>.qmd` is the chapter-file naming convention (`01-introduction.qmd`, `02-state-of-the-field.qmd`, …)
- `template/_preamble.tex` holds LaTeX preamble for PDF output
- `Makefile` targets: `make render`, `make preview`, `make clean`

For articles, use `output/publication/article/main.qmd` with single-file layout.

## Red Flags

| Thought | Reality |
|---------|----------|
| "The source roughly says …" | Either a verbatim quote with page, or a paraphrase with a citation. No hearsay. |
| "I'll cite this passage properly later" | Later citations get forgotten. Get it right now, or not at all. |
| "I'll start drafting; structure can come later" | Skeleton first, sign-off, then prose. |
| "Wiki-lint isn't needed, I know everything is fine" | Mandatory before every draft — broken wikilinks are invisible when rendered. |
| "The chapter is so good, I'll ignore the render errors" | A chapter that won't render is not a chapter. |

## Key Principles

- **The wiki is truth** — every claim traceable to a synthesis or source page
- **Every citation verified** — bibkey existence before commit
- **Skeleton before prose** — structural sign-off first
- **Render check is part of drafting** — not "later"
- **One draft per run, one log entry** — keep changes traceable
