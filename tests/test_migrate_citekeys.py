"""Tests for the one-time citekey migration (scripts/migrate-citekeys.py).

These pin the invariants that make a mass rename safe. Each one guards a failure
mode that is *silent* in production — a manuscript still renders, a linter still
passes, and the damage only surfaces weeks later:

  * bijection    — two works must never collapse onto one key
  * no chaining  — A's new key must not equal B's old key
  * right bound  — `@smith2016` must not eat `@smith2016b` (a DIFFERENT work)
  * wikilinks    — `[[hensel-2024]]` must survive untouched while
                   `[@hensel-2024]` is rewritten (they look identical to a naive
                   string replace, and 8 projects have slug == bibkey)
  * Quarto xrefs — `@sec-methods` is a cross-reference, not a citation
  * code         — citations inside code fences are examples, not citations
  * idempotency  — a second run is a no-op

Stdlib unittest — no pytest.

Run: python -m unittest discover -s tests
"""
import importlib.util
import json
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "migrate-citekeys.py"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mc = _load("migrate_citekeys", SCRIPT)


def _bib(key, author="Smith, John", year="2016", title="Software citation principles",
         etype="article"):
    return (f"@{etype}{{{key},\n"
            f"  author    = {{{author}}},\n"
            f"  title     = {{{title}}},\n"
            f"  year      = {{{year}}}\n"
            f"}}\n")


class KeyGeneration(unittest.TestCase):
    def test_surname_year_shorttitle(self):
        key, reason = mc.make_key(_bib("x"))
        self.assertEqual(key, "smith-2016-software")
        self.assertEqual(reason, "ok")

    def test_stopwords_dropped(self):
        key, _ = mc.make_key(_bib("x", title="The Religion of Idumea"))
        self.assertEqual(key, "smith-2016-religion")

    def test_umlauts_folded_like_the_pdf_rule(self):
        key, _ = mc.make_key(_bib("x", author="Müller, Jörg", title="Über Räume"))
        self.assertEqual(key, "mueller-2016-ueber")

    def test_editor_is_the_fallback_for_author(self):
        body = "  editor = {Porten, Bezalel and Yardeni, Ada},\n  title = {Textbook of Aramaic Ostraca},\n  year = {2020}\n"
        key, _ = mc.make_key(body)
        self.assertEqual(key, "porten-2020-textbook")

    def test_year_range_takes_the_first_year(self):
        # Reference works carry ranges: "1998–2007". The key needs one year.
        body = "  author = {Doe, Jane},\n  title = {Samaria},\n  year = {1998–2007}\n"
        key, _ = mc.make_key(body)
        self.assertEqual(key, "doe-1998-samaria")

    def test_authorless_reference_work_is_not_guessed(self):
        # RGG / DNP / TRE / LThK have no author. Their conventional siglum is an
        # initialism no machine derives reliably ("Der Neue Pauly" -> dnp, NOT np).
        # It must surrender to the human, not invent a plausible-looking key.
        body = "  title = {Samaria},\n  booktitle = {Der Neue Pauly},\n  year = {1996}\n"
        key, reason = mc.make_key(body)
        self.assertIsNone(key)
        self.assertIn("author/editor", reason)

    def test_generated_keys_satisfy_the_schema_pattern(self):
        for body in (_bib("x"), _bib("x", author="Ben-Yosef, Erez",
                                     title="Rethinking the Social Complexity")):
            key, _ = mc.make_key(body)
            self.assertRegex(key, mc.CITEKEY_RE)


