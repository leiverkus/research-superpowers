"""Tests for the page-level full-text search over the shared library.

The index is a *derived* artefact and the failure modes are all quiet ones, so each
is pinned here:

  * a scan with no text layer indexes as zero pages — it must be REPORTED, because a
    silently-empty document makes the library look complete when it is not
  * a corrupt PDF must not abort the run for the other 500
  * re-indexing must PURGE the old pages, or a shrunk document keeps answering with
    passages it no longer contains
  * a PDF deleted from the library must lose its rows, or search returns hits in a
    file that is gone
  * `ben-yosef` and `14C` must not be read as FTS5 operators
  * the index must never land in the library folder: SQLite and file-sync corrupt
    each other (the same failure class as a git repo inside Nextcloud)

`extract_pages` is the only part that shells out, so it is replaced here rather than
synthesising real PDFs.

Stdlib unittest. Run: python -m unittest discover -s tests
"""
import importlib.util
import os
import sqlite3
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


bs = _load("bib_search", SCRIPTS / "bib-search.py")


class _Fixture:
    """A library plus a private cache dir, with pdftotext stubbed out."""

    def __init__(self, pages_by_key):
        self.pages = dict(pages_by_key)
        self.calls = []

    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        d = pathlib.Path(self._tmp.name)
        self.library = d / "Bibliothek"
        (self.library / "pdf").mkdir(parents=True)
        for k in self.pages:
            (self.library / "pdf" / f"{k}.pdf").write_bytes(b"%PDF-1.4\n" + k.encode())

        self._old_cache = os.environ.get("XDG_CACHE_HOME")
        os.environ["XDG_CACHE_HOME"] = str(d / "cache")

        self._real_extract = bs.extract_pages
        fixture = self

        def fake(pdf):
            fixture.calls.append(pdf.stem)
            pages = fixture.pages[pdf.stem]
            if isinstance(pages, Exception):
                raise pages
            return list(pages)

        bs.extract_pages = fake
        return self

    def __exit__(self, *a):
        bs.extract_pages = self._real_extract
        if self._old_cache is None:
            os.environ.pop("XDG_CACHE_HOME", None)
        else:
            os.environ["XDG_CACHE_HOME"] = self._old_cache
        self._tmp.cleanup()

    def touch(self, key, pages):
        """Rewrite a PDF (new size ⇒ new content) and change what it extracts to."""
        self.pages[key] = pages
        p = self.library / "pdf" / f"{key}.pdf"
        p.write_bytes(b"%PDF-1.4\n" + b"x" * (p.stat().st_size + 10))

    def remove(self, key):
        (self.library / "pdf" / f"{key}.pdf").unlink()
        self.pages.pop(key)


class Indexing(unittest.TestCase):
    def test_a_hit_carries_the_page_it_was_found_on(self):
        # The whole point: a document-level hit still leaves you hunting through 40
        # pages. drafting-manuscript needs to know WHICH page to open.
        with _Fixture({"benyosef-2019-copper": ["intro", "the smelting site at Timna", "bib"]}) as f:
            bs.build(f.library, quiet=True)
            hits = bs.search(f.library, "smelting")
            self.assertEqual(len(hits), 1)
            self.assertEqual(hits[0]["bibkey"], "benyosef-2019-copper")
            self.assertEqual(hits[0]["page"], 2)
            self.assertIn("smelting", hits[0]["snippet"])

    def test_blank_pages_do_not_shift_the_page_numbers(self):
        with _Fixture({"a-2020-x": ["", "", "shasu nomads"]}) as f:
            bs.build(f.library, quiet=True)
            self.assertEqual(bs.search(f.library, "shasu")[0]["page"], 3)

    def test_a_scan_with_no_text_layer_is_REPORTED(self):
        # Indexing it silently as "empty" would make the library look complete.
        with _Fixture({"good-2020-x": ["copper"], "scan-1999-y": ["", "  "]}) as f:
            st = bs.build(f.library, quiet=True)
            self.assertEqual(st["no_text"], ["scan-1999-y"])
            self.assertEqual(bs.status(f.library)["no_text"], ["scan-1999-y"])

    def test_a_corrupt_pdf_does_not_abort_the_other_500(self):
        with _Fixture({"broken-2020-x": RuntimeError("Syntax Error: Couldn't read xref"),
                       "fine-2020-y": ["edom"]}) as f:
            st = bs.build(f.library, quiet=True)
            self.assertEqual(st["failed"], ["broken-2020-x"])
            self.assertEqual(len(bs.search(f.library, "edom")), 1)   # the other one indexed
            self.assertEqual(bs.status(f.library)["failed"][0][0], "broken-2020-x")


