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

The templates use the following fonts, which may need to be installed:

```bash
# Linux Libertine / Linux Biolinum (body text)
# Download: https://libertine-fonts.org/
# macOS: copy .otf files into ~/Library/Fonts/

# Fira Code (monospace / code)
brew install font-fira-code
# Or: https://github.com/tonsky/FiraCode/releases
```

**If you do not want to install the fonts**, the `mainfont`, `sansfont`,
and `monofont` entries in `_quarto.yml` or in the frontmatter of the
`.qmd` files can be removed or replaced with system fonts. Quarto will
then use the LaTeX default fonts.

### Python (for the lint script)
```bash
# PyYAML is required for lint-wiki.py
pip install pyyaml
```

## Quick test

```bash
# Build the article as PDF
cd output/publication/article && make pdf

# Build the book as HTML
cd output/publication/book && make html

# Build the presentation as Reveal.js
cd output/presentation && make slides
```
