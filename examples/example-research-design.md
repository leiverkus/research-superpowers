# Niedrige Chronologie Eisenzeit II — Research Design

**Status:** approved (2026-04-18 — Patrick Leiverkus)
**Slug:** `niedrige-chronologie-eisenzeit`
**Output of:** `brainstorming-research`
**Next skill:** `writing-research-plan`

---

## Fragestellung

Wie belastbar ist Finkelsteins "Low Chronology"-These (Datierung der monumentalen
Architektur in Megiddo, Gezer, Hazor ins 9. statt ins 10. Jh. v.Chr.) angesichts
der 14C-Daten der Tel Rehov-Kampagnen 2005–2020 und der neueren Bayes-Modelle
von Mazar/Streit/Regev?

## Relevanz

- **Wissenschaftlich:** Low vs. High Chronology entscheidet über die historische
  Verortung von "Davidischen" und "Salomonischen" Monumentalbauten — berührt
  Schnittmenge Archäologie / Biblische Historiographie / Theologie.
- **Forschungsstand:** Die Debatte ist seit 2001 offen; 14C-Modellierungen sind
  seit ~2013 dominant, aber unterschiedliche Kalibrierungskurven (IntCal13 vs
  IntCal20) wurden noch nicht systematisch auf Levantine Daten angewendet.
- **Eigener Beitrag:** Re-Analyse aller publizierten Rehov/Megiddo-14C-Daten
  mit IntCal20 + einheitlichem Bayes-Modell (OxCal 4.4), um zu prüfen, ob die
  Datenbasis selbst eine Seite stützt oder die Lücke im Mittelwert liegt.

## Methodik

1. Systematische Literaturrecherche (OpenAlex, IxTheo, Zenon-DAI) 2001–2026,
   Fokus: 14C-Daten Levante Iron IIA/B.
2. Ingest der Schlüsselpublikationen als Source-Seiten.
3. Extraktion aller publizierten 14C-Rohdaten (Lab-ID, Material, conv. Age, σ).
4. Bayes-Phasenmodell in OxCal 4.4 (IntCal20) für die Übergänge Iron I → IIA → IIB.
5. Sensitivitätsanalyse: IntCal13 vs IntCal20, verschiedene Phasengrenzen-Priors.
6. Interpretation: confirmed Low / confirmed High / indeterminate.

## Datenquellen

- Finkelstein & Piasetzky (2003, 2011, 2015) — Low Chronology-Kerntexte
- Mazar (2005, 2011) — High Chronology-Gegenposition
- Regev, Finkelstein, Adams, Boaretto (diverse) — 14C-Datensätze
- Tel Rehov-Grabungsberichte (Mazar et al. 2005, 2020)
- OxCal 4.4 + IntCal20 (Referenz-Software + Kurve)

## Output-Ziel

**Artikel** (~9.000 Wörter) für *Radiocarbon* oder *Ägypten und Levante*.

Sekundärnutzen: Kapitel-Vorstufe für spätere Habilitation zur
Levantinischen Chronologie.

## Erwartete Ergebnisse

Eines von drei Szenarien:
- **S1 (Low bestätigt):** Bayes-Modell mit IntCal20 verschiebt Mittelwerte um
  < 10 Jahre, zentrale Hypothese (9. Jh. Monumentalbau) bleibt.
- **S2 (High bestätigt):** Systematische Verschiebung um > 15 Jahre nach oben;
  Mazar-Position wird stärker.
- **S3 (Indeterminate):** Überlappung der Phasen-Posteriors zu groß für
  Entscheidung — Kalibrierung als Flaschenhals identifiziert.

Pre-registration fixiert, welches Szenario welcher Datenlage entspricht.

## Risiken

- **Datenverfügbarkeit:** Einige Rohdaten nur in Appendizes unpublizierter
  Dissertationen — evtl. Anfrage an Labore nötig.
- **Kalibrierungs-Updates:** IntCal20 wurde 2020 publiziert, 2025 aktualisiert —
  muss dokumentieren, welche Version benutzt wird.
- **Bias:** Autor ist in einem theologischen Umfeld sozialisiert — Adversarial
  Peer-Review (Archäologe) zwingend.

## Machbarkeit

- **Zeitrahmen:** 6 Monate (Q2-Q4 2026)
- **Tools vorhanden:** OxCal 4.4 lokal, Python/PyMC für Vergleichsmodell,
  research-project-template
- **Literaturzugang:** Uni-Bibliothek + DAI-Zenon + Propylaeum

## Abgrenzung

- **NICHT behandelt:** Iron Age I (Frühzeit) — separate Debatte
- **NICHT behandelt:** Historische / biblische Interpretation der Monumentalbauten
- **NICHT behandelt:** Keramik-Typologie (außer als relatives Kontrollkriterium)

## Ethik / Open Science

- 14C-Rohdaten werden als Supplementary Material auf Zenodo publiziert (CC-BY).
- OxCal-Inputfiles offen.
- Bayes-Code (PyMC-Variante) auf GitHub unter MIT.
- Keine humanen Samples, keine Grabungsberechtigungen berührt.

---

**Design sign-off:** 2026-04-18, Patrick Leiverkus
**Next:** `/research-plan` oder `writing-research-plan` Skill