class BibParsing(unittest.TestCase):
    """Real bibs mix entry shapes. Missing entries is the worst failure mode:
    a half-migrated bib leaves the manuscript citing keys that no longer exist,
    and Quarto renders those as ??? while exiting 0.
    """

    MIXED = """% a comment line
@misc{ravi-2024,
  author = {Ravi, Nikhila and Gabeur, Valentin},
  title = {SAM 2: Segment Anything in Images and Videos},
  year = {2024}
}

@inproceedings{kirillov-2023, title={Segment Anything}, DOI={10.1109/iccv.2023.00371}, \
booktitle={ICCV}, author={Kirillov, Alexander and Mintun, Eric}, year={2023}, month=Oct, \
pages={3992–4003} }

@article{osco-2023, title={The Segment Anything Model for remote sensing}, volume={124}, \
ISSN={1569-8432}, author={Osco, Lucas Prado}, year={2023}, pages={103540} }
"""

    def test_single_line_entries_are_not_missed(self):
        found = {k for _, k, _ in mc.iter_bib_entries(self.MIXED)}
        self.assertEqual(found, {"ravi-2024", "kirillov-2023", "osco-2023"},
                         "a '\\n}'-anchored parser drops every single-line entry")

    def test_fields_read_from_single_line_entries(self):
        bodies = {k: b for _, k, b in mc.iter_bib_entries(self.MIXED)}
        key, _ = mc.make_key(bodies["kirillov-2023"])
        self.assertEqual(key, "kirillov-2023-segment")

    def test_uppercase_field_names(self):
        bodies = {k: b for _, k, b in mc.iter_bib_entries(self.MIXED)}
        self.assertEqual(mc._field(bodies["kirillov-2023"], "doi"),
                         "10.1109/iccv.2023.00371")   # written as `DOI={...}`

    def test_nested_braces_in_a_title_do_not_end_the_entry(self):
        text = "@article{a-2020,\n  title = {A {SAM}-based method},\n  author = {Doe, J},\n  year = {2020}\n}\n"
        entries = list(mc.iter_bib_entries(text))
        self.assertEqual(len(entries), 1)
        self.assertEqual(mc._field(entries[0][2], "title"), "A {SAM}-based method")


class Invariants(unittest.TestCase):
    def test_bijection_violation_aborts(self):
        # two different works generating the same key must never silently merge
        with self.assertRaises(SystemExit) as cm:
            mc.assert_invariants({"a2016": "smith-2016-x", "b2016": "smith-2016-x"})
        self.assertIn("NOT A BIJECTION", str(cm.exception))

    def test_chaining_violation_aborts(self):
        # A's NEW key == B's OLD key: a sequential rewrite would merge two works
        with self.assertRaises(SystemExit) as cm:
            mc.assert_invariants({"a": "smith-2016-x", "smith-2016-x": "smith-2016-y"})
        self.assertIn("CHAINING", str(cm.exception))

    def test_clean_mapping_passes(self):
        mc.assert_invariants({"Smith2016": "smith-2016-software",
                              "katz2021": "katz-2021-fair"})


class Substitution(unittest.TestCase):
    def _sub(self, mapping, text):
        return mc.build_substituter(mapping)(text)

    def test_right_boundary_protects_a_longer_key(self):
        # @smith2016 must NOT eat @smith2016b — they are different works.
        mapping = {"smith2016": "smith-2016-software", "smith2016b": "smith-2016b-other"}
        out = self._sub(mapping, "See [@smith2016] and [@smith2016b].")
        self.assertEqual(out, "See [@smith-2016-software] and [@smith-2016b-other].")

    def test_wikilink_is_never_touched(self):
        # The killer case: slug == bibkey. [[hensel-2024]] is a page link,
        # [@hensel-2024] is a citation. Only the latter may change.
        mapping = {"hensel-2024": "hensel-2024-yahwism"}
        out = self._sub(mapping, "See [[hensel-2024]] and cite [@hensel-2024].")
        self.assertEqual(out, "See [[hensel-2024]] and cite [@hensel-2024-yahwism].")

    def test_email_is_not_a_citation(self):
        out = self._sub({"smith2016": "smith-2016-x"}, "mail me at foo@smith2016")
        self.assertEqual(out, "mail me at foo@smith2016")

    def test_bare_and_suppressed_citations(self):
        mapping = {"smith2016": "smith-2016-x"}
        self.assertEqual(self._sub(mapping, "as @smith2016 shows"), "as @smith-2016-x shows")
        self.assertEqual(self._sub(mapping, "[-@smith2016]"), "[-@smith-2016-x]")

    def test_identity_pairs_are_a_no_op(self):
        self.assertIsNone(mc.build_substituter({"smith-2016-x": "smith-2016-x"}))


