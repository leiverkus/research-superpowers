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
        fm.append('bibkey: "x-2026"')
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
        _page(d, "proj-a", "sources/toffolo-2014.md", "source", "Toffolo 2014", bibkey="toffolo-2014")
        _page(d, "proj-a", "concepts/low-chronology.md", "concept", "Low Chronology")
        _page(d, "proj-b", "entities/i-finkelstein.md", "entity", "I. Finkelstein", gnd_id="118533533")
        _page(d, "proj-b", "entities/tel-rehov.md", "entity", "Tel Rehov", idai_gazetteer_id="9999")
        _page(d, "proj-b", "sources/toffolo-2014.md", "source", "Toffolo 2014", bibkey="toffolo-2014")
        return [pathlib.Path(d) / "proj-a", pathlib.Path(d) / "proj-b"]

    def test_shared_gnd_and_bibkey_are_reported(self):
        with tempfile.TemporaryDirectory() as d:
            roots = self._two_projects(d)
            overlap, projects = gg.build_overlap(roots)
            found = {(o["field"], o["value"]) for o in overlap}
            self.assertIn(("gnd_id", "118533533"), found)
            self.assertIn(("bibkey", "toffolo-2014"), found)
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


if __name__ == "__main__":
    unittest.main()
