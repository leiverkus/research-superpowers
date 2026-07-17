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

    def _run(self, d, keys, pages, cited=()):
        root = pathlib.Path(d) / "proj"
        (root / "knowledge" / "sources").mkdir(parents=True)
        (root / "output" / "bibtex").mkdir(parents=True)
        (root / "output" / "bibtex" / "references.bib").write_text(
            "\n".join(f"@article{{{k},\n  author = {{X, Y}},\n  title = {{T}},\n  year = {{2016}}\n}}"
                      for k in keys) + "\n", encoding="utf-8")
        for i, k in enumerate(pages):
            (root / "knowledge" / "sources" / f"s{i}.md").write_text(
                SOURCE.format(key=k, body="body"), encoding="utf-8")
        if cited:
            (root / "output" / "article").mkdir(parents=True)
            (root / "output" / "article" / "a.qmd").write_text(
                "# T\n\n" + " ".join(f"[@{k}]" for k in cited) + "\n", encoding="utf-8")
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


class AcquiredButNotIngested(unittest.TestCase):
    """Check 9 — the direction nobody was asking.

    Check 8 asks "does every source page have a PDF?". Nothing asked the reverse, so a
    source could be searched for, paid for, downloaded — and then simply forgotten.
    Across the 17 live wikis that was true of 146 sources; one project had 48 of its 55
    PDFs never ingested. The wiki looked healthy the whole time.
    """

    _run = LintChecksTheLibrary._run

    def test_a_pdf_with_no_source_page_is_reported(self):
        with _Env(), tempfile.TemporaryDirectory() as d:
            root = _library(d, ["smith-2016-software", "jones-2020-data"])
            os.environ[lib.ENV_VAR] = str(root)
            hard, advisory = self._run(d, ["smith-2016-software", "jones-2020-data"],
                                       ["smith-2016-software"])          # jones: no page
            self.assertEqual(hard, [])                                    # never hard
            joined = "\n".join(advisory)
            self.assertIn("Acquired but NOT ingested (1 of 2)", joined)
            self.assertIn("jones-2020-data", joined)
            self.assertIn("ingest-source", joined)

    def test_a_CITED_but_never_ingested_source_slips_past_check_7(self):
        # The case that motivated this check: the manuscript already cites the work, so
        # check 7 ("uncited, no source page") stays silent — yet no one ever read it
        # into the wiki, and drafting has nothing to reach back into.
        with _Env(), tempfile.TemporaryDirectory() as d:
            root = _library(d, ["smith-2016-software", "jones-2020-data"])
            os.environ[lib.ENV_VAR] = str(root)
            _, advisory = self._run(d, ["smith-2016-software", "jones-2020-data"],
                                    ["smith-2016-software"], cited=["jones-2020-data"])
            joined = "\n".join(advisory)
            self.assertNotIn("Uncited, no source page", joined)     # check 7 is quiet
            self.assertIn("jones-2020-data", joined)                # check 9 is not
            self.assertIn("Acquired but NOT ingested", joined)

    def test_an_entry_with_no_pdf_is_NOT_reported_here(self):
        # "Not acquired" is acquire-sources' business, not ingest's. Reporting it here
        # would make every un-downloaded entry look like a forgotten ingest.
        with _Env(), tempfile.TemporaryDirectory() as d:
            root = _library(d, ["smith-2016-software"])          # jones has NO pdf
            os.environ[lib.ENV_VAR] = str(root)
            _, advisory = self._run(d, ["smith-2016-software", "jones-2020-data"],
                                    ["smith-2016-software"])
            joined = "\n".join(advisory)
            self.assertNotIn("Acquired but NOT ingested", joined)
            self.assertIn("All 1 acquired sources are ingested.", joined)

    def test_a_fully_ingested_project_says_so(self):
        with _Env(), tempfile.TemporaryDirectory() as d:
            root = _library(d, ["smith-2016-software"])
            os.environ[lib.ENV_VAR] = str(root)
            _, advisory = self._run(d, ["smith-2016-software"], ["smith-2016-software"])
            self.assertIn("All 1 acquired sources are ingested.", "\n".join(advisory))

    def test_unconfigured_machine_stays_silent(self):
        with _Env(), tempfile.TemporaryDirectory() as d:
            hard, advisory = self._run(d, ["smith-2016-software"], [])
            self.assertEqual(hard, [])
            self.assertNotIn("Acquired but NOT ingested", "\n".join(advisory))


