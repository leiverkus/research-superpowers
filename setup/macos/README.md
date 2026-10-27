# Setting up a Mac for research-superpowers

One command does everything that can be automated. It is safe to run again; it
skips what is already there.

From a clone of this repository:

```bash
bash setup/macos/setup-macos.sh
```

Without a clone:

```bash
curl -fsSL https://raw.githubusercontent.com/leiverkus/research-superpowers/main/setup/macos/setup-macos.sh | bash
```

Without the optional pieces (GitHub CLI, Claude desktop app):

```bash
SKIP_OPTIONAL=1 bash setup/macos/setup-macos.sh
```

What Homebrew installs is listed in the [`Brewfile`](Brewfile). The script adds
what Homebrew cannot do, and ends with a check of every piece.

## What you need, and what for

### Required: the plugin does not run without these

| What | How | What for |
|---|---|---|
| Xcode Command Line Tools | `xcode-select --install` | `git`, `make`, compilers |
| Homebrew | [brew.sh](https://brew.sh) | installs everything else |
| Git | `brew "git"` | project repositories, the plugin marketplace |
| Python ≥ 3.10 | `brew "python"` | `lint-wiki.py`, `wiki-to-graph.py`, `bib-search.py`, the drift check at session start. macOS's own `/usr/bin/python3` (3.9) is too old. |
| PyYAML | `pip install --user` into Homebrew's Python (the script does it) | the one library the wiki scripts need; there is no Homebrew formula for it |
| Claude Code | `cask "claude-code"` | the plugin runs inside it |
| research-superpowers | `claude plugin install research-superpowers@leiverkus-research` (the script does it) | the plugin itself |

### For working with source PDFs

| What | How | What for |
|---|---|---|
| Poppler | `brew "poppler"` | `pdftotext`, `pdfinfo`, `pdfimages`: reading sources, the full-text index (`bib-search`), `add-to-library` |
| Ghostscript | `brew "ghostscript"` | `scripts/optimize-pdf.py` |
| OCRmyPDF + language data | `brew "ocrmypdf"`, `brew "tesseract-lang"` | a text layer for scanned PDFs, which the drift report and `bib-search` flag. The language data (German, Hebrew, …) is about 650 MB. |

### For manuscripts (article, book, talk)

| What | How | What for |
|---|---|---|
| Quarto | `cask "quarto"` | renders `output/**/*.qmd` to PDF, HTML and DOCX; pandoc included |
| TeX (TinyTeX) | `quarto install tinytex` (the script does it) | PDF output with KOMA-Script; Quarto fetches missing LaTeX packages on the first render |
| Fonts | `font-gentium-plus`, `font-noto-sans`, `font-fira-code`, `font-ezra-sil` | the templates set them: Gentium Plus for transliteration (ḥ ṣ ṭ ʾ ʿ), Noto Sans for headings, Fira Code for code, Ezra SIL for Hebrew |

### For editing

| What | How | What for |
|---|---|---|
| Zettlr | `cask "zettlr"` | Markdown editor for wiki pages (`knowledge/`), notes (`input/`) and `.qmd` drafts. It reads YAML frontmatter, `[[wikilinks]]` and `@citekeys`. For citation previews, add the project's or the library's `references.bib` under *Preferences → Citations*. |

### Recommended

| What | How | What for |
|---|---|---|
| uv | `brew "uv"` | provides `uvx`, which starts the MCP server |
| dao-paper-search MCP | `claude mcp add …` (the script asks) | search in Zenon, IxTheo, IAA, ADAJ, Propylaeum, Gnomon; verified citation lines; authority IDs (GND, Wikidata, iDAI.gazetteer). Version `1.2.0`, whose direct DOI lookup the skills rely on. See [`docs/recommended-mcps.md`](../../docs/recommended-mcps.md). |
| CORE API key | free at [core.ac.uk/services/api](https://core.ac.uk/services/api) | only for `search_core` |
| Shared PDF library | a folder, its path as one line in `~/.config/research-superpowers/library` (the script asks) | every project shares `references.bib` and `pdf/<bibkey>.pdf` |

### Optional

| What | How | What for |
|---|---|---|
| GitHub CLI | `brew "gh"` | pull requests and releases of your own repositories |
| Claude desktop app | `cask "claude"` | Cowork, the Code tab |
| Graphviz | `brew "graphviz"` (commented out in the Brewfile) | plugin maintainers only: regenerate `docs/assets/phase-flow.svg` |
| dao-searxng MCP | your own SearXNG instance (Docker) | web search with source classes; see [`docs/recommended-mcps.md`](../../docs/recommended-mcps.md) |

## What the script cannot do for you

- **Sign in to Claude.** `claude auth login` opens the browser.
- **API key and e-mail** for the MCP server are yours to enter. The key is read
  without echo and stored only in your Claude configuration.
- **Paywalled PDFs** come through your university's VPN or library proxy;
  `acquire-sources` writes the list.

## Keeping it current

```bash
brew update && brew upgrade
```

```bash
claude plugin marketplace update leiverkus-research && claude plugin update research-superpowers@leiverkus-research
```

The `claude-code` cask is updated only by `brew upgrade`; it does not update
itself. Keep **one** Claude Code install, the Homebrew cask or the native
installer (`~/.local/bin/claude`), or two versions run side by side.

An app already installed outside Homebrew (for example the Claude desktop app)
makes `brew bundle` stop with "already exists". Run with `SKIP_OPTIONAL=1`, or
hand the app to Homebrew once with `brew install --cask --adopt claude`.
