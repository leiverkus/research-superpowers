"""Tests for the cross-project authority-overlap tool (global-graph step 1).

Covers the high-precision join: authority IDs / bibkeys shared across projects
are reported; ids present in only one project, or with differing values, are
not. Stdlib unittest — no pytest.

Run: python -m unittest discover -s tests
"""
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "templates" / "research-project-template" / "scripts"
GG = SCRIPTS / "wiki-global-graph.py"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gg = _load("wiki_global_graph", GG)


def _page(d, project, rel, typ, title, **ids):
    fm = ["---", f'title: "{title}"', f"type: {typ}",
          "created: 2026-07-12", "updated: 2026-07-12",
          "status: review", "author: llm"]
    if typ == "source":
        fm.append('bibkey: "x-2026-title"')
    for k, v in ids.items():
        fm.append(f'{k}: "{v}"')
    fm.append("---")
    p = pathlib.Path(d) / project / "knowledge" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(fm) + "\nbody\n", encoding="utf-8")
    return p


class AuthorityOverlap(unittest.TestCase):
    def _two_projects(self, d):
        # proj-a and proj-b share a GND (different slugs) and a bibkey, but have
        # different gazetteer ids.
        _page(d, "proj-a", "entities/finkelstein.md", "entity", "Israel Finkelstein", gnd_id="118533533")
        _page(d, "proj-a", "entities/megiddo.md", "entity", "Tel Megiddo", idai_gazetteer_id="2048473")
        _page(d, "proj-a", "sources/toffolo-2014.md", "source", "Toffolo 2014", bibkey="toffolo-2014-radiocarbon")
        _page(d, "proj-a", "concepts/low-chronology.md", "concept", "Low Chronology")
        _page(d, "proj-b", "entities/i-finkelstein.md", "entity", "I. Finkelstein", gnd_id="118533533")
        _page(d, "proj-b", "entities/tel-rehov.md", "entity", "Tel Rehov", idai_gazetteer_id="9999")
        _page(d, "proj-b", "sources/toffolo-2014.md", "source", "Toffolo 2014", bibkey="toffolo-2014-radiocarbon")
        return [pathlib.Path(d) / "proj-a", pathlib.Path(d) / "proj-b"]

    def test_shared_gnd_and_bibkey_are_reported(self):
        with tempfile.TemporaryDirectory() as d:
            roots = self._two_projects(d)
            overlap, projects = gg.build_overlap(roots)
            found = {(o["field"], o["value"]) for o in overlap}
            self.assertIn(("gnd_id", "118533533"), found)
            self.assertIn(("bibkey", "toffolo-2014-radiocarbon"), found)
            # both projects listed for the shared GND
            gnd = next(o for o in overlap if o["field"] == "gnd_id")
            self.assertEqual({x["project"] for x in gnd["occurrences"]}, {"proj-a", "proj-b"})

    def test_distinct_and_singleton_ids_are_not_reported(self):
        with tempfile.TemporaryDirectory() as d:
            roots = self._two_projects(d)
            overlap, _ = gg.build_overlap(roots)
            found = {(o["field"], o["value"]) for o in overlap}
            # different gazetteer ids → no place overlap
            self.assertNotIn(("idai_gazetteer_id", "2048473"), found)
            self.assertNotIn(("idai_gazetteer_id", "9999"), found)
            # exactly the two genuine cross-project ids
            self.assertEqual(len(overlap), 2)

    def test_shared_orcid_matches_across_drifted_slugs(self):
        # The Evidentia case: the same researcher appears in two modules under
        # DIFFERENT slugs (enrico-crema vs crema). Slug matching can't see it;
        # a shared orcid can. This is why orcid is an authority join key.
        with tempfile.TemporaryDirectory() as d:
            _page(d, "proj-a", "entities/enrico-crema.md", "entity", "Enrico Crema", orcid="0000-0001-6727-5138")
            _page(d, "proj-b", "entities/crema.md", "entity", "E. Crema", orcid="0000-0001-6727-5138")
            roots = [pathlib.Path(d) / "proj-a", pathlib.Path(d) / "proj-b"]
            overlap, _ = gg.build_overlap(roots)
            self.assertEqual([(o["field"], o["value"]) for o in overlap],
                             [("orcid", "0000-0001-6727-5138")])
            self.assertEqual({x["slug"] for x in overlap[0]["occurrences"]}, {"enrico-crema", "crema"})

    def test_shared_getty_aat_matches_concepts_across_slugs(self):
        # The concept-vocabulary lever: the same method recurs across modules as
        # concept pages under different slugs; a shared getty_aat_id links them
        # (what slug matching and the entity authority keys can't).
        with tempfile.TemporaryDirectory() as d:
            _page(d, "proj-a", "concepts/point-process.md", "concept", "Spatial point process", getty_aat_id="300444444")
            _page(d, "proj-b", "concepts/spp.md", "concept", "Point-pattern analysis", getty_aat_id="300444444")
            roots = [pathlib.Path(d) / "proj-a", pathlib.Path(d) / "proj-b"]
            overlap, _ = gg.build_overlap(roots)
            self.assertEqual([(o["field"], o["value"]) for o in overlap],
                             [("getty_aat_id", "300444444")])
            self.assertEqual({x["slug"] for x in overlap[0]["occurrences"]}, {"point-process", "spp"})

    def test_missing_knowledge_dir_is_skipped_not_fatal(self):
        with tempfile.TemporaryDirectory() as d:
            _page(d, "proj-a", "entities/x.md", "entity", "X", gnd_id="1")
            (pathlib.Path(d) / "proj-empty").mkdir()
            roots = [pathlib.Path(d) / "proj-a", pathlib.Path(d) / "proj-empty"]
            overlap, projects = gg.build_overlap(roots)
            self.assertEqual(overlap, [])
            self.assertTrue(any(p.get("missing") for p in projects))

    def test_deterministic(self):
        with tempfile.TemporaryDirectory() as d:
            roots = self._two_projects(d)
            self.assertEqual(gg.build_overlap(roots), gg.build_overlap(roots))

    def test_cli_runs_and_reports_shared_id(self):
        with tempfile.TemporaryDirectory() as d:
            roots = self._two_projects(d)
            r = subprocess.run(
                [sys.executable, str(GG), "overlap", str(roots[0]), str(roots[1]), "--json"],
                capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            data = json.loads(r.stdout)
            self.assertEqual(len(data["overlap"]), 2)

    def test_cli_needs_two_roots(self):
        with tempfile.TemporaryDirectory() as d:
            _page(d, "proj-a", "entities/x.md", "entity", "X", gnd_id="1")
            r = subprocess.run(
                [sys.executable, str(GG), "overlap", str(pathlib.Path(d) / "proj-a")],
                capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 1)


def _bib(d, project, entries):
    """Write a .bib into <project>/output/bibtex/references.bib."""
    p = pathlib.Path(d) / project / "output" / "bibtex" / "references.bib"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(entries), encoding="utf-8")


