---
name: semantic-wiki-review
description: Use when the user asks for a *content* review of the wiki — contradictions between pages, outdated claims overtaken by newer sources, weakly supported assertions, missing cross-references that the structural linter cannot detect. Distinct from `wiki-lint` (structural, deterministic, CI-gated).
---

# Semantic Wiki Review

`scripts/lint-wiki.py` proves the wiki is structurally well-formed:
frontmatter present, wikilinks resolve, no orphans. It cannot tell you
whether two source pages contradict each other, whether a synthesis still
holds after a newer source was ingested, or whether a claim lacks citation
backing. That work needs reading — and that is what this skill is for.

**Announce at start:** "Using semantic-wiki-review to audit the wiki for
content issues."

Not a gate. Manual trigger only. Runs alongside the workflow, never blocks it.

## When to use

- User asks: "are the wiki pages consistent?", "any contradictions?",
  "which synthesis pages are stale?"
- After a batch of new sources was ingested and earlier syntheses may be stale.
- Before promoting a `status: review` page to `status: stable`.
- As a recurring sanity pass (monthly, before manuscript submission).

**NOT for:** structural lint (use `wiki-lint`), single-page proofreading,
or fact-checking against external sources (that is a literature task).

## Scope

Pick a scope before reading — full wiki audit is expensive. Defaults:

| Scope | When |
|-------|------|
| All `status: stable` pages | Before manuscript submission |
| All pages touching topic X | After ingesting a major new source on X |
| All syntheses citing source Y | After source Y was substantially revised |
| Recently-changed pages (last N days) | Periodic check |

State the scope to the user before reading.

## Checklist

1. **Determine scope** — confirm with user if ambiguous.
2. **List in-scope pages** — read each fully (no skim).
3. **Build a claim ledger** as you read — one line per substantive claim,
   tagged with `[[source-key]]` and page-of-origin.
