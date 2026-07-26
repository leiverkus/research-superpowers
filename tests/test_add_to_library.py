"""Tests for scripts/add-to-library.py — the deterministic half of the
`add-to-library` capability (compute the bibkey, place the PDF, append the
entry to the shared master).

Network-free by construction: the metadata *verification* is the skill's job
(Crossref/OpenAlex via MCP), not this script's — the script is handed already-
verified fields. So there is nothing here to mock. `commit` copies the PDF's
bytes and writes text; it never calls pdftotext, so these run without poppler.
The `inspect` subcommand does shell out to pdfinfo/pdftotext, so its one test is
skipped when those tools are absent.

Stdlib unittest. Run: python -m unittest discover -s tests
"""
import argparse
import importlib.util
import os
import pathlib
import shutil
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "templates" / "research-project-template" / "scripts"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


atl = _load("add_to_library", SCRIPTS / "add-to-library.py")
lib = _load("library", SCRIPTS / "library.py")


class _Env:
    """Point the resolver at a throwaway library via the env var, and neutralise
    the global config so a stray real one can't leak in."""

    def __init__(self, library_root):
        self.library_root = library_root

    def __enter__(self):
        self._old = os.environ.pop(lib.ENV_VAR, None)
        os.environ[lib.ENV_VAR] = str(self.library_root)
        self._global = lib.GLOBAL_CONFIG
        lib.GLOBAL_CONFIG = pathlib.Path(tempfile.mkdtemp()) / "nonexistent"
        return self

    def __exit__(self, *a):
        if self._old is not None:
            os.environ[lib.ENV_VAR] = self._old
        else:
            os.environ.pop(lib.ENV_VAR, None)
        lib.GLOBAL_CONFIG = self._global


def _mklib(d, bib_text=""):
    root = pathlib.Path(d) / "Bibliothek"
    (root / "pdf").mkdir(parents=True)
    (root / "references.bib").write_text(bib_text, encoding="utf-8")
    return root


def _pdf(d, name="in.pdf", body=b"%PDF-1.4\n%body\n"):
    p = pathlib.Path(d) / name
    p.write_bytes(body)
    return p


def _ns(**kw):
    """A commit Namespace with every field the command reads defaulted to None."""
    base = {f: None for f in atl.ENTRY_FIELDS}
    base.update(root=pathlib.Path("."), pdf=None, etype="article", kurztitel=None,
                bibkey=None, write=False, force=False, json=False)
    base.update(kw)
    return argparse.Namespace(**base)


class Helpers(unittest.TestCase):
    def test_norm_doi_strips_prefixes_and_trailing_punctuation(self):
        self.assertEqual(atl.norm_doi("https://doi.org/10.1179/Lev.2003"), "10.1179/lev.2003")
        self.assertEqual(atl.norm_doi("doi: 10.1017/ABC)"), "10.1017/abc")
        self.assertEqual(atl.norm_doi(""), "")

    def test_surname_of_handles_comma_and_plain_and_multi_author(self):
        self.assertEqual(atl.surname_of("Finkelstein, Israel"), "Finkelstein")
        self.assertEqual(atl.surname_of("Israel Finkelstein"), "Finkelstein")
        self.assertEqual(atl.surname_of("Mazar, A and Ben-Tor, A"), "Mazar")

    def test_union_terms_is_case_insensitive_first_seen(self):
        self.assertEqual(atl.union_terms("Iron Age; chronology", "iron age; survey"),
                         ["Iron Age", "chronology", "survey"])

    def test_set_keywords_replaces_an_existing_field(self):
        block = "@article{a-2020-x,\n  title = {T},\n  keywords = {old},\n}"
        out = atl.set_keywords(block, ["one", "two"])
        self.assertIn("keywords = {one; two}", out)
        self.assertNotIn("{old}", out)

    def test_set_keywords_inserts_when_absent(self):
        block = "@article{a-2020-x,\n  title = {T}\n}"
        out = atl.set_keywords(block, ["fresh"])
        self.assertIn("keywords = {fresh}", out)
        self.assertIn("title = {T},", out)          # a comma was added before insertion

    def test_iter_entries_and_field(self):
        text = ("@article{a-2020-x,\n  title = {A},\n  doi = {10.1/x}\n}\n\n"
                "@book{b-2019-y,\n  title = {B}\n}\n")
        got = {k: etype for k, _b, etype in atl.iter_entries(text)}
        self.assertEqual(got, {"a-2020-x": "article", "b-2019-y": "book"})
        block = next(b for k, b, _e in atl.iter_entries(text) if k == "a-2020-x")
        self.assertEqual(atl.field(block, "doi"), "10.1/x")
        self.assertIsNone(atl.field(block, "year"))


