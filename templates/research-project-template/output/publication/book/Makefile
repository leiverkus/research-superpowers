# Makefile for the Quarto book project
# Usage: make pdf | make latex | make html | make docx | make epub | make all | make clean

QUARTO := quarto
OUTPUT_DIR := _output

.PHONY: all pdf latex html docx epub clean preview help

## Build all formats at once
all: pdf html docx epub

## PDF (KOMA-Script scrbook)
pdf:
	$(QUARTO) render --to pdf

## LaTeX source (without PDF compilation)
latex:
	$(QUARTO) render --to pdf --no-compile --output-dir $(OUTPUT_DIR)

## HTML website
html:
	$(QUARTO) render --to html

## Word document
docx:
	$(QUARTO) render --to docx

## E-book
epub:
	$(QUARTO) render --to epub

## Live preview in the browser (HTML)
preview:
	$(QUARTO) preview

## Remove build artefacts
clean:
	rm -rf $(OUTPUT_DIR)
	rm -rf .quarto

## Show help
help:
	@echo "Available targets:"
	@echo "  make pdf      — PDF with KOMA-Script (scrbook)"
	@echo "  make latex    — LaTeX source (.tex)"
	@echo "  make html     — HTML website"
	@echo "  make docx     — Word document"
	@echo "  make epub     — E-book"
	@echo "  make all      — All formats"
	@echo "  make preview  — Live preview (HTML)"
	@echo "  make clean    — Remove build artefacts"
