---
title: "Iron Age IIA Chronology in the Southern Levant — Research Plan"
type: plan
created: 2026-04-19
updated: 2026-04-19
status: ready
author: mixed
design: "[[low-chronology-design]]"
methodology: hermeneutic
---

# Iron Age IIA Chronology in the Southern Levant — Research Plan

**Slug:** `low-chronology-iron-age`
**Design:** [`input/ideas/low-chronology-design.md`](low-chronology-design.md)
**Output target:** journal article (~6,000 words), *Tel Aviv* or *Near Eastern Archaeology*
**Language:** en

> **For agentic workers:** REQUIRED SUB-SKILL: Use `research-superpowers:executing-research-plan` to run this plan task by task.

**Research Question:** Did the central Negev fortresses fall within the chronological window of the early *Iron IIA* (10th c. BCE), as Cohen 1979 argued, or later (9th c. BCE), as the *Low Chronology* of Finkelstein 1999 / 2003 requires?

**Method sketch (hermeneutic):** Close reading of the foundational positions and the *Forschungsstand* literature; per-source ingest with a focus aligned to that source's contribution to the Negev-fortress sub-question; synthesis traces the argument structure of the debate; draft argues for one of the three interpretive outcomes named in the design (regional variation / one-resolution / Forschungsstand reading).

**Expected source corpus:** Cohen 1979, Finkelstein 1999 / 2003, Finkelstein & Piasetzky 2003, Mazar 2011, Regev et al. 2020, plus ~15 further A/B-rated *Forschungsstand* sources from a literature-review pass.

**Iteration expectation:** Multiple cycles between `ingest-source` and this plan are expected. The hermeneutic circle is constitutive: each ingest may sharpen the project's question; that's logged in `knowledge/_meta/log.md` as the loop runs, not held against the original framing.

---

## Data Sources

- [[finkelstein-piasetzky-2003]] — *already ingested* (focus: 14C reconciliation between Low and Modified Conventional Chronologies)
- [[mazar-2011]] — stub ingested (focus: Modified Conventional Chronology response to the Low Chronology)
- [[regev-et-al-2020]] — stub ingested (focus: current Tel Rehov 14C dataset)
- Cohen 1979 — *ingest pending* (focus: stratigraphic and ceramic argument for 10th-c. Negev fortress horizon)
- Finkelstein 1999 — *ingest pending* (focus: Low Chronology methodology)
- Finkelstein 2003 — *ingest pending* (focus: Low Chronology applied to Megiddo and the southern Levant)

Forschungsstand literature: discovered by a `literature-review` pass; ingested per source under a project-question-aligned focus.

---

## Tasks

### Task 1: Literature review

**Files:** `input/bibliography/literaturguide.md`, `output/bibtex/references.bib`

- [ ] Dispatch `literature-scout` (OpenAlex, IxTheo, Zenon-DAI, Propylaeum), 1979–2025
- [ ] Screen and grade (A/B/C). Minimum 15 A/B sources
- [ ] Generate `literaturguide.md` in 9-section format
- [ ] Update `references.bib`

### Task 2: Ingest foundational sources

**Files:** `knowledge/sources/*.md`, `knowledge/entities/*.md`

- [ ] Cohen 1979 — focus: "Cohen's stratigraphic and ceramic argument for a 10th-c. Negev fortress horizon"
- [ ] Finkelstein 1999 — focus: "Low Chronology methodology and the regional argument"
- [ ] Finkelstein 2003 — focus: "Low Chronology applied to monumental architecture, implications for Negev"
- [ ] (Finkelstein & Piasetzky 2003 already ingested; re-ingest only if the focus drifts)
- [ ] Wiki-lint exits 0

### Task 3: Ingest *Forschungsstand* sources

**Files:** `knowledge/sources/*.md`

- [ ] Ingest ≥ 8 further A/B-rated sources from the literature-review output, each with a per-source focus statement
- [ ] Each ingest produces source page + entity stubs + BibTeX entry + log line
- [ ] Wiki-lint exits 0 after each batch of 3 ingests

### Task 4: Synthesise the chronology debate

**Files:** `knowledge/synthesis/chronology-debate.md`

- [ ] Trace argument structure: data selection, calibration, phase modelling, framework choice
- [ ] Map which side hinges on which evidence at each level
- [ ] Reference each source via its focus block(s)
- [ ] Apply Critical-Thinking checklist (`executing-research-plan`) before marking ready
- [ ] User sets `status: stable` after review (agents never self-promote)

### Task 5: Draft article

**Files:** `output/article/article.md`

- [ ] Confirm `wiki-lint` exits 0
- [ ] Skeleton: Introduction → Forschungsstand → Argument structure of the debate → The Negev case → Discussion → Conclusion
- [ ] Sign-off on skeleton with user
- [ ] Draft section by section, ~6,000 words ±15%
- [ ] Inline citations as `[@bibkey, p. XX]` only from `output/bibtex/references.bib`
- [ ] `quarto render` exits 0

### Task 6: Peer review

**Files:** `output/article/reviews/`

- [ ] Dispatch constructive reviewer (archaeology focus)
- [ ] Dispatch adversarial reviewer (Bayesian-methodology focus, even though we don't run a model — the methodological framing must still hold up)
- [ ] Classify each issue Major / Minor / Editorial
- [ ] Walk user through each with accept / reject / defer decisions

### Task 7: Finish

- [ ] Closing checklist (see `finishing-a-research-project`)
- [ ] Zenodo DOI for the manuscript + supplementary
- [ ] Submission handoff (cover letter draft)

---

## Verification

The project is complete when:

- [ ] `scripts/lint-wiki.py` exits 0
- [ ] ≥ 15 sources ingested under focus statements, all with `status: stable` (set by the user)
- [ ] `knowledge/synthesis/chronology-debate.md` has `status: stable`
- [ ] `quarto render` on `output/article/` produces PDF without warnings
- [ ] Peer-review round completed with all Major issues resolved or explicitly deferred with rationale
- [ ] Manuscript explicitly commits to one of the three interpretive outcomes (regional variation / one-resolution / Forschungsstand reading)
- [ ] Zenodo deposit logged

## Hermeneutic-revision log

Hermeneutic projects expect the research question to shift through engagement with sources. Revisions to this plan are logged in `knowledge/_meta/log.md` with date and rationale; the design doc is the stable anchor, the plan accretes.

**So far:** —

---

**Sign-off:** 2026-04-19, Patrick Leiverkus (status: ready — no pre-registration required for this hermeneutic project)
**Next:** `executing-research-plan` skill
