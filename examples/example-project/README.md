# Example Project — Low Chronology (Mini Demo)

A minimally populated project tree showing what `research-superpowers` looks
like on a real research undertaking. One source (Finkelstein 2003) has been
ingested, one synthesis page exists, and one draft section has been generated.

## Structure

```
example-project/
├── input/
│   ├── ideas/
│   │   ├── low-chronology-design.md          # output of brainstorming-research
│   │   └── low-chronology-plan.md            # output of writing-research-plan
│   ├── bibliography/                          # (empty — PDFs stay local)
│   └── data/                                  # (empty — data stays local)
├── knowledge/
│   ├── sources/
│   │   └── finkelstein-piasetzky-2003.qmd    # ingest output
│   ├── synthesis/
│   │   └── chronology-debate.qmd             # first synthesis (status: draft)
│   └── _meta/
│       └── log.qmd                           # workflow log
├── output/
│   ├── publication/article/
│   │   └── main.qmd                          # draft skeleton
│   ├── bibtex/
│   │   └── references.bib                    # 1 BibTeX entry
│   └── data-analysis/                        # (empty — scripts to follow)
└── README.md
```

## What can be seen here?

- **Pre-registration works:** `input/ideas/*-plan.md` contains the frozen
  hypothesis; all subsequent analyses have to be measured against it.
- **Ingest output:** `knowledge/sources/finkelstein-piasetzky-2003.qmd` is a
  complete artefact — frontmatter, core theses, quotations, entities.
- **BibTeX consistent:** every cite-key in `knowledge/**` exists in
  `output/bibtex/references.bib`.
- **Draft skeleton:** `output/publication/article/main.qmd` carries the
  section structure from `drafting-manuscript`, with placeholders of ~1500 words each.
- **Log:** `knowledge/_meta/log.qmd` shows the pattern of `ingest`,
  `synthesis`, and `draft` entries.

## Continuing the workflow

From here, `/execute-plan` (Task 2, data extraction) would run next.
