"""Tests for the source-depth report (`depth` field + lint reporting).

A source page has two jobs, and the second is easy to skip because nothing asks
for it: capture what THIS project takes from the source under a question, and
record what the source contains AT ALL, so a question that shifts later can find
its way back. Measured on a live project, 5 of 136 pages carried the second —
and the one page a researcher praised carried it in full.

Three properties keep the check useful rather than merely loud:

  * it must read the bilingual headings researchers actually write. The
    reference page says "## Aufbau des Aufsatzes" and "## Die zwanzig
    Kernthesen"; an English-only check reports the best page in the corpus as
    missing both.
  * UNCOVERED must fire only on an EXPLICIT dash. A map table's first column
    need not be the coverage column — the reference page puts the section number
    there, and its unnumbered front matter would otherwise read as uncovered.
  * nothing here gates. Exhausting a source is never the goal.

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


lw = _load("lint_wiki_depth", TEMPLATE / "scripts" / "lint-wiki.py")


def _page(d: pathlib.Path, slug: str, *, depth=None, body="") -> pathlib.Path:
    fm = ["---", f'title: "{slug}"', "type: source", "created: 2026-01-01",
          "updated: 2026-01-01", "status: draft", "author: llm",
          "bibkey: someone-2001-a-work"]
    if depth:
        fm.append(f"depth: {depth}")
    fm += ["---", "", f"# {slug}", ""]
    p = d / f"{slug}.md"
    p.write_text("\n".join(fm) + body + "\n", encoding="utf-8")
    return p


GERMAN_MAP = """
## Aufbau des Aufsatzes

| | Abschnitt | S. |
|---|---|---|
| | An Orientation | 151-153 |
| 1 | Religion and Yahwism | 155-165 |

## Die zwanzig Kernthesen

