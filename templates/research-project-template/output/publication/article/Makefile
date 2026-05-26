# Makefile für Quarto-Artikel
# Verwendung: make pdf | make latex | make html | make docx | make all | make clean

QUARTO := quarto
SOURCE := artikel.qmd
OUTPUT_DIR := _output

.PHONY: all pdf latex html docx clean preview help

## Alle Formate gleichzeitig bauen
all: pdf html docx

## PDF (KOMA-Script scrartcl)
pdf:
	$(QUARTO) render $(SOURCE) --to pdf --output-dir $(OUTPUT_DIR)

## LaTeX-Quellcode (ohne PDF-Kompilierung)
latex:
	$(QUARTO) render $(SOURCE) --to pdf --no-compile --output-dir $(OUTPUT_DIR)

## HTML
html:
	$(QUARTO) render $(SOURCE) --to html --output-dir $(OUTPUT_DIR)

## Word-Dokument
docx:
	$(QUARTO) render $(SOURCE) --to docx --output-dir $(OUTPUT_DIR)

## Live-Vorschau im Browser (HTML)
preview:
	$(QUARTO) preview $(SOURCE)

## Build-Artefakte entfernen
clean:
	rm -rf $(OUTPUT_DIR)
	rm -rf .quarto
	rm -f *.tex *.log *.aux

## Hilfe anzeigen
help:
	@echo "Verfügbare Targets:"
	@echo "  make pdf      — PDF mit KOMA-Script (scrartcl)"
	@echo "  make latex    — LaTeX-Quellcode (.tex)"
	@echo "  make html     — HTML-Seite"
	@echo "  make docx     — Word-Dokument"
	@echo "  make all      — Alle Formate"
	@echo "  make preview  — Live-Vorschau (HTML)"
	@echo "  make clean    — Build-Artefakte entfernen"