class PlacePdf(unittest.TestCase):
    def test_same_content_is_a_noop(self):
        with tempfile.TemporaryDirectory() as d:
            src = _pdf(d, "src.pdf", b"%PDF-1.4 same\n")
            tgt = pathlib.Path(d) / "t.pdf"
            tgt.write_bytes(b"%PDF-1.4 same\n")
            mtime = tgt.stat().st_mtime_ns
            self.assertTrue(atl._place_pdf(src, tgt, force=False))
            self.assertEqual(tgt.stat().st_mtime_ns, mtime)     # not rewritten

    def test_different_content_is_refused_without_force(self):
        with tempfile.TemporaryDirectory() as d:
            src = _pdf(d, "src.pdf", b"%PDF new\n")
            tgt = pathlib.Path(d) / "t.pdf"
            tgt.write_bytes(b"%PDF old\n")
            self.assertFalse(atl._place_pdf(src, tgt, force=False))
            self.assertEqual(tgt.read_bytes(), b"%PDF old\n")    # untouched

    def test_force_overwrites(self):
        with tempfile.TemporaryDirectory() as d:
            src = _pdf(d, "src.pdf", b"%PDF new\n")
            tgt = pathlib.Path(d) / "t.pdf"
            tgt.write_bytes(b"%PDF old\n")
            self.assertTrue(atl._place_pdf(src, tgt, force=True))
            self.assertEqual(tgt.read_bytes(), b"%PDF new\n")


class CommitNewEntry(unittest.TestCase):
    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            root = _mklib(d)
            pdf = _pdf(d)
            with _Env(root):
                rc = atl.cmd_commit(_ns(pdf=pdf, author="Finkelstein, Israel", year="2003",
                                        title="The Low Chronology", kurztitel="low chronology",
                                        journal="Levant", doi="10.1/x",
                                        keywords="low chronology; iron age"), lib)
            self.assertEqual(rc, 0)
            self.assertEqual((root / "references.bib").read_text(encoding="utf-8"), "")
            self.assertEqual(list((root / "pdf").glob("*.pdf")), [])

    def test_write_places_pdf_and_appends_entry(self):
        with tempfile.TemporaryDirectory() as d:
            root = _mklib(d)
            pdf = _pdf(d)
            with _Env(root):
                rc = atl.cmd_commit(_ns(pdf=pdf, author="Finkelstein, Israel", year="2003",
                                        title="The Low Chronology", kurztitel="low chronology",
                                        journal="Levant", pages="65-77", doi="10.1/x",
                                        keywords="low chronology; iron age", write=True), lib)
            self.assertEqual(rc, 0)
            key = "finkelstein-2003-low-chronology"
            self.assertTrue((root / "pdf" / f"{key}.pdf").is_file())
            bib = (root / "references.bib").read_text(encoding="utf-8")
            self.assertIn(f"@article{{{key},", bib)
            self.assertIn("keywords = {low chronology; iron age}", bib)
            self.assertIn("doi", bib)

    def test_a_missing_slot_is_a_hard_stop_not_a_half_key(self):
        with tempfile.TemporaryDirectory() as d:
            root = _mklib(d)
            pdf = _pdf(d)
            with _Env(root):
                rc = atl.cmd_commit(_ns(pdf=pdf, author="", year="2003",
                                        kurztitel="low", doi="10.1/verified",
                                        write=True), lib)     # no surname
            self.assertEqual(rc, 1)
            self.assertEqual((root / "references.bib").read_text(encoding="utf-8"), "")

    def test_appended_entry_is_separated_by_a_blank_line(self):
        existing = "@article{prior-2000-x,\n  title = {P},\n  year  = {2000},\n}\n"
        with tempfile.TemporaryDirectory() as d:
            root = _mklib(d, existing)
            pdf = _pdf(d)
            with _Env(root):
                atl.cmd_commit(_ns(pdf=pdf, author="Mazar, A", year="2011",
                                   title="Iron Age", kurztitel="iron age",
                                   doi="10.1/verified", write=True), lib)
            bib = (root / "references.bib").read_text(encoding="utf-8")
            self.assertIn("}\n\n@article{mazar-2011-iron-age,", bib)


