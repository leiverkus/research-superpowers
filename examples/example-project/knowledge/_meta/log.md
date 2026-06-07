---
title: "Workflow Log"
type: concept
created: 2026-04-18
updated: 2026-04-19
status: stable
author: human
---

## Workflow Log

Append-only log of all workflow events. Format:

```
- YYYY-MM-DD · <event> · <slug> · <details>
```

Events: `brainstorm` | `plan` | `ingest` | `synthesis` | `draft` | `review` |
`deviation` | `finish`

---

- 2026-04-18 · brainstorm · low-chronology · design signed off → input/ideas/low-chronology-design.md
- 2026-04-19 · plan · low-chronology · status=ready (hermeneutic; no pre-registration) → input/ideas/low-chronology-plan.md
- 2026-04-19 · ingest · finkelstein-piasetzky-2003 · focus: «the 14C reconciliation between Low and Modified Conventional Chronologies»
- 2026-04-19 · synthesis · chronology-debate · status=draft (1 source)
- 2026-05-28 · ingest · mazar-2011 · focus: «the Modified Conventional Chronology response to the Low Chronology» (stub from literature-review queue)
- 2026-05-28 · ingest · regev-et-al-2020 · focus: «the current Tel Rehov 14C dataset and re-modelling» (stub from literature-review queue)
- 2026-05-28 · synthesis · chronology-debate · status=review (3 sources, argument-structure mapping added)
