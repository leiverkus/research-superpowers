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
import os
import pathlib
import re
import subprocess
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


def _fields(text, key):
    for _etype, k, body in mb.iter_entries(text):
        if k == key:
            return mb.fields_of(body)
    return None


class MasterOnlyFold(unittest.TestCase):
    """The master-only fold makes the merge monotonic: an entry added straight to
    the master (by add-to-library), cited by no project, must not be dropped on the
    next merge — but ONLY master-only keys are folded, so a project's corrected
    value always wins over a stale master rendering of the same key."""

    def test_a_master_only_entry_survives_the_merge(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            a = _project(root, "a", "@article{cited-2020-x,\n  title = {X}, year = {2020}\n}\n")
            out = root / "master.bib"
            out.write_text("@article{direct-2099-z,\n  author = {Solo, H},\n"
                           "  title = {Added Directly}, year = {2099}\n}\n", encoding="utf-8")
            report = _run(a, out=out)
            text = out.read_text(encoding="utf-8")
            self.assertIn("direct-2099-z", text)            # carried through, not dropped
            self.assertIn("cited-2020-x", text)
            self.assertEqual(_fields(text, "direct-2099-z")["title"], "Added Directly")
            self.assertIn("1 master-only", report)

    def test_a_project_value_is_NOT_overridden_by_a_stale_master_value(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            a = _project(root, "a", "@article{shared-2015-y,\n  title = {The Corrected Title},\n"
                                     "  doi = {10.1/right}\n}\n")
            out = root / "master.bib"
            out.write_text("@article{shared-2015-y,\n  title = {Old Wrong Title},\n"
                           "  doi = {10.1/wrong}\n}\n", encoding="utf-8")
            _run(a, out=out)
            f = _fields(out.read_text(encoding="utf-8"), "shared-2015-y")
            self.assertEqual(f["title"], "The Corrected Title")
            self.assertEqual(f["doi"], "10.1/right")

    def test_no_master_file_yet_is_fine(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            a = _project(root, "a", "@article{cited-2020-x,\n  title = {X}\n}\n")
            out = root / "does-not-exist-yet.bib"
            report = _run(a, out=out)
            self.assertIn("cited-2020-x", out.read_text(encoding="utf-8"))
            self.assertNotIn("master-only", report)          # nothing to carry through

    def test_master_only_keywords_only_entry_survives(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            a = _project(root, "a", "@article{cited-2020-x,\n  title = {X}\n}\n")
            out = root / "master.bib"
            out.write_text("@article{direct-2099-z,\n  title = {D},\n"
                           "  keywords = {alpha; beta}\n}\n", encoding="utf-8")
            _run(a, out=out)
            f = _fields(out.read_text(encoding="utf-8"), "direct-2099-z")
            self.assertIn("alpha", f["keywords"])
            self.assertIn("beta", f["keywords"])


def _cli(*argv, config_home=None):
    """Run the script as the user runs it — argv straight through, no shell."""
    env = dict(os.environ)
    if config_home:
        env["XDG_CONFIG_HOME"] = str(config_home)
    p = subprocess.run([sys.executable, str(SCRIPT), *argv],
                       capture_output=True, text=True, env=env)
    return p.returncode, p.stdout, p.stderr


class RootsAreValidated(unittest.TestCase):
    """`(root / "output").glob(...)` on a root that does not exist returns EMPTY
    WITHOUT raising — which is why a shell-mangled path was invisible: the merge
    reported "0 FACTUAL conflicts" over a set that silently lacked a project. The
    merge is the release gate for the shared master, so a root that cannot be read
    must stop it, not shrink it."""

    def test_a_nonexistent_root_stops_the_run_and_names_the_path(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            a = _project(root, "a", "@article{x-2020-y,\n  title = {T}\n}\n")
            code, _out, err = _cli("--roots", str(a), str(root / "typo"),
                                   "--out", str(root / "m.bib"), "--report-only")
            self.assertNotEqual(code, 0)
            self.assertIn("typo", err)
            self.assertFalse((root / "m.bib").exists())

    def test_a_root_without_a_bib_warns_but_does_not_stop(self):
        # Legitimate for a freshly scaffolded project — must not block the merge.
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            a = _project(root, "a", "@article{x-2020-y,\n  title = {T}\n}\n")
            empty = root / "fresh"
            (empty / "output").mkdir(parents=True)
            code, out, _err = _cli("--roots", str(a), str(empty),
                                   "--out", str(root / "m.bib"), "--report-only")
            self.assertEqual(code, 0)
            self.assertIn("1 without a .bib", out)
            self.assertIn("fresh", out)

    def test_the_header_reports_how_many_roots_were_read(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            a = _project(root, "a", "@article{x-2020-y,\n  title = {T}\n}\n")
            b = _project(root, "b", "@article{z-2021-q,\n  title = {Q}\n}\n")
            _code, out, _err = _cli("--roots", str(a), str(b),
                                    "--out", str(root / "m.bib"), "--report-only")
            self.assertIn("2 project root(s) read", out)


class FromRegistry(unittest.TestCase):
    """--from-registry exists so the registry never passes through the shell.
    `--roots $(grep …)` word-splits INSIDE a path (iCloud: "Mobile Documents"),
    `--roots $ROOTS` does not split at all in zsh — both drop projects silently."""

    def _registry(self, cfg, *paths):
        d = cfg / "research-superpowers"
        d.mkdir(parents=True, exist_ok=True)
        (d / "projects").write_text(
            "# registered projects\n\n" + "".join(f"{p}\n" for p in paths), encoding="utf-8")

    def test_a_registered_path_with_spaces_is_read_as_ONE_root(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            cfg = root / "config"
            a = _project(root, "Mobile Documents project a",
                         "@article{x-2020-y,\n  title = {T}\n}\n")
            self._registry(cfg, a)
            code, out, err = _cli("--from-registry", "--out", str(root / "m.bib"),
                                  "--report-only", config_home=cfg)
            self.assertEqual(code, 0, err)
            self.assertIn("1 distinct bibkeys from 1 project root(s) read", out)

    def test_comments_and_blank_lines_are_not_roots(self):
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            cfg = root / "config"
            a = _project(root, "a", "@article{x-2020-y,\n  title = {T}\n}\n")
            b = _project(root, "b", "@article{z-2021-q,\n  title = {Q}\n}\n")
            self._registry(cfg, a, b)
            _code, out, _err = _cli("--from-registry", "--out", str(root / "m.bib"),
                                    "--report-only", config_home=cfg)
            self.assertIn("2 project root(s) read", out)

    def test_a_stale_registry_line_stops_the_run(self):
        # The registry is edited by hand; a typo there must not shrink the merge
        # any more quietly than a mangled command line does.
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            cfg = root / "config"
            a = _project(root, "a", "@article{x-2020-y,\n  title = {T}\n}\n")
            self._registry(cfg, a, root / "retired-last-year")
            code, _out, err = _cli("--from-registry", "--out", str(root / "m.bib"),
                                   "--report-only", config_home=cfg)
            self.assertNotEqual(code, 0)
            self.assertIn("retired-last-year", err)

    def test_roots_and_from_registry_are_mutually_exclusive(self):
        code, _out, err = _cli("--from-registry", "--roots", "/tmp", "--out", "/tmp/m.bib")
        self.assertNotEqual(code, 0)
        self.assertIn("not allowed with", err)

    def test_one_of_the_two_is_required(self):
        code, _out, err = _cli("--out", "/tmp/m.bib")
        self.assertNotEqual(code, 0)
        self.assertIn("required", err)


if __name__ == "__main__":
    unittest.main()
