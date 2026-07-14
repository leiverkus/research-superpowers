"""Tests for check 10 — a page anchor outside the work's printed page range.

This is the check that catches a fabricated citation, and it is HARD, so its false-positive
behaviour matters more than its recall. Every case below is drawn from the live corpus.

Why it exists: `acquire-sources` downloads Open-Access PDFs, and a green-OA deposit is very
often the author's ACCEPTED MANUSCRIPT — no printed page numbers exist in it. The ingester
has nothing to anchor to, so it anchors to the physical PDF page and writes "(p. 3)". That
citation is checkable and wrong, which is strictly worse than no citation: it survives review
because it looks like evidence, and drafting reaches back into the wrong page.

Across 5 live projects this found 15 such pages. One of them had *documented its own defect
in prose* — "page anchors are to the manuscript PDF (pp. 1–30)" — while the article is printed
on 33–60. A prose disclaimer does not stop a drafter from citing "(p. 11)". A check does.

Stdlib unittest. Run: python -m unittest discover -s tests
"""
import importlib.util
import json
import os
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "templates" / "research-project-template" / "scripts"
SCHEMA = json.loads((ROOT / "schema" / "knowledge-frontmatter.schema.json").read_text(encoding="utf-8"))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


lw = _load("lint_wiki", SCRIPTS / "lint-wiki.py")

SOURCE = """---
title: "S"
type: source
created: 2026-04-15
updated: 2026-04-15
status: review
author: llm
bibkey: {key}
---

# S

## Focus: test — 2026-04-15

### Claims relevant to this focus
{claims}

## Connections
{connections}
"""


class Spans(unittest.TestCase):
    def test_a_plain_range(self):
        self.assertEqual(lw._printed_spans("1118--1130"), [(1118, 1130)])

    def test_a_continued_article_has_TWO_spans(self):
        # Real: burnett-2016-ammon is printed on 26–40 and continues on 66–67. Collapsing
        # that to 26–67 would hide a real error; taking only 26–40 would invent one.
        self.assertEqual(lw._printed_spans("26--40, 66--67"), [(26, 40), (66, 67)])

    def test_an_article_number_is_not_a_range(self):
        # PLOS, Entangled Religions and friends print no page range at all.
        self.assertEqual(lw._printed_spans("103747"), [])
        self.assertEqual(lw._printed_spans("e0297931"), [])
        self.assertEqual(lw._printed_spans(""), [])


class Anchors(unittest.TestCase):
    def test_the_forms_the_ingest_skill_actually_writes(self):
        self.assertEqual(lw._cited_pages("claim (p. 12)"), {12})
        self.assertEqual(lw._cited_pages("claim (pp. 12–14)"), {12, 14})
        self.assertEqual(lw._cited_pages("claim (pp. 12, 15)"), {12, 15})
        self.assertEqual(lw._cited_pages("a (p. 3) and b (pp. 7, 9–11)"), {3, 7, 9, 11})

    def test_a_figure_or_a_bare_number_is_not_a_page(self):
        self.assertEqual(lw._cited_pages("see (fig. 3) and Table 12, n = 1605"), set())

    def test_an_anchor_following_a_source_link_belongs_to_THAT_source(self):
        # The false positive that fired on the live corpus the day this check shipped:
        # "…converges on the finding reached by [[source-bilotti-2024-point]] (pp. 10–11)."
        # Those are Bilotti's pages. The ingested source is printed on 626–638.
        # Cross-source comparisons live in the BODY, so the section filter alone missed it.
        text = "the finding reached by [[source-bilotti-2024-point]]\n(pp. 10–11)."
        self.assertEqual(lw._cited_pages(text), set())

    def test_an_entity_link_does_NOT_suppress_an_anchor(self):
        # An entity has no pages of its own. "uses [[entity-spatstat]] (p. 6)" is page 6
        # OF THIS SOURCE — suppressing it would gut the check on the pages that use it most.
        self.assertEqual(lw._cited_pages("uses [[entity-spatstat]] (p. 6)"), {6})

    def test_a_citekey_before_the_anchor_also_suppresses_it(self):
        self.assertEqual(lw._cited_pages("as @kempf-2023-point shows (p. 4)"), set())

    def test_connections_are_dropped_before_the_check(self):
        # The false positive that would have got this check switched off:
        # "Cited by [[gillings-2009-affordance]] (p. 344)" is GILLINGS' page 344 —
        # and the ingested source (Ogburn) is printed on 405–413.
        text = ("## Focus: x\n\nclaim (p. 407)\n\n"
                "## Connections\n- Cited by [[gillings-2009-affordance]] (p. 344)\n")
        self.assertEqual(lw._cited_pages(lw._own_sections(text)), {407})


