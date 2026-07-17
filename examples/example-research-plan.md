# Niedrige Chronologie Eisenzeit II — Research Plan

**Status:** pre-registered (2026-04-19 — Patrick Leiverkus)
**Slug:** `niedrige-chronologie-eisenzeit`
**Design:** `input/ideas/niedrige-chronologie-eisenzeit-design.md`
**Output target:** article (*Radiocarbon* or *Ägypten und Levante*)

---

## Research Question

Stützt eine Re-Analyse aller publizierten 14C-Daten aus Megiddo, Hazor, Gezer
und Tel Rehov (2001–2024) mit IntCal20 und einheitlichem Bayes-Phasenmodell
Finkelsteins Low Chronology, Mazars High Chronology, oder keine von beiden?

## Hypothesis (pre-registered — FROZEN)

> H1: Das einheitliche Bayes-Modell mit IntCal20 liefert Phasen-Posteriors,
> deren 68%-HPD-Intervalle für den Übergang Iron IIA → IIB zwischen
> 880 und 830 BCE liegen (Low Chronology).
>
> H0: Der Übergang liegt zwischen 930 und 880 BCE (High Chronology) oder
> ist breiter als 80 Jahre (indeterminate).

## Falsification Criteria

- **H1 abgelehnt**, falls 68%-HPD-Median > 890 BCE ODER HPD-Breite > 80 Jahre
- **H1 bestätigt**, falls 68%-HPD-Median ≤ 880 BCE UND HPD-Breite ≤ 80 Jahre
- **Indeterminate**, falls Kalibrierungs-Sensitivität > 20 Jahre Varianz
  zwischen IntCal13 / IntCal20 / IntCal22

## Method

1. **Daten-Ingest:** Alle 14C-Messungen aus den Schlüsselpublikationen (s.u.)
   als strukturierte Tabelle (`input/data/c14-levant-ironage.csv`): Lab-ID,
   Site, Stratum, Material, conv. Age, σ, Kontext, Publication.
2. **Bayes-Modell (OxCal 4.4):** Phasen-Modell mit Boundary-Priors nach
   Bronk Ramsey (2009); IntCal20 als Default.
3. **Sensitivitätsanalyse:** Re-Run mit IntCal13 und IntCal22; Vergleich
   Phasen-Posteriors.
4. **Interpretation:** Gegen Pre-Registration prüfen. Deviation-Log bei
   abweichenden Befunden.

## Data Sources (Ingest required)

- `[[finkelstein-piasetzky-2003]]` — Low Chronology-Argument
- `[[finkelstein-piasetzky-2011]]` — 14C-Update
- `[[mazar-2011]]` — High Chronology-Response
- `[[regev-et-al-2020]]` — Tel Rehov-Datensatz
- `[[bronk-ramsey-2009]]` — Bayes-Methodik
- `[[reimer-et-al-2020]]` — IntCal20

Dataset: `input/data/c14-levant-ironage.csv` (wird in Task 2 erzeugt).

---

## Tasks

### Task 1: Literature, Acquisition & Source Ingest

- [ ] Literature-scout dispatch (OpenAlex, IxTheo, Zenon-DAI, 2001–2026)
- [ ] `acquire-sources` on the A+B set → auto-download OA PDFs into `input/bibliography/` + `acquisition-todo.md`
- [ ] Manual downloads (VPN) for paywalled originals; re-run `acquire-sources` to reconcile until A/B originals are on disk or deferred
- [ ] Ingest `[[finkelstein-piasetzky-2003]]`
- [ ] Ingest `[[finkelstein-piasetzky-2011]]`
- [ ] Ingest `[[mazar-2011]]`
- [ ] Ingest `[[regev-et-al-2020]]`
- [ ] Ingest `[[bronk-ramsey-2009]]`
- [ ] Ingest `[[reimer-et-al-2020]]`
- [ ] Ingest ≥ 8 further A/B-rated sources from scout output
- [ ] Wiki-lint green
- [ ] Synthesis: `[[chronologie-debatte]]` status draft

