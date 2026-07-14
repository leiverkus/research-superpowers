# input/bibliography/ — text artefacts only

**The source PDFs are NOT here.** They live in the shared library:

    <library>/pdf/<bibkey>.pdf

One copy per source, shared by every project — so the same paper exists once, and a
metadata error is fixed once. `scripts/library.py` resolves where the library is
(machine-local: `RESEARCH_LIBRARY`, then `.research-library`, then
`~/.config/research-superpowers/library`).

## What DOES live here (and is tracked in git)

| File | Written by | Read by |
|---|---|---|
| `literaturguide.md` | `literature-review` | `acquire-sources` (its required input) |
| `audit-log-<date>.json` | `literature-review` | provenance |
| `acquisition-todo.md` | `acquire-sources` | you (fetch these via VPN); `ingest-source`'s hard-stop points here |
| `acquisition-log-<date>.json` | `acquire-sources` | provenance |

These are **per-project**: what *this* project searched for and what it still needs.
They belong in the repo. The PDFs do not — they are large, copyright-bound, and shared.

## The one rule

> **`bibkey` == PDF filename**

`finkelstein-2003-low-chronology` ⟷ `<library>/pdf/finkelstein-2003-low-chronology.pdf`

So `ingest-source` finds the original without guessing, and `drafting-manuscript` can
reach back into the exact page a claim cites.
