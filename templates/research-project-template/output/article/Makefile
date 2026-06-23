# Makefile for the Quarto article
# Usage: make pdf | make latex | make html | make docx | make all | make clean

QUARTO := quarto
SOURCE := article.qmd
OUTPUT_DIR := _output

.PHONY: all pdf latex html docx clean preview help

## Build all formats at once.
## NOTE: must be a single `quarto render` call. Quarto cleans the output
## directory on every render, so chaining separate per-format renders
## (all: pdf html docx) would leave only the last format — the earlier
## outputs get deleted. `--to all` renders every format declared in the
## qmd front matter in one pass, side by side.
all:
	$(QUARTO) render $(SOURCE) --to all --output-dir $(OUTPUT_DIR)

## PDF (KOMA-Script scrartcl)
pdf:
	$(QUARTO) render $(SOURCE) --to pdf --output-dir $(OUTPUT_DIR)

## LaTeX source (without PDF compilation)
latex:
	$(QUARTO) render $(SOURCE) --to pdf --no-compile --output-dir $(OUTPUT_DIR)

## HTML
html:
	$(QUARTO) render $(SOURCE) --to html --output-dir $(OUTPUT_DIR)

## Word document
docx:
	$(QUARTO) render $(SOURCE) --to docx --output-dir $(OUTPUT_DIR)

## Live preview in the browser (HTML)
preview:
	$(QUARTO) preview $(SOURCE)

## Remove build artefacts
clean:
	rm -rf $(OUTPUT_DIR)
	rm -rf .quarto
	# Remove generated .tex (whatever its name) but never the hand-authored
	# _preamble.tex. Runtime find sees the actual files, so this is robust
	# regardless of any output-file override.
	find . -maxdepth 1 -name '*.tex' ! -name '_preamble.tex' -delete
	rm -f *.log *.aux

## Show help
help:
	@echo "Available targets:"
	@echo "  make pdf      — PDF with KOMA-Script (scrartcl)"
	@echo "  make latex    — LaTeX source (.tex)"
	@echo "  make html     — HTML page"
	@echo "  make docx     — Word document"
	@echo "  make all      — All formats"
	@echo "  make preview  — Live preview (HTML)"
	@echo "  make clean    — Remove build artefacts"