### Task 2: Data Extraction

- Files: `input/data/c14-levant-ironage.csv`, `output/data-analysis/extract.py`
- [ ] Python-Skript zum Parsen der Appendix-Tabellen (PDF → CSV)
- [ ] Manuelle Validierung (Stichprobe n=20)
- [ ] Spec-Review (vollständig laut Quellen?) + Quality-Review (Einheiten, σ)
- [ ] Commit `c14-levant-ironage.csv` mit SHA-Log

### Task 3: Bayes-Modell OxCal

- Files: `output/data-analysis/oxcal/phases.oxcal`, `output/data-analysis/oxcal/run.sh`
- [ ] OxCal-Inputfile schreiben (4 Phasen: Iron I, IIA early, IIA late, IIB)
- [ ] Modell laufen lassen, Konvergenz prüfen (A-Index ≥ 60)
- [ ] Posteriors exportieren als JSON
- [ ] Spec-Review + Quality-Review

### Task 4: Sensitivitätsanalyse

- Files: `output/data-analysis/sensitivity.py`, `output/data-analysis/results/sensitivity.json`
- [ ] Re-Run mit IntCal13, IntCal22
- [ ] Posterior-Vergleich (Median, 68%-HPD-Breite)
- [ ] Heatmap `output/data-analysis/results/sensitivity.png`
- [ ] Spec-Review + Quality-Review

### Task 5: Synthesis & Interpretation

- Files: `knowledge/synthesis/chronologie-debatte.md`
- [ ] Ergebnisse gegen Pre-Registration halten (H1 / H0 / indeterminate)
- [ ] Deviation-Log falls abweichend
- [ ] Status → `review` (nicht `stable`: das setzt nur Nutzer)

### Task 6: Draft Article

- Files: `output/article/main.md` (Sections: Introduction / Methods /
  Results / Discussion / Conclusion), Target ~9.000 Wörter
- [ ] Outline (Thesis + Claim Chain + Section-Claims) + Sign-off (STOP 1)
- [ ] Pro Section: Argumentationsskizze → STOP 2 → Prosa → STOP 3 (6 Sections)
- [ ] Citations ausschließlich aus `output/bibtex/references.bib`
- [ ] `make render` exitcode 0
- [ ] Word count ± 10%

### Task 7: Peer Review

- [ ] Dispatch constructive reviewer (Archäologie-Fokus)
- [ ] Dispatch adversarial reviewer (Bayes-Methodik-Fokus)
- [ ] Review-Doku in `output/article/reviews/2026-MM-DD-review.md`
- [ ] Major-Issues mit Nutzer walken

### Task 8: Finish

- [ ] `/finish-project` closing checklist
- [ ] Zenodo-DOI
- [ ] Reproducibility-Statement
- [ ] Submission-Handoff (Cover Letter Draft)

---

## Verification

- [ ] `scripts/lint-wiki.py` exits 0
- [ ] ≥ 14 sources ingested with `status: stable` (gesetzt von Nutzer)
- [ ] `knowledge/synthesis/chronologie-debatte.md` status ≥ `review`
- [ ] `output/data-analysis/results/sensitivity.json` reproduzierbar
  (Seed fixiert, Environment-Lockfile vorhanden)
- [ ] `make render` erzeugt PDF ohne Warnings
- [ ] Hypothesis explizit bewertet (confirmed / refuted / inconclusive)
- [ ] Peer-Review-Dokument vorhanden

## Deviations Log

Jede Abweichung von diesem Plan wird hier UND in `knowledge/_meta/log.md` notiert.
Format:

```
- YYYY-MM-DD · deviation · plan=niedrige-chronologie-eisenzeit · <was änderte sich und warum>
```

**Bisher:** —

---

**Pre-registration sign-off:** 2026-04-19, Patrick Leiverkus
**Next:** `/execute-plan`
