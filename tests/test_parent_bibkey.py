"""Tests for `parent_bibkey` — a chapter whose original is the volume's PDF.

The NO-ORIGINAL gate assumes one work, one file. That holds for articles and
fails for edited volumes: nine chapters of one handbook produce nine findings
for a file that has been in the library all along. Measured on a live project,
15 of 29 findings were this — 52 %, which is the point where a gate stops being
read at all and the real gaps (a translation every quoted inscription in three
chapters depends on) vanish into the noise.

What the field must NOT become is a way to make findings disappear. Two
properties keep it honest and are pinned here:

  * a chapter whose volume is NOT on disk still fails — but as one
    MISSING-VOLUME naming the volume, because that is the single thing a human
    goes and fetches;
  * MISSING-VOLUME counts as a gate finding, so --strict-gates cannot pass a
    wiki that is unable to show its evidence.

Stdlib unittest. Run: python -m unittest discover -s tests
"""
import importlib.util
import json
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


lw = _load("lint_wiki_parent", TEMPLATE / "scripts" / "lint-wiki.py")


def _source_page(d: pathlib.Path, slug: str, bibkey: str, *, parent=None, unavailable=False):
    extra = ""
    if parent:
        extra += f"parent_bibkey: {parent}\n"
    if unavailable:
        extra += 'original_unavailable:\n  form: physical\n  note: "on the shelf"\n'
    p = d / f"{slug}.md"
    p.write_text(
        "---\n"
        f'title: "{slug}"\n'
        "type: source\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "status: draft\n"
        "author: llm\n"
        f"bibkey: {bibkey}\n" + extra +
        "---\n\n# " + slug + "\n",
        encoding="utf-8")
    return p


class SchemaCarriesIt(unittest.TestCase):
    def test_property_exists_with_the_bibkey_pattern(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        prop = schema["properties"]["parent_bibkey"]
        self.assertEqual(prop["pattern"], schema["properties"]["bibkey"]["pattern"],
                         "a volume key is a bibkey and must obey the same shape")

    def test_description_separates_it_from_original_unavailable(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        desc = schema["properties"]["parent_bibkey"]["description"]
        self.assertIn("original_unavailable", desc,
                      "the description must say how this differs from the other exemption")


class Gate(unittest.TestCase):
    def _run(self, pages, pdf_stems):
        with tempfile.TemporaryDirectory() as td:
            lib = pathlib.Path(td) / "pdf"
            lib.mkdir(parents=True)
            for stem in pdf_stems:
                (lib / f"{stem}.pdf").write_bytes(b"%PDF-1.4")
            return "\n".join(lw.gate_originals_present(pages, lib))

    def test_chapter_in_an_acquired_volume_is_exempt_and_counted(self):
        with tempfile.TemporaryDirectory() as td:
            d = pathlib.Path(td)
            pages = {
                "aubet": _source_page(d, "aubet", "aubet-2014-phoenicia",
                                      parent="steiner-2014-oxford-handbook"),
                "zorn": _source_page(d, "zorn", "zorn-2014-babylonian",
                                     parent="steiner-2014-oxford-handbook"),
            }
            out = self._run(pages, ["steiner-2014-oxford-handbook"])
            self.assertNotIn("NO-ORIGINAL", out)
            self.assertIn("2 page(s) are chapters in an acquired volume", out)
            self.assertIn("steiner-2014-oxford-handbook: 2", out)

    def test_missing_volume_fails_once_naming_the_volume(self):
        with tempfile.TemporaryDirectory() as td:
            d = pathlib.Path(td)
            pages = {
                "a": _source_page(d, "a", "bezzel-2025-philistines",
                                  parent="dietrich-2025-samuel-volume"),
                "b": _source_page(d, "b", "killebrew-2025-philistines",
                                  parent="dietrich-2025-samuel-volume"),
            }
            out = self._run(pages, [])
            self.assertIn("MISSING-VOLUME", out)
            self.assertIn("2 chapter page(s)", out)
            self.assertIn("acquire the volume once: dietrich-2025-samuel-volume", out)
            self.assertEqual(out.count("MISSING-VOLUME"), 1,
                             "one volume must produce one finding, not one per chapter")

    def test_a_plain_missing_original_is_untouched(self):
        with tempfile.TemporaryDirectory() as td:
            d = pathlib.Path(td)
            pages = {"w": _source_page(d, "w", "weippert-2010-textbuch")}
            out = self._run(pages, [])
            self.assertIn("NO-ORIGINAL", out)
            self.assertIn("weippert-2010-textbuch", out)

    def test_hint_mentions_the_new_escape_hatch(self):
        with tempfile.TemporaryDirectory() as td:
            d = pathlib.Path(td)
            pages = {"w": _source_page(d, "w", "weippert-2010-textbuch")}
            out = self._run(pages, [])
            self.assertIn("parent_bibkey", out,
                          "a reader hitting the gate should learn the field exists")

    def test_original_unavailable_still_wins_when_both_are_set(self):
        # A declared impossibility is a stronger statement than "see the volume",
        # and the counts must not double-report the same page.
        with tempfile.TemporaryDirectory() as td:
            d = pathlib.Path(td)
            pages = {"x": _source_page(d, "x", "tufnell-1953-lachish",
                                       parent="nobody-2000-volume", unavailable=True)}
            out = self._run(pages, [])
            self.assertIn("declare no original can exist", out)
            self.assertNotIn("MISSING-VOLUME", out)

    def test_chapter_with_its_own_pdf_needs_no_exemption(self):
        with tempfile.TemporaryDirectory() as td:
            d = pathlib.Path(td)
            pages = {"a": _source_page(d, "a", "aubet-2014-phoenicia",
                                       parent="steiner-2014-oxford-handbook")}
            out = self._run(pages, ["aubet-2014-phoenicia"])
            self.assertNotIn("chapters in an acquired volume", out,
                             "a page that passes on its own must not be counted as an exception")


class StrictGatesStillBites(unittest.TestCase):
    def test_missing_volume_is_in_the_gate_finding_pattern(self):
        src = (TEMPLATE / "scripts" / "lint-wiki.py").read_text(encoding="utf-8")
        self.assertIn("NO-ORIGINAL|MISSING-VOLUME|UNSTABLE-DRAFT|HALF-REVIEW", src,
                      "--strict-gates must fail on a chapter whose volume is absent")


if __name__ == "__main__":
    unittest.main()
