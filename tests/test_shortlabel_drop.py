"""`shortlabel` must never reach the shared master bibliography.

A manuscript that cites the same author's five 2026 titles needs to tell them
apart in its own text — "Hensel 2026e". That label is a fact about ONE book's
reference list, not about the work: the next project, whose author wrote a
different set of chapters, numbers the same title 2026b.

Kept in `note`, as it was before 0.40.0, it rode into the master on the next
merge and began instructing every other project in a numbering none of them
shared. A live master picked up fourteen such lines that way.

The field therefore stays in the project bib, where the manuscript tooling reads
it, and is dropped on merge — while `note` itself keeps merging, because the
rest of what lives there (open-access status, edition notes) is shared fact.

Stdlib unittest. Run: python -m unittest discover -s tests
"""
import contextlib
import importlib.util
import io
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "merge-bibs.py"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mb = _load("merge_bibs_shortlabel", SCRIPT)

ENTRY = """@article{hensel-2026-obadja,
  author    = {Hensel, Benedikt},
  title     = {Obadiah's Edom Reconsidered},
  year      = {2026},
  shortlabel = {Hensel 2026e},
  note      = {Open Access (CC BY-NC-ND 4.0)}
}
"""


def _project(root: pathlib.Path, name: str, bib: str) -> pathlib.Path:
    d = root / name / "output" / "bibtex"
    d.mkdir(parents=True)
    (d / "references.bib").write_text(bib, encoding="utf-8")
    return root / name


def _merge(projects: list[pathlib.Path], out: pathlib.Path) -> str:
    argv = sys.argv
    sys.argv = ["merge-bibs.py", "--roots", *[str(p) for p in projects], "--out", str(out)]
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            mb.main()
    finally:
        sys.argv = argv
    return out.read_text(encoding="utf-8")


class ShortlabelIsDropped(unittest.TestCase):
    def test_it_is_in_the_drop_set(self):
        self.assertIn("shortlabel", mb.DROP)

    def test_it_does_not_reach_the_master(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            p = _project(root, "book", ENTRY)
            out = _merge([p], root / "master.bib")
            self.assertNotIn("shortlabel", out)
            self.assertNotIn("Hensel 2026e", out)

    def test_note_still_merges(self):
        """Only the label goes. `note` carries shared fact too, and dropping the
        whole field to solve this would throw the edition notes out with it."""
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            p = _project(root, "book", ENTRY)
            out = _merge([p], root / "master.bib")
            self.assertIn("Open Access (CC BY-NC-ND 4.0)", out)

    def test_the_project_bib_is_left_alone(self):
        """The merge reads project bibs and writes only the master — the label
        must survive where the manuscript tooling looks it up."""
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            p = _project(root, "book", ENTRY)
            _merge([p], root / "master.bib")
            local = (p / "output" / "bibtex" / "references.bib").read_text(encoding="utf-8")
            self.assertIn("Hensel 2026e", local)

    def test_two_projects_labelling_the_same_work_differently_do_not_conflict(self):
        """The failure this prevents: the same work is 2026e here and 2026b
        there, and a merged field would have to pick a winner — silently
        teaching one project the other's numbering."""
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            a = _project(root, "book", ENTRY)
            b = _project(root, "article", ENTRY.replace("Hensel 2026e", "Hensel 2026b"))
            out = _merge([a, b], root / "master.bib")
            self.assertNotIn("2026e", out)
            self.assertNotIn("2026b", out)


if __name__ == "__main__":
    unittest.main()
