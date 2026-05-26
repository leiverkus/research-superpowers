# Low Chronology Iron Age II — Research Design

**Status:** approved (2026-04-18 — Patrick Leiverkus)
**Slug:** `low-chronology-iron-age`
**Output of:** `brainstorming-research`
**Next skill:** `writing-research-plan`

---

## Research Question

How robust is Finkelstein's *Low Chronology* thesis (dating the monumental
architecture at Megiddo, Gezer, and Hazor to the 9th rather than the 10th
century BCE) in light of the 14C dates from the Tel Rehov campaigns of
2005–2020 and the more recent Bayesian models by Mazar/Streit/Regev?

## Relevance

- **Scholarly:** *Low* versus *High Chronology* decides the historical
  placement of the so-called "Davidic" and "Solomonic" monumental buildings —
  touching the intersection of archaeology, biblical historiography, and
  theology.
- **State of research (*Forschungsstand*):** The debate has been open since
  2001; 14C modelling has dominated since around 2013, but different
  calibration curves (IntCal13 versus IntCal20) have not yet been applied
  systematically to Levantine data.
- **Own contribution:** Re-analysis of all published Rehov/Megiddo 14C dates
  using IntCal20 and a unified Bayesian model (OxCal 4.4), to test whether
  the data themselves support one side or whether the gap lies in the mean.

## Method

1. Systematic literature search (OpenAlex, IxTheo, Zenon-DAI) 2001–2026,
   focused on 14C dates from the Levantine *Iron IIA*/B.
2. Ingest of the key publications as source pages.
3. Extraction of all published raw 14C data (lab ID, material, conventional
   age, σ).
4. Bayesian phase model in OxCal 4.4 (IntCal20) for the *Iron I → IIA → IIB*
   transitions.
5. Sensitivity analysis: IntCal13 vs IntCal20, different phase-boundary
   priors.
6. Interpretation: *Low* confirmed / *High* confirmed / indeterminate.

## Data sources

- Finkelstein & Piasetzky (2003, 2011, 2015) — *Low Chronology* core texts
- Mazar (2005, 2011) — *High Chronology* counter-position
- Regev, Finkelstein, Adams, Boaretto (various) — 14C datasets
- Tel Rehov excavation reports (Mazar et al. 2005, 2020)
- OxCal 4.4 + IntCal20 (reference software and curve)

## Output target

**Article** (~9,000 words) for *Radiocarbon* or *Ägypten und Levante*.

Secondary use: a chapter precursor for a later *Habilitation* on Levantine
chronology.

## Expected outcomes

One of three scenarios:
- **S1 (*Low* confirmed):** Bayesian model with IntCal20 shifts the means
  by < 10 years; the central hypothesis (9th-century monumental construction)
  stands.
- **S2 (*High* confirmed):** Systematic upward shift of > 15 years; the Mazar
  position is strengthened.
- **S3 (indeterminate):** Overlap of the phase posteriors is too large to
  decide — calibration identified as the bottleneck.

Pre-registration fixes which scenario corresponds to which data outcome.

## Risks

- **Data availability:** Some raw data appear only in appendices of
  unpublished dissertations — requests to laboratories may be necessary.
- **Calibration updates:** IntCal20 was published in 2020 and updated in
  2025 — the version used must be documented.
- **Bias:** The author was socialised within a theological milieu —
  adversarial peer review (by an archaeologist) is mandatory.

## Feasibility

- **Timeframe:** 6 months (Q2–Q4 2026)
- **Tools available:** OxCal 4.4 locally, Python/PyMC for a comparison
  model, research-project-template.
- **Literature access:** University library + DAI Zenon + Propylaeum.

## Scope boundaries

- **NOT addressed:** *Iron Age I* (early period) — a separate debate.
- **NOT addressed:** Historical or biblical interpretation of the monumental
  buildings.
- **NOT addressed:** Ceramic typology (except as a relative control
  criterion).

## Ethics / open science

- 14C raw data will be published as supplementary material on Zenodo (CC-BY).
- OxCal input files open.
- Bayesian code (PyMC variant) on GitHub under MIT.
- No human samples; no excavation permits touched.

---

**Design sign-off:** 2026-04-18, Patrick Leiverkus
**Next:** `/research-plan` or `writing-research-plan` skill
