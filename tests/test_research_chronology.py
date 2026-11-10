"""Tests for the research-chronology checks in lint-wiki.py.

A wiki that records only "A contradicts B" treats a position from 1996 and one
from 2020 as two voices in the same room. The chronology checks pin what dates
alone can decide:

  * a `supersedes` / `revises` / `responds-to` edge runs from the later source
    to the earlier one — the reverse is impossible and fails;
  * an older stance edge pointing forward in time is reported, not failed,
    because existing wikis carry them;
  * a synthesis or manuscript that cites a superseded source without what
    superseded it is reported — and stops being reported once it cites both.

Stdlib unittest. Run: python -m unittest discover -s tests
"""
import importlib.util
import json
import os
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "templates" / "research-project-template"
SCHEMA = TEMPLATE / "schema" / "knowledge-frontmatter.schema.json"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


lw = _load("lint_wiki_chronology", TEMPLATE / "scripts" / "lint-wiki.py")


def _page(d, slug, *, type_="source", bibkey=None, relations=(), extra="", body=""):
    lines = ["---", f'title: "{slug}"', f"type: {type_}", "created: 2026-01-01",
             "updated: 2026-01-01", "status: review", "author: llm"]
    if bibkey:
        lines.append(f"bibkey: {bibkey}")
    if extra:
        lines.append(extra)
    if relations:
        lines.append("relations:")
        for rel in relations:
            first = True
            for k, v in rel.items():
                lines.append(f"  {'- ' if first else '  '}{k}: {v}")
                first = False
    lines += ["---", "", body, ""]
    p = d / f"{slug}.md"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def _rel(target, type_, **kw):
    return {"target": target, "type": type_, "confidence": "inferred", **kw}