4. **Flag issues** in five categories. Each has a *recording channel* — where
   the finding is written so downstream skills (lint, drafting) can act on it:
   - **Contradictions** — two pages assert incompatible things. → Record as a
     typed `relations:` edge with `type: contradicts` on the *pages themselves*
     (both directions), `confidence: inferred` unless a verbatim quote grounds
     it, plus a `because`. This is NOT a `review_flag` (a flag is about one
     page's own content; a contradiction is a relation between two).
   - **Stale syntheses** — a synthesis page relies on sources that have since
     been complemented or refuted by newer ingests. → `review_flags` `kind: stale`.
   - **Unsupported claims** — assertions without a `[[source]]` link or
     `@citekey` in the text. → `review_flags` `kind: weak-support` (or
     `missing-citation` when a specific citation is simply absent).
   - **Overstatement** — a claim stronger than the source supports (superlatives,
     precise figures without consensus). → `review_flags` `kind: overstatement`.
   - **Missing cross-references** — pages discussing the same entity / concept
     without linking each other. → Report only (a linking suggestion, not a
     content defect); the user or a follow-up adds the wikilink.
   - **Suspect / aggregator citations** — citations whose source URL points
     to aggregator hosts (academia.edu, researchgate.net) or sources flagged
     as suspect/pseudoscientific. → Report only. See MCP Optimisation below.
5. **Record structured findings on the affected pages** — for the content
   categories above, append a `review_flags` entry to the flagged page's
   frontmatter (see "Recording review flags" below), and add/strengthen the
   `relations: contradicts` edges for contradictions. This is the ONLY editing
   the audit does: **frontmatter metadata only, never the page prose.** Existing
   open flags on a page are left in place (dedupe by `kind` + `detail`); do not
   silently reopen a `state: resolved` flag.
6. **Write a review report** to `knowledge/_meta/semantic-review-<YYYY-MM-DD>.md`
   (frontmatter: `type: synthesis`, `status: draft`, `author: llm`) — the
   human-readable digest of the same findings, plus the report-only categories.
7. **Never touch page prose or `status`.** The flags are advisory metadata; the
   user (or a follow-up skill invocation) decides which issues to fix, and only
   the user promotes `status`. Resolving a flag means setting its
   `state: resolved` (with a `resolved:` date) once the concern is addressed —
   not deleting it.

## Report format

```markdown
---
title: "Semantic Wiki Review — <scope> — <date>"
type: synthesis
created: YYYY-MM-DD
updated: YYYY-MM-DD
status: draft
author: llm
---

## Scope
<one sentence>

## Pages audited
- [[page-1]]
- [[page-2]]
- ...

## Contradictions
| Pages | Issue | Suggestion |
|-------|-------|------------|
| [[a]] vs [[b]] | A claims X, B claims ¬X | Resolve in synthesis or note dispute |

## Stale syntheses
| Page | Outdated by | Why |

## Unsupported claims
| Page | Claim | Suggested source / mark as opinion |

## Missing cross-references
| Page | Should link | Why |

## Suspect / aggregator citations
| Page | URL | source_class | Primary source known? | Suggested action |

## Summary
<2-3 sentences: how healthy is the wiki, what to prioritise>
```

## Recording review flags

Single-page content findings are written to the flagged page's own frontmatter
as a `review_flags` entry (schema: `schema/knowledge-frontmatter.schema.json`).
This is a distinct axis from `status` (human-owned maturity — never touched
here) and from `relations: contradicts` (page↔page conflicts). A page can be
`status: stable` and carry an open flag at the same time — that is exactly the
case worth surfacing: a blessed page a newer source now undercuts.

```yaml
# appended to knowledge/synthesis/chronologie-debatte.md frontmatter
review_flags:
  - kind: overstatement          # overstatement | weak-support | stale | missing-citation | open-question
    detail: "Dates the destruction 'securely' to 925 BCE; the cited source says 'probably'."
    raised_by: semantic-wiki-review
    detected: 2026-07-03
    state: open                  # open | resolved
```

Why on the page and not only in the dated report:

- **It gates drafting.** `drafting-manuscript` refuses to draft from a page with
  an open flag without a logged override — the finding cannot be silently
  skipped. A detached report can.
- **It travels with the page** — visible in Obsidian and to any later reader,
  not buried in a `_meta/` file dated weeks ago.
- **It is auditable and resolvable in place** — `state: resolved` + a `resolved:`
  date closes it while keeping the trail; `wiki-lint` reports the open ones.

The dated report (step 6) stays as the human-readable digest and is the only
place the report-only categories (missing cross-references, suspect citations)
live. Findings and report are two views of the same audit — keep them consistent.

## MCP Optimisation (recommended)

> If `dao-searxng-mcp` (see [`docs/recommended-mcps.md`](../../docs/recommended-mcps.md)) is available in the project, use its `source_class` detection for every cited URL. Otherwise judge aggregator status manually via hostname heuristic (academia.edu, researchgate.net, scribd.com, …).

Procedure:

1. Collect every external URL from the audited source / synthesis pages (frontmatter `sources:` or body links).
2. Per URL: call `fetch_url` / `web_search` via `dao-searxng-mcp`; the tool annotates with `source_class` (`primary_publisher` | `academic_repository` | `preprint_server` | `aggregator` | `suspect` | `grey_lit_or_unknown`).
3. URLs with `source_class=aggregator` or `suspect` go into the new "Suspect / aggregator citations" issue category, with a note on whether the primary source (DOI) is known.
4. No automatic fix — the report is advisory; the user decides replacement or retention with rationale.

## Red Flags

| Thought | Reality |
|---------|----------|
| "I can check this in my head" | Above 5 pages impossible — keep a ledger. |
| "The linter already checked" | The linter checks structure, not content. Different job. |
| "I'll fix issues as I find them" | No — the audit repairs nothing. It records `review_flags` (frontmatter) and writes the report; fixing prose is a separate step. |
| "Stable means correct" | Stable means human-reviewed at time X. It can still be stale — flag it, don't demote it. |
| "A contradiction is a page flag" | No — a conflict *between* two pages is a `relations: contradicts` edge; a `review_flag` is about one page's own content. |

## Key Principles

- **Metadata-only, never prose.** The audit records `review_flags` and
  `relations` on pages and writes the dated report — it never edits page prose
  and never changes `status`. Prose repair is a separate, later step.
- **One report per run**, dated, in `knowledge/_meta/`; flags live on the pages.
- **Scope before depth.** 10 pages honestly read beats 100 skimmed.
- **No gate.** This is a tool, not a precondition for other skills.
