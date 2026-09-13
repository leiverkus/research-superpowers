# Frontmatter

Every `knowledge/**/*.md` page begins with a YAML frontmatter block. The normative definition lives in [`schema/knowledge-frontmatter.schema.json`](../schema/knowledge-frontmatter.schema.json) — this page is a narrative pointer, not a duplicate.

## Required fields

`title`, `type`, `created`, `updated`, `status`, `author`.

`type: source` additionally requires `bibkey`.

## Optional fields

`tags`, `sources`, `bibkey` (required on sources), `parent_bibkey` (on a source that is a chapter in an acquired volume — see below), `depth` (how thoroughly a source is worked up — see below), `hypothesis` (on syntheses), `bibliography` (per-page override of the project default), `methodology` (per-page override of the project default), `relations` (structured, confidence-tagged links — see below), `review_flags` (single-page content-review findings — see below), and the authority IDs `orcid` / `wikidata_qid` / `idai_gazetteer_id` / `gnd_id` (on entities; `orcid` for living researchers, the key that covers working scientists for cross-project linkage) and, on concepts, `wikidata_qid` — the primary cross-project *concept* join key — with `getty_aat_id` as an optional extra where the Getty AAT thesaurus has a precise term (heritage-only, so most modern/DH/method concepts have none).

## Field semantics in short

- **type** — `entity` (is), `concept` (means), `source` (cited work), `synthesis` (claims).
- **status** — `draft` → `review` → `stable`. Only the user sets `stable`; agents must not self-promote.
- **author** — `human`, `llm`, or `mixed` (LLM draft + human edits).
- **methodology** — `hermeneutic`, `quantitative`, `mixed`. Controls whether pre-registration gates apply (see `writing-research-plan` skill).
- **dates** — ISO `YYYY-MM-DD`. Bump `updated` on every substantive edit.

For enums, conditional requirements, and the full field list, see the schema file. For the lint behaviour, see `scripts/lint-wiki.py` in the project template.

## Structured relations (optional)

Wikilinks (`[[slug]]`) in the body already express connections, and that stays the primary, low-friction way to link pages. The optional `relations` block adds *machine-readable* edges on top: it names the **relation type** and tags each edge with a **confidence** level, so the graph export (`scripts/wiki-to-graph.py`) and the linter can reason about them.

```yaml
relations:
  - target: finkelstein-2003   # page slug (filename without extension)
    type: cites                # free vocabulary: cites, contradicts, builds-on, mentions, supports
    confidence: inferred       # extracted | inferred | ambiguous | asserted
    because: "Builds on Finkelstein's Low-Chronology dates (p. 290)."  # optional rationale
```

- **target** must resolve to an existing page (the linter checks this, like a wikilink).
- **confidence** — `extracted` (explicitly supported, e.g. a verbatim quote with page), `inferred` (added by the model), `ambiguous` (unclear), `asserted` (a decision the project made, not a finding it read — the edge records a position taken while writing and is grounded in no source). `lint-wiki.py` reports the **inference-rate** (share of `inferred` + `ambiguous`), mirroring the SOFT-GATE override-rate as an audit signal; `asserted` is counted on its own line beside it, never inside it, because it answers a different question — not *how much did the model guess?* but *how much does this project assert on its own authority?*
  > **`asserted` is for synthesis pages that record decisions**, the kind a writing phase produces: which side of a controversy the work takes, which reading it rejects and why. It is not a licence to skip sourcing — an `asserted` edge without a `because` is flagged by the linter, because an assertion that gives no reason cannot be reviewed.
- **because** (optional) — a one-line rationale for the edge, ideally with a quote or page. Recorded per edge and shown in the graph viz and `relations` query; the natural place to ground an `inferred` relation when hardening it to `extracted`, and **required in practice for `asserted`**, where it is the only thing standing between a decision and an assertion. `lint-wiki.py` reports the share of relations that carry one.

## `depth` — how thoroughly a source is worked up

A source page has two jobs: capture what **this** project takes from the source under a question,
and record what the source contains **at all**, so a question that shifts later can find its way
back. The second is what `depth` governs.