if __name__ == "__main__":
    unittest.main()


class DuplicateKeyInTheLibrary(unittest.TestCase):
    """Check 11 — the same key defined twice in the SHARED library.

    Check 2 catches a key defined twice in a project .bib. Nothing checked the library —
    and a duplicate there is strictly worse, because `bib-subset.py` copies the winning
    entry into every project that cites the key. One bad merge poisons all of them.

    BibTeX takes the LAST definition and drops the rest. Silently. Fields and all.

    Found on the live library: `rabunal-2023-unraveling` existed twice. The older entry had
    FOUR authors; the newer had three. The newer won — and Javier Fernández-López de Pablo
    would have vanished from every manuscript citing that work. Nothing in the pipeline
    would have said a word.
    """

    _run = LintChecksTheLibrary._run

    def _library_with_duplicate(self, d):
        root = pathlib.Path(d) / "Bibliothek"
        (root / "pdf").mkdir(parents=True)
        (root / "pdf" / "smith-2016-software.pdf").write_bytes(b"%PDF-1.4\n")
        (root / "references.bib").write_text(
            # the real shape of the bug: same key, and the LAST one is the poorer record
            '@article{smith-2016-software,\n  author = {Smith, A and Jones, B and Wu, C},\n'
            '  title = {T},\n  year = {2016}\n}\n\n'
            '@article{smith-2016-software,\n  author = {Smith, A},\n'
            '  title = {T},\n  year = {2016}\n}\n', encoding="utf-8")
        return root

    def test_a_duplicate_key_in_the_library_is_a_HARD_error(self):
        with _Env(), tempfile.TemporaryDirectory() as d:
            os.environ[lib.ENV_VAR] = str(self._library_with_duplicate(d))
            hard, _ = self._run(d, ["smith-2016-software"], ["smith-2016-software"])
            joined = "\n".join(hard)
            self.assertIn("DUPLICATE-KEY-IN-LIBRARY", joined)
            self.assertIn("smith-2016-software", joined)
            self.assertIn("LAST", joined)      # the message must say which one wins

    def test_a_clean_library_is_silent(self):
        with _Env(), tempfile.TemporaryDirectory() as d:
            root = _library(d, ["smith-2016-software"])
            os.environ[lib.ENV_VAR] = str(root)
            hard, _ = self._run(d, ["smith-2016-software"], ["smith-2016-software"])
            self.assertEqual([h for h in hard if "DUPLICATE-KEY-IN-LIBRARY" in h], [])

    def test_an_unconfigured_machine_does_not_fail_the_build(self):
        # CI has no library. This must not turn every build red.
        with _Env(), tempfile.TemporaryDirectory() as d:
            hard, _ = self._run(d, ["smith-2016-software"], ["smith-2016-software"])
            self.assertEqual([h for h in hard if "DUPLICATE-KEY-IN-LIBRARY" in h], [])


