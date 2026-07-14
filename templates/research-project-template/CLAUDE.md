---
# Project metadata — to be set by the researcher before skills run
methodology: hermeneutic   # hermeneutic | quantitative | mixed
discipline: ""             # e.g. "Biblical Archaeology", "Theology / Old Testament", "Digital Humanities"
languages: [de, en]        # Preferred languages for sources and wiki prose
---

# Research Project Schema

This document defines the structure, conventions, and workflows for the
LLM-supported research wiki. It serves as instruction for the LLM agent
(Claude Code, OpenCode, etc.) and as reference for the human researcher.

## Project methodology

The frontmatter of this file (above) sets the methodological orientation of
the project. Skills read the `methodology` field and adapt their behaviour:

- **hermeneutic** — pre-registration is not enforced; iterative hypothesis
  revision through new reading is legitimate and is documented in the plan
  as a method sketch plus expected sources. Two-stage review is reduced to
  a simpler synthesis review.
- **quantitative** — full pre-registration required (frozen hypothesis,
  operationalisation, stop criterion). Two-stage review (spec + quality) on
  every task.
- **mixed** — pre-registration only for quantitative sub-studies; marked
  explicitly per sub-study in the plan.

Default is `hermeneutic`, because the plugin is primarily intended for
Theology / Biblical Archaeology / DH. Quantitative parts (e.g. geostatistics,
14C-Bayes) are marked per task in the plan, without rebranding the whole
project.

## Architecture

Three functional areas, inspired by Karpathy's LLM wiki pattern, extended
with an explicit output layer for scientific publication.

```
project-root/
├── CLAUDE.md              ← This document (schema & conventions)
├── .gitlab-ci.yml         ← CI/CD (GitLab): lint wiki + render publication + graph → Pages
├── .github/workflows/     ← CI/CD (GitHub Actions): same pipeline, GitHub Pages
├── .mcp.json             ← Registers the wiki-graph MCP (Claude Code)
├── .research-library      ← ONE LINE: path to the shared library. GITIGNORED —
│                             it is machine-local and must never be committed.
├── scripts/
│   ├── library.py         ← Resolves the shared library (env → dotfile → global)
│   ├── bib-subset.py      ← output/bibtex/references.bib ← the cited subset
│   ├── bib-search.py      ← page-level full-text search across the library (FTS5)
│   ├── lint-wiki.py       ← Structural check of the wiki
│   ├── wiki-to-graph.py   ← Knowledge-graph export + live queries
│   ├── graph_mcp.py       ← MCP server exposing the graph queries
│   └── vendor/            ← Bundled cytoscape.min.js (offline HTML viz)
├── input/                 ← Raw material (immutable)
│   ├── description/       ← Project description and research question
│   ├── bibliography/      ← literaturguide.md, acquisition-todo.md, audit logs
│   │                         (TEXT only — the PDFs live in the shared library)
│   ├── data/              ← Research data (CSV, shapefiles, GeoJSON, DBs)
│   ├── notes/             ← Own field notes, observations, memos
│   └── ideas/             ← Loose thoughts, hypotheses, questions
├── knowledge/             ← LLM-generated wiki (plain Markdown .md + wikilinks)
│   ├── _meta/             ← Index, log, status files
│   ├── assets/            ← Figures, diagrams, maps from sources
│   ├── entities/          ← People, places, institutions, artefacts
│   ├── concepts/          ← Theories, methods, terms
│   ├── sources/           ← Summaries of individual sources
│   └── synthesis/         ← Cross-cutting analyses, comparisons, theses
├── output/                ← Publication-ready artefacts
│   ├── book/              ← Quarto book project (chapter structure)
│   ├── article/           ← Quarto article (single file with abstract)
│   ├── presentation/      ← Talks (Quarto Reveal.js/Beamer/PPTX)
│   ├── data-analysis/     ← Scripts, notebooks (R, Python, Julia)
│   ├── code/              ← Software repo (e.g. Django/GeoDjango)
│   └── bibtex/            ← .bib file(s) + CSL styles
│       ├── references.bib
│       └── csl/           ← Citation Style Language files
└── .vscode/               ← VS Code workspace configuration
```

**And, outside the repo — shared by every project:**

```
<library>/                 ← e.g. ~/UOLcloud/Bibliothek (Nextcloud, read-only for the group)
├── references.bib         ← THE master bibliography
└── pdf/<bibkey>.pdf       ← one PDF per source; the filename IS the citekey
```

