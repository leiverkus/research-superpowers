---
name: executing-research-plan
description: Use AFTER writing-research-plan has produced a ready plan (status=ready for hermeneutic projects, status=pre-registered for quantitative/mixed). Reads `input/ideas/<slug>-plan.md`, creates one task-list item per plan task, runs a pre-ingest acquisition gate (acquire-sources) so originals are on disk before any source-ingester runs, and works tasks via subagent dispatch (source-acquirer, source-ingester, analyst, drafter) with two-stage review. Does not execute anything outside the plan.
inputs:
  - name: plan_path
    description: Path to input/ideas/<slug>-plan.md — status=ready (hermeneutic) or status=pre-registered (quantitative/mixed)
    required: true
  - name: project_root
    description: Absolute path to the research project root
    required: true
outputs:
  - path: knowledge/sources/, knowledge/entities/, knowledge/synthesis/
    kind: created_or_modified
  - path: output/data-analysis/**
    kind: created_or_modified
  - path: output/**/*.md
    kind: created_or_modified
  - path: knowledge/_meta/log.md
    kind: appended
agents:
  - source-acquirer
  - source-ingester
  - analyst
  - drafter
---

# Executing a Research Plan

Run a pre-registered plan task by task. Dispatch the right subagent per task, review each result (spec + quality), and only mark done when both reviews pass. Deviations are logged, not hidden.

**Announce at start:** "Using executing-research-plan to run `<slug>-plan.md`."

<SOFT-GATE>
Before executing a task, check:
(1) The task is listed in `input/ideas/<slug>-plan.md`
(2) For `methodology: quantitative` or any task block marked as quantitative: plan frontmatter `status: pre-registered` with user sign-off
(3) For `methodology: hermeneutic`: plan frontmatter `status: ready` is enough — a frozen hypothesis is not required

If unmet: explain to the user which condition is missing, ask for a short
reason, write it to `knowledge/_meta/gate-overrides.log`, and start the
task.

