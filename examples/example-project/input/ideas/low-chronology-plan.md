# Low Chronology Iron Age II — Research Plan

**Status:** pre-registered (2026-04-19 — Patrick Leiverkus)
**Slug:** `low-chronology-iron-age`
**Design:** `input/ideas/low-chronology-iron-age-design.md`
**Output target:** article (*Radiocarbon* or *Ägypten und Levante*)

---

## Research Question

Does a re-analysis of all published 14C dates from Megiddo, Hazor, Gezer, and
Tel Rehov (2001–2024), using IntCal20 and a unified Bayesian phase model,
support Finkelstein's *Low Chronology*, Mazar's *High Chronology*, or
neither?

## Hypothesis (pre-registered — FROZEN)

> H1: The unified Bayesian model with IntCal20 yields phase posteriors whose
> 68% HPD intervals for the *Iron IIA → IIB* transition fall between
> 880 and 830 BCE (*Low Chronology*).
>
> H0: The transition falls between 930 and 880 BCE (*High Chronology*) or
> is wider than 80 years (indeterminate).

## Falsification Criteria

- **H1 rejected** if the 68% HPD median > 890 BCE OR the HPD width > 80 years.
- **H1 confirmed** if the 68% HPD median ≤ 880 BCE AND the HPD width ≤ 80 years.
- **Indeterminate** if calibration sensitivity > 20 years' variance between
  IntCal13 / IntCal20 / IntCal22.

## Method

1. **Data ingest:** All 14C measurements from the key publications (see
   below) compiled as a structured table (`input/data/c14-levant-ironage.csv`):
   lab ID, site, stratum, material, conventional age, σ, context, publication.
2. **Bayesian model (OxCal 4.4):** Phase model with boundary priors after
   Bronk Ramsey (2009); IntCal20 as default.
3. **Sensitivity analysis:** Re-run with IntCal13 and IntCal22; comparison
   of phase posteriors.
4. **Interpretation:** Check against the pre-registration. Deviation log
   for any divergent findings.

## Data Sources (ingest required)

- `[[finkelstein-piasetzky-2003]]` — *Low Chronology* argument
- `[[finkelstein-piasetzky-2011]]` — 14C update
- `[[mazar-2011]]` — *High Chronology* response
- `[[regev-et-al-2020]]` — Tel Rehov dataset
- `[[bronk-ramsey-2009]]` — Bayesian methodology
- `[[reimer-et-al-2020]]` — IntCal20

Dataset: `input/data/c14-levant-ironage.csv` (produced in Task 2).

---

## Tasks

### Task 1: Literature & Source Ingest

- [ ] Literature-scout dispatch (OpenAlex, IxTheo, Zenon-DAI, 2001–2026)
- [ ] Ingest `[[finkelstein-piasetzky-2003]]`
- [ ] Ingest `[[finkelstein-piasetzky-2011]]`
- [ ] Ingest `[[mazar-2011]]`
- [ ] Ingest `[[regev-et-al-2020]]`
- [ ] Ingest `[[bronk-ramsey-2009]]`
- [ ] Ingest `[[reimer-et-al-2020]]`
- [ ] Ingest ≥ 8 further A/B-rated sources from scout output
- [ ] Wiki-lint green
- [ ] Synthesis: `[[chronology-debate]]` status draft

### Task 2: Data Extraction

- Files: `input/data/c14-levant-ironage.csv`, `output/data-analysis/extract.py`
- [ ] Python script to parse the appendix tables (PDF → CSV)
- [ ] Manual validation (sample n=20)
- [ ] Spec review (complete against sources?) + quality review (units, σ)
- [ ] Commit `c14-levant-ironage.csv` with SHA log

### Task 3: Bayesian model in OxCal

- Files: `output/data-analysis/oxcal/phases.oxcal`, `output/data-analysis/oxcal/run.sh`
- [ ] Write the OxCal input file (4 phases: *Iron I*, *IIA early*, *IIA late*, *IIB*)
- [ ] Run the model, check convergence (A-index ≥ 60)
- [ ] Export posteriors as JSON
- [ ] Spec review + quality review

### Task 4: Sensitivity Analysis

- Files: `output/data-analysis/sensitivity.py`, `output/data-analysis/results/sensitivity.json`
- [ ] Re-run with IntCal13, IntCal22
- [ ] Posterior comparison (median, 68% HPD width)
- [ ] Heatmap `output/data-analysis/results/sensitivity.png`
- [ ] Spec review + quality review

### Task 5: Synthesis & Interpretation

- Files: `knowledge/synthesis/chronology-debate.qmd`
- [ ] Compare results against the pre-registration (H1 / H0 / indeterminate)
- [ ] Deviation log if divergent
- [ ] Status → `review` (not `stable`: only the user sets that)

### Task 6: Draft Article

- Files: `output/publication/article/main.qmd` (sections: Introduction / Methods /
  Results / Discussion / Conclusion), target ~9,000 words
- [ ] Skeleton + sign-off
- [ ] Draft section by section (6 sections)
- [ ] Citations exclusively from `output/bibtex/references.bib`
- [ ] `make render` exit code 0
- [ ] Word count ± 10%

### Task 7: Peer Review

- [ ] Dispatch a constructive reviewer (archaeology focus)
- [ ] Dispatch an adversarial reviewer (Bayesian-methodology focus)
- [ ] Review documentation in `output/publication/article/reviews/2026-MM-DD-review.md`
- [ ] Walk major issues with the user

### Task 8: Finish

- [ ] `/finish-project` closing checklist
- [ ] Zenodo DOI
- [ ] Reproducibility statement
- [ ] Submission handoff (cover-letter draft)

---

## Verification

- [ ] `scripts/lint-wiki.py` exits 0
- [ ] ≥ 14 sources ingested with `status: stable` (set by the user)
- [ ] `knowledge/synthesis/chronology-debate.qmd` status ≥ `review`
- [ ] `output/data-analysis/results/sensitivity.json` reproducible
  (seed fixed, environment lockfile present)
- [ ] `make render` produces PDF without warnings
- [ ] Hypothesis explicitly evaluated (confirmed / refuted / inconclusive)
- [ ] Peer-review document on file

## Deviations Log

Every deviation from this plan is noted here AND in `knowledge/_meta/log.qmd`.
Format:

```
- YYYY-MM-DD · deviation · plan=low-chronology-iron-age · <what changed and why>
```

**So far:** —

---

**Pre-registration sign-off:** 2026-04-19, Patrick Leiverkus
**Next:** `/execute-plan`
