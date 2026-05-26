# Makefile für Quarto-Buchprojekt
# Verwendung: make pdf | make latex | make html | make docx | make epub | make all | make clean

QUARTO := quarto
OUTPUT_DIR := _output

.PHONY: all pdf latex html docx epub clean preview help

## Alle Formate gleichzeitig bauen
all: pdf html docx epub

## PDF (KOMA-Script scrbook)
pdf:
	$(QUARTO) render --to pdf

## LaTeX-Quellcode (ohne PDF-Kompilierung)
latex:
	$(QUARTO) render --to pdf --no-compile --output-dir $(OUTPUT_DIR)

## HTML-Website
html:
	$(QUARTO) render --to html

## Word-Dokument
docx:
	$(QUARTO) render --to docx

## E-Book
epub:
	$(QUARTO) render --to epub

## Live-Vorschau im Browser (HTML)
preview:
	$(QUARTO) preview

## Build-Artefakte entfernen
clean:
	rm -rf $(OUTPUT_DIR)
	rm -rf .quarto

## Hilfe anzeigen
help:
	@echo "Verfügbare Targets:"
	@echo "  make pdf      — PDF mit KOMA-Script (scrbook)"
	@echo "  make latex    — LaTeX-Quellcode (.tex)"
	@echo "  make html     — HTML-Website"
	@echo "  make docx     — Word-Dokument"
	@echo "  make epub     — E-Book"
	@echo "  make all      — Alle Formate"
	@echo "  make preview  — Live-Vorschau (HTML)"
	@echo "  make clean    — Build-Artefakte entfernen"
