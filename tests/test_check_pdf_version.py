"""Tests for scripts/check-pdf-version.py — the manuscript-vs-published detector.

`inspect()` shells out to pdfinfo/pdftotext/pdfimages, so these tests stub those
three readers (pdf_meta / page_text / image_count) and drive the scoring logic
directly — no poppler, no real PDF. The behaviour that matters is the VERDICT: a
false "ok" on a manuscript is the load-bearing failure (an invented page anchor
that is checkable and wrong), and this suite pins it — including the repository /
preprint stamps (arXiv, eScholarship, …) that two live sources slipped through as
"ok" before the REPO_STAMP signal existed.

Stdlib unittest. Run: python -m unittest discover -s tests
"""
import importlib.util
import pathlib
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "templates" / "research-project-template" / "scripts" / "check-pdf-version.py"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cpv = _load("check_pdf_version", SCRIPT)


def _inspect(head="", *, pages=10, producer="3B2 Total Publishing", images=5,
             body="", printed=None, page5=""):
    """Run inspect() with the three PDF readers stubbed. `head` is pages 1–2 text,
    `body` is pages 2–8, `page5` the single line-number probe page."""
    meta = {"Pages": str(pages), "Producer": producer, "Creator": ""}

    def fake_page_text(pdf, first, last):
        if first == 1:
            return head
        if first == 5 and last == 5:
            return page5
        return body

    with mock.patch.object(cpv, "pdf_meta", lambda p: meta), \
         mock.patch.object(cpv, "page_text", fake_page_text), \
         mock.patch.object(cpv, "image_count", lambda p: images):
        return cpv.inspect(pathlib.Path("x.pdf"), printed)


class RepositoryStamp(unittest.TestCase):
    def test_arxiv_stamp_is_a_decisive_manuscript(self):
        r = _inspect(head="arXiv:1908.09715v3 [cs.CV] 29 May 2020\nCity-Scale Road Extraction")
        self.assertEqual(r["verdict"], "manuscript")
        self.assertTrue(any(s.startswith("repository-version") for s in r["signals"]))

    def test_escholarship_cover_is_a_decisive_manuscript(self):
        r = _inspect(head="eScholarship.org\nPowered by the California Digital Library\n3D Archaeology")
        self.assertEqual(r["verdict"], "manuscript")

    def test_biorxiv_preprint_banner_is_flagged(self):
        r = _inspect(head="bioRxiv preprint doi: https://doi.org/10.1101/2020.01.01")
        self.assertEqual(r["verdict"], "manuscript")

    def test_white_rose_repository_cover_is_flagged(self):
        r = _inspect(head="This is a repository copy of Some Article Title.")
        self.assertEqual(r["verdict"], "manuscript")

    def test_a_bare_arxiv_word_without_the_stamp_does_not_trip_it(self):
        # A published paper that merely cites arXiv in its intro must NOT be flagged.
        r = _inspect(head="We compare against models released on arXiv and elsewhere.",
                     producer="Elsevier", images=5)
        self.assertEqual(r["verdict"], "ok")
        self.assertFalse(any(s.startswith("repository-version") for s in r["signals"]))


class ExistingSignalsStillWork(unittest.TestCase):
    def test_a_clean_typeset_article_is_ok(self):
        r = _inspect(head="Journal of Things 12(3)\nAn Article", producer="3B2 Arbortext",
                     images=8, body="See Figure 1 and Figure 2.")
        self.assertEqual(r["verdict"], "ok")

    def test_cover_sheet_phrase_is_decisive(self):
        r = _inspect(head="Accepted Manuscript\nThis is the author's accepted version")
        self.assertEqual(r["verdict"], "manuscript")

    def test_word_producer_alone_is_only_suspect(self):
        r = _inspect(head="A Title", producer="Microsoft Word 2019", images=5, body="prose")
        self.assertEqual(r["verdict"], "suspect")

    def test_word_producer_plus_no_figures_is_manuscript(self):
        r = _inspect(head="A Title", producer="Microsoft Word 2019", images=0,
                     body="Figure 1 shows. Figure 2 shows. Figure 3 shows.")
        self.assertEqual(r["verdict"], "manuscript")

    def test_page_count_blowup_is_a_signal(self):
        # 20 physical pages vs 6 printed → factor 3.3, a strong tell (but 1 signal = suspect).
        r = _inspect(head="A Title", producer="3B2", images=5, pages=20, printed=(10, 15))
        self.assertEqual(r["verdict"], "suspect")
        self.assertTrue(any(s.startswith("page-count") for s in r["signals"]))


if __name__ == "__main__":
    unittest.main()