class Idempotency(unittest.TestCase):
    def test_re_adding_the_same_doi_unions_keywords_without_duplicating(self):
        with tempfile.TemporaryDirectory() as d:
            root = _mklib(d)
            pdf = _pdf(d)
            with _Env(root):
                atl.cmd_commit(_ns(pdf=pdf, author="Mazar, A", year="2011", title="Iron Age",
                                   kurztitel="iron age", doi="10.1/z", keywords="alpha",
                                   write=True), lib)
                atl.cmd_commit(_ns(pdf=pdf, author="Mazar, A", year="2011", title="Iron Age",
                                   kurztitel="iron age", doi="10.1/z", keywords="beta",
                                   write=True), lib)
            bib = (root / "references.bib").read_text(encoding="utf-8")
            self.assertEqual(bib.count("@article{mazar-2011-iron-age,"), 1)   # not duplicated
            self.assertIn("keywords = {alpha; beta}", bib)

    def test_re_adding_the_same_doi_under_a_different_kurztitel_unions_into_the_existing_key(self):
        with tempfile.TemporaryDirectory() as d:
            root = _mklib(d)
            pdf = _pdf(d)
            with _Env(root):
                atl.cmd_commit(_ns(pdf=pdf, author="Mazar, A", year="2011", title="Iron Age",
                                   kurztitel="iron age", doi="10.1/z", keywords="alpha",
                                   write=True), lib)
                # same DOI, someone chose a different kurztitel — must not mint a 2nd key
                atl.cmd_commit(_ns(pdf=pdf, author="Mazar, A", year="2011", title="Iron Age",
                                   kurztitel="chronology", doi="10.1/z", keywords="gamma",
                                   write=True), lib)
            bib = (root / "references.bib").read_text(encoding="utf-8")
            self.assertEqual(len(list(atl.iter_entries(bib))), 1)
            self.assertIn("mazar-2011-iron-age", bib)
            self.assertNotIn("mazar-2011-chronology", bib)
            self.assertIn("keywords = {alpha; gamma}", bib)


class Disambiguation(unittest.TestCase):
    def test_a_different_work_at_the_same_key_gets_a_letter(self):
        with tempfile.TemporaryDirectory() as d:
            root = _mklib(d)
            pdf_a = _pdf(d, "a.pdf", b"%PDF A\n")
            pdf_b = _pdf(d, "b.pdf", b"%PDF B\n")
            with _Env(root):
                atl.cmd_commit(_ns(pdf=pdf_a, author="Mazar, A", year="2011", title="Iron Age I",
                                   kurztitel="iron age", doi="10.1/aaa", write=True), lib)
                # genuinely different work (different DOI) that computes the same base key
                atl.cmd_commit(_ns(pdf=pdf_b, author="Mazar, A", year="2011", title="Iron Age II",
                                   kurztitel="iron age", doi="10.1/bbb", write=True), lib)
            bib = (root / "references.bib").read_text(encoding="utf-8")
            keys = {k for k, _b, _e in atl.iter_entries(bib)}
            self.assertEqual(keys, {"mazar-2011-iron-age", "mazar-2011a-iron-age"})
            self.assertTrue((root / "pdf" / "mazar-2011-iron-age.pdf").is_file())
            self.assertTrue((root / "pdf" / "mazar-2011a-iron-age.pdf").is_file())