def _entry(key, title, year="2024", doi=""):
    body = f"@article{{{key},\n  author = {{X, Y}},\n  title = {{{title}}},\n  year = {{{year}}}"
    if doi:
        body += f",\n  doi = {{{doi}}}"
    return body + "\n}\n"


class BibkeyHealth(unittest.TestCase):
    """`overlap` compares bibkey STRINGS, so it reports a shared key as a win and
    is structurally blind to the two ways that can be wrong. `bibkeys` reads the
    .bib — the work behind the key — and sees both.
    """

    def test_collision_one_key_two_works(self):
        # The real case: `hensel-2024` denoted two different papers, so `overlap`
        # asserted a shared source between two projects that share nothing.
        with tempfile.TemporaryDirectory() as d:
            _page(d, "proj-a", "sources/x.md", "source", "X")
            _page(d, "proj-b", "sources/x.md", "source", "X")
            _bib(d, "proj-a", [_entry("hensel-2024", "Reconsidering Yahwism in Idumea")])
            _bib(d, "proj-b", [_entry("hensel-2024", "Transjordan and Judah")])
            roots = [pathlib.Path(d) / "proj-a", pathlib.Path(d) / "proj-b"]
            collisions, splits, _ = gg.build_bibkey_report(roots)
            self.assertEqual([c["key"] for c in collisions], ["hensel-2024"])
            self.assertEqual(splits, [])

    def test_truncated_title_is_not_a_collision(self):
        # The same work transcribed at two lengths must NOT be flagged, or the
        # signal drowns in noise. (Real: "The Religion of Idumea" vs "The Religion
        # of Idumea and Its Relationship to Early Judaism".)
        with tempfile.TemporaryDirectory() as d:
            _page(d, "proj-a", "sources/x.md", "source", "X")
            _page(d, "proj-b", "sources/x.md", "source", "X")
            _bib(d, "proj-a", [_entry("levin-2020", "The Religion of Idumea", "2020")])
            _bib(d, "proj-b", [_entry("levin-2020",
                                      "The Religion of Idumea and Its Relationship to Early Judaism",
                                      "2020")])
            roots = [pathlib.Path(d) / "proj-a", pathlib.Path(d) / "proj-b"]
            collisions, _, _ = gg.build_bibkey_report(roots)
            self.assertEqual(collisions, [])

    def test_collision_when_only_one_side_has_a_doi(self):
        # A DOI on one side only proves nothing about difference. An earlier cut of
        # this check required DOIs on BOTH sides and silently missed hensel-2024.
        with tempfile.TemporaryDirectory() as d:
            _page(d, "proj-a", "sources/x.md", "source", "X")
            _page(d, "proj-b", "sources/x.md", "source", "X")
            _bib(d, "proj-a", [_entry("maeir-2021", "Identity Creation Strategies",
                                      "2021", "10.1086/714573")])
            _bib(d, "proj-b", [_entry("maeir-2021", "On Defining Israel", "2021")])
            roots = [pathlib.Path(d) / "proj-a", pathlib.Path(d) / "proj-b"]
            collisions, _, _ = gg.build_bibkey_report(roots)
            self.assertEqual([c["key"] for c in collisions], ["maeir-2021"])

    def test_latex_transcription_is_not_a_collision(self):
        # The SAME paper is transcribed three ways across three real bibs:
        #   {\c{C}}atalh{\"o}y{\"u}k   ·   {Çatalhöyük}   ·   Çatalhöyük
        # and {I}ron {A}ge vs {Iron} {Age}. A fingerprint that tokenises on
        # [a-z0-9]+ without de-LaTeX-ing and folding to ASCII shatters these into
        # different words and reports a collision that does not exist.
        with tempfile.TemporaryDirectory() as d:
            for p in ("proj-a", "proj-b", "proj-c"):
                _page(d, p, "sources/x.md", "source", "X")
            _bib(d, "proj-a", [_entry("forte-2012-archaeology",
                                      r"{3D} Archaeology at {\c{C}}atalh{\"o}y{\"u}k", "2012")])
            _bib(d, "proj-b", [_entry("forte-2012-archaeology",
                                      "{3D} Archaeology at {Çatalhöyük}", "2012")])
            _bib(d, "proj-c", [_entry("forte-2012-archaeology",
                                      "3D Archaeology at Çatalhöyük", "2012")])
            roots = [pathlib.Path(d) / p for p in ("proj-a", "proj-b", "proj-c")]
            collisions, _, _ = gg.build_bibkey_report(roots)
            self.assertEqual(collisions, [], f"LaTeX/accent transcription flagged: {collisions}")

    def test_shared_doi_beats_a_differing_title(self):
        # A DOI identifies a work uniquely. The same Berlejung 2025 book is recorded
        # as "YHWH's Diversity: A Lot of Names…" in one project and "YHWH's Diversity
        # and the One God" in another — same DOI, same publisher. One work.
        with tempfile.TemporaryDirectory() as d:
            _page(d, "proj-a", "sources/x.md", "source", "X")
            _page(d, "proj-b", "sources/x.md", "source", "X")
            doi = "10.1628/978-3-16-164306-4"
            _bib(d, "proj-a", [_entry("berlejung-2025-yhwh",
                                      "YHWH's Diversity: A Lot of Names and No Iconography?",
                                      "2025", doi)])
            _bib(d, "proj-b", [_entry("berlejung-2025-yhwh",
                                      "{YHWH}'s Diversity and the One God", "2025", doi)])
            roots = [pathlib.Path(d) / "proj-a", pathlib.Path(d) / "proj-b"]
            collisions, _, _ = gg.build_bibkey_report(roots)
            self.assertEqual(collisions, [], "an agreeing DOI must settle identity")

    def test_split_one_work_two_keys(self):
        # The missed join: same paper, different key. `overlap` never links them.
        with tempfile.TemporaryDirectory() as d:
            _page(d, "proj-a", "sources/x.md", "source", "X")
            _page(d, "proj-b", "sources/x.md", "source", "X")
            _bib(d, "proj-a", [_entry("Smith2016", "Software Citation Principles", "2016")])
            _bib(d, "proj-b", [_entry("smith2016", "Software Citation Principles", "2016")])
            roots = [pathlib.Path(d) / "proj-a", pathlib.Path(d) / "proj-b"]
            collisions, splits, _ = gg.build_bibkey_report(roots)
            self.assertEqual(collisions, [])
            self.assertEqual(len(splits), 1)
            self.assertEqual({o["key"] for o in splits[0]["occurrences"]},
                             {"Smith2016", "smith2016"})

    def test_migrated_portfolio_is_clean(self):
        # After the migration both projects derive the key from the work itself,
        # so the collision is gone and the join is restored.
        with tempfile.TemporaryDirectory() as d:
            _page(d, "proj-a", "sources/x.md", "source", "X")
            _page(d, "proj-b", "sources/x.md", "source", "X")
            _bib(d, "proj-a", [_entry("smith-2016-software", "Software Citation Principles", "2016")])
            _bib(d, "proj-b", [_entry("smith-2016-software", "Software Citation Principles", "2016")])
            roots = [pathlib.Path(d) / "proj-a", pathlib.Path(d) / "proj-b"]
            collisions, splits, _ = gg.build_bibkey_report(roots)
            self.assertEqual(collisions, [])
            self.assertEqual(splits, [])

    def test_labels_disambiguate_by_path_not_by_counter(self):
        # Every Evidentia wiki lives in <Module>/paper/, so a counter would label
        # them paper#1 … paper#9 — telling the reader nothing about which project
        # a finding belongs to.
        with tempfile.TemporaryDirectory() as d:
            roots = [pathlib.Path(d) / "Aoristos" / "paper",
                     pathlib.Path(d) / "Signa" / "paper"]
            for r in roots:
                r.mkdir(parents=True)
            self.assertEqual(gg._labels(roots), ["Aoristos/paper", "Signa/paper"])

    def test_cli_bibkeys_exits_nonzero_on_collision(self):
        with tempfile.TemporaryDirectory() as d:
            _page(d, "proj-a", "sources/x.md", "source", "X")
            _page(d, "proj-b", "sources/x.md", "source", "X")
            _bib(d, "proj-a", [_entry("k-2024", "Alpha work")])
            _bib(d, "proj-b", [_entry("k-2024", "Completely other work")])
            r = subprocess.run(
                [sys.executable, str(GG), "bibkeys",
                 str(pathlib.Path(d) / "proj-a"), str(pathlib.Path(d) / "proj-b"), "--json"],
                capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 1, "a collision must fail the command")
            self.assertEqual(len(json.loads(r.stdout)["collisions"]), 1)


if __name__ == "__main__":
    unittest.main()