""" + "".join(f"### {i}. Eine These (S. {150+i})\n\nText.\n\n" for i in range(1, 21))


class SchemaCarriesDepth(unittest.TestCase):
    def test_enum_and_default(self):
        s = json.loads(SCHEMA.read_text(encoding="utf-8"))
        d = s["properties"]["depth"]
        self.assertEqual(d["enum"], ["map", "standard", "deep"])
        self.assertEqual(d["default"], "standard")

    def test_description_says_map_is_not_a_licence_for_thinness(self):
        s = json.loads(SCHEMA.read_text(encoding="utf-8"))
        desc = s["properties"]["depth"]["description"]
        self.assertIn("consult", desc.lower())
        self.assertIn("never lower", desc.lower())


class BilingualHeadings(unittest.TestCase):
    """The reference page is German. An English-only check would report it as bare."""

    def test_german_headings_are_recognised(self):
        with tempfile.TemporaryDirectory() as td:
            d = pathlib.Path(td)
            p = _page(d, "hensel-2024", body=GERMAN_MAP)
            out = "\n".join(lw.report_source_depth({"hensel-2024": p}))
            self.assertNotIn("NO-MAP", out)
            self.assertNotIn("THIN", out)

    def test_english_headings_are_recognised(self):
        english = ("\n## Section map\n\n| Covered | Section | pp. |\n|---|---|---|\n"
                   "| x | One | 1-10 |\n\n## Core theses\n\n"
                   + "".join(f"### {i}. A thesis (p. {i})\n\nText.\n\n" for i in range(1, 11)))
        with tempfile.TemporaryDirectory() as td:
            d = pathlib.Path(td)
            p = _page(d, "smith-2001", body=english)
            out = "\n".join(lw.report_source_depth({"smith-2001": p}))
            self.assertNotIn("NO-MAP", out)
            self.assertNotIn("THIN", out)


class UncoveredNeedsAnExplicitDash(unittest.TestCase):
    def test_blank_first_cell_is_not_uncovered(self):
        """Regression: the reference page numbers sections in column one and
        leaves it blank for its front matter. Counting blanks reported five
        uncovered sections on the most thoroughly worked page in the corpus."""
        with tempfile.TemporaryDirectory() as td:
            d = pathlib.Path(td)
            p = _page(d, "hensel-2024", body=GERMAN_MAP)
            out = "\n".join(lw.report_source_depth({"hensel-2024": p}))
            self.assertNotIn("UNCOVERED", out)

    def test_explicit_dash_is_counted(self):
        body = GERMAN_MAP.replace("| 1 | Religion and Yahwism | 155-165 |",
                                  "| — | Religion and Yahwism | 155-165 |")
        with tempfile.TemporaryDirectory() as td:
            d = pathlib.Path(td)
            p = _page(d, "hensel-2024", body=body)
            out = "\n".join(lw.report_source_depth({"hensel-2024": p}))
            self.assertIn("UNCOVERED", out)
            self.assertIn("1 section(s)", out)

    def test_uncovered_is_called_a_worklist_not_a_finding(self):
        body = GERMAN_MAP.replace("| 1 | Religion", "| — | Religion")
        with tempfile.TemporaryDirectory() as td:
            d = pathlib.Path(td)
            p = _page(d, "x", body=body)
            out = "\n".join(lw.report_source_depth({"x": p}))
            self.assertIn("worklist", out.lower())


class DepthTiers(unittest.TestCase):
    def test_map_asks_for_no_theses(self):
        body = "\n## Aufbau des Aufsatzes\n\n| | A | 1-2 |\n"
        with tempfile.TemporaryDirectory() as td:
            d = pathlib.Path(td)
            p = _page(d, "handbook", depth="map", body=body)
            out = "\n".join(lw.report_source_depth({"handbook": p}))
            self.assertNotIn("THIN", out)

    def test_deep_asks_for_twenty(self):
        with tempfile.TemporaryDirectory() as td:
            d = pathlib.Path(td)
            # GERMAN_MAP carries exactly 20 — one short of the bar once we cut one.
            body = GERMAN_MAP.replace("### 20. Eine These (S. 170)\n\nText.\n\n", "")
            p = _page(d, "own-work", depth="deep", body=body)
            out = "\n".join(lw.report_source_depth({"own-work": p}))
            self.assertIn("THIN", out)
            self.assertIn("(19/20)", out)

    def test_depth_spread_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            d = pathlib.Path(td)
            pages = {"a": _page(d, "a", depth="map", body="\n## Aufbau\n\n| | x | 1 |\n"),
                     "b": _page(d, "b", body=GERMAN_MAP)}
            out = "\n".join(lw.report_source_depth(pages))
            self.assertIn("map 1", out)
            self.assertIn("standard 1", out)


class ThesisShapesFoundInTheWild(unittest.TestCase):
    """Three shapes occur on author-approved pages. The first release knew one.

    It reported a 9.483-word excerpt with seventeen numbered theses as having
    none — on the page type its author cares about most. Surveyed across 782
    source pages in 21 projects: exactly these two were misread, and the fix must
    change nothing else.
    """

    def _n(self, body):
        return lw.count_theses(body.splitlines())

    def test_explicit_kernthesen_heading_counts_every_entry(self):
        body = "## Die zwanzig Kernthesen\n\n### 1. A (S. 1)\n\n### Unnummeriert (S. 2)\n"
        self.assertEqual(self._n(body), 2)

    def test_generic_thesen_split_across_parts_counts_numbered_entries(self):
        """Real shape: '## Teil A — Die exegetischen Thesen (§1–4)'."""
        body = ("## Teil A — Die exegetischen Thesen (§1–4)\n\n"
                "### 1. Eine crux (§1.1)\n\n### 2. Späte Schicht (§1.1)\n\n"
                "## Teil B — Die historischen Thesen\n\n"
                "### 3. ⭐ Idumäa (§5)\n\n### Ein Zwischentitel ohne Nummer\n")
        self.assertEqual(self._n(body), 3,
                         "numbered theses in both parts, the unnumbered subheading not")

    def test_thesis_as_heading_counts_once_each(self):
        """Real shape: '## These 1: Othering durch Nähe'."""
        body = ("## These 1: Othering durch Nähe (Ms. 4–7)\n\n"
                "### Drei Beobachtungen (Ms. 5)\n\n"
                "## These 2: Obadjas Edom (Ms. 8–13)\n\n"
                "## These 3: Eine Stimme unter mehreren (Ms. 13–15)\n")
        self.assertEqual(self._n(body), 3,
                         "the ### beneath a thesis heading elaborates it; it is not a fourth thesis")

    def test_focus_heading_mentioning_thesis_is_not_a_thesis_section(self):
        """Real shape, many times over: the word sits inside focus headings."""
        body = ("## Focus: Continuity thesis — aniconism as post-exilic — 2026-08-01\n\n"
                "### 1. Claim one\n\n### 2. Claim two\n")
        self.assertEqual(self._n(body), 0)

    def test_assessment_of_standing_theses_is_not_a_thesis_list(self):
        body = ("## Assessment — what this source does to the wiki's standing theses\n\n"
                "### Stale syntheses\n")
        self.assertEqual(self._n(body), 0)

    def test_focus_claims_are_never_theses(self):
        body = "## Focus: x — 2026-01-01\n\n### Claims relevant to this focus\n1. a\n2. b\n"
        self.assertEqual(self._n(body), 0)


class NothingGates(unittest.TestCase):
    def test_report_never_raises_on_a_bare_page(self):
        with tempfile.TemporaryDirectory() as td:
            d = pathlib.Path(td)
            p = _page(d, "bare")
            out = "\n".join(lw.report_source_depth({"bare": p}))
            self.assertIn("NO-MAP", out)

    def test_depth_findings_are_not_in_the_gate_pattern(self):
        src = (TEMPLATE / "scripts" / "lint-wiki.py").read_text(encoding="utf-8")
        gate_line = [l for l in src.splitlines() if "UNSTABLE-DRAFT|HALF-REVIEW" in l][0]
        for token in ("NO-MAP", "THIN", "UNCOVERED"):
            self.assertNotIn(token, gate_line,
                             f"{token} must not become a --strict-gates failure")


if __name__ == "__main__":
    unittest.main()