class EndToEnd(unittest.TestCase):
    def _project(self, d):
        root = pathlib.Path(d)
        (root / "output" / "bibtex").mkdir(parents=True)
        (root / "knowledge" / "sources").mkdir(parents=True)
        (root / "output" / "article").mkdir(parents=True)

        (root / "output" / "bibtex" / "references.bib").write_text(
            _bib("Smith2016") + _bib("hensel-2024", author="Hensel, Benedikt",
                                     year="2024", title="Reconsidering Yahwism"),
            encoding="utf-8")

        # a source page: frontmatter bibkey + body citation + a wikilink whose
        # slug is IDENTICAL to the bibkey (the trap)
        (root / "knowledge" / "sources" / "hensel-2024.md").write_text(
            '---\ntitle: "Hensel 2024"\ntype: source\ncreated: 2026-07-14\n'
            'updated: 2026-07-14\nstatus: review\nauthor: llm\nbibkey: hensel-2024\n---\n'
            "Body cites [@hensel-2024] and links to [[hensel-2024]] and [@Smith2016].\n"
            "Code: `@Smith2016` stays.\n",
            encoding="utf-8")

        (root / "output" / "article" / "article.qmd").write_text(
            "See @sec-methods and [@Smith2016; @hensel-2024].\n", encoding="utf-8")
        return root

    def test_full_migration(self):
        with tempfile.TemporaryDirectory() as d:
            root = self._project(d)
            mapfile = pathlib.Path(d) / "map.json"
            self.assertEqual(mc.cmd_plan(root, mapfile), 0)

            data = json.loads(mapfile.read_text(encoding="utf-8"))
            gen = {r["old"]: r["new"] for r in data["entries"]}
            self.assertEqual(gen["Smith2016"], "smith-2016-software")
            self.assertEqual(gen["hensel-2024"], "hensel-2024-reconsidering")

            backup = pathlib.Path(d) / "backup"
            self.assertEqual(mc.cmd_apply(root, mapfile, write=True, backup_dir=backup), 0)
            # the backup is the only undo an untracked file has — it must exist
            self.assertTrue((backup / "output" / "bibtex" / "references.bib").is_file())

            bib = (root / "output" / "bibtex" / "references.bib").read_text(encoding="utf-8")
            self.assertIn("@article{smith-2016-software,", bib)
            self.assertIn("@article{hensel-2024-reconsidering,", bib)
            self.assertNotIn("@article{Smith2016,", bib)

            page = (root / "knowledge" / "sources" / "hensel-2024.md").read_text(encoding="utf-8")
            self.assertIn("bibkey: hensel-2024-reconsidering", page)
            self.assertIn("[@hensel-2024-reconsidering]", page)
            self.assertIn("[[hensel-2024]]", page)          # wikilink SURVIVED
            self.assertIn("`@Smith2016`", page)             # inline code SURVIVED

            qmd = (root / "output" / "article" / "article.qmd").read_text(encoding="utf-8")
            self.assertIn("@sec-methods", qmd)              # Quarto xref SURVIVED
            self.assertIn("[@smith-2016-software; @hensel-2024-reconsidering]", qmd)

    def test_second_run_is_a_no_op(self):
        with tempfile.TemporaryDirectory() as d:
            root = self._project(d)
            mapfile = pathlib.Path(d) / "map.json"
            mc.cmd_plan(root, mapfile)
            self.assertEqual(
                mc.cmd_apply(root, mapfile, write=True,
                             backup_dir=pathlib.Path(d) / "b1"), 0)
            before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}

            # re-planning the migrated project yields identity keys → nothing to do
            map2 = pathlib.Path(d) / "map2.json"
            mc.cmd_plan(root, map2)
            self.assertEqual(
                mc.cmd_apply(root, map2, write=True,
                             backup_dir=pathlib.Path(d) / "b2"), 0)

            after = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
            for p, content in before.items():
                self.assertEqual(after[p], content, f"{p} changed on the second run")

    def test_refuses_to_write_untracked_files_without_a_backup(self):
        # An untracked / gitignored file has NO git undo. Three project repos had
        # exactly that state. The tool must refuse rather than shred it.
        with tempfile.TemporaryDirectory() as d:
            root = self._project(d)              # not a git repo → all untracked
            mapfile = pathlib.Path(d) / "map.json"
            mc.cmd_plan(root, mapfile)
            before = (root / "output" / "bibtex" / "references.bib").read_bytes()
            self.assertEqual(mc.cmd_apply(root, mapfile, write=True, backup_dir=None), 1)
            self.assertEqual(
                (root / "output" / "bibtex" / "references.bib").read_bytes(), before,
                "refused run must not have written anything")

    def test_map_with_unresolved_decision_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root = self._project(d)
            mapfile = pathlib.Path(d) / "map.json"
            mapfile.write_text(json.dumps({"entries": [
                {"old": "dnp-samaria", "new": None, "status": "needs-decision"}]}),
                encoding="utf-8")
            with self.assertRaises(SystemExit):
                mc.load_map(mapfile)

    def test_map_with_offshape_key_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            mapfile = pathlib.Path(d) / "map.json"
            mapfile.write_text(json.dumps({"entries": [
                {"old": "Smith2016", "new": "smith2016", "status": "ok"}]}),
                encoding="utf-8")
            with self.assertRaises(SystemExit) as cm:
                mc.load_map(mapfile)
            self.assertIn("citekey pattern", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
