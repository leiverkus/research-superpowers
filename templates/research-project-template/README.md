# Research Project Template

An LLM-supported research wiki following the **Input → Knowledge → Output**
pattern, inspired by
[Karpathy's LLM wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

You collect sources, the LLM turns them into a structured, cross-referenced
wiki, and publications — articles, books, presentations — flow out of the
wiki.

## What is this?

This repository is a **template for scientific research projects**. It
provides:

- A clean folder structure that separates raw material, knowledge, and
  publications
- Conventions for an LLM-generated wiki in Quarto (`.qmd`)
- Ready-made templates for book projects, journal articles, and
  presentations with Makefiles
- Team workflows over GitLab, Zotero, and Nextcloud
- Automatic wiki rendering as a website (GitLab Pages)
- A lint script for structural checks on the wiki

## Quickstart

### 1. Fork the repository

Click **Fork** in GitLab. Name the new repository after your project.

### 2. Clone locally and set up

```bash
git clone git@gitlab.your-institution.de:your-name/your-project.git
cd your-project
```

### 3. Write the project description

Edit `input/description/project-description.md` — fill in the research
question, methodology, scope, and collaborators. The LLM agent reads this
file at the start of every session as orientation.

### 4. Set up Zotero

- Add your institution email to your Zotero account (institutional licence
  gives you unlimited storage)
- Create a Zotero group and invite team members
- Install Better BibTeX and configure auto-export to
  `output/bibtex/references.bib`

### 5. Process your first source

```bash
# Start the LLM agent (Claude Code or OpenCode)
claude    # or: opencode

# In the agent:
> Ingest the "Finkelstein 2003" article from Zotero.
```

The agent reads the project description, finds the article via the Zotero
MCP server, creates a source page in the wiki, and updates the index and
log.

### 6. View the wiki in the browser

```bash
cd knowledge && make preview
```

## Structure

```
input/                 Raw material (immutable, maintained by humans)
├── description/       Project description and research question
├── bibliography/      PDFs (managed in Zotero)
├── data/              Research data (shared via Nextcloud)
├── notes/             Field notes, memos
└── ideas/             Hypotheses, questions

knowledge/             LLM-generated wiki (.qmd)
├── entities/          People, places, sites, artefacts
├── concepts/          Theories, methods, terms
├── sources/           Summaries of individual sources
├── synthesis/         Cross-cutting analyses and theses
├── assets/            Figures and diagrams from sources
└── _meta/             Index and log

output/                Publication-ready artefacts
├── publication/
│   ├── book/          Quarto book project with chapters
│   └── article/       Scholarly article with abstract
├── presentation/      Talks (Reveal.js, Beamer, PowerPoint)
├── data-analysis/     Scripts and notebooks
├── app/               Software repository
└── bibtex/            Bibliography and CSL styles
```

| Area | Who writes | Who reads |
|---------|-------------|-----------|
| `input/` | Human | LLM |
| `knowledge/` | LLM | Human + LLM |
| `output/` | Human + LLM | All |

## Workflows

| Workflow | Trigger | What happens |
|----------|----------|-------------|
| **Ingest** | New source in Zotero | LLM reads the source, creates wiki pages, updates the index |
| **Query** | Ask a research question | LLM searches the wiki and answers with references |
| **Lint** | Periodic / on request | Script + LLM check structure, links, contradictions |
| **Draft** | Request a manuscript section | LLM produces a draft from wiki content with citations |

Details: → [CLAUDE.md](CLAUDE.md)

## Makefiles

Every template has a Makefile. Overview:

```bash
# Wiki
cd knowledge
make wiki              # build the HTML website
make preview           # live preview

# Book project
cd output/publication/book
make pdf               # PDF (KOMA-Script scrbook)
make html              # HTML website
make docx              # Word
make epub              # e-book

# Scholarly article
cd output/publication/article
make pdf               # PDF (KOMA-Script scrartcl)
make html              # HTML
make docx              # Word

# Presentation
cd output/presentation
make slides            # Reveal.js HTML slides
make pptx              # PowerPoint
make beamer            # LaTeX Beamer PDF
make handout           # A4 handout PDF
```

## Prerequisites

| Software | For what | Install (macOS) |
|----------|-------|---------------------|
| [Quarto](https://quarto.org) | All outputs | `brew install quarto` |
| XeLaTeX | PDF output | `quarto install tinytex` |
| [Zotero](https://zotero.org) + Better BibTeX | Bibliography | zotero.org/download |
| Python 3 + PyYAML | Lint script | `pip install pyyaml` |
| Linux Libertine, Fira Code | Fonts for PDF | See `output/README.md` |

Optional tools:

| Software | For what |
|----------|-------|
| [VS Code](https://code.visualstudio.com) + Foam | Wiki navigation, graph view |
| [Obsidian](https://obsidian.md) | Alternative wiki navigation |
| [Claude Code](https://docs.claude.com) / [OpenCode](https://opencode.ai) | LLM agent |
| Zotero MCP Server | LLM access to your library |
| Nextcloud | Shared research data |

## Team use

This template is designed for collaborative research projects:

- **Git** (via GitLab) for the wiki and publications
- **Zotero Group Library** for the shared bibliography
  (institutional licence for unlimited storage)
- **Nextcloud** for large research data (geospatial, images)
- **Merge requests** for reviewing wiki ingests
- **GitLab Pages** for automatic wiki rendering

Branch conventions, roles, and the full team workflow are documented in
[CLAUDE.md](CLAUDE.md#team-collaboration).

## Customise

After forking, edit these files:

1. **`input/description/project-description.md`** — your research question
   and project description
2. **`CLAUDE.md` → Project-specific conventions** — language, terminology,
   special page types
3. **`output/publication/`** — adapt the templates to your publisher /
   journal (CSL style, document class, fonts)
4. **`.gitlab-ci.yml`** — URL and paths for your GitLab instance

The example pages (prefix `_example-`) in `knowledge/` show the expected
style and can be deleted once you have your own content.

## License

> [Add your license here, e.g. CC BY 4.0 for the template, separate
> license for the research content.]

## Acknowledgements

Concept based on [Karpathy's LLM wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).
Tools: [Quarto](https://quarto.org),
[Zotero](https://zotero.org),
[Foam](https://foambubble.github.io/foam/).