@unittest.skipUnless(shutil.which("pdfinfo") and shutil.which("pdftotext"),
                     "inspect needs poppler (pdfinfo/pdftotext)")
class Inspect(unittest.TestCase):
    def test_inspect_reports_no_text_layer_for_an_empty_pdf(self):
        with tempfile.TemporaryDirectory() as d:
            pdf = _pdf(d, "empty.pdf", b"%PDF-1.4\n%%EOF\n")
            result = atl.inspect(pdf)
            self.assertFalse(result["has_text_layer"])
            self.assertEqual(result["dois"], [])


if __name__ == "__main__":
    unittest.main()


class VerificationGate(unittest.TestCase):
    """The one SOFT-GATE condition with no override path, moved out of skill prose
    and into the script: metadata must be verified against a real record.

    The bibkey is a cross-project join key written into a SHARED bibliography. A
    wrong one propagates to every project and every colleague and cannot be
    recalled from their drafts — so 'the user was sure' is not a path, and
    silence is no longer available."""

    def test_no_doi_and_no_reason_refuses_to_write(self):
        with tempfile.TemporaryDirectory() as d:
            root = _mklib(d)
            pdf = _pdf(d)
            with _Env(root):
                rc = atl.cmd_commit(_ns(pdf=pdf, author="Stern, I", year="2008",
                                        title="Idumea", kurztitel="idumea",
                                        write=True), lib)
            self.assertEqual(rc, 2)
            self.assertEqual((root / "references.bib").read_text(encoding="utf-8"), "")
            self.assertFalse(list((root / "pdf").glob("*.pdf")))

    def test_a_doi_is_the_verified_path(self):
        with tempfile.TemporaryDirectory() as d:
            root = _mklib(d)
            pdf = _pdf(d)
            with _Env(root):
                rc = atl.cmd_commit(_ns(pdf=pdf, author="Kloner, A", year="2007",
                                        title="Idumea", kurztitel="idumea",
                                        doi="10.1515/9781575065809-009", write=True), lib)
            self.assertEqual(rc, 0)
            self.assertIn("@article{kloner-2007-idumea,",
                          (root / "references.bib").read_text(encoding="utf-8"))

    def test_an_explicit_reason_is_allowed_but_travels_with_the_record(self):
        # A side log would be lost the moment the entry is read in another
        # project. Whoever reads this record must see that it is unverified.
        with tempfile.TemporaryDirectory() as d:
            root = _mklib(d)
            pdf = _pdf(d)
            with _Env(root):
                rc = atl.cmd_commit(_ns(pdf=pdf, author="Kloner, A", year="2007",
                                        title="Idumea", kurztitel="idumea",
                                        unverified_reason="1962 monograph, no DOI exists",
                                        write=True), lib)
            self.assertEqual(rc, 0)
            bib = (root / "references.bib").read_text(encoding="utf-8")
            self.assertIn("UNVERIFIED: 1962 monograph, no DOI exists", bib)

    def test_the_reason_does_not_clobber_an_existing_note(self):
        with tempfile.TemporaryDirectory() as d:
            root = _mklib(d)
            pdf = _pdf(d)
            with _Env(root):
                atl.cmd_commit(_ns(pdf=pdf, author="Kloner, A", year="2007",
                                   title="Idumea", kurztitel="idumea",
                                   note="offprint", unverified_reason="no DOI",
                                   write=True), lib)
            bib = (root / "references.bib").read_text(encoding="utf-8")
            self.assertIn("offprint", bib)
            self.assertIn("UNVERIFIED: no DOI", bib)
