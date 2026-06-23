# Makefile for the Quarto presentation
# Usage: make slides | make pptx | make beamer | make beamer-latex | make handout | make all | make clean

QUARTO := quarto
SOURCE := talk.qmd
OUTPUT_DIR := _output

.PHONY: all slides pptx beamer beamer-latex handout clean preview help

## Build all formats at once.
## A talk declares TWO PDF formats (beamer slides + pdf handout). They cannot
## be built the way article/book are:
##   - `quarto render --to all` fails: beamer and pdf both compile a LaTeX
##     intermediate named talk.tex, which collides within the single pass.
##   - Separate renders into the SAME --output-dir wipe each other: Quarto
##     cleans the output dir at the start of every render.
## In-place renders (no --output-dir) do NOT clean the directory, and each
## format is a separate invocation (so no talk.tex collision). So: render each
## in place, then collect the artefacts into _output. Fails loud if any render
## fails (make stops on the first non-zero exit).
all:
	$(QUARTO) render $(SOURCE) --to revealjs
	$(QUARTO) render $(SOURCE) --to pptx
	$(QUARTO) render $(SOURCE) --to beamer
	$(QUARTO) render $(SOURCE) --to pdf
	@mkdir -p $(OUTPUT_DIR)
	@mv -f $(SOURCE:.qmd=).html $(SOURCE:.qmd=).pptx *.pdf $(OUTPUT_DIR)/ 2>/dev/null || true
	@rm -rf $(OUTPUT_DIR)/$(SOURCE:.qmd=)_files; mv -f $(SOURCE:.qmd=)_files $(OUTPUT_DIR)/ 2>/dev/null || true
	@echo "Built all formats into $(OUTPUT_DIR)/:"; ls -1 $(OUTPUT_DIR)/

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
	# Remove generated .tex (whatever its name — beamer/pdf use output-file
	# overrides) but never a hand-authored _preamble.tex. Runtime find sees
	# the actual files, so this is robust regardless of the name.
	find . -maxdepth 1 -name '*.tex' ! -name '_preamble.tex' -delete
	rm -f *.log *.aux *.nav *.snm *.toc *.vrb

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
