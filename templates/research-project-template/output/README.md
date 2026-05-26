# Output-Vorlagen: Abhängigkeiten

## Erforderliche Software

### Quarto (alle Vorlagen)
```bash
# macOS
brew install quarto

# Oder direkt von https://quarto.org/docs/get-started/
```

### LaTeX (für PDF-Ausgabe)
```bash
# Empfohlen: TinyTeX via Quarto
quarto install tinytex

# Alternativ: MacTeX (vollständig, ~4 GB)
brew install --cask mactex
```

### Fonts (für PDF mit KOMA-Script)

Die Vorlagen verwenden folgende Fonts, die ggf. installiert
werden müssen:

```bash
# Linux Libertine / Linux Biolinum (Fließtext)
# Download: https://libertine-fonts.org/
# macOS: .otf-Dateien in ~/Library/Fonts/ kopieren

# Fira Code (Monospace / Code)
brew install font-fira-code
# Oder: https://github.com/tonsky/FiraCode/releases
```

**Falls die Fonts nicht installiert werden sollen**, können die
`mainfont`, `sansfont` und `monofont`-Einträge in `_quarto.yml`
bzw. im Frontmatter der `.qmd`-Dateien entfernt oder durch
System-Fonts ersetzt werden. Quarto verwendet dann die
LaTeX-Standardschriften.

### Python (für Lint-Skript)
```bash
# PyYAML wird für lint-wiki.py benötigt
pip install pyyaml
```

## Schnelltest

```bash
# Wiki als Website bauen
cd knowledge && make wiki

# Artikel als PDF bauen
cd output/publication/article && make pdf

# Buch als HTML bauen
cd output/publication/book && make html

# Präsentation als Reveal.js bauen
cd output/presentation && make slides
```
