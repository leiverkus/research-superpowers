# Makefile for the Quarto article
# Usage: make pdf | make latex | make html | make docx | make all | make clean

QUARTO := quarto
SOURCE := article.qmd
OUTPUT_DIR := _output

.PHONY: all pdf latex html docx clean preview help

## Build all formats at once
all: pdf html docx

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
	rm -f *.tex *.log *.aux

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
