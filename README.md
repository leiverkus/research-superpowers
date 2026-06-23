# research-superpowers

[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.15.1-blue.svg)](CHANGELOG.md)
[![Plugin for: Claude Code + OpenCode](https://img.shields.io/badge/plugin-Claude%20Code%20%2B%20OpenCode-purple.svg)](#installation)
[![Lint](https://github.com/leiverkus/research-superpowers/actions/workflows/lint.yml/badge.svg?branch=main)](https://github.com/leiverkus/research-superpowers/actions/workflows/lint.yml)

A Claude Code / OpenCode plugin that turns LLM-assisted research into a disciplined, reproducible workflow.

Inspired by [obra/superpowers](https://github.com/obra/superpowers), adapted to the research lifecycle: **idea → plan → literature → ingest → analysis → draft → peer review → publication**.

Built for theology, biblical archaeology, ancient history, and digital humanities — methodology-aware (hermeneutic / quantitative / mixed) so it doesn't force quantitative pre-registration onto hermeneutic work, but enforces it where it belongs.

## Why

LLM-assisted research is fast but easy to get wrong:

- Citations get hallucinated. Author–year strings drift from what the source actually says.
- Synthesis pages get written from memory of the source, not the source itself.
- The "I'll cite this properly later" moment never returns.
- Pre-registration norms from quantitative psychology get jammed into hermeneutic disciplines where the hermeneutic circle is constitutive, not a methodological failure.
- "Don't cite academia.edu as a primary source" stays as a red flag the model ignores, until a structural mechanism makes it enforceable.

`research-superpowers` makes the discipline structural:

- **14 skills** with checklists, SOFT-GATES, and red-flag tables for every phase
- **6 subagents** for context-isolated heavy lifting (ingest, draft, review, analysis, literature search, lint)
- **Frontmatter schema** that the linter validates and your editor live-checks
- **Methodology branching** — `hermeneutic` projects skip frozen-hypothesis pre-registration; `quantitative` keeps it; `mixed` is per sub-study
- **Audit-trail SOFT-GATES** that prompt for a written override reason and log it, instead of silently blocking
- **Two recommended MCPs** for verified citations and web source-class detection (optional; plugin works without them)

## Who is this for

- **Researchers in theology, biblical archaeology, ancient history, digital humanities** who want LLM help without losing the discipline their field expects from a manuscript.
- **Anyone running mixed-methods projects** where some sub-studies need formal pre-registration and others legitimately don't.
- **Teams** who want a shared schema for their research wiki, with structural checks (frontmatter validation, wikilink resolution, override-rate tracking).

If you write Python ML papers with frozen RCT hypotheses, this plugin's discipline machinery is overkill (use a simpler workflow). If you write archaeology / theology / DH papers with contested sources and iterative reading, this is for you.

## Installation

**New here?** The full [`docs/installation.md`](docs/installation.md) walks through everything step by step — prerequisites, the three install paths, verification, troubleshooting. Allow 5–10 minutes.

**Cowork user or no terminal?** [`docs/installation-cowork.md`](docs/installation-cowork.md) is the click-only path — just Claude, no Python, no Git. Allow 3–5 minutes.

**Familiar with Claude Code plugins?** Three lines:

```text
claude                                                          # open Claude Code anywhere
/plugin marketplace add leiverkus/research-superpowers          # register the marketplace
/plugin install research-superpowers@leiverkus-research         # install the plugin
```

That installs and activates it. Restart Claude Code and you'll see a "Research Superpowers" notice at session start.

### Other install paths

- **Direct from GitHub** (no marketplace registration):
  ```
  /plugin install https://github.com/leiverkus/research-superpowers
  ```
- **Local clone** (for development or customisation):
  ```bash
  git clone https://github.com/leiverkus/research-superpowers ~/code/research-superpowers
  ```
  then in Claude Code:
  ```
  /plugin install ~/code/research-superpowers
  ```
- **OpenCode**: symlink `skills/` into your project's `.claude/skills/` — OpenCode reads SKILL.md files natively. Details in [`docs/installation.md`](docs/installation.md#recommended-path-for-opencode-users).

### Prerequisites

- [Claude Code](https://docs.claude.com/en/docs/claude-code) 2.x or newer
- Python 3.10+ with PyYAML (`python3 -m pip install --user pyyaml`)
- Git

If any are missing, [`docs/installation.md`](docs/installation.md#before-you-start) shows how to install each.

**For PDF output only** (Quarto/XeLaTeX — not needed for HTML or the wiki): the
templates ship with free, OFL-licensed fonts tuned for scholarly transcription
of Semitic languages — Latin transliteration (ḥ ṣ ṭ ʾ ʿ ā ī ū), polytonic
Greek, and native Hebrew (RTL):

```bash
# macOS (Homebrew casks)
brew install --cask font-gentium-plus font-noto-sans font-fira-code
# Ezra SIL (Hebrew) has no cask — download from https://software.sil.org/ezra/
# and copy the .ttf into ~/Library/Fonts/
```

| Role | Font | Covers |
|------|------|--------|
| body | **Gentium Plus** | Latin transliteration + polytonic Greek |
| headings | **Noto Sans** | transliterated terms incl. ʾ / ʿ |
| code | **Fira Code** | monospace |
| Hebrew (RTL) | **Ezra SIL** | native Hebrew with niqqud/cantillation |

Full install + usage notes (incl. the Hebrew `\foreignlanguage` macro) are in
the template's [`output/README.md`](templates/research-project-template/output/README.md).

### Create your first research project

After the plugin is installed, scaffold a project from the template:

```bash
cp -r ~/.claude/plugins/cache/leiverkus-research/research-superpowers/templates/research-project-template ~/Documents/my-first-project
cd ~/Documents/my-first-project
```

Edit the three frontmatter lines at the top of `CLAUDE.md` (`methodology`, `discipline`, `languages`), then run `claude` in the project root. You're ready — head to the [Quickstart](docs/quickstart.md) for your first ingest.

### Recommended (optional): MCPs for verified citations

Two MCP servers by the same author add structurally verified citations and source-class detection. The plugin works without them. See [`docs/recommended-mcps.md`](docs/recommended-mcps.md) for setup.

## 30-second example

In a research project (scaffold one from `templates/research-project-template/`), drop a PDF into `input/bibliography/` and tell Claude Code:

> Ingest the Finkelstein 2003 PDF.

The `ingest-source` skill triggers, reads the PDF fully, derives slug `finkelstein-2003`, extracts bibliographic data and entities (people, places, concepts), and writes:

- `knowledge/sources/finkelstein-2003.md` — structured wiki page (theses, methodology, verbatim quotes with pages, mentioned entities)
- one stub `knowledge/entities/<entity>.md` per new entity
- one BibTeX entry in `output/bibtex/references.bib`
- one log line in `knowledge/_meta/log.md`
- runs `python scripts/lint-wiki.py` — exits 0

You review the diff, accept or revise, commit. Repeat per source. After ~5 sources, synthesise. After synthesis is `status: stable`, draft. Every claim cites a source page; every citation resolves in BibTeX; every render is checked.

Full walkthrough: [`docs/tutorial.md`](docs/tutorial.md).

## Skill topology

```
brainstorming-research → writing-research-plan → literature-review ⇄ ingest-source
   → executing-research-plan → drafting-manuscript → requesting-peer-review → finishing-a-research-project
```

| Skill | Phase | What it does |
|---|---|---|
| `brainstorming-research` | Idea | Turns a vague interest into an approvable design doc |
| `writing-research-plan` | Plan | Design → research plan (methodology-aware: hermeneutic vs quantitative templates) |
| `literature-review` | Discovery | Strategic search across DAO + cross-platform databases, produces literature guide + BibTeX |
| `ingest-source` | Intake | One PDF → wiki source page + entities + BibTeX + log |
| `executing-research-plan` | Execution | Routes tasks to subagents; methodology-aware review tiers |
| `drafting-manuscript` | Drafting | Stable syntheses → publishable prose with inline citations, render-checked |
| `requesting-peer-review` | Review | Two-stage (constructive + adversarial) with discipline-specific checklists |
| `finishing-a-research-project` | Closing | 13-item closing checklist, DOI, archive |

Cross-cutting (context-triggered, no phase binding):

| Skill | Purpose |
|---|---|
| `wiki-lint` | Structural validation (frontmatter, wikilinks, override rate) — runs `scripts/lint-wiki.py` |
| `wiki-graph` | Structure analysis — runs `scripts/wiki-to-graph.py`; god nodes, bridges, clusters; exports graph.json / graph.graphml |
| `semantic-wiki-review` | LLM content audit (contradictions, stale syntheses, aggregator citations) |
| `grant-finder` | DFG / ERC / VolkswagenStiftung / Henkel / Thyssen funding-landscape mapping |

Subagents (`agents/<name>.md`) provide context isolation for heavy tasks; each declares `implements: <skill-name>` and never duplicates the skill's checklist.

Phase graph with hermeneutic back-edges and SOFT-GATE semantics: [`docs/phase-flow.md`](docs/phase-flow.md).

## Documentation

| File | Purpose |
|---|---|
| [`docs/installation.md`](docs/installation.md) | Step-by-step install with prerequisites, paths, troubleshooting |
| [`docs/installation-cowork.md`](docs/installation-cowork.md) | Click-only install path for Cowork / non-terminal users |
| [`docs/quickstart.md`](docs/quickstart.md) | 5 minutes from install to first ingest |
| [`docs/tutorial.md`](docs/tutorial.md) | End-to-end walkthrough on a realistic mini-project |
| [`docs/concepts.md`](docs/concepts.md) | SOFT-GATE pattern, methodology branching, SOT pattern — the *why* |
| [`docs/recommended-mcps.md`](docs/recommended-mcps.md) | Optional MCP setup (verified citations + source-class detection) |
| [`docs/frontmatter-schema.md`](docs/frontmatter-schema.md) | Pointer to the central JSON schema |
| [`docs/phase-flow.md`](docs/phase-flow.md) | Graph of phases with back-edges and SOFT-GATEs |
| [`docs/skill-contract.md`](docs/skill-contract.md) | SOT pattern + `inputs:` / `outputs:` frontmatter |
| [`docs/skill-authoring.md`](docs/skill-authoring.md) | How to add or change a skill |
| [`CHANGELOG.md`](CHANGELOG.md) | Full version history |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | How to contribute (language convention, PR checklist) |

## Repository layout

```
research-superpowers/
├── README.md                     # this file
├── LICENSE                       # MIT
├── CHANGELOG.md
├── CONTRIBUTING.md
├── .gitignore
├── .claude-plugin/plugin.json    # plugin manifest
├── schema/
│   ├── knowledge-frontmatter.schema.json
│   └── README.md
├── hooks/                        # SessionStart hook injects the skill index
├── skills/                       # 12 SKILL.md files (the SOT for each workflow)
├── agents/                       # 6 thin-pointer subagents
├── templates/research-project-template/
│   ├── CLAUDE.md                 # frontmatter declares methodology + discipline
│   ├── schema/                   # mirror of plugin schema (for project-local lint)
│   ├── scripts/lint-wiki.py      # validates against the schema; reports override rate
│   └── .vscode/settings.json     # yaml.schemas → live frontmatter validation
├── examples/example-project/     # a small worked example
└── docs/                         # the docs listed above
```

## Versioning

[Semantic Versioning](https://semver.org/). At `0.x.y`, minor versions may include breaking changes when they buy real architectural clarity (see [`CHANGELOG.md`](CHANGELOG.md) — v0.2 was a major architecture overhaul). Patch versions are additive. Once we reach `1.0.0`, strict semver applies.

## License

MIT, Patrick Leiverkus, 2026. See [`LICENSE`](LICENSE).
