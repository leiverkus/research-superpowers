# Does a vector index beat FTS for concept search? — measured, no

**Date:** 2026-07-17 · **Verdict:** do not build · **Library:** 593 documents / 32,137 pages

A semantic index over the shared source library was designed in detail and then
measured *before* being built. It loses to the full-text search that already exists.
This record exists so the question is not re-opened from scratch — and because the
previous round of these numbers lived only in a chat session and was lost.

## The question

`bib-search.py` is lexical. A paper that *describes* random labelling without ever
naming it is invisible to it. Would embedding the library close that gap?

## The gold set

Five papers that `Evidentia/Choros/paper/knowledge/_meta/corpus-counts.md` (column C,
hand-checked, 27 rows) records as using random labelling. **Page anchors below are
PHYSICAL PDF pages, verified against the index** — `corpus-counts.md` cites *article*
pages, and the two differ (keron: article p. 203 = PDF p. 222, a 19-page offset).
Measuring against the article anchors is the trap; it was hit once during this work.

| bibkey | PDF p. | How the paper names the method |
|---|---|---|
| `moclan-2023-identifying` | 11 | jargon — "random labelling" |
| `keron-2015-use` | 222 | jargon, US spelling — "random labeling" (on 32 pages) |
| `carreropazos-2019-spatial` | 7 | near-jargon — rank permutation of marks |
| `diezmartin-2021-tracing` | 11 | **prose** — "shuffling only the labels of the points" (also "randomly relabeled", p. 10) |
| `rabunal-2023-unraveling` | 9 | **prose only** — "random type assignment to the points in the pattern" |

Query used throughout (jargon-free, as the acceptance test demands):

> *the null model shuffles the labels of the observed points while keeping their locations fixed*

## The lexical baseline — the bar that matters

Scored at `--limit 40`, document level (the metric the skill documents).

| Query | of 5 |
|---|---|
| naive `"random labelling"` | 1 |
| the alias recipe shipped in #60 | 2 |
| **+ the stems `relabel*` and `shuffl*`** | **3** |

Only `rabunal-2023` is genuinely unreachable lexically; `carreropazos` is reachable but
outranked. The vector arm's entire remaining job was therefore **one paper**.

## What the vector arm actually did

Prototyped with `sentence-transformers`. Two haystacks: a 10-page hard-distractor set
carrying four of the gold pages, and a 3,000-page sample carrying all five.

**Hard-distractor set** — 10 pages, all about point-process null models, only 4 gold.
Precision@4 (chance ≈ 1.6/4), BGE-M3, by chunk size:

| chunk tokens | vectors (full library) | float32 | precision@4 |
|---|---|---|---|
| 450 (the design) | 103,584 | 0.42 GB | **0/4** |
| 250 | 178,917 | 0.73 GB | 1/4 |
| 150 | 298,196 | 1.22 GB | 2/4 |
| 80 | 546,169 | 2.24 GB | 2/4 |
| 40 | 1,089,198 | 4.46 GB | 1/4 |

No chunk size clears chance by a margin. 450 tokens — the designed value — inverts the
ranking perfectly: all six distractors above all four gold pages.

**3,000-page haystack** — a tenth of the library, so a tenth of the difficulty:

| model | query | recall@10 | recall@20 | gold ranks (of 3,005) |
|---|---|---|---|---|
| BGE-M3 | EN | 0/5 | 0/5 | 334 – 621 |
| BGE-M3 | DE prose | 0/5 | 0/5 | 110 – 857 |
| BGE-M3 | DE term | 0/5 | 0/5 | 94 – 345 |
| Qwen3-0.6B | EN | **1/5** | 1/5 | 3 – 344 |
| Qwen3-0.6B | DE prose | 0/5 | 1/5 | 16 – 813 |
| Qwen3-0.6B | DE term | 0/5 | 0/5 | 24 – 472 |

**The single best result across every run is 1 of 5 — and it is `keron`, which plain FTS
already finds** via the US spelling. The vector arm contributed **zero** papers FTS misses,
and `rabunal` — the one paper it was for — never rose above rank 44 of 3,005 (≈ 460
extrapolated to the full library, against a target of ≤ 20).

## Why it fails — the diagnosis, not the symptom

The models are not bad at the task. On isolated short sentences BGE-M3 separates it cleanly:

| cos | sentence |
|---|---|
| 0.6386 | diezmartin's sentence, near-verbatim to the query |
| 0.5975 | "random labelling" — bare jargon |
| **0.4555** | **rabunal's paraphrase — the semantic-only case** |
| 0.3093 | distractor: a CSR envelope |
| 0.2795 | unrelated (Arabah copper smelting) |

The capability is there and it drowns. A page of dense academic prose carries one method
sentence among hundreds; the mean over any economically viable chunk washes out exactly the
phrase being sought. Shrinking the chunk trades the dilution for a different failure — at 40
tokens too many distractor sentences look alike — while multiplying the vectors tenfold.

## Cost, for the record

| | FTS (today) | vector arm |
|---|---|---|
| index build | **11 s** | 78 min (BGE-M3) / 139 min (Qwen3) |
| dependencies | none (stdlib) | 1.0 GB venv + 1.1 GB (Qwen3) or 4.3 GB (BGE-M3) on disk |
| index size | 176 MB | 0.42 – 2.24 GB |

Two design notes worth keeping even though the build was cancelled:

- **Qwen3-Embedding-0.6B beats BGE-M3** by roughly 4× on rank quality and is 4× smaller on
  disk (1.1 GB vs 4.3 GB — the BGE-M3 repo ships `.bin`, ONNX and the sparse/ColBERT heads).
  It is ~2× slower to embed. If this question is ever re-opened, start there, not with BGE-M3.
- **Cross-lingual retrieval works** — a German query returns English pages at ranks comparable
  to an English query — it simply never reaches usable precision here. The library is 94.4 %
  English / 5.1 % German / 1 French document, so the multilingual case is small to begin with.

## Corrections to the record this produced

Figures that were stale or wrong when this started, all re-measured:

| claim | measured |
|---|---|
| library: 582 docs / 30,843 pages / 625 short pages | **593 / 32,137 / 748**, 0 without a text layer |
| `pip install sentence-transformers` ≈ 2.5 GB | **1.0 GB** |
| BGE-M3 ≈ 2.27 GB on disk | **4.3 GB** |
| ~3 chunks/page → 92,500 vectors | **2.48/page → ~79,700** at 450 tokens |
| embed run ≈ 26 min | **78 min** (BGE-M3), 139 min (Qwen3) |

## Reproducing

The scripts here are a **record, not maintained code** — they are not run by CI, and the
repo deliberately has no runtime dependency beyond the standard library + PyYAML.

```bash
python3.12 -m venv venv && ./venv/bin/pip install sentence-transformers
./venv/bin/python probe3.py    # the decisive one: haystack + recall@10/@20
```

| script | what it answers |
|---|---|
| `probe1_pages.py` | whole pages, hard-distractor set — the naive baseline |
| `probe2_chunked.py` | the plan's design: 450 tokens, 80 overlap, never across a page boundary |
| `probe3_haystack.py` | **the falsification test** — 3,000-page haystack, recall@10/@20 |
| `probe4_chunksizes.py` | chunk-size sweep with the cost of each |
| `probe5_multilingual.py` | German query → English papers, plus the FTS null control |

They read `~/.cache/research-superpowers/index-*.sqlite` directly and hard-code the Choros
bibkeys; they are tied to that library, not general tools.
