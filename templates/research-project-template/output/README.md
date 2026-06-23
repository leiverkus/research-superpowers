# Output templates: dependencies

## Required software

### Quarto (all templates)
```bash
# macOS
brew install quarto

# Or directly from https://quarto.org/docs/get-started/
```

### LaTeX (for PDF output)
```bash
# Recommended: TinyTeX via Quarto
quarto install tinytex

# Alternative: MacTeX (full, ~4 GB)
brew install --cask mactex
```

### Fonts (for PDF with KOMA-Script)

The PDF build uses a Unicode TeX engine (**XeLaTeX or LuaLaTeX** — Quarto
selects one automatically once `mainfont` is set; both work with the setup
below). The templates are tuned for scholarly transcription of Semitic
languages —
academic Latin transliteration (ḥ ṣ ṭ ḏ ṯ ḫ ġ ā ī ū š, plus ʾ / ʿ for
aleph/ayin), polytonic Greek, and native Hebrew (RTL). All chosen fonts are
free and OFL-licensed, so they can be redistributed with the project.

```bash
# Gentium Plus — main body font: Latin transliteration + polytonic Greek
#   (SIL, OFL). One font covers both, so Greek quotations need no extra setup.
brew install --cask font-gentium-plus
# Or: https://software.sil.org/gentium/

# Ezra SIL — native Hebrew (BHS-style, with niqqud and cantillation marks)
#   (SIL, OFL). Used for RTL Hebrew via the babel block in _preamble.tex.
#   Download https://software.sil.org/ezra/ and copy the .ttf into
#   ~/Library/Fonts/ (macOS) or ~/.fonts/ (Linux).

# Noto Sans (sans / headings) — broad diacritic coverage (incl. ʾ / ʿ) for
#   transliterated section titles; pairs cleanly with Gentium Plus (OFL).
brew install --cask font-noto-sans

# Fira Code (monospace / code)
brew install --cask font-fira-code
# Or: https://github.com/tonsky/FiraCode/releases
```

Using native Hebrew in a paragraph (Greek just works in the main font):

```markdown
The opening word is \foreignlanguage{hebrew}{בְּרֵאשִׁית} ("in the beginning").
```

The `\foreignlanguage{hebrew}{…}` macro is enabled by the Hebrew babel block
in `article/_preamble.tex` and `book/template/_preamble.tex`. On a minimal
TeX install (TinyTeX) the Hebrew language data may need to be pulled in once:
`tlmgr install babel-hebrew hyphen-hebrew`. The
**presentation** (`talk.qmd`) uses Gentium Plus for transliteration and Greek
but has no Hebrew babel block — add the same two lines to a Beamer header if a
talk needs native Hebrew.

**If you do not want to install the fonts**, the `mainfont`, `sansfont`,
and `monofont` entries in `_quarto.yml` or in the frontmatter of the
`.qmd` files can be removed or replaced with system fonts (and the Hebrew
block dropped from the preambles). Quarto will then use the LaTeX default
fonts — but transcription coverage of the diacritics above is not guaranteed.

### Python (for the lint script)
```bash
# PyYAML is required for lint-wiki.py
pip install pyyaml
```

## Quick test

```bash
# Build the article as PDF
cd output/article && make pdf

# Build the book as HTML
cd output/book && make html

# Build the presentation as Reveal.js
cd output/presentation && make slides
```