class Chronology(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name)
        self.k = self.root / "knowledge"
        self.k.mkdir()
        self.addCleanup(self._tmp.cleanup)

    def run_check(self):
        pages = lw.collect_pages(self.k)
        return lw.lint_chronology(pages, self.root)

    def test_year_from_bibkey_and_orig_year(self):
        self.assertEqual(lw.source_year({"bibkey": "mazar-2011b-iron-age"}), 2011)
        self.assertEqual(lw.source_year({"bibkey": "noth-1981-history", "orig_year": 1943}), 1943)
        self.assertIsNone(lw.source_year({"bibkey": "no-year-here"}))

    def test_later_supersedes_earlier_is_clean(self):
        _page(self.k, "old", bibkey="a-1996-x")
        _page(self.k, "new", bibkey="b-2020-y",
              relations=[_rel("old", "supersedes", basis="new-evidence")])
        issues, advisory = self.run_check()
        self.assertEqual(issues, [])
        self.assertIn("supersedes 1", advisory[0])
        self.assertIn("1996–2020", advisory[0])

    def test_earlier_cannot_supersede_later(self):
        for rtype in ("supersedes", "revises", "responds-to"):
            with self.subTest(rtype):
                _page(self.k, "old", bibkey="a-1996-x", relations=[_rel("new", rtype)])
                _page(self.k, "new", bibkey="b-2020-y")
                issues, _ = self.run_check()
                self.assertEqual(len(issues), 1)
                self.assertIn("CHRONO-ORDER", issues[0])

    def test_orig_year_corrects_a_reprint(self):
        # A 2021 reprint of a 1990 text cannot supersede a 2005 paper …
        _page(self.k, "reprint", bibkey="a-2021-x", extra="orig_year: 1990",
              relations=[_rel("mid", "supersedes")])
        _page(self.k, "mid", bibkey="b-2005-y")
        issues, _ = self.run_check()
        self.assertEqual(len(issues), 1)

    def test_forward_stance_edge_is_advisory(self):
        _page(self.k, "old", bibkey="a-2003-x", relations=[_rel("new", "contradicts")])
        _page(self.k, "new", bibkey="b-2011-y")
        issues, advisory = self.run_check()
        self.assertEqual(issues, [])
        self.assertTrue(any("ANACHRONISM" in l for l in advisory))

    def test_later_contradicting_earlier_is_not_reported(self):
        _page(self.k, "old", bibkey="a-2003-x")
        _page(self.k, "new", bibkey="b-2011-y", relations=[_rel("old", "contradicts")])
        issues, advisory = self.run_check()
        self.assertEqual(issues, [])
        self.assertFalse(any("ANACHRONISM" in l for l in advisory))

    def test_synthesis_citing_only_the_superseded_source(self):
        _page(self.k, "old", bibkey="a-1996-x")
        _page(self.k, "new", bibkey="b-2020-y",
              relations=[_rel("old", "revises", basis="new-evidence")])
        _page(self.k, "syn", type_="synthesis", body="As [[old]] shows.")
        _, advisory = self.run_check()
        hit = [l for l in advisory if "SUPERSEDED-CITED" in l]
        self.assertEqual(len(hit), 1)
        self.assertIn("[[new]] (2020, new-evidence)", hit[0])

        _page(self.k, "syn", type_="synthesis", body="[[old]] held X; [[new]] gave it up.")
        _, advisory = self.run_check()
        self.assertFalse(any("SUPERSEDED-CITED" in l for l in advisory))

    def test_chain_is_satisfied_by_the_latest_position(self):
        _page(self.k, "a", bibkey="a-1990-x")
        _page(self.k, "b", bibkey="b-2000-y", relations=[_rel("a", "supersedes")])
        _page(self.k, "c", bibkey="c-2010-z", relations=[_rel("b", "supersedes")])
        _page(self.k, "syn", type_="synthesis", body="[[a]] and now [[c]].")
        _, advisory = self.run_check()
        self.assertFalse(any("SUPERSEDED-CITED" in l for l in advisory))

    def test_responds_to_does_not_supersede(self):
        _page(self.k, "old", bibkey="a-1996-x")
        _page(self.k, "new", bibkey="b-2020-y", relations=[_rel("old", "responds-to")])
        _page(self.k, "syn", type_="synthesis", body="As [[old]] shows.")
        _, advisory = self.run_check()
        self.assertFalse(any("SUPERSEDED-CITED" in l for l in advisory))

    def test_manuscript_citing_only_the_superseded_source(self):
        _page(self.k, "old", bibkey="a-1996-x")
        _page(self.k, "new", bibkey="b-2020-y", relations=[_rel("old", "supersedes")])
        out = self.root / "output" / "article"
        out.mkdir(parents=True)
        (out / "ch1.qmd").write_text("The date is early [@a-1996-x, p. 3].\n", encoding="utf-8")
        _, advisory = self.run_check()
        hit = [l for l in advisory if "SUPERSEDED-CITED" in l]
        self.assertEqual(len(hit), 1)
        self.assertIn("ch1.qmd", hit[0])

    def test_evidence_until_after_publication(self):
        _page(self.k, "s", bibkey="a-2014-x", extra="evidence_until: 2019")
        _, advisory = self.run_check()
        self.assertTrue(any("EVIDENCE-DATE" in l for l in advisory))

    def test_schema_accepts_new_fields_and_rejects_bad_basis(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        p = _page(self.k, "new", bibkey="b-2020-y", extra="orig_year: 2001\nevidence_until: 2018",
                  relations=[_rel("new", "revises", basis="new-method")])
        self.assertEqual(lw.validate_frontmatter(lw.parse_frontmatter(p), schema, p), [])
        p = _page(self.k, "new", bibkey="b-2020-y",
                  relations=[_rel("new", "revises", basis="because-i-say-so")])
        self.assertTrue(lw.validate_frontmatter(lw.parse_frontmatter(p), schema, p))
        self.assertEqual(lw.lint_relations(lw.collect_pages(self.k)), [])


if __name__ == "__main__":
    unittest.main()