A task is "done" only when the type-specific review passes (see "Review by
methodology" below). Never silently rewrite a hypothesis mid-run —
deviations go into the deviation log.
</SOFT-GATE>

## Checklist

1. **Load the plan** — read `input/ideas/<slug>-plan.md` end-to-end
2. **Verify the plan is ready** (methodology-aware): `methodology: hermeneutic` → frontmatter `status: ready` is enough (no frozen hypothesis); `methodology: quantitative`/`mixed` (or a task block marked `pre-registered: true`) → `status: pre-registered` + user confirmation of the hypothesis
3. **Create task-list items** — one per task in the plan (use the plan's own wording)
4. **Personal-data check (before any task that reads `input/data/` or `input/notes/`)** — interviews, questionnaires, field notes or excavation diaries naming living people, correspondence, unpublished data shared by colleagues. Ask once: does this material contain personal or confidential data, and do the consent forms / data agreements allow processing by the AI provider this session uses? If not, or unknown: stop that task and say so — the options are anonymising first (remove names, places, identifiers before the file is read), or running the task with a local / institution-hosted model (e.g. KISSKI/GWDG, a local Ollama or LM Studio model). Record the answer in the plan's task block (`personal_data: none | anonymised | local-model-only`) so the next session does not ask again. Published scholarship and the user's own non-personal notes need no check
5. **Acquisition gate (before any ingest task)** — guarantee the originals are on disk first; run the **Acquisition gate** algorithm below. `literature-review` only searches — without this gate every `source-ingester` hard-stops on a missing PDF.
6. **Route each task to the right subagent:**
   - **Ingest task** → `source-ingester` (see `agents/source-ingester.md`)
   - **Analysis task** → `analyst` (runs Python/R in `output/data-analysis/`)
   - **Synthesis task** → main conversation, not subagent (high context integration) — follow [Writing a synthesis](#writing-a-synthesis)
   - **Draft task** → invoke `drafting-manuscript` skill (which may dispatch `drafter`)
7. **Two-stage review per task:**
   - **Spec reviewer** (fresh subagent): does the output match the task spec exactly?
   - **Quality reviewer** (fresh subagent): is the code/page/result methodologically sound?
   - Any "no" → route back to the executing subagent with reviewer feedback
8. **Log deviations** — if findings force change, append to `knowledge/_meta/log.md` and mark subsequent analyses as exploratory
9. **Run wiki-lint after every ingest and synthesis task**
10. **After all tasks done:** check plan's Verification section; only green on all boxes means complete
11. **Transition:** if plan output target is book/article → `drafting-manuscript`; if grant → `grant-finder`; if done → `finishing-a-research-project`

## Acquisition gate (before any ingest task)

`literature-review` searches but downloads nothing; `source-ingester` **hard-stops**
on a missing original. This gate sits between them: it guarantees every ingest
task's PDF is on disk (or explicitly deferred) before the first `source-ingester`
is dispatched — so you get one clean acquisition step instead of a wall of
per-source hard-stops.

1. **Collect required originals** — from every ingest task in the plan, derive the
   expected library path `<library>/pdf/<bibkey>.pdf` (the naming
   convention `acquire-sources` writes and `ingest-source` reads).
2. **Scan the library** — `<library>/pdf/*.pdf` (resolve with `scripts/library.py`;
   never in subfolders). If every required original is present → skip the gate,
   go to routing.
3. **Attempt acquisition** — run `acquire-sources` on the A+B set (dispatch the
   `source-acquirer` subagent for ≥ ~8 missing items). It auto-downloads the
   Open-Access copies into the library and (re)generates `input/bibliography/acquisition-todo.md`.
4. **If `acquisition-todo.md` is non-empty** (originals still missing), enter the
   **interactive resume loop** — do NOT silently skip:
   - **a. Offer the list.** Present the missing sources from `acquisition-todo.md`
     plus the manual-download instruction (university VPN / library proxy; save
     each into `<library>/pdf/` under the exact `<bibkey>.pdf`
     filename). Mark the dependent ingest tasks as blocked and **pause** —
     do not dispatch those ingests.
   - **b. On the user's resume signal**, re-scan `<library>/pdf/` for the newly
     added PDFs and **reconcile** — re-run `acquire-sources` in reconcile mode:
     resolved rows drop out of (are checked off) `acquisition-todo.md`.
   - **c. Ask the branch:** "Search for **alternatives** (open-access substitutes
     via `literature-review`) for what's still missing, or **continue with what's
     present**?"
     - *Alternatives* → loop back to `literature-review` / `literature-scout` to
       find OA alternatives for the gaps, grade them into the guide table, then
       re-run `acquire-sources` on the new candidates → back to step 4.
     - *Continue* → proceed to routing with the acquired subset.
   - **d. Loop a–c** until the user says to move on to ingest.
5. **Proceed to routing** — dispatch `source-ingester` only for tasks whose
   original is now on disk; any still-missing stay `blocked`/deferred per the
   user's choice. Non-blocked downstream work (analysis on existing data, etc.) is
   not held up by a blocked ingest.

> **"Alternativen" = a different open-access source on the same topic**, NOT a
> preprint/prior-version/review substitute for the *same* paper. Substituting one
> edition for another remains `ingest-source`'s consent-gated decision and is out
> of scope for this gate.

## Process Flow

```dot
digraph executing {
    "Load plan" [shape=box];
    "Pre-registered & signed?" [shape=diamond];
    "Back to writing-research-plan" [shape=box];
    "Create task list from plan" [shape=box];
    "Acquisition gate: scan the library" [shape=box];
    "All originals present?" [shape=diamond];
    "Run acquire-sources" [shape=box];
    "Worklist empty?" [shape=diamond];
    "Offer manual list, block ingests, pause" [shape=box];
    "User resumes" [shape=box];
    "Reconcile (re-scan + re-run)" [shape=box];
    "Alternatives or continue?" [shape=diamond];
    "literature-review for OA alternatives" [shape=box];
    "Next task" [shape=box];
    "Route by task type" [shape=diamond];
    "Dispatch source-ingester" [shape=box];
    "Dispatch analyst" [shape=box];
    "Handle synthesis inline" [shape=box];
    "Invoke drafting-manuscript" [shape=box];
    "Spec review" [shape=box];
    "Quality review" [shape=box];
    "Both pass?" [shape=diamond];
    "Route back with feedback" [shape=box];
    "Mark task done" [shape=box];
    "More tasks?" [shape=diamond];
    "Verify against plan checklist" [shape=box];
    "All green?" [shape=diamond];
    "Transition" [shape=doublecircle];

    "Load plan" -> "Pre-registered & signed?";
    "Pre-registered & signed?" -> "Back to writing-research-plan" [label="no"];
    "Pre-registered & signed?" -> "Create task list from plan" [label="yes"];
    "Create task list from plan" -> "Acquisition gate: scan the library";
    "Acquisition gate: scan the library" -> "All originals present?";
    "All originals present?" -> "Next task" [label="yes"];
    "All originals present?" -> "Run acquire-sources" [label="no"];
    "Run acquire-sources" -> "Worklist empty?";
    "Worklist empty?" -> "Next task" [label="yes"];
    "Worklist empty?" -> "Offer manual list, block ingests, pause" [label="no"];
    "Offer manual list, block ingests, pause" -> "User resumes";
    "User resumes" -> "Reconcile (re-scan + re-run)";
    "Reconcile (re-scan + re-run)" -> "Alternatives or continue?";
    "Alternatives or continue?" -> "literature-review for OA alternatives" [label="alternatives"];
    "literature-review for OA alternatives" -> "Run acquire-sources";
    "Alternatives or continue?" -> "Next task" [label="continue"];
    "Next task" -> "Route by task type";
    "Route by task type" -> "Dispatch source-ingester" [label="ingest"];
    "Route by task type" -> "Dispatch analyst" [label="analysis"];
    "Route by task type" -> "Handle synthesis inline" [label="synthesis"];
    "Route by task type" -> "Invoke drafting-manuscript" [label="draft"];
    "Dispatch source-ingester" -> "Spec review";
    "Dispatch analyst" -> "Spec review";
    "Handle synthesis inline" -> "Spec review";
    "Invoke drafting-manuscript" -> "Spec review";
    "Spec review" -> "Quality review";
    "Quality review" -> "Both pass?";
    "Both pass?" -> "Route back with feedback" [label="no"];
    "Route back with feedback" -> "Next task";
    "Both pass?" -> "Mark task done" [label="yes"];
    "Mark task done" -> "More tasks?";
    "More tasks?" -> "Next task" [label="yes"];
    "More tasks?" -> "Verify against plan checklist" [label="no"];
    "Verify against plan checklist" -> "All green?";
    "All green?" -> "Next task" [label="no, fix"];
    "All green?" -> "Transition" [label="yes"];
}
```

## Task Type Routing

| Plan keyword | Subagent / Skill | Output landing zone |
|--------------|------------------|---------------------|
| "Acquire / fetch PDFs / besorge Quellen" | `acquire-sources` skill (→ `source-acquirer` for ≥8) | `<library>/pdf/*.pdf`, `input/bibliography/acquisition-todo.md` |
| "Ingest X" | `source-ingester` | `knowledge/sources/`, `knowledge/entities/`, `output/bibtex/` |
| "Analyze / compute / run" | `analyst` | `output/data-analysis/`, `output/data-analysis/results/` |
| "Synthesize / integrate / write synthesis" | inline (main conversation) | `knowledge/synthesis/` |
| "Draft chapter / section / article" | `drafting-manuscript` skill | `output/**/*.md` |

## Writing a synthesis

A synthesis is where the project says what its sources add up to, and it is
where model-written text is weakest. The typical failure is not a false
statement but an empty one: *"a complex picture emerges"*, *"the evidence must
be assessed in a differentiated way"*, *"cult centralisation played an
important role"*, *"further research is needed"*. Each sentence is true of
almost any topic, so it says nothing about this one. Such sentences are the
model's safe default when it integrates many sources at once: the averaged
position, hedged on all sides. The rules below make the specific conclusion the
easier one to write.

1. **Re-read before concluding.** Write the conclusions from the source pages
   (and their focus blocks) re-read now — not from the ingest summaries still
   in the conversation, which are compressed already. A synthesis written at
   the end of a long ingest run is a summary of summaries.
2. **The author's conclusion first.** Before writing the conclusions, ask the
   user what they think the material shows, in their own words (rough is fine)
   — the same discipline as `drafting-manuscript` STOP 0, for the same reason:
   approving a polished machine conclusion is not drawing one. Do not offer a
   candidate in that message. If the user asks you to propose, mark the
   conclusion `agent-proposed` in the page until they restate it.
3. **Each conclusion is a claim block**, not a paragraph of summary:

   ```markdown
   ### C1 — <short label>
   - **Claim:** <one sentence that could turn out wrong>
   - **Kind:** finding (what the sources report) | reading (an interpretation in
     the literature — whose) | own thesis (the project's inference — marked as such)
   - **Carried by:** [[source-a]] (p. 61), [[source-b]] (p. 12–14) — n independent sources
   - **Concrete anchor:** <the named site / passage / stratum / dating / dataset
     the claim is about>
   - **Against:** <the strongest counter-position, cited — or "none found in the wiki">
   - **Would be wrong if:** <the finding or argument that would overturn it>
   ```

   A conclusion with no concrete anchor, or nothing that could make it wrong, is
   not finished: narrow it until it has both, or move it to `What stays open`.
4. **Specificity test.** For every sentence in the conclusions, swap the topic
   words for a neighbouring topic (another site, another text, another period).
   If the sentence is still true, it says nothing here — cut it or make it
   specific. Typical offenders, in both languages: *komplexes / vielschichtiges
   Bild*, *differenziert zu betrachten*, *spielt eine wichtige / zentrale Rolle*,
   *im Spannungsfeld von*, *weitere Forschung ist nötig*, *a nuanced picture
   emerges*, *plays a crucial role*, *highlights the importance of*,
   *multifaceted*, *it remains to be seen*.
5. **Disagreement is a finding, not a conclusion.** "Scholars disagree" says
   something about the literature. Say who holds what, on which evidence, since
   when (see the research chronology) — and what the project concludes from
   that: one side, a third reading, or an explicit bracket with the reason.
6. **Open questions are specific too.** `What stays open` names the question
   and what would settle it (a source not yet read, an excavation report, a
   test) — not "further research is needed".
7. **Keep the hedges the sources give, and add none of your own.** A conclusion
   is as strong as its sources carry; the hedge goes on the claim where the
   evidence is thin, not across the whole page as insurance.

## Critical Thinking — Cross-Cutting Checklist

Walk through this on every method choice and before every subagent dispatch:

1. **Claim first, then evidence** — what exactly is being claimed? State the claim precisely, then ask what evidence would support it.
2. **Evidence type** — primary data, secondary synthesis, expert opinion, theoretical argument. Drives the method choice.
3. **Framework matched to discipline:**
   - **GRADE** — causal / quantitative claims
   - **Cochrane ROB** — experimental designs
   - **Source-critical (*Quellenkritik*)** — textual-historical sources
   - **Stratigraphic reliability** — archaeological claims
   - **Reproducibility audit** — computational / DH
4. **Name confounders explicitly** — what gets overlooked, what could explain the finding otherwise
5. **Check logical fallacies** — ad hominem, affirming the consequent, equivocation, cherry-picking, post hoc
6. **Falsifiability** — what would refute the claim?

If the answer to any of these is "I don't know," that belongs in the quality review or gets resolved before dispatch.

## Review by Methodology

The review tiering depends on the `methodology` field in the project
frontmatter (`CLAUDE.md`) or in the task-block frontmatter.

### Quantitative Tasks — Two-Stage Review

For tasks under `methodology: quantitative` or task blocks with
`pre-registered: true`: dispatch two fresh subagents (minimal context:
just task spec + output):

**Spec reviewer prompt template:**
> You are a spec compliance reviewer. Task spec: <paste from plan>. Output: <paste or path>. Does the output match the spec exactly? Report mismatches. Do not assess quality.

**Quality reviewer prompt template:**
> You are a methodological quality reviewer. Output: <paste or path>. Methodological context: <paste plan Method section>. Is this sound? Check: (1) are assumptions stated, (2) are limitations named, (3) does the script contain control checks with known answers, and do they pass, (4) does the load-bearing result agree across the independent recomputation, (5) is each procedure's choice justified by the plan rather than by its result, (6) would a peer reviewer accept this? Report issues.

Both "yes" → task done. Any "no" → feedback back to the executing subagent.

### Hermeneutic Tasks — Synthesis Review

For tasks under `methodology: hermeneutic` (no pre-registration):
single-stage review in the main context, focused on plausibility and
source fidelity rather than spec compliance.

**Synthesis reviewer prompt template (in main context, no subagent needed):**
> Output: <path or paste>. Method sketch: <from plan>.
> (1) Is the argument actually supported by the cited sources
>     (spot-check 3 central citations)?
> (2) Are alternative readings named where they suggest themselves?
> (3) Is the hermeneutic position transparent (which pre-understanding
>     horizon, which method is applied)?
> (4) Is every conclusion specific? Apply the specificity test from
>     "Writing a synthesis" to each sentence of the conclusions and quote the
>     ones that would hold for a neighbouring topic just as well.
> (5) Is every conclusion a complete claim block — concrete anchor,
>     carrying sources with pages, kind (finding / reading / own thesis), a
>     counter-position, and what would make it wrong?

Return findings as correction notes, not as a pass/fail gate. The user
decides final acceptance.

### Mixed Projects

The plan marks per task which review mode applies. Pre-registered tasks
run through two-stage; hermeneutic tasks run through synthesis review.

## Deviations

If a task surfaces a result that contradicts the pre-registered hypothesis, or if the method must change:

1. **Stop.** Do not rewrite the hypothesis.
2. **Append to `knowledge/_meta/log.md`:**
   ```
   - YYYY-MM-DD · deviation · plan=<slug> · <what changed and why>
   ```
3. **Mark any analysis downstream of the deviation as exploratory** in its frontmatter (`status: exploratory`).
4. **Surface to user** — "The plan said X, the data shows Y. Continuing as exploratory. OK?"

## Red Flags

| Thought | Reality |
|---------|---------|
| "Just start ingesting — the PDFs are probably there" | No — run the acquisition gate first; otherwise every `source-ingester` hard-stops on a missing original, one source at a time. |
| "Some originals are still missing, I'll just skip them quietly" | No — surface the worklist, block those ingests, and let the user fetch them or pick alternatives. Silent skipping hides gaps. |
| "The hypothesis doesn't fit, I'll tweak it slightly" | No — log entry, result becomes exploratory. |
| "Review is overkill for such a small task" | Small tasks are exactly where errors slip past. Always both reviews. |
| "I'll just do it myself instead of dispatching a subagent" | Subagent isolation protects context and forces prompt clarity. |
| "The synthesis is stable now" | Only the user sets `stable`. |
| "A complex picture emerges — that's an honest conclusion" | It is true of every topic. Name who holds what, on which evidence, and what the project concludes. |
| "I just ingested all the sources, I can write the synthesis from that" | You have their summaries in context, already compressed. Re-read the source pages before concluding. |
| "I'll hedge the conclusions to be safe" | Hedge the claim whose evidence is thin, with the reason. A blanket hedge makes every conclusion unfalsifiable. |

## Key Principles

- **Acquire before ingest** — the acquisition gate guarantees originals are on disk (or explicitly deferred) before any `source-ingester` runs
- **The plan is law** — anything outside the plan is scope creep or deviation
- **One subagent per task** — fresh context, no context collapse
- **Two-stage review** — spec THEN quality, not mixed
- **Deviation > revision** — divergent findings get flagged, not absorbed
- **Verification is a list, not a feeling** — the plan's checkboxes are the completion test
