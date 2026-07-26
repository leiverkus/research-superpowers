---
name: add-to-library
description: Add ONE document (a PDF) directly to the shared master library — outside the project ingest flow. Auto-discovers the bibliographic metadata, VERIFIES it against Crossref/OpenAlex (never guessing), derives keywords cheaply from the PDF's docinfo + first-page abstract (no full read), computes the canonical bibkey, places the PDF at <library>/pdf/<bibkey>.pdf and appends the entry to <library>/references.bib. Stops and asks when metadata cannot be verified. Triggers on "add this PDF to the library", "add to the master bibliography", "put this straight in the library", "füge das Dokument der Bibliothek hinzu", "nimm das PDF in die Bibliothek auf". NOT ingest-source (which reads a source into a project's wiki), NOT acquire-sources (which downloads a review's worklist).
inputs:
  - name: source_path
    description: Path to the single PDF to add to the library
    required: true
  - name: project_root
    description: Absolute path to a research project root (used only to resolve the shared library via scripts/library.py)
    required: true
  - name: doi
    description: DOI of the document, if already known. Skips DOI discovery from the PDF.
    required: false
  - name: bibkey
    description: Override the computed bibkey. Use only when you have a reason the autor-jahr-kurztitel rule cannot produce the right key.
    required: false
outputs:
  - path: <library>/pdf/<bibkey>.pdf
    kind: created
  - path: <library>/references.bib
    kind: appended
  - path: knowledge/_meta/log.md
    kind: appended
---

## Boundary: where this sits

`add-to-library` is the **direct-to-library** route, deliberately outside the project pipeline:

- `ingest-source` reads an acquired source **into a project's wiki** (source page + entities + a project-local BibTeX entry) with a full read. It is project-scoped.
- `acquire-sources` **downloads** the PDFs a `literature-review` guide lists.
- `add-to-library` takes **one PDF you already have** and adds it to the shared master so it surfaces in `bib-search.py` for every future project — **no wiki content, no full read.** Later, if a project actually cites it, `ingest-source` reads it as usual; the master entry is already there.

Use it when a colleague sends a PDF, or you download one, and you want it in the collection now without ingesting it.

# Add a document directly to the master library

**Announce at start:** "Using add-to-library to add `<pdf>` to the shared master library — I'll verify the metadata before writing anything."

The deterministic mechanics (compute the bibkey, place the PDF, append the entry) live in `scripts/add-to-library.py`. **Your** job is the judgement the script cannot do: verify the metadata against a real record, and curate the keywords. Never let the script mint a key from data you have not verified.

<SOFT-GATE>
Before closing, check:
(1) the metadata was **verified** against Crossref/OpenAlex (or a manual Crossref lookup) — not taken from the PDF's docinfo alone,
(2) the PDF is placed at `<library>/pdf/<bibkey>.pdf` and the bibkey follows `autor-jahr-kurztitel`,
(3) the entry is in `<library>/references.bib` with that exact key,
(4) `keywords` carries 3–8 curated terms (canonical name + aliases),
(5) `bib-search.py index` was re-run and the fused self-test (step 7: canonical name `--q` alias `--key <bibkey>`) surfaced the entry, keyword hit first,
(6) `knowledge/_meta/log.md` has an `add-to-library` line,
(7) the PDF is not egregiously oversized — `optimize-pdf.py check <pdf>` reports it unflagged, or it was optimised (`optimize-pdf.py optimize --replace`) and re-indexed. Publishers ship figures at absurd resolutions; the whole library syncs to everyone (and every LFS version is kept forever), so a bloated file is a standing cost. The shrink is reading-lossless and self-verifying (page count + text layer); the pristine file stays re-fetchable by DOI.

If a condition is unmet: name it, ask for a one-line reason, write it to `knowledge/_meta/gate-overrides.log`, and close. **Exception — never soft-gate past (1):** if the metadata cannot be verified, do not write; stop and ask.

**(1) is enforced by the script, not by your resolve.** `add-to-library.py commit` refuses without `--doi` unless you pass `--unverified-reason "…"`, and that reason is written into the entry's `note` field as `UNVERIFIED: …` — visible to everyone who ever reads that record, in every project. You cannot write an unverified entry silently.
</SOFT-GATE>

## Checklist

Create TodoWrite tasks for each:

1. **Resolve the library.** `python scripts/add-to-library.py inspect <pdf>` resolves it via `scripts/library.py`. If it reports the library is not configured, that is the machine-local `.research-library` problem — surface the message, do not proceed.

2. **Inspect the PDF (cheap).**
   ```bash
   python scripts/add-to-library.py inspect <pdf> --json
   ```
   Returns docinfo (`Title`/`Author`/`Keywords`/`Subject`), the first-page text (where the abstract lives), any DOI printed on the front pages, and `has_text_layer`.
   **⛔ Stop-and-ask** if `has_text_layer` is false **and** no DOI was found: a scan with no verifiable identifier cannot be added cheaply — OCR it first, or add it via `ingest-source`.

3. **Discover and VERIFY the metadata** (this is the load-bearing step). Prefer the `dao-paper-search-mcp` (see [`docs/recommended-mcps.md`](../../docs/recommended-mcps.md)); fall back to a manual Crossref lookup if it is absent.
   - **With a DOI** (from step 2 or the `doi` input):
     ```text
     dao-paper-search-mcp.search_crossref(doi=<doi>)
       → response.inline_citation.authoritative_bibliography_line   (verbatim)
     ```
     or manually: `curl -s https://api.crossref.org/works/<doi>`.
   - **Without a DOI:** search `search_crossref` / `search_openalex` by the title + author from docinfo, and require a **confident** single match.
   - **Cross-check the record against the PDF** — title, first author, year must match the docinfo and first page. A DOI can resolve to the wrong record; a title search can return a namesake.
   - **⛔ Stop-and-ask** on any mismatch, low confidence, or no confident match after the manual fallback. Never guess bibliographic data (the project's hard rule). Present the candidate(s) and ask.
   - Choose the entry type: `article`, `incollection` (book chapter — use `--booktitle`), `book`, `inproceedings`, … Chapter-vs-whole-book is a judgement; if the record is ambiguous, ask.

4. **Derive keywords cheaply.** From the docinfo `Keywords`/`Subject` fields (often empty or boilerplate — treat as hints) **plus** the first-page abstract text from step 2, curate **3–8** terms: the canonical name plus known synonyms and aliases across spellings and disciplines (the same discipline as `drafting-manuscript`'s "Searching for a concept, not a string"). **No full read.** Thin keywords are acceptable — they accrete later at `ingest-source` time. Never let weak keywords justify skipping step 3.

   Where the value sits: the abstract's own vocabulary is already in the full-text index — a later rank-fused alias search (`bib-search.py --q`, the *ranking* arm) will match those words with or without you. What only this step can add is the *recall* arm: terms the abstract does **not** use — the other disciplines' names, the spelling the field you come from doesn't — because fusion re-ranks what some alias literally matches and adds zero recall. One alias the abstract omits is worth more than three it repeats.

5. **Choose the kurztitel.** One to three significant title words — a judgement, not the first three words of the title (*"The Low Chronology and the Problem of…"* → `low chronology`, not `low-chronology-problem`). `add-to-library.py` proposes one via `library.propose_shorttitle`; refine it.

6. **Commit — dry-run first, then write.**
   ```bash
   python scripts/add-to-library.py commit --pdf <pdf> \
       --author "<first author, as in BibTeX>" --year <YYYY> --title "<full title>" \
       --etype <type> --kurztitel "<chosen>" \
       [--journal … --booktitle … --pages … --volume … --number … --doi … --url …] \
       --keywords "term one; term two; term three"
   ```
   Review the proposed **bibkey** and, if it reports a **disambiguation letter** (`mazar-2011b-iron-age`), confirm the new document is genuinely a different work from the existing `mazar-2011-…` before writing. Then re-run with `--write`. The commit step:
   - computes the bibkey from your verified fields (refuses, rather than inventing, if a slot is empty);
   - if the work is already in the library (matched by DOI), **unions your keywords** into the existing entry instead of duplicating the key;
   - places the PDF (refuses to overwrite a *different* file at the target path without `--force`);
   - appends the entry to `<library>/references.bib`.

7. **Re-index** so the source is immediately searchable:
   ```bash
   python scripts/bib-search.py index
   ```
   Then close the loop with the search a later drafter would run — canonical name plus your aliases, rank-fused:
   ```bash
   python scripts/bib-search.py '"<canonical name>"' --q '<alias>' --key <bibkey>
   ```
   The keyword hit should print first (ahead of any page hit, `page: null`). If nothing comes back, the entry is invisible to exactly the query it exists for — fix the keywords now, while the abstract is still in front of you.

8. **Log.** Append one line to `knowledge/_meta/log.md`:
   ```
   - YYYY-MM-DD · add-to-library · <bibkey> · verified via <crossref|openalex>
   ```

9. **Soft-gate** (above) and report: the bibkey, where the PDF landed, the keywords written.

## BibTeX & keyword convention

Same as `ingest-source`'s BibTeX Entry Convention. `keywords` is semicolon-separated, 3–8 terms, canonical name plus synonyms/aliases — it is what `bib-search.py` matches when a source describes a method in prose without naming it; the rank-fused `--q` alias search changes ranking only, never recall, so this field is the sole non-text-derived path into a search result (see `ingest-source`'s keyword step for the full division of labour). The bibkey is `autor-jahr-kurztitel`, all lowercase ASCII (umlauts → `ae`/`oe`/`ue`, `ß` → `ss`; Turkish `ı` → `i`, Polish `ł` → `l`; particles/spaces removed), letter suffix **after the year** for a genuine clash. `bibkey == PDF filename stem` is the cross-project join key — the script enforces the shape.

## Red flags

| Tempting shortcut | Why it's wrong |
|---|---|
| "The docinfo Title is the citation — use it." | Docinfo is frequently wrong, stale, or a template placeholder. Verify against Crossref/OpenAlex (step 3). |
| "curl returned 200, so the DOI is right." | A 200 only means the DOI resolves. Check the returned **record** matches the PDF's title/author/year. |
| "No DOI, but I'll infer the year from the filename." | That is guessing bibliographic data. **Stop and ask** (step 3). |
| "The keywords look thin, so I'll skip verification and just file it." | Keywords are never a reason to skip step 3. Verification gates the write; keywords do not. |
| "The abstract names the method — `--q` fusion will find this entry, keywords are redundant." | The abstract's words are in the index either way; fusion only re-ranks what an alias literally matches. Keywords earn their keep as the aliases the abstract does *not* use — and without a full read, nobody has recorded those yet. |
| "The base bibkey already exists — I'll just overwrite it." | If it's the same work, keywords union in automatically. If it's different, take the disambiguation letter. Never overwrite a live key. |
