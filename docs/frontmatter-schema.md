# Frontmatter

Every `knowledge/**/*.md` page begins with a YAML frontmatter block. The normative definition lives in [`schema/knowledge-frontmatter.schema.json`](../schema/knowledge-frontmatter.schema.json) — this page is a narrative pointer, not a duplicate.

## Required fields

`title`, `type`, `created`, `updated`, `status`, `author`.

`type: source` additionally requires `bibkey`.

## Optional fields

`tags`, `sources`, `bibkey` (required on sources), `hypothesis` (on syntheses), `bibliography` (per-page override of the project default), `methodology` (per-page override of the project default).

## Field semantics in short

- **type** — `entity` (is), `concept` (means), `source` (cited work), `synthesis` (claims).
- **status** — `draft` → `review` → `stable`. Only the user sets `stable`; agents must not self-promote.
- **author** — `human`, `llm`, or `mixed` (LLM draft + human edits).
- **methodology** — `hermeneutic`, `quantitative`, `mixed`. Controls whether pre-registration gates apply (see `writing-research-plan` skill).
- **dates** — ISO `YYYY-MM-DD`. Bump `updated` on every substantive edit.

For enums, conditional requirements, and the full field list, see the schema file. For the lint behaviour, see `scripts/lint-wiki.py` in the project template.

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
