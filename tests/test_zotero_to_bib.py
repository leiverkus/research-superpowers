"""Tests for scripts/zotero-to-bib.py — generating references.bib from Zotero.

The tool exists because Better BibTeX cannot be made to emit our citekeys. A
pilot on a 36-source project proved it: with BBX configured as closely to our
convention as its formula language allows, 8 of 36 keys still diverged, and an
item pinned BOTH ways (Extra `Citation Key:` AND Zotero's native `citationKey`)
was still exported under BBX's own generated key.

So these tests pin the one thing that matters: **the key comes from Extra, never
from `citationKey`** — because `citationKey` is whatever BBX invented.

Stdlib unittest. Run: python -m unittest discover -s tests
"""
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


z = _load("zotero_to_bib", ROOT / "scripts" / "zotero-to-bib.py")


def _item(**kw):
    d = {"itemType": "journalArticle", "title": "A title", "date": "2016",
         "creators": [{"creatorType": "author", "lastName": "Smith", "firstName": "John"}],
         "extra": "Citation Key: smith-2016-software"}
    d.update(kw)
    return d


class CitekeySource(unittest.TestCase):
    def test_key_comes_from_extra(self):
        self.assertEqual(z.citekey_of(_item()), "smith-2016-software")

    def test_native_citationkey_is_ignored(self):
        # THE point of the tool. BBX writes its own key into `citationKey`; that
        # key re-created a collision the citekey migration had just removed
        # (both Marín-Buzón 2021 papers collapse onto marin-buzon-2021-photogrammetry).
        it = _item(citationKey="marin-buzon-2021-photogrammetry")
        self.assertEqual(z.citekey_of(it), "smith-2016-software")

    def test_extra_with_other_lines(self):
        it = _item(extra="ArticleType: research-article\nCitation Key: glueck-1934-explorations\nfoo: bar")
        self.assertEqual(z.citekey_of(it), "glueck-1934-explorations")

    def test_no_key_returns_none(self):
        # main() turns this into a hard failure: a silently dropped entry leaves
        # the manuscript citing a key that is in no .bib, and Quarto renders that
        # as ??? while exiting 0.
        self.assertIsNone(z.citekey_of(_item(extra="")))


class EntryEmission(unittest.TestCase):
    def test_journal_article(self):
        out = z.to_entry(_item(publicationTitle="Nature", volume="5", issue="2",
                               pages="10–20", DOI="10.1/x"), "smith-2016-software")
        self.assertIn("@article{smith-2016-software,", out)
        self.assertIn("journal", out)
        self.assertIn("{Nature}", out)
        self.assertIn("pages", out)
        self.assertIn("10--20", out)          # en-dash folded to BibTeX range
        self.assertIn("{2016}", out)

    def test_conference_paper_becomes_inproceedings(self):
        out = z.to_entry(_item(itemType="conferencePaper",
                               proceedingsTitle="ISPRS Archives"), "x-2016-y")
        self.assertIn("@inproceedings{", out)
        self.assertIn("booktitle", out)
        self.assertIn("{ISPRS Archives}", out)

    def test_book_section_becomes_incollection(self):
        out = z.to_entry(_item(itemType="bookSection", bookTitle="A Reader"), "x-2016-y")
        self.assertIn("@incollection{", out)
        self.assertIn("{A Reader}", out)

    def test_editor_only_work(self):
        it = _item(itemType="book", creators=[
            {"creatorType": "editor", "lastName": "Porten", "firstName": "Bezalel"},
            {"creatorType": "editor", "lastName": "Yardeni", "firstName": "Ada"}])
        out = z.to_entry(it, "porten-2020-textbook")
        self.assertIn("editor", out)
        self.assertIn("Porten, Bezalel and Yardeni, Ada", out)
        self.assertNotIn("author", out)

    def test_ampersand_is_escaped(self):
        out = z.to_entry(_item(publicationTitle="Nature & Science"), "x-2016-y")
        self.assertIn(r"Nature \& Science", out)

    def test_year_extracted_from_full_date(self):
        out = z.to_entry(_item(date="2021-07-14"), "x-2021-y")
        self.assertIn("year", out)
        self.assertIn("{2021}", out)

    def test_deterministic(self):
        it = _item(publicationTitle="Nature", volume="5")
        self.assertEqual(z.to_entry(it, "k"), z.to_entry(it, "k"))


if __name__ == "__main__":
    unittest.main()
