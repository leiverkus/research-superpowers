# Tutorial — End-to-End Walkthrough

A complete pass through every phase, on one realistic example. The example project ("Iron Age IIA Chronology in the Southern Levant") matches `examples/example-project/` in the plugin repo — you can compare against the artefacts checked in there.

Time: 30–60 minutes for the read-through; the actual research it stands in for would be months.

## What we're doing

**Research question** (intentionally narrow for the tutorial): *Did the central Negev fortresses fall within the chronological window of the early Iron Age IIA (10th c. BCE), as Cohen 1979 argued, or later (9th c. BCE), as the Low Chronology of Finkelstein 1999/2003 requires?*

**Methodology**: hermeneutic. We weigh stratigraphic, ceramic, and 14C arguments from a contested literature; we do not run a quantitative sub-study in this tutorial. (If you wanted a Bayesian 14C re-analysis, you would mark that single task `pre-registered: true` and the plan template would add a hypothesis + falsification criteria block; everything else stays the same.)

**Output target**: a journal article (~6000 words) plus a peer-review pass.

## Phase 1 — Brainstorming (skill: `brainstorming-research`)

You open Claude Code in a fresh project (scaffolded from the template — see [`quickstart.md`](quickstart.md) steps 1–2) and say:

> Let's research the dating of the central Negev fortresses — Cohen 1979 vs the Low Chronology.

The assistant invokes `brainstorming-research`. It probes:

- What's the exact question? (Cohen's High Chronology vs. Finkelstein's Low Chronology, applied to the Negev fortresses specifically.)
- What's known already? (You sketch: Cohen excavated 1976–1982; published synthesis 1979; Finkelstein revised the chronology in 1996, 1999, 2003; subsequent 14C dates from Tel Rehov add complications.)
- What's the methodology? (Hermeneutic — close reading of the published reports plus the chronology-debate literature.)
- What's the deliverable? (Journal article, ~6000 words, English.)
- What would *change your mind*? (If the Cohen stratigraphy turns out to be undermined by post-Cohen excavation, or if a new 14C series from a Negev fortress site lands.)

The skill writes `input/ideas/negev-fortresses-chronology-design.md`. **SOFT-GATE:** the skill won't proceed to plan-writing until you sign off on the design. You read it, edit one sentence, say "looks good, proceed."

## Phase 2 — Writing the plan (skill: `writing-research-plan`)

The plan reads the `methodology: hermeneutic` from your project `CLAUDE.md` and uses the hermeneutic template (research question + method sketch + expected sources + iteration expectation — *no* frozen hypothesis).

It writes `input/ideas/negev-fortresses-chronology-plan.md` with tasks:

```
- [ ] Literature review on the Iron Age IIA chronology debate
- [ ] Ingest Cohen 1979 (foundational High Chronology argument)
- [ ] Ingest Finkelstein 1999 (Low Chronology core)
- [ ] Ingest Finkelstein & Piasetzky 2003 (14C reconciliation)
- [ ] Ingest Mazar 2011 (Modified Conventional Chronology response)
- [ ] Synthesise: chronology debate as it touches Negev fortresses
- [ ] Draft article (Forschungsstand → argument → conclusion)
- [ ] Peer review (constructive + adversarial)
```

You confirm, the plan is saved with `status: ready`.

## Phase 3 — Literature review (skill: `literature-review`)

You say "do the literature review." The skill confirms scope (theology + Levantine archaeology, EN/DE/HE, 1976–present) and dispatches the `literature-scout` subagent.

If you have `dao-paper-search-mcp` set up (see [`recommended-mcps.md`](recommended-mcps.md)), the scout uses `search_zenon`, `search_openalex`, `search_ixtheo` etc. and returns each hit with `inline_citation.markdown` and `audit.source_class`. Without the MCP, the scout uses manual API calls and you accept slightly less polished citation strings.