class KeywordReading(unittest.TestCase):
    """`library.read_keywords()` — the BibTeX `keywords` field reader `bib-search.py`
    builds its keyword index from. Pure string processing (no subprocess, unlike
    `extract_pages`), so these test it directly against a literal .bib file rather
    than going through `_Env`/`find_library`."""

    def _bib(self, d, text):
        p = pathlib.Path(d) / "references.bib"
        p.write_text(text, encoding="utf-8")
        return p

    def test_splits_on_semicolon_and_trims(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._bib(d, "@article{a-2020-x,\n"
                              "  keywords = { random labelling ;  mark permutation  }\n}\n")
            self.assertEqual(lib.read_keywords(p), {"a-2020-x": ["random labelling", "mark permutation"]})

    def test_an_entry_with_no_keywords_field_is_ABSENT_not_empty(self):
        # "not in the dict" and "in the dict with []" would mean different things to a
        # caller computing coverage — this reader must never manufacture the latter.
        with tempfile.TemporaryDirectory() as d:
            p = self._bib(d, "@article{a-2020-x,\n  title = {T}\n}\n")
            self.assertEqual(lib.read_keywords(p), {})
            self.assertNotIn("a-2020-x", lib.read_keywords(p))

    def test_an_unbalanced_entry_is_skipped_never_guessed(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._bib(d,
                "@article{broken-2019-x,\n"
                "  title = {Missing closing brace\n"
                "  keywords = {should never be reached}\n\n"
                "@article{fine-2021-y,\n"
                "  keywords = {a real term}\n}\n")
            got = lib.read_keywords(p)
            self.assertNotIn("broken-2019-x", got)

    def test_an_unbalanced_entry_does_not_corrupt_a_LATER_valid_entry(self):
        # Regex-driven `finditer` over the whole text, not a sequential cursor — one
        # bad entry must not drag down everything found after it.
        with tempfile.TemporaryDirectory() as d:
            p = self._bib(d,
                "@article{broken-2019-x,\n"
                "  title = {Missing closing brace\n"
                "  keywords = {should never be reached}\n\n"
                "@article{fine-2021-y,\n"
                "  keywords = {a real term}\n}\n")
            got = lib.read_keywords(p)
            self.assertEqual(got.get("fine-2021-y"), ["a real term"])

    def test_within_entry_dedup_is_case_insensitive_and_keeps_first_seen_casing(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._bib(d, "@article{a-2020-x,\n"
                              "  keywords = {Low Chronology; low chronology; LOW CHRONOLOGY}\n}\n")
            self.assertEqual(lib.read_keywords(p), {"a-2020-x": ["Low Chronology"]})

    def test_multiple_entries_each_keep_their_own_list(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._bib(d,
                "@article{a-2020-x,\n  keywords = {alpha; beta}\n}\n\n"
                "@article{b-2021-y,\n  keywords = {gamma}\n}\n")
            self.assertEqual(lib.read_keywords(p),
                              {"a-2020-x": ["alpha", "beta"], "b-2021-y": ["gamma"]})

    def test_empty_and_whitespace_only_terms_are_dropped(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._bib(d, "@article{a-2020-x,\n  keywords = {alpha;; ;   ;beta}\n}\n")
            self.assertEqual(lib.read_keywords(p), {"a-2020-x": ["alpha", "beta"]})


mb = _load("merge_bibs", ROOT / "scripts" / "merge-bibs.py")


class MakeBibkey(unittest.TestCase):
    """`library.make_bibkey` — the canonical `autor-jahr[letter]-kurztitel` key.

    The key is the PDF filename stem AND the cross-project join key, so the
    folding must match migrate-citekeys.py exactly and an unfillable slot must
    raise (so the skill stops and asks) rather than mint a half-key."""

    def test_the_documented_canonical_example(self):
        self.assertEqual(lib.make_bibkey("Finkelstein", "2003", "low chronology"),
                         "finkelstein-2003-low-chronology")

    def test_umlauts_fold_the_filename_way(self):
        self.assertEqual(lib.make_bibkey("Müller", "2020", "Übergang"),
                         "mueller-2020-uebergang")

    def test_undecomposable_letters_survive_folding(self):
        # NFKD alone drops Turkish ı / Polish ł — the explicit table must catch them.
        self.assertEqual(lib.make_bibkey("Sırmaçek", "2019", "detection"),
                         "sirmacek-2019-detection")   # ı→i, ç→c; without the table: srmacek
        self.assertEqual(lib.make_bibkey("Trybała", "2021", "mapping"),
                         "trybala-2021-mapping")      # ł→l keeps the l; without it: trybaa

    def test_particles_and_spaces_collapse_into_the_surname(self):
        self.assertEqual(lib.make_bibkey("van der Toorn", "1996", "family religion"),
                         "vandertoorn-1996-family-religion")

    def test_a_hyphenated_kurztitel_argument_is_accepted_as_is(self):
        # The caller may pass the kurztitel already hyphenated; slugifying is idempotent.
        self.assertEqual(lib.make_bibkey("Mazar", "2011", "iron-age"),
                         "mazar-2011-iron-age")

    def test_disambiguation_letter_goes_after_the_year(self):
        self.assertEqual(lib.make_bibkey("Mazar", "2011", "iron age", letter="b"),
                         "mazar-2011b-iron-age")

    def test_a_year_range_takes_the_first_year(self):
        self.assertEqual(lib.make_bibkey("Smith", "1998–2007", "survey"),
                         "smith-1998-survey")

    def test_a_missing_slot_raises_not_returns_a_half_key(self):
        with self.assertRaises(ValueError):
            lib.make_bibkey("", "2003", "low chronology")     # no surname
        with self.assertRaises(ValueError):
            lib.make_bibkey("Finkelstein", "no year here", "low")   # no 4-digit year
        with self.assertRaises(ValueError):
            lib.make_bibkey("Finkelstein", "2003", "!!!")     # kurztitel slugs to nothing

    def test_a_multi_character_letter_is_rejected(self):
        with self.assertRaises(ValueError):
            lib.make_bibkey("Mazar", "2011", "iron age", letter="ab")


class ProposeShorttitle(unittest.TestCase):
    def test_drops_stopwords_and_keeps_the_first_significant_words(self):
        self.assertEqual(
            lib.propose_shorttitle("The Low Chronology and the Problem of the Archaeology"),
            "low-chronology-problem")

    def test_respects_the_words_limit(self):
        self.assertEqual(lib.propose_shorttitle("Copper Smelting in the Arabah", words=1),
                         "copper")

    def test_a_title_of_only_stopwords_yields_none(self):
        self.assertIsNone(lib.propose_shorttitle("The And Of"))

    def test_none_title_is_tolerated(self):
        self.assertIsNone(lib.propose_shorttitle(""))


class NextFreeLetter(unittest.TestCase):
    def test_a_bare_incumbent_gives_the_newcomer_a(self):
        # The bare-year incumbent holds the no-letter slot; the newcomer takes 'a'.
        self.assertEqual(
            lib.next_free_letter(["mazar-2011-iron-age", "smith-2011-other"], "Mazar", "2011"),
            "a")

    def test_skips_letters_already_in_use(self):
        self.assertEqual(
            lib.next_free_letter(["mazar-2011-iron-age", "mazar-2011a-copper"], "Mazar", "2011"),
            "b")

    def test_no_prior_key_at_all_still_returns_a_letter(self):
        # Caller only asks for a letter once a genuine collision is known, so 'a' is fine.
        self.assertEqual(lib.next_free_letter([], "Mazar", "2011"), "a")

    def test_folding_matches_make_bibkey_so_the_scan_actually_hits(self):
        self.assertEqual(
            lib.next_free_letter(["mueller-2020-uebergang"], "Müller", "2020"), "a")


class EmitEntry(unittest.TestCase):
    """`library.emit_entry` must be byte-identical to what merge-bibs.py writes,
    so a directly-added entry and the same entry re-rendered by a later merge
    produce no spurious diff on the shared references.bib."""

    def _merge_bibs_render(self, etype, key, fields):
        # Reproduce merge-bibs.py's exact entry-writing loop (main(), lines 227–236).
        f = {k: v for k, v in fields.items() if str(v).strip()}
        width = max((len(k) for k in f), default=6)
        lines = [f"@{etype}{{{key},"]
        for name in mb.FIELD_ORDER:
            if name in f:
                lines.append(f"  {name.ljust(width)} = {{{f[name]}}},")
        for name in sorted(set(f) - set(mb.FIELD_ORDER)):
            lines.append(f"  {name.ljust(width)} = {{{f[name]}}},")
        lines.append("}")
        return "\n".join(lines)

    def test_field_order_matches_merge_bibs(self):
        self.assertEqual(lib.BIB_FIELD_ORDER, mb.FIELD_ORDER)

    def test_output_is_byte_identical_to_merge_bibs(self):
        fields = {"author": "Finkelstein, Israel", "title": "The Low Chronology",
                  "journal": "Levant", "year": "2003", "doi": "10.1179/lev.2003.35.1.65",
                  "keywords": "low chronology; iron age"}
        self.assertEqual(lib.emit_entry("article", "finkelstein-2003-low-chronology", fields),
                         self._merge_bibs_render("article", "finkelstein-2003-low-chronology", fields))

    def test_round_trips_through_the_merge_bibs_parser(self):
        fields = {"author": "Mazar, Amihai", "title": "Iron Age Chronology",
                  "year": "2011", "keywords": "iron age; chronology"}
        text = lib.emit_entry("article", "mazar-2011-iron-age", fields) + "\n"
        parsed = list(mb.iter_entries(text))
        self.assertEqual(len(parsed), 1)
        etype, key, body = parsed[0]
        self.assertEqual((etype, key), ("article", "mazar-2011-iron-age"))
        got = mb.fields_of(body)
        self.assertEqual(got["author"], "Mazar, Amihai")
        self.assertEqual(got["title"], "Iron Age Chronology")
        self.assertEqual(got["keywords"], "iron age; chronology")

    def test_blank_fields_are_dropped(self):
        text = lib.emit_entry("article", "a-2020-x",
                              {"author": "X, Y", "doi": "", "note": "   "})
        self.assertIn("author", text)
        self.assertNotIn("doi", text)
        self.assertNotIn("note", text)
