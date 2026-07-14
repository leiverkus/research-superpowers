# Frontmatter

Every `knowledge/**/*.md` page begins with a YAML frontmatter block. The normative definition lives in [`schema/knowledge-frontmatter.schema.json`](../schema/knowledge-frontmatter.schema.json) — this page is a narrative pointer, not a duplicate.

## Required fields

`title`, `type`, `created`, `updated`, `status`, `author`.

`type: source` additionally requires `bibkey`.

## Optional fields

`tags`, `sources`, `bibkey` (required on sources), `hypothesis` (on syntheses), `bibliography` (per-page override of the project default), `methodology` (per-page override of the project default), `relations` (structured, confidence-tagged links — see below), `review_flags` (single-page content-review findings — see below), and the authority IDs `orcid` / `wikidata_qid` / `idai_gazetteer_id` / `gnd_id` (on entities; `orcid` for living researchers, the key that covers working scientists for cross-project linkage) and `getty_aat_id` (on concepts — the Getty AAT controlled-vocabulary join key that makes cross-project *concept* overlap visible).

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
    confidence: inferred       # extracted | inferred | ambiguous
    because: "Builds on Finkelstein's Low-Chronology dates (p. 290)."  # optional rationale
```

- **target** must resolve to an existing page (the linter checks this, like a wikilink).
- **confidence** — `extracted` (explicitly supported, e.g. a verbatim quote with page), `inferred` (added by the model), `ambiguous` (unclear). `lint-wiki.py` reports the **inference-rate** (share of `inferred` + `ambiguous`), mirroring the SOFT-GATE override-rate as an audit signal.
- **because** (optional) — a one-line rationale for the edge, ideally with a quote or page. Recorded per edge and shown in the graph viz and `relations` query; the natural place to ground an `inferred` relation when hardening it to `extracted`. `lint-wiki.py` reports the share of relations that carry one.

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
