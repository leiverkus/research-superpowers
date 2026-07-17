# Example Project — Low Chronology (Mini Demo)

A minimally populated project tree showing what `research-superpowers` looks
like on a real research undertaking. Three sources have been ingested (Finkelstein
& Piasetzky 2003 fully; Mazar 2011 and Regev et al. 2020 as stubs), one synthesis
page exists, and the article's argument architecture has been outlined — but no
section has been drafted yet, because the drafting gate is deliberately unmet.

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
│   ├── entities/
│   │   └── tel-rehov.md                     # entity extracted during ingest
│   ├── sources/
│   │   ├── finkelstein-piasetzky-2003.md    # ingest output (full)
│   │   ├── mazar-2011.md                    # ingest output (stub)
│   │   └── regev-et-al-2020.md              # ingest output (stub)
│   ├── synthesis/
│   │   └── chronology-debate.md             # first synthesis (status: review,
│   │                                        #   one open review_flag)
│   └── _meta/
│       ├── log.md                           # workflow log
│       └── graph/                           # wiki-graph export
├── output/
│   ├── article/
│   │   ├── outline/
│   │   │   └── main.md                       # argument architecture (Stage A)
│   │   └── main.qmd                          # section stubs — Stage B not started
│   ├── bibtex/
│   │   └── references.bib                    # 3 BibTeX entries
│   └── data-analysis/                        # (empty — scripts to follow)
└── README.md
```

## What can be seen here?

- **Pre-registration works:** `input/ideas/*-plan.md` contains the frozen
  hypothesis; all subsequent analyses have to be measured against it.
- **Ingest output:** `knowledge/sources/finkelstein-piasetzky-2003.md` is a
  complete artefact — frontmatter, core theses, quotations, entities.
- **BibTeX consistent:** every cite-key in `knowledge/**` exists in
  `output/bibtex/references.bib`.
- **Argument architecture before prose:** `output/article/outline/main.md` is
  Stage A of `drafting-manuscript` — thesis, claim chain, and per section its
  claim, evidence, function in the chain, scope boundary and word budget. The
  path is derived from the target file (`article/main.qmd` →
  `article/outline/main.md`); it is never rendered.
- **A gate doing its job:** every section sits at `Status: outlined` and none
  has been drafted. `[[chronology-debate]]` is `status: review` and carries an
  open `review_flag` (`weak-support`), so the drafting SOFT-GATE is unmet — and
  there is no `gate-overrides.log`, because it was not overridden. The outline
  is what makes the real problem visible: S4 is the article's load-bearing
  section and its only source (Cohen 1979) is not ingested yet.
- **Log:** `knowledge/_meta/log.md` shows the pattern of `ingest`, `synthesis`,
  and `draft` entries.

## Continuing the workflow

Ingest Cohen 1979, full-ingest `mazar-2011` and `regev-et-al-2020`, resolve the
open flag on `chronology-debate` — then `drafting-manuscript` Stage B can run
section by section.