class Check(unittest.TestCase):
    def _run(self, bib_pages, claims, connections=""):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d) / "proj"
            (root / "knowledge" / "sources").mkdir(parents=True)
            (root / "output" / "bibtex").mkdir(parents=True)
            (root / "output" / "bibtex" / "references.bib").write_text(
                "@article{smith-2016-software,\n  author = {Smith, A},\n  title = {T},\n"
                f"  year = {{2016}},\n  pages = {{{bib_pages}}}\n}}\n", encoding="utf-8")
            (root / "knowledge" / "sources" / "s.md").write_text(
                SOURCE.format(key="smith-2016-software", claims=claims,
                              connections=connections), encoding="utf-8")
            cwd = os.getcwd()
            try:
                os.chdir(root)
                return lw.lint_citekeys(lw.collect_pages(pathlib.Path("knowledge")), SCHEMA)
            finally:
                os.chdir(cwd)

    def test_a_physical_page_masquerading_as_a_printed_one_is_a_HARD_error(self):
        # crema-2010-probabilistic, cited at (p. 2) in two live projects.
        # The article is printed on 1118–1130.
        hard, _ = self._run("1118--1130", "1. claim (p. 2)\n2. claim (pp. 9, 10)")
        self.assertTrue(any("PAGE-OUT-OF-RANGE" in h for h in hard))
        self.assertTrue(any("1118–1130" in h for h in hard))

    def test_a_page_inside_the_range_passes(self):
        hard, _ = self._run("1118--1130", "1. claim (p. 1120)\n2. claim (pp. 1125–1128)")
        self.assertEqual([h for h in hard if "PAGE-OUT-OF-RANGE" in h], [])

    def test_the_second_span_of_a_continued_article_passes(self):
        # Without multi-span support this fires on a perfectly correct citation.
        hard, _ = self._run("26--40, 66--67", "1. claim (p. 38)\n2. the tail (p. 66)")
        self.assertEqual([h for h in hard if "PAGE-OUT-OF-RANGE" in h], [])

    def test_a_page_in_the_GAP_between_two_spans_still_fails(self):
        # 26–40 and 66–67 — page 50 is in neither. Treating the field as one 26–67 span
        # would let this through.
        hard, _ = self._run("26--40, 66--67", "1. claim (p. 50)")
        self.assertTrue(any("PAGE-OUT-OF-RANGE" in h for h in hard))

    def test_a_foreign_page_in_Connections_does_NOT_fire(self):
        hard, _ = self._run("405--413", "1. claim (p. 407)",
                            "- Cited by [[other-work]] (p. 344)")
        self.assertEqual([h for h in hard if "PAGE-OUT-OF-RANGE" in h], [])

    def test_no_printed_range_means_no_check(self):
        # Article-number journals. Guessing a range here would fire on every page.
        hard, _ = self._run("e0297931", "1. claim (p. 3)\n2. claim (p. 20)")
        self.assertEqual([h for h in hard if "PAGE-OUT-OF-RANGE" in h], [])


if __name__ == "__main__":
    unittest.main()
