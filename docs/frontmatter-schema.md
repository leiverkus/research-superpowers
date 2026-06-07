# Frontmatter

Every `knowledge/**/*.md` page begins with a YAML frontmatter block. The normative definition lives in [`schema/knowledge-frontmatter.schema.json`](../schema/knowledge-frontmatter.schema.json) — this page is a narrative pointer, not a duplicate.

## Required fields

`title`, `type`, `created`, `updated`, `status`, `author`.

`type: source` additionally requires `bibkey`.

## Optional fields

`tags`, `sources`, `bibkey` (required on sources), `hypothesis` (on syntheses), `bibliography` (per-page override of the project default), `methodology` (per-page override of the project default), `relations` (structured, confidence-tagged links — see below), and the authority IDs `wikidata_qid` / `idai_gazetteer_id` / `gnd_id` (on entities).

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
```

- **target** must resolve to an existing page (the linter checks this, like a wikilink).
- **confidence** — `extracted` (explicitly supported, e.g. a verbatim quote with page), `inferred` (added by the model), `ambiguous` (unclear). `lint-wiki.py` reports the **inference-rate** (share of `inferred` + `ambiguous`), mirroring the SOFT-GATE override-rate as an audit signal.

The field is additive: pages without `relations` remain valid, and plain wikilinks continue to work unchanged (the graph export treats them as `extracted` edges).

## Minimal example

```yaml
---
title: "Finkelstein 2003 — Low Chronology Revisited"
type: source
created: 2026-04-15
updated: 2026-04-15
status: review
author: llm
bibkey: finkelstein-2003
---
```
