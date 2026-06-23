# input/bibliography/

Source PDFs and the bibliography artefacts for this project.

## What lives here

| File / pattern | Written by | Purpose |
|---|---|---|
| `Lastname - Title - Year.pdf` | you (manual) or `acquire-sources` (auto) | the source PDFs — the canonical "everything" the wiki interprets |
| `literaturguide.md` | `literature-review` | strategic, graded reading guide (A/B/C) |
| `audit-log-<date>.json` | `literature-review` | machine-readable search protocol |
| `acquisition-todo.md` | `acquire-sources` | worklist of sources to **download manually** |
| `acquisition-log-<date>.json` | `acquire-sources` | which sources were auto-downloaded vs left for you |

## The acquire → download → ingest loop

1. **`literature-review`** searches and writes `literaturguide.md` (it downloads nothing).
2. **`acquire-sources`** downloads the Open-Access PDFs for the A+B sources here automatically, and writes **`acquisition-todo.md`** listing everything it could not fetch (paywalled, bot-blocked, no OA copy).
3. **You** open `acquisition-todo.md` and download those originals — e.g. via your **university VPN / library proxy**, which reaches far more than an automated download can. Save each one into this folder under the **exact** `Save as` filename the table gives (`Lastname - Title - Year.pdf`).
4. **Re-run `acquire-sources`** — it rescans this folder, drops the now-present files from the worklist, and tells you what is still missing. Repeat until the list is short enough.
5. **`ingest-source`** reads each acquired original into the wiki. It **hard-stops** on a missing original — it will *not* silently substitute a preprint, prior version, or book review. (A substitute can be ingested only with your explicit consent, and is then marked `based_on:` in the source page.)

## Naming

`Lastname - Title - Year.pdf` (first author's surname, a short title, the year).
The `rename-scientific-pdf` skill can normalise a messy filename to this scheme.
`ingest-source` derives the wiki slug `<lastname>-<year>` from it.

> `acquisition-todo.md` and `acquisition-log-*.json` are runtime outputs — they
> are not part of the template and appear once you run `acquire-sources`.