class Incremental(unittest.TestCase):
    def test_unchanged_pdfs_are_not_re_extracted(self):
        with _Fixture({"a-2020-x": ["copper"], "b-2021-y": ["edom"]}) as f:
            bs.build(f.library, quiet=True)
            f.calls.clear()
            st = bs.build(f.library, quiet=True)
            self.assertEqual(f.calls, [])            # pdftotext never ran again
            self.assertEqual(st["skipped"], 2)

    def test_a_changed_pdf_is_re_extracted_and_its_OLD_pages_purged(self):
        # Without the purge, a shrunk document keeps answering with passages it no
        # longer contains.
        with _Fixture({"a-2020-x": ["copper smelting"]}) as f:
            bs.build(f.library, quiet=True)
            f.touch("a-2020-x", ["pottery typology"])
            bs.build(f.library, quiet=True)
            self.assertEqual(f.calls[-1], "a-2020-x")
            self.assertEqual(bs.search(f.library, "copper"), [])      # gone
            self.assertEqual(len(bs.search(f.library, "pottery")), 1)

    def test_a_pdf_deleted_from_the_library_loses_its_rows(self):
        with _Fixture({"a-2020-x": ["copper"], "b-2021-y": ["edom"]}) as f:
            bs.build(f.library, quiet=True)
            f.remove("a-2020-x")
            st = bs.build(f.library, quiet=True)
            self.assertEqual(st["removed"], 1)
            self.assertEqual(bs.search(f.library, "copper"), [])
            self.assertEqual(bs.status(f.library)["docs"], 1)

    def test_rebuild_starts_from_scratch(self):
        with _Fixture({"a-2020-x": ["copper"]}) as f:
            bs.build(f.library, quiet=True)
            f.calls.clear()
            bs.build(f.library, rebuild=True, quiet=True)
            self.assertEqual(f.calls, ["a-2020-x"])


class Queries(unittest.TestCase):
    def test_punctuation_is_words_not_operators(self):
        # `ben-yosef` must not be read as NOT, `14C-dating` must not be a syntax error,
        # and an unbalanced quote must not blow up in the user's face — each of these
        # is something a researcher types without a second thought.
        with _Fixture({"a-2020-x": ["ben-yosef reports 14C-dating of the unstratified slag"]}) as f:
            bs.build(f.library, quiet=True)
            for q in ("ben-yosef", "14C-dating", "slag (unstratified)", '"slag'):
                with self.subTest(q=q):
                    self.assertTrue(bs.search(f.library, q), f"no hit for {q!r}")

    def test_bare_words_are_ANDed(self):
        with _Fixture({"a-2020-x": ["copper in the arabah"], "b-2021-y": ["copper only"]}) as f:
            bs.build(f.library, quiet=True)
            hits = bs.search(f.library, "copper arabah")
            self.assertEqual([h["bibkey"] for h in hits], ["a-2020-x"])

    def test_phrases_and_prefixes_still_work(self):
        with _Fixture({"a-2020-x": ["the copper smelting furnaces"]}) as f:
            bs.build(f.library, quiet=True)
            self.assertTrue(bs.search(f.library, '"copper smelting"'))
            self.assertFalse(bs.search(f.library, '"smelting copper"'))
            self.assertTrue(bs.search(f.library, "furnac*"))

    def test_diacritics_fold(self):
        # The library is German-, French- and Hebrew-transliteration-heavy.
        with _Fixture({"a-2020-x": ["Kupferverhüttung im Arabah-Tal"]}) as f:
            bs.build(f.library, quiet=True)
            self.assertTrue(bs.search(f.library, "kupferverhuttung"))
            self.assertTrue(bs.search(f.library, "Kupferverhüttung"))

    def test_key_restricts_to_one_document(self):
        with _Fixture({"a-2020-x": ["edom"], "b-2021-y": ["edom"]}) as f:
            bs.build(f.library, quiet=True)
            hits = bs.search(f.library, "edom", key="b-2021-y")
            self.assertEqual([h["bibkey"] for h in hits], ["b-2021-y"])

    def test_searching_without_an_index_says_how_to_build_one(self):
        with _Fixture({"a-2020-x": ["copper"]}) as f:
            with self.assertRaises(FileNotFoundError) as cm:
                bs.search(f.library, "copper")
            self.assertIn("bib-search.py index", str(cm.exception))


