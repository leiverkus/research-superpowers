"""Tests for scripts/forward-search.py — who answered a work, and what came later.

No network: OpenAlex is replaced by a fake `get`. What is pinned here is what
the script adds on top of the API, because that is where it can mislead:

  * one monograph registered as seventeen DOIs is ONE row, not seventeen;
  * a work already in a .bib is marked — including a book part whose book is;
  * a bibkey without a DOI is matched by title AND year, and says so;
  * a failed lookup yields a note, never an empty "nobody cites this";
  * the request carries no e-mail address.

Stdlib unittest. Run: python -m unittest discover -s tests
"""
import importlib.util
import pathlib
import tempfile
import unittest
import urllib.error

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "templates" / "research-project-template" / "scripts" / "forward-search.py"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fs = _load("forward_search", SCRIPT)


def work(wid, doi, title, year, authors=()):
    return {"id": f"https://openalex.org/{wid}", "doi": f"https://doi.org/{doi}" if doi else None,
            "display_name": title, "publication_year": year, "type": "article",
            "authorships": [{"author": {"id": f"https://openalex.org/A{i}", "display_name": a}}
                            for i, a in enumerate(authors, 1)]}


TARGET = work("W1", "10.1179/peq.1999.131.2.102", "Edomites and Idumaeans", 1999, ["John Bartlett"])
CITING = [
    work("W10", "10.13109/9783666502873.xiii", "Abbreviations", 2026),
    work("W11", "10.13109/9783666502873", "Idumea and the Idumeans", 2026, ["Michał Marciak"]),
    work("W12", "10.13109/9783666502873.346", "Index of Geographic Names", 2026),
    work("W20", "10.3390/rel11100487", "The Religion of Idumea", 2020, ["Yigal Levin"]),
    work("W30", "10.1093/0199262896.003.0001", "Introduction", 2004, ["Judith Lieu"]),
    work("W31", "10.1093/0199262896.002.0001", "Preface", 2004),
    work("W40", None, "Silver Dome-shaped Coins", 2007, ["Haim Gitler", "Oren Tal"]),
]


class FakeOpenAlex:
    def __init__(self, known_doi=True):
        self.calls = []
        self.known_doi = known_doi

    def __call__(self, path, params):
        self.calls.append((path, dict(params)))
        if path.startswith("/works/doi:"):
            if not self.known_doi:
                raise urllib.error.HTTPError(path, 404, "Not Found", None, None)
            return TARGET
        flt = params.get("filter", "")
        if flt.startswith("cites:"):
            return {"meta": {"count": len(CITING), "next_cursor": None}, "results": CITING}
        if flt.startswith("title.search:"):
            return {"results": [work("W99", None, "Something Else Entirely", 1999), TARGET]}
        if flt.startswith("authorships.author.id:"):
            return {"results": [work("W50", "10.1234/later", "A Later Statement", 2008, ["John Bartlett"])]}
        raise AssertionError(f"unexpected request {path} {params}")


BIBS = {
    "bartlett-1999-edomites": {"doi": "10.1179/peq.1999.131.2.102", "title": "Edomites and Idumaeans",
                               "author": "Bartlett, John R.", "year": "1999"},
    "levin-2020-religion": {"doi": "10.3390/rel11100487", "title": "The Religion of Idumea",
                            "author": "Levin, Yigal", "year": "2020"},
    "lieu-2004-christian": {"doi": "10.1093/0199262896", "title": "Christian Identity",
                            "author": "Lieu, Judith", "year": "2004"},
    "nodoi-1988-kingdom": {"doi": "", "title": "Edomites and Idumaeans", "author": "Bartlett, John",
                           "year": "1999"},
}


class Collapse(unittest.TestCase):
    def test_book_parts_fold_into_the_book(self):
        rows = fs.collapse_book_parts([fs.slim(w) for w in CITING])
        self.assertEqual(len(rows), 4)                       # Marciak, Levin, Lieu, Gitler
        marciak = rows[0]
        self.assertEqual(marciak["title"], "Idumea and the Idumeans")   # the book, not "Abbreviations"
        self.assertEqual(marciak["parts"], 3)
        self.assertEqual(marciak["authors"], ["Michał Marciak"])

    def test_without_the_book_itself_the_authored_part_is_kept(self):
        lieu = next(r for r in fs.collapse_book_parts([fs.slim(w) for w in CITING])
                    if r["year"] == 2004)
        self.assertEqual(lieu["title"], "Introduction")      # has an author; "Preface" has none
        self.assertEqual(lieu["parts"], 2)

    def test_an_ordinary_article_is_left_alone(self):
        rows = fs.collapse_book_parts([fs.slim(CITING[3]), fs.slim(CITING[6])])
        self.assertEqual([r.get("parts") for r in rows], [None, None])


