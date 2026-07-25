---
name: drift-report
description: Use to check the shared library, the current wiki, and all registered projects for accumulated drift — un-indexed PDFs, scans without a text layer, PDF bloat, project-bib keywords not yet merged into the master, cross-project bibkey collisions, lint regressions from out-of-band edits. Wraps hooks/drift_check.py, the same state-triggered check that runs automatically at session start. Triggers on "drift report", "check everything", "was steht an", "prüf mal alles", "ist alles konsistent", "check the library". NOT wiki-lint (single-project structural lint — this composes it), NOT semantic-wiki-review (LLM content audit — this is deterministic only).
inputs:
  - name: project_root
    description: Research project to run from (defaults to cwd; any directory works — library and registry checks run regardless)
    required: false
outputs:
  - path: ~/.cache/research-superpowers/last-drift-report.md
    kind: created_or_modified
  - path: ~/.cache/research-superpowers/drift-state.json
    kind: modified
---

# Drift Report

Deterministic maintenance findings across three scopes — current project,
shared library, all registered projects — produced by the same script the
SessionStart hook runs. **Report-only** with one exception: the incremental
search-index update (a derived cache).

**Announce at start:** "Using drift-report to check for accumulated drift."

## How the automatic path works (so you can explain it)

At session start, `hooks/drift_check.py` compares cheap fingerprints (library
PDF count/mtimes, master-bib hash, each registered project's bib hash, the
current wiki's file count/mtimes) against `~/.cache/research-superpowers/drift-state.json`.
**Nothing changed → nothing runs, nothing is injected.** Drift is caused by
actions, not by time — in-session actions are covered by the skills that cause
them (ingest lints, add-to-library re-indexes); the hook covers what happens
out-of-band: manual VPN downloads, Nextcloud syncs from teammates, Obsidian
edits, ingests in *other* projects. The first run is a silent baseline.
Kill switch: `RESEARCH_SUPERPOWERS_NO_DRIFT_CHECK=1`.

## Manual run (this skill's job)

```bash
python3 "$CLAUDE_PLUGIN_ROOT/hooks/drift_check.py" --force --human
```

`--force` ignores the fingerprints (checks everything now — this is how you
inspect a freshly installed machine despite the silent baseline); `--human`
prints the report instead of hook JSON. Run from a project root when possible —
the wiki-lint scope only exists there.

## The checks, and what each finding means

| Finding | Meaning | Fix (never run without the user's go-ahead) |
|---|---|---|
| lint FAILS after out-of-band edit | someone edited `knowledge/` outside a session (Obsidian, editor) | `python scripts/lint-wiki.py`, then fix per `wiki-lint` skill |
| PDFs with no text layer | scans arrived (VPN download, teammate sync) — invisible to search | `ocrmypdf`, then re-index |
| PDFs unreadable | corrupt files in the library | `bib-search.py status` for the list |
| PDFs > 40 MB | publisher bloat syncing to everyone, forever | `optimize-pdf.py scan .` → `optimize` after review |
| merge drift | ingests wrote bibkeys/keywords into project bibs that the master lacks — new keywords are invisible to every OTHER project's `bib-search` until merged | `merge-bibs.py --report-only` first, review FACTUAL conflicts, then merge |
| bibkey COLLISION / SPLIT | one key names two works (a false cross-project join) or one work has two keys (a silently missed join) | `migrate-citekeys.py`, guided by the audit output |
| index updated (info) | the one permitted mutation — derived cache, incremental | nothing to do |

## Registry

Cross-project checks read `~/.config/research-superpowers/projects` (one
project root per line, `#` comments). The hook **auto-registers** the project
each session starts in, so the registry fills itself through normal use; edit
the file to add projects you never open with Claude Code, or to remove retired
ones.

## Red flags

| Thought | Reality |
|---|---|
| "Merge drift found — I'll just run merge-bibs with --out now" | No. `--report-only` first: FACTUAL conflicts (wrong DOI, wrong year) need a human verdict before anything writes to the shared master. |
| "The report is empty, so the check must be broken" | Silence IS the report. Nothing changed since the last look — verify with `--force --human` if in doubt. |
| "A collision — I'll rename the key in this project" | A bibkey is a cross-project join key derived from the work's metadata. Fix it with `migrate-citekeys.py` in EVERY affected project, not ad hoc in one. |
| "I'll OCR/optimize the PDFs right away, it's obviously needed" | Library files sync to every machine and every teammate. Surface the worklist; the user decides when the shared collection gets rewritten. |
