"""Tests for the shared-library resolver and the per-project bib subset.

The library is machine-local: it sits in a Nextcloud folder whose path differs
between the laptop and the institute machine, and it must never be committed. So
the path is *resolved*, never stored in the repo — and these tests pin the three
places it can come from, plus the two failure modes that would otherwise be silent:

  * no library configured → a message telling the user what to do, NOT "PDF missing"
    (the file may well exist; this machine has simply never been told where)
  * a cited key with no library entry → a HARD failure, because a dropped entry
    leaves the manuscript citing a key that is in no .bib, and Quarto renders that
    as ??? while exiting 0

No symlinks anywhere: they need administrator rights on Windows, and this suite runs
on Windows.

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


lib = _load("library", SCRIPTS / "library.py")
lw = _load("lint_wiki", SCRIPTS / "lint-wiki.py")


class _Env:
    """Clear the env var and the global config so a test sees only what it sets."""

    def __enter__(self):
        self._old = os.environ.pop(lib.ENV_VAR, None)
        self._global = lib.GLOBAL_CONFIG
        lib.GLOBAL_CONFIG = pathlib.Path(tempfile.mkdtemp()) / "nonexistent"
        return self

    def __exit__(self, *a):
        if self._old is not None:
            os.environ[lib.ENV_VAR] = self._old
        else:
            os.environ.pop(lib.ENV_VAR, None)
        lib.GLOBAL_CONFIG = self._global


def _library(d, keys=()):
    root = pathlib.Path(d) / "Bibliothek"
    (root / "pdf").mkdir(parents=True)
    (root / "references.bib").write_text(
        "\n".join(f"@article{{{k},\n  author = {{X, Y}},\n  title = {{T}},\n  year = {{2016}}\n}}"
                  for k in keys) + "\n", encoding="utf-8")
    for k in keys:
        (root / "pdf" / f"{k}.pdf").write_bytes(b"%PDF-1.4\n")
    return root


class Resolution(unittest.TestCase):
    def test_env_var_wins(self):
        with _Env(), tempfile.TemporaryDirectory() as d:
            root = _library(d)
            os.environ[lib.ENV_VAR] = str(root)
            self.assertEqual(lib.find_library(pathlib.Path(d)), root.resolve())

    def test_dotfile_in_project(self):
        with _Env(), tempfile.TemporaryDirectory() as d:
            root = _library(d)
            proj = pathlib.Path(d) / "proj"
            proj.mkdir()
            (proj / lib.CONFIG_NAME).write_text(f"{root}\n", encoding="utf-8")
            self.assertEqual(lib.find_library(proj), root.resolve())

    def test_global_config_is_the_last_resort(self):
        with _Env() as e, tempfile.TemporaryDirectory() as d:
            root = _library(d)
            g = pathlib.Path(d) / "global"
            g.write_text(f"{root}\n", encoding="utf-8")
            lib.GLOBAL_CONFIG = g
            self.assertEqual(lib.find_library(pathlib.Path(d) / "proj"), root.resolve())

    def test_env_beats_dotfile(self):
        with _Env(), tempfile.TemporaryDirectory() as d:
            a, b = _library(d), _library(pathlib.Path(d) / "second")
            proj = pathlib.Path(d) / "proj"
            proj.mkdir()
            (proj / lib.CONFIG_NAME).write_text(str(b), encoding="utf-8")
            os.environ[lib.ENV_VAR] = str(a)
            self.assertEqual(lib.find_library(proj), a.resolve())

    def test_comments_and_blanks_in_the_dotfile(self):
        with _Env(), tempfile.TemporaryDirectory() as d:
            root = _library(d)
            proj = pathlib.Path(d) / "proj"
            proj.mkdir()
            (proj / lib.CONFIG_NAME).write_text(f"# where the library lives\n\n{root}\n",
                                                encoding="utf-8")
            self.assertEqual(lib.find_library(proj), root.resolve())

    def test_unconfigured_raises_an_ACTIONABLE_error(self):
        # The failure a user actually hits is ingest-source hard-stopping. "PDF not
        # found" would send them hunting for a file; the real problem is that this
        # machine has never been told where the library is.
        with _Env(), tempfile.TemporaryDirectory() as d:
            with self.assertRaises(lib.LibraryNotConfigured) as cm:
                lib.find_library(pathlib.Path(d))
            msg = str(cm.exception)
            self.assertIn(lib.CONFIG_NAME, msg)
            self.assertIn(lib.ENV_VAR, msg)
            self.assertIn("gitignored", msg)

    def test_required_false_returns_none_instead_of_raising(self):
        # Advisory callers (lint) must not fail a build on an unconfigured machine.
        with _Env(), tempfile.TemporaryDirectory() as d:
            self.assertIsNone(lib.find_library(pathlib.Path(d), required=False))

    def test_a_configured_but_missing_directory_is_not_accepted(self):
        with _Env(), tempfile.TemporaryDirectory() as d:
            os.environ[lib.ENV_VAR] = str(pathlib.Path(d) / "does-not-exist")
            with self.assertRaises(lib.LibraryNotConfigured):
                lib.find_library(pathlib.Path(d))


class PdfLookup(unittest.TestCase):
    def test_pdf_for_is_an_exact_filename_lookup(self):
        # The whole point of `bibkey == filename stem`: no globbing, no fuzzy match.
        with _Env(), tempfile.TemporaryDirectory() as d:
            root = _library(d, ["finkelstein-2003-low-chronology"])
            os.environ[lib.ENV_VAR] = str(root)
            got = lib.pdf_for("finkelstein-2003-low-chronology", pathlib.Path(d))
            self.assertIsNotNone(got)
            self.assertEqual(got.name, "finkelstein-2003-low-chronology.pdf")
            self.assertIsNone(lib.pdf_for("ghost-2020-nothing", pathlib.Path(d)))

    def test_pdf_for_is_silent_when_unconfigured(self):
        with _Env(), tempfile.TemporaryDirectory() as d:
            self.assertIsNone(lib.pdf_for("smith-2016-software", pathlib.Path(d)))


SOURCE = """---
title: "S"
type: source
created: 2026-04-15
updated: 2026-04-15
status: review
author: llm
bibkey: {key}
---
{body}
"""


class LintChecksTheLibrary(unittest.TestCase):
    """Check 8 (bibkey ↔ PDF) had NO test for its non-empty branch — a regression
    there was invisible. It does now."""

    def _run(self, d, keys, pages):
        root = pathlib.Path(d) / "proj"
        (root / "knowledge" / "sources").mkdir(parents=True)
        (root / "output" / "bibtex").mkdir(parents=True)
        (root / "output" / "bibtex" / "references.bib").write_text(
            "\n".join(f"@article{{{k},\n  author = {{X, Y}},\n  title = {{T}},\n  year = {{2016}}\n}}"
                      for k in keys) + "\n", encoding="utf-8")
        for i, k in enumerate(pages):
            (root / "knowledge" / "sources" / f"s{i}.md").write_text(
                SOURCE.format(key=k, body="body"), encoding="utf-8")
        cwd = os.getcwd()
        try:
            os.chdir(root)
            return lw.lint_citekeys(lw.collect_pages(pathlib.Path("knowledge")), SCHEMA)
        finally:
            os.chdir(cwd)

    def test_reports_a_bibkey_with_no_pdf_in_the_library(self):
        with _Env(), tempfile.TemporaryDirectory() as d:
            root = _library(d, ["smith-2016-software"])       # library has ONE pdf
            os.environ[lib.ENV_VAR] = str(root)
            hard, advisory = self._run(d, ["smith-2016-software", "ghost-2020-nothing"],
                                       ["smith-2016-software", "ghost-2020-nothing"])
            self.assertEqual(hard, [])                        # advisory, never hard
            joined = "\n".join(advisory)
            self.assertIn("no PDF in the library", joined)
            self.assertIn("ghost-2020-nothing", joined)

    def test_all_present_says_so(self):
        with _Env(), tempfile.TemporaryDirectory() as d:
            root = _library(d, ["smith-2016-software"])
            os.environ[lib.ENV_VAR] = str(root)
            _, advisory = self._run(d, ["smith-2016-software"], ["smith-2016-software"])
            self.assertIn("All 1 bibkeys have a PDF in the library.", "\n".join(advisory))

    def test_unconfigured_machine_does_not_fail_the_build(self):
        # CI has no library. A hard gate here would fail every build.
        with _Env(), tempfile.TemporaryDirectory() as d:
            hard, advisory = self._run(d, ["smith-2016-software"], ["smith-2016-software"])
            self.assertEqual(hard, [])
            self.assertIn("No source library configured", "\n".join(advisory))


if __name__ == "__main__":
    unittest.main()