The repos stay in **Git**; only the PDFs live in the cloud folder. A git repo inside
a Nextcloud folder **corrupts**: Nextcloud syncs `.git/` file-by-file with no
transactional guarantee and writes "conflicted copy" files *inside* `.git/objects`.
Git is already the sync — the cloud carries only what git cannot hold.

## Core rules

### Input folder
- **Immutable, with one exception.** The LLM treats `input/` as human-owned and
  never writes into it — **except `input/bibliography/`**, where the
  `literature-review` and `acquire-sources` skills write their own **text**
  artefacts (`literaturguide.md`, `audit-log-*.json`, `acquisition-todo.md`,
  `acquisition-log-*.json`). Downloaded **PDFs** go to the shared library, not
  here.
- **`input/description/`** contains the project description and research
  question. The LLM reads this folder **at the start of every session** and
  uses its contents as orientation for ingest, query, synthesis and lint.
  Several files can live here (e.g. project description, exposé, proposal
  draft, methodological guidelines).
- New sources are dropped here by the human (PDF, data, notes).
- **Source PDFs do NOT live in this repo. They live in the shared library:**
  `<library>/pdf/<bibkey>.pdf`. That folder is the single source of truth that
  `acquire-sources` reconciles against and `ingest-source` reads from — and it is
  shared across every project, so the same paper exists **once**, and a metadata
  error is fixed **once**.
- **Where the library is, is machine-local.** Resolve it — never hard-code it:
  1. `RESEARCH_LIBRARY` (environment variable; this is what CI sets)
  2. `.research-library` in the project root — one line, **gitignored**
  3. `~/.config/research-superpowers/library`

  `scripts/library.py` does the resolving (`from library import pdf_for`). No
  symlink: symlinks need administrator rights on Windows, and `input/bibliography/`
  is mixed-ownership — its PDFs are shared, but `literaturguide.md`,
  `acquisition-todo.md` and the audit logs are per-project and **tracked**.
- **`input/bibliography/` therefore keeps its text artefacts and holds no PDFs.**
- **Searching the library** — `scripts/bib-search.py` indexes every PDF in the
  library with SQLite FTS5, **one row per page**, and answers with `bibkey · page ·
  snippet`:

  ```bash
  python scripts/bib-search.py index               # build / update (incremental)
  python scripts/bib-search.py "copper smelting"   # search every source, all projects
  python scripts/bib-search.py "shasu" --key tebes-2021-archaeology   # inside one source
  ```

  The page it reports is the **physical** PDF page — exactly what you need to *open*
  the file, and exactly what you must **not** cite. Read the printed page number off
  the page itself.

  The index is a **local cache** (`~/.cache/research-superpowers/`), never in the
  synced folder: SQLite and file-sync corrupt each other, the same failure class as a
  git repo inside Nextcloud. It is derived — if it is lost, rebuild it. PDFs with no
  text layer (scans) are **reported**, not silently indexed as empty; run `ocrmypdf`
  on those.
- **PDF filename schema (canonical): `autor-jahr-kurztitel.pdf`** — all
  lowercase ASCII, hyphen-separated. `autor` = first author's surname (umlauts
  → `ae`/`oe`/`ue`, `ß` → `ss`; particles and spaces removed, e.g.
  "van der Toorn" → `vandertoorn`); `jahr` = four-digit year (add a
  disambiguation letter for clashes: `finkelstein-2003b`); `kurztitel` = one to
  three significant title words, hyphen-joined, stopwords dropped. Example:
  `finkelstein-2003-low-chronology.pdf`. `acquire-sources` writes downloads
  straight to this name; manually fetched PDFs are renamed to it before ingest.
- **`bibkey` == the PDF filename stem** — the *whole* stem, not a prefix:
  `finkelstein-2003-low-chronology.pdf` → `bibkey: finkelstein-2003-low-chronology`.
  This is a **cross-project join key**: `scripts/wiki-global-graph.py` matches
  sources across projects on it, so it must be a deterministic function of the
  work's own metadata — the same work must yield the same key in *every* project.
  A per-project choice breaks the join silently. (An audit of 17 wikis found the
  old `autor-jahr` rule honoured by only 40% of 511 keys: 17 cross-project joins
  were lost, and 3 keys each denoted *two different papers*.) `lint-wiki.py`
  enforces the shape; `wiki-global-graph.py bibkeys` audits it across projects.
