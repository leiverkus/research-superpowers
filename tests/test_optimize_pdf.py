"""Tests for scripts/optimize-pdf.py — the reading-lossless PDF shrinker.

The load-bearing behaviours are two pure decisions and one safety rule:

  * classify() — is a file bloated, and by roughly how much? A false "flagged" wastes
    a Ghostscript run; a false "clean" leaves bytes on the table. Pinned across the
    three real bloat shapes (over-resolution, raw-storage, CMYK) and the clean case.
  * verify()   — is the optimised copy trustworthy? Only if the page count is identical
    AND the text layer survived. A shrunk file whose text broke is worse than a big one.
  * optimize_file() KEEPS THE ORIGINAL when verify() fails and removes the broken output —
    the one rule that must never regress.

The PDF readers shell out to gs/poppler; the tests stub them, so no binaries are needed.
Stdlib unittest. Run: python -m unittest discover -s tests
"""
import importlib.util
import os
import pathlib
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "templates" / "research-project-template" / "scripts" / "optimize-pdf.py"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


opt = _load("optimize_pdf", SCRIPT)


class TestClassify(unittest.TestCase):
    def test_over_resolution_is_flagged(self):
        # the 118 MB / 1877 ppi article: enormous, downsampling ~ (300/1877)²
        r = opt.classify(mb=118, pages=25, median_ppi=1877, cmyk=0)
        self.assertTrue(r["flagged"])
        self.assertEqual(r["reason"], "over-resolution")
        self.assertGreater(r["est_saved_mb"], 90)

    def test_small_over_resolution_still_flagged(self):
        # 12 MB / 614 ppi — below any file-size floor, but ~8 MB is recoverable
        r = opt.classify(mb=12, pages=20, median_ppi=614, cmyk=0)
        self.assertTrue(r["flagged"])
        self.assertEqual(r["reason"], "over-resolution")

    def test_clean_grayscale_scan_not_flagged(self):
        # a 336 MB book scanned at a sensible 300 ppi gains nothing from downsampling
        r = opt.classify(mb=336, pages=719, median_ppi=300, cmyk=0)
        self.assertFalse(r["flagged"])
        self.assertEqual(r["est_saved_mb"], 0.0)

    def test_raw_storage_flagged(self):
        # 85 MB / 39 pages / only 200 ppi ⇒ images stored uncompressed
        r = opt.classify(mb=85, pages=39, median_ppi=200, cmyk=0)
        self.assertTrue(r["flagged"])
        self.assertEqual(r["reason"], "raw-storage")

    def test_cmyk_prepress_flagged(self):
        r = opt.classify(mb=23, pages=177, median_ppi=300, cmyk=71)
        self.assertTrue(r["flagged"])
        self.assertEqual(r["reason"], "cmyk")

    def test_tiny_file_never_flagged(self):
        # already-optimised: same high-ish ppi but nothing worth recovering
        r = opt.classify(mb=3, pages=25, median_ppi=600, cmyk=0)
        self.assertFalse(r["flagged"])


class TestVerify(unittest.TestCase):
    def test_ok_when_pages_and_text_hold(self):
        self.assertTrue(opt.verify(25, 80000, 25, 79990)["ok"])

    def test_page_count_change_fails(self):
        v = opt.verify(25, 80000, 24, 80000)
        self.assertFalse(v["ok"])
        self.assertIn("page count", v["reason"])

    def test_text_collapse_fails_and_points_to_human(self):
        v = opt.verify(25, 80000, 25, 40000)   # dropped to 50%
        self.assertFalse(v["ok"])
        self.assertIn("inspect", v["reason"])


class TestOptimizeFileSafety(unittest.TestCase):
    """optimize_file must discard a broken output and keep the original."""

    def _run(self, dst_pages, dst_text):
        src = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        src.write(b"%PDF-1.6\n" + b"0" * 5_000_000)   # a "big" source
        src.close()
        dst = src.name[:-4] + ".out.pdf"

        def fake_gs(args, **kw):
            with open(dst, "wb") as f:      # Ghostscript "produces" a smaller file
                f.write(b"%PDF-1.6\n" + b"0" * 500_000)
            return mock.Mock(returncode=0)

        # source: 25 pages, 80k chars, over-resolution so it is flagged
        with mock.patch.object(opt, "subprocess") as sp, \
             mock.patch.object(opt, "pdf_pages", side_effect=lambda p: 25 if p == src.name else dst_pages), \
             mock.patch.object(opt, "pdf_text_len", side_effect=lambda p: 80000 if p == src.name else dst_text), \
             mock.patch.object(opt, "pdf_image_stats", return_value={"median_ppi": 1877, "max_ppi": 2750, "cmyk": 0, "n_images": 300}):
            sp.run.side_effect = fake_gs
            res = opt.optimize_file(src.name, dst)
        try:
            return res, os.path.exists(dst)
        finally:
            for p in (src.name, dst, src.name[:-4] + ".out.pdf"):
                if os.path.exists(p):
                    os.remove(p)

    def test_broken_text_layer_keeps_original(self):
        res, dst_exists = self._run(dst_pages=25, dst_text=10000)   # text collapsed
        self.assertFalse(res["ok"])
        self.assertFalse(dst_exists, "the broken optimised file must be removed")

    def test_page_change_keeps_original(self):
        res, dst_exists = self._run(dst_pages=24, dst_text=80000)   # a page vanished
        self.assertFalse(res["ok"])
        self.assertFalse(dst_exists)

    def test_clean_result_is_accepted(self):
        res, dst_exists = self._run(dst_pages=25, dst_text=79000)   # all good
        self.assertTrue(res["ok"])
        self.assertTrue(dst_exists)
        self.assertLess(res["new_mb"], res["old_mb"])


if __name__ == "__main__":
    unittest.main()
