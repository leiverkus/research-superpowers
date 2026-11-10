"""Tests for `wiki-to-graph.py timeline` and the SUPERSEDED-POSITION lint pointer.

A list of typed edges does not show a debate's history. The timeline does, and
it must do so without adding anything: it is the existing edges, sorted by the
year each source is dated by. Pinned here:

  * sources come out in publication order, `orig_year` included, undated last;
  * a source's stance toward the focus and its responses to EARLIER sources in
    the list are kept apart;
  * `basis` survives into the edge and the JSON;
  * a concept that a source supersedes is reported by the linter as a pointer.

Stdlib unittest. Run: python -m unittest discover -s tests
"""
import importlib.util
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "templates" / "research-project-template" / "scripts"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


wg = _load("wiki_to_graph_timeline", SCRIPTS / "wiki-to-graph.py")
lw = _load("lint_wiki_timeline", SCRIPTS / "lint-wiki.py")


def _page(d, slug, type_, *, bibkey=None, relations=(), extra="", body=""):
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
    (d / f"{slug}.md").write_text("\n".join(lines), encoding="utf-8")


class Timeline(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self._tmp.name)
        self.k = self.root / "knowledge"
        self.k.mkdir()
        self.addCleanup(self._tmp.cleanup)
        _page(self.k, "gap", "concept")
        _page(self.k, "old", "source", bibkey="a-1988-x", body="On the [[gap]].")
        _page(self.k, "reprint", "source", bibkey="b-2021-y", extra="orig_year: 1970",
              body="See [[gap]].")
        _page(self.k, "new", "source", bibkey="c-2024-z", relations=[
            {"target": "gap", "type": "supersedes", "basis": "new-evidence",
             "confidence": "extracted", "because": '"quote (p. 235)"'},
            {"target": "old", "type": "responds-to", "confidence": "inferred"}])
        _page(self.k, "undated", "source", bibkey="nokey", body="[[gap]]")
        _page(self.k, "elsewhere", "source", bibkey="d-2000-w")

    def timeline(self, focus):
        pages = wg.collect_pages(self.k)
        nodes = wg.build_nodes(pages)
        edges, _ = wg.build_edges(pages)
        return wg.q_timeline(nodes, edges, focus)

    def test_sources_come_out_in_publication_order(self):
        tl = self.timeline("gap")
        self.assertEqual([s["id"] for s in tl["sources"]], ["reprint", "old", "new", "undated"])
        self.assertEqual([s["year"] for s in tl["sources"]], [1970, 1988, 2024, None])
        self.assertEqual(tl["span"], [1970, 2024])

    def test_unconnected_sources_are_left_out(self):
        self.assertNotIn("elsewhere", [s["id"] for s in self.timeline("gap")["sources"]])

    def test_stance_and_responses_are_kept_apart(self):
        new = next(s for s in self.timeline("gap")["sources"] if s["id"] == "new")
        self.assertEqual([s["type"] for s in new["stance"]], ["supersedes"])
        self.assertEqual(new["stance"][0]["basis"], "new-evidence")
        self.assertEqual([(r["type"], r["target"]) for r in new["responses"]],
                         [("responds-to", "old")])
        old = next(s for s in self.timeline("gap")["sources"] if s["id"] == "old")
        self.assertEqual(old["stance"], [])     # a wikilink is a link, not a stance

    def test_superseded_by_names_the_source_and_its_basis(self):
        self.assertEqual(self.timeline("gap")["superseded_by"],
                         [{"id": "new", "year": 2024, "basis": "new-evidence"}])

    def test_a_source_can_be_the_focus(self):
        tl = self.timeline("old")
        self.assertEqual([s["id"] for s in tl["sources"]], ["old", "new"])
        self.assertEqual(tl["superseded_by"], [])

    def test_basis_and_year_reach_the_graph(self):
        pages = wg.collect_pages(self.k)
        nodes = {n["id"]: n for n in wg.build_nodes(pages)}
        edges, _ = wg.build_edges(pages)
        self.assertEqual(nodes["new"]["year"], 2024)
        self.assertNotIn("year", nodes["gap"])
        e = next(e for e in edges if e["relation_type"] == "supersedes")
        self.assertEqual(e["basis"], "new-evidence")
        self.assertNotIn("basis", next(e for e in edges if e["relation_type"] == "responds-to"))

    def test_lint_points_at_the_superseded_position(self):
        _, advisory = lw.lint_chronology(lw.collect_pages(self.k), self.root)
        hit = [l for l in advisory if "SUPERSEDED-POSITION" in l]
        self.assertEqual(len(hit), 1)
        self.assertIn("gap.md", hit[0])
        self.assertIn("[[new]] (2024, new-evidence)", hit[0])


if __name__ == "__main__":
    unittest.main()
