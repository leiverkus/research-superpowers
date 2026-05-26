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
4. **Flag issues** in five categories:
   - **Contradictions** — two pages assert incompatible things.
   - **Stale syntheses** — a synthesis page relies on sources that have since
     been complemented or refuted by newer ingests.
   - **Unsupported claims** — assertions without a `[[source]]` link or
     `@citekey` in the text.
   - **Missing cross-references** — pages discussing the same entity / concept
     without linking each other.
   - **Suspect / aggregator citations** — citations whose source URL points
     to aggregator hosts (academia.edu, researchgate.net) or sources flagged
     as suspect/pseudoscientific. See MCP Optimisation below.
5. **Write a review report** to `knowledge/_meta/semantic-review-<YYYY-MM-DD>.qmd`
   (frontmatter: `type: synthesis`, `status: draft`, `author: llm`).
6. **Do not edit** the audited pages. The report is advisory; the user (or a
   follow-up skill invocation) decides which issues to fix.

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
| "I'll fix issues as I find them" | No — the audit is read-only. Repair is a separate step. |
| "Stable means correct" | Stable means human-reviewed at time X. It can still be stale. |

## Key Principles

- **Read-only.** Never edit during the audit. Write the report, then fix separately.
- **One report per run**, dated, in `knowledge/_meta/`.
- **Scope before depth.** 10 pages honestly read beats 100 skimmed.
- **No gate.** This is a tool, not a precondition for other skills.
