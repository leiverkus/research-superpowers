---
name: wiki-lint
description: Use to validate the knowledge wiki — frontmatter completeness, broken wikilinks, orphaned pages, status consistency. Wraps `scripts/lint-wiki.py` from the research project template. Required before drafting and before finishing.
inputs:
  - name: project_root
    description: Absolute path to the research project root
    required: true
outputs:
  - path: knowledge/**/*.md
    kind: modified
  - path: knowledge/_meta/log.md
    kind: appended
agents:
  - wiki-linter
---

# Wiki Lint

Run the wiki linter and act on its findings. Mandatory gate before `drafting-manuscript` and `finishing-a-research-project`; useful after bulk ingest or whenever the wiki has grown.

**Announce at start:** "Using wiki-lint to validate the knowledge tree."

<SOFT-GATE>
Before transitioning to `drafting-manuscript` or `finishing-a-research-project`:
(1) `scripts/lint-wiki.py` exits 0

If not met: tell the user which classes of issues remain (errors / warnings /
orphans), ask for a short reason to proceed anyway (e.g. "orphan is intentional
— it's the index page"), and write the reason into
`knowledge/_meta/gate-overrides.log`. Errors should as a rule be fixed rather
than overridden — the override is an audit trail, not a substitute.
</SOFT-GATE>

## When to use

- Before `drafting-manuscript` (soft gate)
- Before `finishing-a-research-project` (soft gate)
- After `ingest-source` batch runs (≥ 3 new sources)
- When user says "clean up the wiki", "lint", "check the wiki"
- Periodically when the project is long-running

## Checklist

1. **Locate the lint script** — `scripts/lint-wiki.py` in the project root (from template)
2. **Run it** — `python scripts/lint-wiki.py`. **If Python or PyYAML or the script itself is missing, take the Python-free fallback path below.**
3. **Parse output** into categories: errors, warnings, orphans
4. **Fix errors inline** (missing frontmatter fields, broken wikilinks, invalid `type` values)
5. **Assess warnings** — stale pages, status inconsistency, empty sections — decide with user: fix / defer / ignore
6. **Handle orphans** — pages with no incoming wikilinks: decide link-in, delete, or mark as root
7. **Re-run lint** until exit 0 on errors
8. **Log** the run in `knowledge/_meta/log.md` with summary (N errors fixed, N warnings deferred)
9. **Dispatch `wiki-linter` subagent** (optional) for large wikis — see `agents/wiki-linter.md`

**See also:** `scripts/wiki-to-graph.py` is the sibling tool for *structure analysis* (not validation) — it exports the wiki as a graph (`graph.json` / `graph.graphml`) and reports god_nodes (most-connected pages) and bridges (entities joining otherwise-unconnected sources). Useful after a lint pass to spot hubs and weak links; it reads the same `relations` frontmatter the linter validates.

## Python-free fallback

For users on Cowork or any environment without a shell — or any project where `python3` / `pyyaml` / `scripts/lint-wiki.py` are simply not available — the skill performs frontmatter validation inline.

**Trigger the fallback automatically when:**
- `scripts/lint-wiki.py` does not exist in the project, OR
- the Bash tool is not available, OR
- running the script returns a "command not found" error for `python3` or `python`, OR
- the user explicitly says "lint without Python" or "use the inline check"

**Tell the user upfront:**
> "Running wiki-lint in fallback mode (no Python). This checks frontmatter but skips wikilink resolution and orphan detection — those would cost too many tokens on a full wiki scan. For a complete check, install Python+PyYAML and use the `scripts/lint-wiki.py` script. Recommended for projects above ~20 pages."

**Fallback procedure:**

1. Read `schema/knowledge-frontmatter.schema.json` from the project root. If absent, read the plugin's copy (the plugin ships one).
2. List every `knowledge/**/*.md` file (excluding files prefixed `_example-`).
3. For each file: parse the YAML frontmatter (the block between the first two `---` lines) and validate against:
   - `required` fields exist and are non-empty
   - `type` is one of `entity | concept | source | synthesis`
   - `status` is one of `draft | review | stable`
   - `author` is one of `human | llm | mixed`
   - `created` and `updated` match the ISO date pattern `^\d{4}-\d{2}-\d{2}$`
   - if `type: source`, then `bibkey` is present
   - if `wikidata_qid` is present, it matches `^Q\d+$`
   - if `idai_gazetteer_id` is present, it matches `^\d+$`
4. Report any failures in the same format as the Python script: `MISSING: <path> — required field '<field>' is missing` / `INVALID: <path> — <field>='<value>' (allowed: …)`.
5. Print a status summary: total pages, draft/review/stable distribution.
6. **Explicitly skip** wikilink resolution and orphan detection. State this in the output so the user knows what's not covered.

**What the fallback does NOT do:**

- Broken-wikilink detection (would need to read every page's body, then cross-reference — O(N²) in tokens).
- Orphan-page detection (same reason).
- Gate-override-rate reporting (the override log lives in the project; the fallback could read it but the Python script's output format is more concise).

If those checks are needed and Python isn't an option, dispatch the `wiki-linter` subagent (`agents/wiki-linter.md`) — it has a fresh context budget and can afford the full scan once per session.

## Process Flow

```dot
digraph lint {
    "Locate lint script" [shape=box];
    "Run lint-wiki.py" [shape=box];
    "Parse output" [shape=box];
    "Errors present?" [shape=diamond];
    "Fix errors inline" [shape=box];
    "Warnings: fix / defer / ignore" [shape=box];
    "Orphans: link / delete / mark root" [shape=box];
    "Re-run lint" [shape=box];
    "Exit 0 on errors?" [shape=diamond];
    "Log run summary" [shape=box];
    "Done" [shape=doublecircle];

    "Locate lint script" -> "Run lint-wiki.py";
    "Run lint-wiki.py" -> "Parse output";
    "Parse output" -> "Errors present?";
    "Errors present?" -> "Fix errors inline" [label="yes"];
    "Errors present?" -> "Warnings: fix / defer / ignore" [label="no"];
    "Fix errors inline" -> "Warnings: fix / defer / ignore";
    "Warnings: fix / defer / ignore" -> "Orphans: link / delete / mark root";
    "Orphans: link / delete / mark root" -> "Re-run lint";
    "Re-run lint" -> "Exit 0 on errors?";
    "Exit 0 on errors?" -> "Fix errors inline" [label="no"];
    "Exit 0 on errors?" -> "Log run summary" [label="yes"];
    "Log run summary" -> "Done";
}
```

## What lint-wiki.py Checks

(per the template's `scripts/lint-wiki.py`)

- Frontmatter present + required fields (`title`, `type`, `created`, `updated`, `status`, `author`)
- `type` ∈ {entity, concept, source, synthesis}
- `status` ∈ {draft, review, stable}
- `author` ∈ {human, llm, mixed}
- Dates are ISO (`YYYY-MM-DD`)
- Wikilinks `[[...]]` resolve to existing files
- No duplicate page titles within a section
- Orphan detection (pages with zero incoming wikilinks)

## Common Fixes

| Error | Fix |
|-------|-----|
| `missing frontmatter field: status` | Add `status: draft` (or proper value) |
| `broken wikilink: [[finkelstein-2003]]` | Either create `knowledge/sources/finkelstein-2003.md` via `ingest-source`, or correct the slug |
| `invalid type: Person` | Change to `entity` (types are: entity, concept, source, synthesis) |
| `created is not ISO date` | Reformat to `YYYY-MM-DD` |
| `orphan: knowledge/entities/foo.md` | Add an incoming link from a relevant source/synthesis page |

## Red Flags

| Thought | Reality |
|---------|----------|
| "Lint is bureaucracy, skip it" | SOFT-GATE before drafting and finishing. The override gets logged. |
| "I'd notice broken wikilinks while reading" | No — when rendered they vanish silently. They're only visible to the linter. |
| "Orphans are fine, just internal notes" | Orphan means unreachable. Link them in or delete them. |
| "I can ignore all warnings" | Every warning needs a decision, not silence. |

## Key Principles

- **Fail loud, fix fast** — errors block, warnings demand a decision
- **One lint run = one log entry** — traceability
- **Orphans are a smell** — often a sign of missing synthesis
- **Lint BEFORE draft** — never after the fact
- **Subagent for bulk fixes** — don't burn the main context on large wikis