```yaml
depth: deep      # map | standard | deep   (default: standard)
```

| | section map | Kernthesen | for |
|---|---|---|---|
| `map` | ✓ | — | handbooks, lexica, gazetteers — works one **consults**, not reads |
| `standard` | ✓ | ≥ 10 | the normal case |
| `deep` | ✓ | ≥ 20, long form | the handful of works a project rests on — typically its own author's |

`map` is not a licence for thinness but an honest statement. Quoting from such a source means
raising it to `standard` first. A re-ingest may **raise** the depth and never lower it.

Which sources get which depth is a **project** decision, not a per-ingest one: set it in the
**Ingest depth** block of the project's `CLAUDE.md`, the mirror of the `Manuscript style (drafting
depth)` block that `drafting-manuscript` already reads. `lint-wiki.py` reports the spread plus
`NO-MAP`, `THIN` and `UNCOVERED` — none of which gates, because exhausting a source is never the
goal.

## `parent_bibkey` — a chapter whose original is the volume's PDF

`lint-wiki.py`'s NO-ORIGINAL gate assumes one work, one file: `<library>/pdf/<bibkey>.pdf`. That
is right for articles and wrong for edited volumes, where nine chapters of one handbook produce
nine findings for a file that has been in the library all along.

```yaml
bibkey: aubet-2014-phoenicia-iron-age-ii
parent_bibkey: steiner-killebrew-2014-oxford-handbook-levant
```

The chapter keeps its own bibkey — own authors, own title, own pages — and the gate is satisfied
by the volume's PDF. Three things this field is **not**:

- not `original_unavailable`, which declares that no PDF *can* exist. Here one does; it is simply
  filed under the volume's key.
- not `based_on`, which records that a *substitute* was read. A chapter in its own volume is the
  original.
- not a "see also". It is a claim about where the bytes are, and the linter checks it.

If the volume is missing too, the page still fails — as one `MISSING-VOLUME` naming the volume
rather than one finding per chapter, because that is the single thing a human goes and fetches.
`MISSING-VOLUME` counts as a gate finding, so `--strict-gates` cannot pass a wiki that is unable to
show its evidence.

The field is additive: pages without `relations` remain valid, and plain wikilinks continue to work unchanged (the graph export treats them as `extracted` edges).

## Review flags (optional)

`review_flags` records **single-page content-review findings** raised by the `semantic-wiki-review` skill (or a human reviewer). It is a *third, independent axis*, deliberately kept apart from the other two:

| Axis | Field | Owned by | Answers |
|------|-------|----------|---------|
| Maturity | `status` | the user | how finished / trusted is this page? |
| Page↔page conflict | `relations: contradicts` | ingest / review | does this page disagree with *another* page? |
| Page-level health | `review_flags` | review | does *this* page's own content have an open concern? |

Keeping them separate matters: a review must never overwrite the user's `status`, and the case that matters most — a `status: stable` page that a newer source now undercuts — is only representable when `stable` and an open flag can coexist.

```yaml
review_flags:
  - kind: overstatement          # overstatement | weak-support | stale | missing-citation | open-question
    detail: "Dates the destruction 'securely' to 925 BCE; the source says 'probably'."
    raised_by: semantic-wiki-review
    detected: 2026-07-03
    state: open                  # open | resolved
    # resolved: 2026-07-10       # optional — set when state moves to resolved
```

- **kind** — the class of concern (enum above). A conflict *between two pages* is not a flag; it is a `relations: contradicts` edge.
- **state** — `open` gates drafting: `drafting-manuscript` will not draft from a page with an open flag without a logged override, and `wiki-lint` surfaces open flags in its `Review flags` section (advisory — it does **not** fail the exit code on them; only a *malformed* flag fails, via schema validation).
- **Resolve in place**, don't delete: set `state: resolved` (and optionally a `resolved:` date) so the audit trail survives.

The field is additive: pages without `review_flags` remain valid.

## Minimal example

```yaml
---
title: "Finkelstein 2003 — Low Chronology Revisited"
type: source
created: 2026-04-15
updated: 2026-04-15
status: review
author: llm
bibkey: finkelstein-2003-low-chronology
---
```