Output: `input/bibliography/literaturguide.md` with ~18 sources graded A/B/C, plus BibTeX entries merged into `output/bibtex/references.bib`, plus `input/bibliography/audit-log-2026-05-27.json`.

**SOFT-GATE:** the skill checks for ≥ 15 distinct sources. We have 18 A/B graded sources, so the gate passes. The guide records each source's `oa_pdf`/DOI but **downloads nothing** — that is the next phase.

## Phase 4 — Acquire the PDFs (skill: `acquire-sources`)

You say "acquire the sources." The skill takes the A+B set from `literaturguide.md` and, for each, tries to fetch an Open-Access PDF — preferring the recorded `oa_pdf`, then resolving via the MCP / Unpaywall by DOI. Every download is **validated** (HTTP 200 + `application/pdf` + `%PDF-` magic bytes + size + not an HTML login page), so a publisher "Access Denied" page is never mistaken for a source.

Output: the open ones land in `input/bibliography/` as `Finkelstein - The Archaeology of the Israelite Settlement - 1988.pdf` etc.; everything paywalled or bot-blocked goes into **`input/bibliography/acquisition-todo.md`** — a table with the DOI, any candidate URL, and the exact filename to save under. Say 11 of 18 download automatically; 7 need you.

You open `acquisition-todo.md`, connect the **university VPN**, and download those 7 originals into `input/bibliography/` under the given filenames. Then you say "acquire the sources" again — the re-run rescans the folder, drops the 7 now-present files from the worklist, and reports "all 18 A+B sources acquired." (Had you skipped this and gone straight to ingest, `ingest-source` would have hard-stopped on the first missing original instead of quietly ingesting a preprint.)

## Phase 5 — Ingest, one source at a time (skill: `ingest-source`)

You say "ingest the Cohen 1979 PDF." The skill first asks for a **focus** — what *this project* takes from *this source* — and proposes the project's research question as the default:

> Default focus from `input/description/project-description.md`: «Did the central Negev fortresses fall within the 10th c. BCE (Cohen 1979) or later (Low Chronology)?» Use this for the ingest, or refine? E.g. for Cohen 1979 specifically you might say "focus on Cohen's stratigraphic and ceramic argument for a 10th-c. Negev fortress horizon".

You refine — the project research question is too broad for *this* source. You give: *"Cohen's stratigraphic and ceramic argument for a 10th-c. Negev fortress horizon."*

The skill then:

1. Reads the PDF in full **under that focus** (not just abstract; reads with the focus question actively in mind, marking anything that bears on it).
2. Derives slug `cohen-1979`.
3. Creates `knowledge/sources/cohen-1979.md` with frontmatter (`type: source`, `status: review`, `author: llm`, `bibkey: cohen-1979`) and a body containing exactly one `## Focus: <your focus> — <date>` block (claims, direct quotes, explicit boundary of what the source does *not* address), a one-paragraph `## Other content in this source` note, and union `## Mentioned entities` + `## Connections` sections.
4. Extracts entities **relevant to the focus**: `cohen` (person), `negev-fortresses` (concept), `tel-arad` (place), `kadesh-barnea` (place), `iron-age-iia` (concept), `high-chronology` (concept). Entities unrelated to the focus (e.g. Cohen's brief excursus on Phoenician trade) are not extracted now — they stay in the PDF until a future re-ingest needs them.
5. Creates an entity page for each new one.
6. Writes the BibTeX entry.
7. Appends a line to `knowledge/_meta/log.md`: `- 2026-05-28 · ingest · [[cohen-1979]] · focus: «Cohen's stratigraphic and ceramic argument for a 10th-c. Negev fortress horizon»`.
8. Runs `python scripts/lint-wiki.py` — exits 0.

You repeat for Finkelstein 1999, Finkelstein & Piasetzky 2003, Mazar 2011, plus 2–3 more from the literature guide that turn out to be cited heavily. Each gets its own focus, refined from the project research question.

**Re-ingest later with a different focus.** When you start drafting the chapter on regional variation — say 6 weeks later — you realise you need Cohen 1979 again, this time for his typological comparison between the central Negev and the Beersheva Valley. You ingest again:

> "Ingest Cohen 1979 focused on the typological comparison with the Beersheva Valley."

The skill detects `knowledge/sources/cohen-1979.md` already exists with one focus block, and switches to **append mode**:

> Source `cohen-1979` is already ingested with 1 focus block:
> - 2026-05-28: "Cohen's stratigraphic and ceramic argument for a 10th-c. Negev fortress horizon"
>
> Proceeding will append a new focus block for: "the typological comparison with the Beersheva Valley".

You confirm; the skill appends a new `## Focus: …` block at the bottom of the existing page (before `## Other content in this source`), updates the "other content" paragraph if new aspects emerge, and unions any new entities into `## Mentioned entities`. The first focus block stays untouched. One bibkey, one wiki page, two lenses.

If you have `dao-paper-search-mcp`, the entity pages get populated with `wikidata_qid` (for people) and `idai_gazetteer_id` (for places) — `resolve_author("Israel Finkelstein")` returns `Q461571`; `resolve_site("Tel Megiddo")` returns `2048473`. These authority IDs let you deduplicate later and pull canonical metadata.

## Phase 6 — Executing the plan (skill: `executing-research-plan`)

For each task in the plan, the skill routes:

- **Ingest tasks** → `source-ingester` subagent (done above).
- **Synthesis task** ("chronology debate as it touches Negev fortresses") → handled in the main conversation (high context integration; subagent isolation would lose the cross-source argument).

The synthesis page lands at `knowledge/synthesis/chronology-debate-negev.md`. You read it, push back on one paragraph (the assistant overstated Mazar's position), revise together, and only then promote `status: review` → `status: stable`. **Only the user promotes to stable.** Agents never self-promote — this is a hard editorial rule, not a soft gate.

The skill walks the [Critical Thinking checklist](../skills/executing-research-plan/SKILL.md) on the synthesis before flagging it ready: claim → evidence → framework (*Quellenkritik* for textual / stratigraphic claims) → confounders → fallacies → falsifiability.

Because `methodology: hermeneutic`, the review is a single-pass "synthesis review" (plausibility + source fidelity), not the two-stage spec+quality review that quantitative tasks would get.

## Phase 7 — Drafting the article (skill: `drafting-manuscript`)

**SOFT-GATE** check before drafting:

1. At least one synthesis page is `status: stable` ✓ (`chronology-debate-negev.md`)
2. All sources cited in the planned section exist as `knowledge/sources/*.md` and have BibTeX entries ✓
3. `wiki-lint` is green ✓
4. The plan has an explicit Draft task ✓

Skill produces the section skeleton first:

```
1. Introduction — the chronology problem in the Negev
2. State of the field — Cohen 1979 to Mazar 2011
3. The case for late 10th century (High Chronology)
4. The case for 9th century (Low Chronology)
5. Reconciliation attempts (14C, Modified Conventional)
6. What the Negev fortresses can and cannot tell us
7. Conclusion
```

You approve the skeleton. The skill drafts each section in prose, citing inline as `[@cohen-1979, p. 79]`, `[@finkelstein-1999]`, etc. Every citation key gets verified against `output/bibtex/references.bib`. Direct quotes come from the source page's "Verbatim quotes" section, never reconstructed from memory.

The skill writes to `output/article/main.qmd` and runs `quarto render`. The first render fails (one citation key collision — you have `mazar-2011` and `mazar-2011b`); the skill resolves it and re-renders successfully.

Log line appended to `_meta/log.md`.

## Phase 8 — Peer review (skill: `requesting-peer-review`)

You say "review the article." The skill confirms the manuscript path, identifies discipline (Biblical Archaeology), selects reporting standards (stratigraphic documentation + source criticism), and dispatches two fresh subagents:

- **Constructive reviewer**: writes `output/article/reviews/2026-05-28-constructive-review.md`. Major Issues: "section 4 needs a clearer statement of which Negev sites the Low Chronology directly addresses vs. which it generalises over." Minor Issues, Editorial, Methodological Assessment, etc.
- **Adversarial reviewer**: writes `2026-05-28-adversarial-review.md`. Major Issues: "the manuscript treats Tel Rehov 14C as decisive for Negev datings, but the spatial separation is significant — argue this or weaken the claim."

The skill walks you through each Major and Minor: accept (→ revise), reject (with rationale), defer (with reason in log). You accept 4, defer 1. Decisions log to `_meta/log.md`.

Revisions route back to `drafting-manuscript` for one more pass.

## Phase 9 — Finishing (skill: `finishing-a-research-project`)

The closing checklist:

```
[x] make render exits 0
[x] wiki-lint exits 0
[x] All citation keys in manuscript exist in references.bib
[x] Both review reports archived
[x] Major issues resolved or deferred with rationale
[x] Hypothesis explicitly addressed (in our case: the question was settled in
    favour of a chronology that acknowledges regional variation — written
    explicitly in the conclusion)
[x] Reproducibility statement in supplementary section
[ ] DOI on Zenodo (do this now: skill offers)
[x] Closing log entry
```

You agree to the Zenodo deposit; the skill prepares the metadata (it doesn't submit on your behalf — you do that step), then logs the DOI.

`git add . && git commit -m "finish: negev-fortresses-chronology"`. Project closed.

## What you produced

```
input/ideas/
├── negev-fortresses-chronology-design.md
└── negev-fortresses-chronology-plan.md

input/bibliography/
├── literaturguide.md
├── audit-log-2026-05-27.json
├── acquisition-todo.md            (manual-download worklist; empty once all acquired)
├── acquisition-log-2026-05-28.json
└── [PDFs of each acquired source, "Lastname - Title - Year.pdf"]

knowledge/
├── _meta/
│   ├── index.md
│   └── log.md
├── sources/         (7 .md files, status review/stable)
├── entities/        (~15 .md files)
├── concepts/        (3 .md files: high-chronology, low-chronology, iron-age-iia)
└── synthesis/
    └── chronology-debate-negev.md  (status: stable)

output/
├── bibtex/references.bib
└── article/
    ├── main.qmd
    ├── main.pdf
    └── reviews/
        ├── 2026-05-28-constructive-review.md
        └── 2026-05-28-adversarial-review.md
```

Every step is reproducible from the artefacts. Every claim in the manuscript traces to a source page; every source page traces to a PDF on disk; every BibTeX entry traces to a citation key in the manuscript.

## Quantitative sub-study? Add one mid-flow.

If at Phase 7 you realised "actually a Bayesian re-analysis of the published 14C dates would help section 5," you would:

1. Go back to `writing-research-plan` and add one task with `pre-registered: true` in the task-block frontmatter.
2. State hypothesis + operationalisation + stop criterion for that task only.
3. `executing-research-plan` routes that task to the `analyst` subagent (Python with PyMC), and applies the two-stage spec+quality review.
4. The result becomes a synthesis page that the manuscript section then cites.

The rest of the project stays hermeneutic. This is what "methodology: mixed" looks like in practice.

## Where to look in the example project

`examples/example-project/` in the plugin repo has a smaller version of this same workflow — fewer sources, only the early phases populated, but you can see the file layout and frontmatter conventions in concrete form.

## Where to go next

- [`concepts.md`](concepts.md) for the *why* behind SOFT-GATEs, methodology branching, SOT pattern.
- [`skill-authoring.md`](skill-authoring.md) if you want to add a skill of your own.
- [`recommended-mcps.md`](recommended-mcps.md) to get the verified-citation MCPs into your workflow.
