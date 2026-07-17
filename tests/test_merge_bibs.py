"""Tests for the curated-keywords handling in the master-bibliography merge
(scripts/merge-bibs.py).

Two projects' `keywords` fields for the same bibkey are both correct facts, not a
disagreement — the generic field-merge below picks ONE winner ("keep the richer
rendering") for everything else, and that is the wrong instrument here: it would
silently drop whichever project's terms lose the "longer string wins" comparison.
These pin the union+dedupe path that replaces it for this one field, and that it
never surfaces as a printed "rendering difference" the way a real disagreement does.

Stdlib unittest. Run: python -m unittest discover -s tests
"""
import contextlib
import importlib.util
import io
import pathlib
import re
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "merge-bibs.py"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mb = _load("merge_bibs", SCRIPT)


def _project(root, name, bib_text):
    p = root / name / "output" / "bibtex"
    p.mkdir(parents=True)
    (p / "references.bib").write_text(bib_text, encoding="utf-8")
    return root / name


def _run(*roots, out):
    argv = mb.sys.argv
    mb.sys.argv = ["merge-bibs.py", "--roots", *[str(r) for r in roots], "--out", str(out)]
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            mb.main()
    finally:
        mb.sys.argv = argv
    return buf.getvalue()


class KeywordUnion(unittest.TestCase):
    def test_two_projects_distinct_keyword_sets_union_without_conflict(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            a = _project(root, "a", "@article{x-2020-y,\n  author = {A, B}, title = {T}, "
                                     "year = {2020},\n  keywords = {random labelling; mark permutation}\n}\n")
            b = _project(root, "b", "@article{x-2020-y,\n  author = {A, B}, title = {T}, "
                                     "year = {2020},\n  keywords = {null model; random labelling}\n}\n")
            out = root / "merged.bib"
            report = _run(a, b, out=out)

            self.assertIn("0 FACTUAL conflict(s)", report)
            merged = out.read_text(encoding="utf-8")
            m = re.search(r"keywords\s*=\s*\{([^}]*)\}", merged)
            self.assertIsNotNone(m)
            terms = {t.strip().casefold() for t in m.group(1).split(";")}
            self.assertEqual(terms, {"random labelling", "mark permutation", "null model"})

    def test_a_repeated_term_across_projects_dedupes_case_insensitively(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            a = _project(root, "a", "@article{x-2020-y,\n  author = {A, B}, title = {T}, "
                                     "year = {2020},\n  keywords = {Low Chronology}\n}\n")
            b = _project(root, "b", "@article{x-2020-y,\n  author = {A, B}, title = {T}, "
                                     "year = {2020},\n  keywords = {low chronology}\n}\n")
            out = root / "merged.bib"
            _run(a, b, out=out)

            merged = out.read_text(encoding="utf-8")
            m = re.search(r"keywords\s*=\s*\{([^}]*)\}", merged)
            terms = [t.strip() for t in m.group(1).split(";")]
            self.assertEqual(len(terms), 1)                 # one surviving term, not two

    def test_a_keyword_union_never_shows_up_as_a_rendering_difference(self):
        # Before the fix, two DIFFERENT keyword strings for the same key were just
        # another field disagreement — `norm()` would not consider them equal, and
        # the generic path would report a "rendering difference" and silently drop
        # whichever set lost the length comparison. The union must produce zero.
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            a = _project(root, "a", "@article{x-2020-y,\n  author = {A, B}, title = {T}, "
                                     "year = {2020},\n  keywords = {alpha; beta; gamma}\n}\n")
            b = _project(root, "b", "@article{x-2020-y,\n  author = {A, B}, title = {T}, "
                                     "year = {2020},\n  keywords = {delta}\n}\n")
            out = root / "merged.bib"
            report = _run(a, b, out=out)

            self.assertIn("0 rendering difference(s)", report)

    def test_an_entry_carrying_only_keywords_still_reaches_the_output(self):
        # No author/title/year at all for this key in EITHER project — `seen` is
        # never touched for it, only `keyword_terms` is. It must not vanish.
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            a = _project(root, "a", "@article{x-2020-y,\n  keywords = {alpha}\n}\n")
            out = root / "merged.bib"
            _run(a, out=out)

            merged = out.read_text(encoding="utf-8")
            self.assertIn("x-2020-y", merged)
            self.assertIn("keywords", merged)


if __name__ == "__main__":
    unittest.main()