class WhereTheIndexLives(unittest.TestCase):
    def test_the_index_is_NEVER_inside_the_library(self):
        # SQLite + file-sync corrupt each other. Same failure class as git-in-Nextcloud.
        with _Fixture({"a-2020-x": ["copper"]}) as f:
            bs.build(f.library, quiet=True)
            db = bs.index_path(f.library)
            self.assertTrue(db.exists())
            self.assertNotIn(f.library.resolve(), db.resolve().parents)
            self.assertEqual(list(f.library.rglob("*.sqlite*")), [])

    def test_two_libraries_do_not_share_an_index(self):
        with _Fixture({"a-2020-x": ["copper"]}) as f:
            other = f.library.parent / "Zweitbibliothek"
            (other / "pdf").mkdir(parents=True)
            self.assertNotEqual(bs.index_path(f.library), bs.index_path(other))


class SchemaVersion(unittest.TestCase):
    """SCHEMA_VERSION has to be READ, not just written.

    It was written and never read back for three releases, which made a version bump
    a silent no-op: `INSERT OR IGNORE` leaves the old row alone, `CREATE ... IF NOT
    EXISTS` leaves the old tables alone, and the new code then queries the old shape.
    The mismatch would surface as a wrong answer rather than an error.
    """

    def test_a_fresh_index_carries_the_current_version(self):
        with _Fixture({"a-2020-x": ["copper"]}) as f:
            bs.build(f.library, quiet=True)
            con = sqlite3.connect(bs.index_path(f.library))
            v = con.execute("SELECT v FROM meta WHERE k = 'schema'").fetchone()[0]
            con.close()
            self.assertEqual(int(v), bs.SCHEMA_VERSION)

    def test_an_index_from_another_schema_is_refused_not_answered(self):
        with _Fixture({"a-2020-x": ["copper"]}) as f:
            bs.build(f.library, quiet=True)
            old = bs.SCHEMA_VERSION
            try:
                bs.SCHEMA_VERSION = old + 1
                # The read-only entry points must refuse. Answering from a schema
                # they do not understand is the failure this check exists to stop.
                with self.assertRaises(bs.IndexSchemaMismatch):
                    bs.status(f.library)
                with self.assertRaises(bs.IndexSchemaMismatch):
                    bs.search(f.library, "copper")
            finally:
                bs.SCHEMA_VERSION = old

    def test_build_repairs_the_mismatch_itself(self):
        with _Fixture({"a-2020-x": ["copper"]}) as f:
            bs.build(f.library, quiet=True)
            old = bs.SCHEMA_VERSION
            try:
                bs.SCHEMA_VERSION = old + 1
                # `build` is the one entry point that can fix it, so it must — the
                # index is derived; there is nothing to lose and nothing to migrate.
                st = bs.build(f.library, quiet=True)
                self.assertEqual(st["indexed"], 1)
                con = sqlite3.connect(bs.index_path(f.library))
                v = con.execute("SELECT v FROM meta WHERE k = 'schema'").fetchone()[0]
                con.close()
                self.assertEqual(int(v), old + 1)
                self.assertEqual(len(bs.search(f.library, "copper")), 1)
            finally:
                bs.SCHEMA_VERSION = old
                bs.build(f.library, rebuild=True, quiet=True)

    def test_rebuild_takes_the_wal_sidecars_with_it(self):
        """Unlinking the .sqlite alone leaves the -wal, and SQLite replays it into
        the fresh file — so a 'rebuild' would inherit the rows it meant to drop."""
        with _Fixture({"a-2020-x": ["copper"]}) as f:
            bs.build(f.library, quiet=True)
            db = bs.index_path(f.library)
            db.with_suffix(".sqlite-wal").write_bytes(b"stale")
            bs.build(f.library, rebuild=True, quiet=True)
            self.assertFalse(db.with_suffix(".sqlite-wal").exists()
                             and db.with_suffix(".sqlite-wal").read_bytes() == b"stale")


if __name__ == "__main__":
    unittest.main()