class Owned(unittest.TestCase):
    def test_owned_works_are_marked_including_parts_of_an_owned_book(self):
        rows = fs.collapse_book_parts([fs.slim(w) for w in CITING])
        fs.mark_owned(rows, {v["doi"]: k for k, v in BIBS.items() if v["doi"]})
        by_year = {r["year"]: r.get("bibkey") for r in rows}
        self.assertEqual(by_year[2020], "levin-2020-religion")
        self.assertEqual(by_year[2004], "lieu-2004-christian")   # part → its book
        self.assertIsNone(by_year[2026])


class Forward(unittest.TestCase):
    def run_one(self, token, fake, **kw):
        return fs.forward(token, BIBS, pathlib.Path("."), author=kw.get("author", False),
                          since=kw.get("since"), use_library=False, get=fake)

    def test_a_bibkey_is_resolved_and_its_citations_listed(self):
        fake = FakeOpenAlex()
        res = self.run_one("bartlett-1999-edomites", fake, author=True)
        self.assertEqual(res["openalex"], "W1")
        self.assertEqual(len(res["cited_by"]), 4)
        self.assertEqual(res["cited_by_records"], 7)
        self.assertEqual(res["later_by_author"][0]["title"], "A Later Statement")
        self.assertIn("from_publication_date:2000-01-01", fake.calls[-1][1]["filter"])

    def test_a_doi_works_as_well_as_a_bibkey(self):
        res = self.run_one("https://doi.org/10.1179/PEQ.1999.131.2.102", FakeOpenAlex())
        self.assertEqual(res["bibkey"], "bartlett-1999-edomites")

    def test_no_doi_falls_back_to_title_and_year_and_says_so(self):
        fake = FakeOpenAlex()
        res = self.run_one("nodoi-1988-kingdom", fake)
        self.assertEqual(res["openalex"], "W1")              # not W99, whose title differs
        self.assertTrue(any("matched by title" in n for n in res["notes"]))
        self.assertIn("publication_year:1999", fake.calls[0][1]["filter"])

    def test_since_narrows_the_citing_query(self):
        fake = FakeOpenAlex()
        self.run_one("bartlett-1999-edomites", fake, since=2015)
        self.assertIn("cites:W1,from_publication_date:2015-01-01",
                      [c[1].get("filter") for c in fake.calls])

    def test_an_unknown_token_is_an_error_not_an_empty_result(self):
        res = self.run_one("no-such-key", FakeOpenAlex())
        self.assertIn("error", res)
        self.assertNotIn("cited_by", res)

    def test_a_network_failure_is_a_note_not_silence(self):
        def down(path, params):
            raise urllib.error.URLError("no route")
        res = self.run_one("bartlett-1999-edomites", down)
        self.assertNotIn("cited_by", res)
        self.assertTrue(any("request failed" in n for n in res["notes"]))

    def test_rendering_states_that_the_lists_are_incomplete(self):
        text = fs.render(self.run_one("bartlett-1999-edomites", FakeOpenAlex()))
        self.assertIn("Nothing found is not the same", text)
        self.assertIn("● levin-2020-religion", text)
        self.assertIn("[3 records]", text)


class Plumbing(unittest.TestCase):
    def test_bib_reading_and_surname(self):
        with tempfile.TemporaryDirectory() as d:
            bib = pathlib.Path(d) / "r.bib"
            bib.write_text('@article{a-2001-x, author = {van der Toorn, Karel and B, C}, '
                           'title = {A {Title}}, year = {2001}, doi = {https://doi.org/10.1234/ABC}}\n'
                           '@book{b-2002-y, author = "Mazar, Amihai", title = "T", year = 2002}\n',
                           encoding="utf-8")
            bibs = fs.read_bibs([bib])
        self.assertEqual(bibs["a-2001-x"]["doi"], "10.1234/abc")
        self.assertEqual(bibs["a-2001-x"]["title"], "A Title")
        self.assertEqual(fs.first_surname(bibs["a-2001-x"]["author"]), "van der Toorn")
        self.assertEqual(fs.first_surname("Amihai Mazar"), "Mazar")
        self.assertEqual(bibs["b-2002-y"]["year"], "2002")

    def test_no_email_address_is_sent(self):
        src = SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn("mailto=", src)
        self.assertNotIn("@", fs.USER_AGENT)


if __name__ == "__main__":
    unittest.main()