- **The wiki slug is NOT the bibkey.** The slug is a human-readable page name
  (`sources/hensel-2024.md`, `sources/source-hensel-2024.md` — either is fine);
  the `bibkey` is the citation key. They need not be identical, and in most
  projects they are not. Nothing joins on the slug.
- **Acquisition before ingest.** After `literature-review`, run
  `acquire-sources`: it auto-downloads the Open-Access PDFs for the A+B set into
  the shared library (`<library>/pdf/`) and writes `input/bibliography/acquisition-todo.md` — a worklist of
  sources it could not fetch (paywalled / bot-blocked). Download those manually
  (e.g. via university VPN) and save them in `<library>/pdf/` under the
  exact `<bibkey>.pdf` filename the worklist gives, then re-run
  `acquire-sources` to reconcile (or ingest the ones
  already present). `ingest-source` **hard-stops** on a missing original rather
  than silently using a preprint or review — so acquire first. See
  `input/bibliography/README.md`.
- BibTeX entries for new sources are written during ingest into
  `output/bibtex/`, not left in input.

### Knowledge folder
- **LLM-generated and LLM-maintained.** The human reads and steers, the
  LLM writes and updates.
- **File format: plain Markdown (`.md`).** Wiki pages are ordinary
  Markdown with YAML frontmatter — read directly in Foam/Obsidian or the
  GitLab/GitHub repository browser, with no build step. **Quarto is
  reserved for `output/`** (the article/book/presentation),
  which genuinely needs formats, CSL, cross-references and figures. The
  wiki is for thinking and steering, not formal output.
- Every file starts with YAML frontmatter (see frontmatter schema).
- Cross-references between wiki pages use wikilink syntax: `[[filename]]`
  (without extension; compatible with Foam and Obsidian). Do **not**
  escape the brackets (`\[\[…\]\]`) — some Markdown formatters do this on
  save and it breaks the links; if your editor does, disable that rule for
  this repo.
- Citations use the pandoc format: `@citekey` or `[@citekey]`, referencing
  `output/bibtex/references.bib`. In the `.md` wiki these render as plain
  text (they only resolve when pulled into a Quarto publication); that is
  intended.
- The human is free to make corrections — the wiki is no shrine.

#### Figures (`knowledge/assets/`)

Important figures from sources are stored in `knowledge/assets/` during
ingest and referenced in the wiki pages.

- **File naming convention:**
  `<citekey>-<description>.<ext>`, e.g.
  `finkelstein-2003-low-chronology-stratigraphy-megiddo.png`
- **What gets extracted:** maps, stratigraphies, diagrams, find photos,
  tables as image — anything visually relevant for understanding the
  source or the research question.
- **What does not get extracted:** decorative figures, generic graphics,
  publisher logos.
- **Embedding in wiki pages** uses plain Markdown image syntax (renders in
  Foam/Obsidian/GitLab without a build):
  ```markdown
  ![Stratigraphy of Megiddo](../assets/finkelstein-2003-low-chronology-stratigraphy-megiddo.png)
  ```
  The Quarto cross-reference form (`{#fig-…}` + `@fig-…`) is reserved for
  publication pages under `output/`.
- **Source attribution:** every figure must state its origin in the
  caption, e.g.:
  ```markdown
  ![Stratigraphy of Megiddo (after @finkelstein-2003-low-chronology, Fig. 3)](../assets/finkelstein-2003-low-chronology-stratigraphy-megiddo.png){#fig-megiddo-strat}
  ```
- **Mind copyright:** figures from published works may be used in the
  internal wiki (scholarly work), but not carried over into the
  publication (`output/`) without permission. For the
  publication, create your own figures or obtain reproduction rights.

### Output folder
- **Human-driven, LLM-supported.** This is where the finished product
  emerges: manuscript, analysis, software.
- Quarto/LaTeX projects reference the shared BibTeX file in
  `output/bibtex/references.bib`.
- Code in `data-analysis/` and `code/` has its own README files.

### Manuscript style (drafting depth)

The wiki is deliberately terse; the manuscript must not be. When `drafting-manuscript`
turns wiki pages into prose it reads this block first — **tune these to the
project's discipline and genre.** Defaults:

- **Develop, don't reflow.** Each substantive point becomes a developed passage
  (claim → the source's grounding → a concrete example → why it matters), not
  one sentence per wiki bullet. Prose that just restates bullets is unfinished.
- **Examples and explanations are required**, and they must come **from the
  sources** — the source pages' `### Direct quotes` / `### Examples &
  illustrations`, or the original PDF at `<library>/pdf/<bibkey>.pdf` at the cited
  pages. Reaching back to the source for depth is expected; inventing depth from
  memory is not.
- **Grounded elaboration is cited; expository framing (transitions, restating an
  argument's logic) is uncited.** New factual claims from memory are forbidden.
- **Target length is a floor for development, not a quota** — set generous word
  counts on Draft tasks so the draft is forced to elaborate rather than compress.
- **Register:** academic, discipline-appropriate Fachsprache, impersonal voice
  (adjust here if the project wants first-person plural, essayistic tone, etc.).

## Frontmatter schema

Every wiki page in `knowledge/` is a `.md` file with YAML frontmatter
following the central schema in
[`schema/knowledge-frontmatter.schema.json`](schema/knowledge-frontmatter.schema.json).

Minimal example:

```yaml
---
title: "Page title"
type: source
created: 2026-04-15
updated: 2026-04-15
status: review
author: llm
bibkey: lastname-year-shorttitle
---
```

Required fields: `title`, `type`, `created`, `updated`, `status`, `author`.
For `type: source` also `bibkey`.
Optional fields (e.g. `tags`, `sources`, `hypothesis`, `bibliography`,
`methodology`) and enum values: see the schema file and
`docs/frontmatter-schema.md` in the plugin.

`scripts/lint-wiki.py` validates against the schema on each run.

## Page types

For each page type an example file lives in the respective folder
(prefix `_example-`). These files serve as templates for style,
structure, and frontmatter, and are skipped by the lint script
(`scripts/lint-wiki.py` ignores the `_example-` / `_beispiel-` prefix).

### Entity (`knowledge/entities/`)
People, places, sites, institutions, artefacts, software projects.
Structure: short description → relevance to the research question →
relationships to other entities → sources.
Example: `_example-tel-megiddo.md`

### Concept (`knowledge/concepts/`)
Theories, methods, technical terms, technical concepts.
Structure: definition → context in research → related concepts →
critical perspectives → sources.
Example: `_example-low-chronology.md`

### Source (`knowledge/sources/`)
Summary of a single source from the shared library.
Structure: bibliographic info → core theses → methodology → relevant
results → own assessment → connections to other pages.
Example: `_example-finkelstein-2003.md`

### Synthesis (`knowledge/synthesis/`)
Cross-cutting analyses that connect several sources and concepts.
Structure: research question → argumentation → evidence from sources →
open questions → implications for your own work.
Example: `_example-chronologie-debatte.md`

## Workflows

**Before any workflow:** the LLM reads `input/description/` (if not yet
done in this session) to know the research question and project context.

### 1. Ingest (process a new source)

Trigger: human drops a new file into `input/` and tells the LLM:
"Process [filename]."

Steps:
1. LLM reads `input/description/` (research question and project context).
2. LLM reads the source.
3. LLM creates a Source page in `knowledge/sources/`.
4. LLM extracts important figures (maps, diagrams, stratigraphies, find
   photos) from the source and stores them in `knowledge/assets/` using
   the naming schema `<citekey>-<description>.<ext>`. The figures are
   embedded in the Source page and, where relevant, in Entity or Concept
   pages via plain Markdown image syntax.
5. LLM checks whether new Entities or Concepts need to be created.
6. LLM updates existing pages affected by the new source.
7. LLM updates `knowledge/_meta/index.md`.
8. LLM writes an entry into `knowledge/_meta/log.md`.
9. LLM appends the BibTeX entry to `output/bibtex/references.bib`.
10. Human reviews the changes (git diff) and gives feedback.

### 2. Query (ask a question)

Trigger: human asks a research question.

Steps:
1. LLM reads `knowledge/_meta/index.md` to find relevant pages.
2. LLM reads the relevant pages.
3. LLM answers the question with references to wiki pages.
4. If the answer constitutes a standalone analysis → create a new
   Synthesis page in `knowledge/synthesis/`.

### 3. Lint (maintenance)

Trigger: periodic or on demand ("check the wiki").

Checkpoints:
- Orphan pages (no incoming links)
- Contradictions between pages
- Stale claims (newer sources contradict them)
- Missing pages (mentioned but not created)
- Missing cross-references
- Status distribution (too many drafts?)
- Frontmatter completeness

For the structural checks (frontmatter, links, orphan pages) the
lint script can be used:

```bash
python scripts/lint-wiki.py           # standard check
python scripts/lint-wiki.py --verbose # with details on correct files
```

The script checks deterministically and fast. Content checks
(contradictions, stale claims) require the LLM.

### 4. Draft (manuscript draft)

Trigger: human says "Draft [section/chapter]."

Steps:
1. LLM gathers relevant Synthesis and Source pages.
2. LLM creates a draft in `output/`, following the **Manuscript style
   (drafting depth)** rules above — develop each point with examples and
   explanation drawn from the sources, do not reflow bullets into flat prose.
   - For a book chapter: in `output/book/`
   - For an article: in `output/article/`
3. Where a wiki page is too thin to develop a point, the LLM reaches back to the
   source — its `### Direct quotes` / `### Examples & illustrations`, or the
   original PDF at `<library>/pdf/<bibkey>.pdf` at the cited pages — and cites what it uses.
4. The draft contains Quarto citations (`@citekey`) referring to
   `output/bibtex/references.bib`.
5. Human revises the draft.

### 5. Read the wiki

The wiki is plain Markdown — no build step. Read and navigate it directly
in **Foam** or **Obsidian** (wikilinks, backlinks, graph view) or in the
GitLab/GitHub repository browser. Quarto is **not** used for the knowledge
layer; it builds only the publication output (`output/`). The
CI lints the wiki structure (`scripts/lint-wiki.py`) and renders + deploys
the publication on every push to `main`.

For an explicit, queryable graph, run `python scripts/wiki-to-graph.py` — it
exports to `knowledge/_meta/graph/`:
- **`graph.html`** — a self-contained interactive viz (open in any browser; no
  install, no network). Colour by node type or by detected community; filter by
  node type / relation type / confidence; search; click a node to highlight its
  neighbourhood. Covers everyday exploration without Gephi/yEd.
- **`graph.json`** — for scripting/queries.
- **`graph.graphml`** — for Gephi/yEd (heavy layout, community detection).
- **`GRAPH_REPORT.md`** — a deterministic prose summary (overview, god_nodes,
  bridges, labelled communities, asserted relations, suggested questions); the
  static, git-diffable sibling of `graph.html`, byte-identical on an unchanged
  wiki.

All carry derived **god_nodes** (most-connected pages) and **bridges** (entities
joining otherwise-unconnected sources). Edges come from wikilinks plus the
optional confidence-tagged `relations:` frontmatter block.

To **query the live graph** during a session (recomputed each call — always
current — so no stale export), the same script takes sub-commands:

```bash
python scripts/wiki-to-graph.py neighbors <slug> --depth 2   # what connects to a page
python scripts/wiki-to-graph.py path <a> <b>                 # how two pages connect
python scripts/wiki-to-graph.py god-nodes --top-n 10         # most-connected pages
python scripts/wiki-to-graph.py bridges                      # load-bearing entities
python scripts/wiki-to-graph.py communities                  # thematic clusters (auto-detected, labelled)
python scripts/wiki-to-graph.py report                       # GRAPH_REPORT.md to stdout
python scripts/wiki-to-graph.py relations --type contradicts # typed edges by type/confidence
python scripts/wiki-to-graph.py search <term>                # find a node
python scripts/wiki-to-graph.py stats                        # counts + inference-rate
# add --json to any query for machine-readable output
```

The same queries are exposed as an **MCP server** (`scripts/graph_mcp.py`,
stdlib-only, a thin wrapper over the CLI). `.mcp.json` registers it for
**Claude Code** automatically, so in a session the agent can call the
`graph_neighbors` / `graph_path` / `graph_god_nodes` / `graph_bridges` /
`graph_communities` / `graph_relations` / `graph_search` / `graph_stats` tools
natively. For
**OpenCode**, add the equivalent to `opencode.json`:

```json
"mcp": { "wiki-graph": { "type": "local",
  "command": ["python3", "scripts/graph_mcp.py"] } }
```

### Across several projects (authority overlap)

If you run more than one research project, `scripts/wiki-global-graph.py` reports
which entities and sources they **share** — matched on the authority IDs the
frontmatter already carries (`gnd_id` / `idai_gazetteer_id` / `wikidata_qid` for
entities, `bibkey` for sources), never on fuzzy title guessing:

```bash
python scripts/wiki-global-graph.py overlap ../other-project . --json
```

It reports the shared identifiers (the `same_as` edges a merged global graph
would draw) and states the concept/no-ID blind spot. This is step 1 of the
cross-project graph; the merged-graph steps are on the roadmap (see the plugin's
`docs/ROADMAP.md`).

**Audit the `bibkey` join key itself:**

```bash
python scripts/wiki-global-graph.py bibkeys ../proj-a ../proj-b .
```

`overlap` compares bibkey *strings*, so it reports a shared key as a win and is
structurally blind to the two ways that can be wrong. `bibkeys` reads the `.bib`
— the *work* behind the key — and reports both:

- **COLLISION** — one key, two different works. `overlap` asserts a shared source
  where none exists. Exit code 1.
- **SPLIT** — one work, two different keys. The join is silently missed.

Run it whenever you add a project. It cannot be a CI gate: no single repo's CI
can see the others.

## Meta files

### `knowledge/_meta/index.md`

```markdown
# Wiki index

## Entities
- [[entity-name]] — short description (N sources)

## Concepts
- [[concept-name]] — short description

## Sources
- [[source-lastname-year]] — title

## Synthesis
- [[synthesis-topic]] — research question
```

### `knowledge/_meta/log.md`

Append-only. Every entry starts with a consistent prefix:

```markdown
## [2026-04-15] ingest | Finkelstein 2003
- Source page created: [[source-finkelstein-2003]]
- Entity updated: [[entity-tel-megiddo]]
- Concept newly created: [[concept-low-chronology]]
- BibTeX appended: finkelstein-2003-low-chronology

## [2026-04-15] query | Chronology debate
- Synthesis created: [[synthesis-chronologie-debatte]]

## [2026-04-15] lint | routine
- 3 orphan pages found
- 1 contradiction flagged: [[concept-iron-age-dating]]
```

## Editor setup

### VS Code + Foam (recommended for technical users)

Recommended extensions:
- **Foam** (`foam.foam-vscode`) — wikilinks, backlinks, graph view
- **Quarto** (`quarto-dev.quarto`) — rendering, preview
- **Markdown All in One** — shortcuts, TOC
- **BibTeX** (`james-yu.latex-workshop` or `phr0s.bib`) — citation management
- **GitLens** — track wiki history

Workspace settings: see `.vscode/settings.json`.

### Obsidian (alternative for less technical users)

- Vault = project root
- Community plugins: Dataview, Templater, Citations
- Set "Attachment folder" → `input/data/assets/`
- Graph view shows the wiki structure visually

### LLM agent (Claude Code / OpenCode)

- Schema file: this document (`CLAUDE.md`)
- Point the filesystem MCP server at the project root
- For OpenCode: create an `AGENTS.md` with the same content
- The agent reads this document at the start of every session

## Git conventions

The whole project is a Git repository. `knowledge/` and `output/` are
versioned via Git; `input/` lives, depending on the setup, in Nextcloud
or Zotero (see section "Team collaboration").

### Commit prefixes

- `ingest:` — new source processed
- `knowledge:` — wiki pages updated
- `draft:` — manuscript draft created/edited
- `lint:` — maintenance performed
- `data:` — research data added
- `meta:` — schema or configuration changed

### Branch conventions

- `main` — stable version. Only via merge request.
- `ingest/<shortname>` — one ingest run per branch, e.g.
  `ingest/finkelstein-2003`. Merged after review.
- `synthesis/<topic>` — work on a Synthesis page, e.g.
  `synthesis/chronologie-debatte`.
- `draft/<section>` — manuscript sections, e.g.
  `draft/kapitel-3-methodik`.
- `lint/<date>` — maintenance runs, e.g. `lint/2026-04-15`.

### CI/CD (GitLab pipeline / GitHub Actions)

Two equivalent pipelines ship with the template — use whichever host you are on:
`.gitlab-ci.yml` (GitLab) and `.github/workflows/pages.yml` (GitHub Actions).
Both do the same thing:

- **On push to `main` (and on GitLab merge requests):** the wiki is linted
  (`scripts/lint-wiki.py`), article and book are rendered to HTML, and the
  **knowledge graph is rebuilt** (`scripts/wiki-to-graph.py`). On `main` all of
  it is deployed to Pages. The wiki itself is plain Markdown and is **not**
  rendered — read it in the repository browser, Foam, or Obsidian.
- **Reachable at** the project's Pages URL:
  - Article: `/` (main page)
  - Book: `/book/`
  - **Knowledge graph: `/graph/`** — the interactive `graph.html` (open it in
    the browser) plus the deterministic `GRAPH_REPORT.md` overview.

The graph exports are gitignored (a build artifact), so CI rebuilds them fresh
on every push: the published `/graph/` is always current and nobody commits
`graph.html`. The team can read the current state in the browser without
installing Quarto or running Python locally. PDF builds still run locally via
the Makefiles.

> **GitHub Pages one-time setup:** repo *Settings → Pages → Build and
> deployment → Source: "GitHub Actions"*. GitLab Pages needs no setup.

## Team collaboration

### What is synced where

| Folder/Resource | System | Rationale |
|------------------|--------|------------|
| `knowledge/` | GitLab (Git) | Text-based, merge-friendly, versioning matters |
| `output/` | GitLab (Git) | Text-based, shared editing |
| Bibliography (metadata + PDFs) | Zotero group library | Institutional licence, unlimited storage |
| `input/data/` | Nextcloud | Large binary files, geodata |
| `input/notes/` | GitLab (Git) | Markdown, searchable |
| `input/ideas/` | GitLab (Git) | Markdown, searchable |

### GitLab setup

Create the project on GitLab, clone locally:

```bash
git clone git@gitlab.university.de:team/project.git
cd project
```

Make merge requests mandatory for `main` (Project Settings → Merge
Requests → Branch protection).

### Nextcloud integration for data

The Nextcloud client syncs a local folder. Wire that into your project
via symlink:

```bash
# macOS: Nextcloud folder is typically ~/Nextcloud/
ln -s ~/Nextcloud/project-data input/data-shared
```

The symlink `input/data-shared` is excluded in `.gitignore` but points
at the shared Nextcloud folder. All team members see the same data
without it landing in Git.

### Zotero group library (institutional licence)

The university has a Zotero institutional licence. All members with a
verified university email get unlimited cloud storage for personal
libraries and group libraries.

#### One-time: set up the group

1. **Register the university email in Zotero**: every team member adds
   their university address under zotero.org/settings/account → "Manage
   Email Addresses". Unlimited storage is activated automatically.
2. **Create a Zotero group** (zotero.org/groups/new, type: Private).
3. Invite all team members.
4. **Install Better BibTeX** (zotero.org/support/better-bibtex).
5. **Configure Better BibTeX**:
   - Preferences → Better BibTeX → Citation Keys → format:
     ```
     auth.lower + "-" + year + "-" + veryshorttitle.lower
     ```
     This reproduces the project convention exactly:
     `finkelstein-2003-low-chronology`. **Do not leave it at the default**
     (`auth.lower + year` → `finkelstein2003`): that key carries no title, so two
     papers by the same author in the same year collide onto one key — and it is a
     cross-project join key. A 17-wiki audit found exactly that happening three
     times, each silently asserting that two unrelated papers were the same source.
6. **Configure auto-export**: group library → right-click → Export
   Library → Better BibLaTeX → target: `output/bibtex/references.bib`
   → enable "Keep updated".

`references.bib` is updated locally and automatically whenever the
Zotero group changes.

> **`references.bib` IS committed to Git.** Do not gitignore it. The CI needs it
> on disk to render the article and book with Quarto — without it, every citation
> renders as `???` and the build is not reproducible. An ignored bib also has no
> git undo. An earlier version of this document claimed the opposite; that claim
> propagated into four projects' `.gitignore` and left their bibliographies
> unrecoverable. The **PDFs** live in the shared library, not in the repo (large
> and copyright-bound).

#### Adding PDFs to the group

PDFs are stored directly in the group library and distributed to all
members via Zotero sync:

1. Import the PDF via the browser connector or drag & drop into the
   group library.
2. Zotero uploads the PDF to cloud storage.
3. All team members receive the PDF automatically on the next sync.

#### LLM access to the PDFs

The LLM agent accesses the PDFs through the **Zotero MCP server**. It
talks to the local Zotero API (port 23119) and can search the library,
fetch metadata and read PDF full text.

Requirements:
- Zotero must be running locally.
- Enable the local API: Preferences → Advanced → Config Editor → set
  `extensions.zotero.httpServer.localAPI.enabled` to `true`.
- Enable the full-text index: Preferences → Search.

Setup for Claude Code:
```bash
claude mcp add zotero -- uvx "zotero-mcp-server[all]"
```

Setup for OpenCode (`config.toml`):
```toml
[mcp.zotero]
command = "uvx"
args = ["zotero-mcp-server[all]"]
```

During ingest you tell the agent something like:
"Process the Finkelstein 2003 article from Zotero."
The agent searches the library, reads the full text, and creates the
Source page in the wiki.

#### Recommended MCPs for the DAO workflow

In addition to the Zotero MCP, from `research-superpowers` v0.3 onwards
we recommend:

- **`dao-paper-search-mcp`** — searches in Zenon DAI, IAA, ADAJ, IxTheo,
  Propylaeum, OpenAlex, Crossref, Semantic Scholar and others; returns
  structurally verified citation blocks (Author-Year + references line)
  and authority IDs (Wikidata, iDAI.gazetteer, GND) for entity pages.
- **`dao-searxng-mcp`** — web search with `source_class` detection
  (primary / aggregator / suspect) and automatic DOI detection.

Both are **optional**: skills keep working without them. Setup and
rationale: see `research-superpowers/docs/recommended-mcps.md`.

### Ingest workflow in a team

Ingests are the point where the LLM changes many files at once. They
should always go through merge requests:

```bash
# Person A runs an ingest
git checkout -b ingest/finkelstein-2003
# LLM processes the source, edits wiki pages
git add -A
git commit -m "ingest: Finkelstein 2003 (Low Chronology)"
git push -u origin ingest/finkelstein-2003
# Open a merge request on GitLab
# Person B reviews, requests changes if needed
# After approval: merge into main
```

### Log entries with author

For team usage, add the author to the log prefix:

```markdown
## [2026-04-15] ingest | patrick | Finkelstein 2003
## [2026-04-15] synthesis | anna | Chronology debate
## [2026-04-15] lint | patrick | routine maintenance
```

### Avoiding manuscript conflicts

Split Quarto projects across multiple files:

```yaml
# output/book/_quarto.yml
project:
  type: book
book:
  chapters:
    - index.qmd
    - 01-introduction.qmd
    - 02-state-of-research.qmd
    - 03-methodology.qmd
    - 04-results.qmd
    - 05-discussion.qmd
    - references.qmd
```

Each person works on their own chapter file. Merge conflicts only
arise when two people genuinely edit the same chapter.

### Roles (optional)

Useful in larger teams:

- **Ingest role:** processes new sources, maintains the wiki. Ensures
  consistent style and frontmatter.
- **Synthesis role:** works on Synthesis pages and prepares manuscript
  sections.
- **Lint role:** runs periodic maintenance.
- **Maintainer:** reviews merge requests, manages `main`.

One person can hold several roles. What matters is that it is clear
who reviews which merge request.

## Research question and project description

The central research question and project description live in
`input/description/`. The LLM reads this folder at the start of every
session before doing anything else.

**Instruction to the LLM agent:** read all Markdown files in
`input/description/` and use the research question, methodology, and
scope defined there as a guide for:
- **Ingest:** assess the relevance of new sources against the research
  question. Prioritise aspects that contribute to answering it.
- **Query:** tie answers back to the research question.
- **Synthesis:** build Synthesis pages along the line of argument that
  follows from the research question.
- **Lint:** check whether wiki pages contribute to the research
  question or drift off topic.

## Project-specific conventions

### Geospatial data and coordinates

When researching coordinates for places, sites, or other geographic
objects, the following rules apply:

- **Cross-check multiple times.** Never take coordinates from a single
  source. Compare at least two independent sources (e.g. GeoNames,
  Pleiades, PEQ, Wikipedia, official surveys, published excavation
  reports).
- **Prefer directly found coordinates.** When a source gives explicit
  coordinates (e.g. from an excavation report or a GIS database), prefer
  those over derived coordinates (e.g. the centre of a coarse map, a
  rough location based on place descriptions, LLM-generated guesses).
- **Document accuracy.** In entity pages for places, record the source
  of the coordinates and the estimated accuracy:
  - `exact` — from GPS measurement or a high-resolution GIS database
  - `verified` — from at least two agreeing sources
  - `approximate` — from a single source or derived
  - `uncertain` — only rough location possible
- **Coordinate format:** decimal degrees (WGS 84), e.g. `32.5847, 35.1749`.

> [Add further project-specific rules here:
> - Preferred language(s) for wiki pages
> - Domain terminology and abbreviations
> - Special page types (e.g. site, stratigraphy)
> - Data formats and standards]
