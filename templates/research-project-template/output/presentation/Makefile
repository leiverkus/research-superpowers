# Makefile for the Quarto presentation
# Usage: make slides | make pptx | make beamer | make beamer-latex | make handout | make all | make clean

QUARTO := quarto
SOURCE := talk.qmd
OUTPUT_DIR := _output

.PHONY: all slides pptx beamer beamer-latex handout clean preview help

## Build all formats at once
all: slides pptx beamer handout

## Reveal.js HTML slides (default format for talks)
slides:
	$(QUARTO) render $(SOURCE) --to revealjs --output-dir $(OUTPUT_DIR)

## PowerPoint
pptx:
	$(QUARTO) render $(SOURCE) --to pptx --output-dir $(OUTPUT_DIR)

## LaTeX Beamer PDF
beamer:
	$(QUARTO) render $(SOURCE) --to beamer --output-dir $(OUTPUT_DIR)

## LaTeX Beamer source (without PDF compilation)
beamer-latex:
	$(QUARTO) render $(SOURCE) --to beamer --no-compile --output-dir $(OUTPUT_DIR)

## Handout (A4 PDF with all content, not slide format)
handout:
	$(QUARTO) render $(SOURCE) --to pdf --output-dir $(OUTPUT_DIR)

## Live preview of the slides in the browser
preview:
	$(QUARTO) preview $(SOURCE)

## Remove build artefacts
clean:
	rm -rf $(OUTPUT_DIR)
	rm -rf .quarto
	rm -f *.tex *.log *.aux *.nav *.snm *.toc *.vrb

## Show help
help:
	@echo "Available targets:"
	@echo "  make slides       — Reveal.js HTML slides"
	@echo "  make pptx         — PowerPoint file"
	@echo "  make beamer       — LaTeX Beamer PDF"
	@echo "  make beamer-latex — LaTeX Beamer source (.tex)"
	@echo "  make handout      — Handout (A4 PDF)"
	@echo "  make all          — All formats"
	@echo "  make preview      — Live preview (Reveal.js)"
	@echo "  make clean        — Remove build artefacts"
