# Makefile für Quarto-Präsentation
# Verwendung: make slides | make pptx | make beamer | make beamer-latex | make handout | make all | make clean

QUARTO := quarto
SOURCE := vortrag.qmd
OUTPUT_DIR := _output

.PHONY: all slides pptx beamer beamer-latex handout clean preview help

## Alle Formate gleichzeitig bauen
all: slides pptx beamer handout

## Reveal.js HTML-Slides (Standardformat für Vorträge)
slides:
	$(QUARTO) render $(SOURCE) --to revealjs --output-dir $(OUTPUT_DIR)

## PowerPoint
pptx:
	$(QUARTO) render $(SOURCE) --to pptx --output-dir $(OUTPUT_DIR)

## LaTeX Beamer PDF
beamer:
	$(QUARTO) render $(SOURCE) --to beamer --output-dir $(OUTPUT_DIR)

## LaTeX Beamer Quellcode (ohne PDF-Kompilierung)
beamer-latex:
	$(QUARTO) render $(SOURCE) --to beamer --no-compile --output-dir $(OUTPUT_DIR)

## Handout (A4 PDF mit allen Inhalten, kein Folienformat)
handout:
	$(QUARTO) render $(SOURCE) --to pdf --output-dir $(OUTPUT_DIR)

## Live-Vorschau der Slides im Browser
preview:
	$(QUARTO) preview $(SOURCE)

## Build-Artefakte entfernen
clean:
	rm -rf $(OUTPUT_DIR)
	rm -rf .quarto
	rm -f *.tex *.log *.aux *.nav *.snm *.toc *.vrb

## Hilfe anzeigen
help:
	@echo "Verfügbare Targets:"
	@echo "  make slides       — Reveal.js HTML-Slides"
	@echo "  make pptx         — PowerPoint-Datei"
	@echo "  make beamer       — LaTeX Beamer PDF"
	@echo "  make beamer-latex — LaTeX Beamer Quellcode (.tex)"
	@echo "  make handout      — Handout (A4 PDF)"
	@echo "  make all          — Alle Formate"
	@echo "  make preview      — Live-Vorschau (Reveal.js)"
	@echo "  make clean        — Build-Artefakte entfernen"
