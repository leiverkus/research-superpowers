# Makefile for the research wiki (Quarto website)
# Usage: make wiki | make preview | make clean

QUARTO := quarto

.PHONY: wiki preview clean help

## Build the wiki as an HTML website
wiki:
	$(QUARTO) render

## Live preview in the browser
preview:
	$(QUARTO) preview

## Remove build artefacts
clean:
	rm -rf _site
	rm -rf .quarto

## Show help
help:
	@echo "Available targets:"
	@echo "  make wiki     — build the wiki as an HTML website"
	@echo "  make preview  — live preview in the browser"
	@echo "  make clean    — remove build artefacts"
