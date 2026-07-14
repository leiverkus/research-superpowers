"""Unit tests for the wiki tooling (stdlib unittest — no pytest dependency).

Covers the robustness cases from the engineering review: invalid frontmatter
(bad dates, wrong types, bad patterns, non-list arrays), duplicate slugs, the
gate-override count, and that bad YAML never crashes the parsers.

Run: python -m unittest discover -s tests
"""
import importlib.util
import os
import json
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


lw = _load("lint_wiki", SCRIPTS / "lint-wiki.py")
wg = _load("wiki_to_graph", SCRIPTS / "wiki-to-graph.py")
SCHEMA = json.loads((ROOT / "schema" / "knowledge-frontmatter.schema.json").read_text(encoding="utf-8"))

VALID = """---
title: "A page"
type: source
created: 2026-04-15
updated: 2026-04-15
status: review
author: llm
bibkey: lastname-2026-title
tags: [chronology, levant]
---
Body text.
"""


def _write(d, rel, text):
    p = pathlib.Path(d) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


class FrontmatterValidation(unittest.TestCase):
    def test_valid_page_has_no_issues(self):
        with tempfile.TemporaryDirectory() as d:
            p = _write(d, "a.md", VALID)
            self.assertEqual(lw.validate_frontmatter(lw.parse_frontmatter(p), SCHEMA, p), [])

    def test_invalid_date_does_not_crash_and_is_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            p = _write(d, "a.md", VALID.replace("2026-04-15", "2026-99-99", 1))
            fm = lw.parse_frontmatter(p)              # must not raise ValueError
            self.assertIsInstance(fm, dict)
            issues = lw.validate_frontmatter(fm, SCHEMA, p)
            self.assertTrue(any("DATE" in i for i in issues), issues)

    def test_wrong_types_flagged(self):
        bad = VALID.replace('title: "A page"', "title: 42").replace("tags: [chronology, levant]", "tags: not-a-list")
        with tempfile.TemporaryDirectory() as d:
            p = _write(d, "a.md", bad)
            issues = lw.validate_frontmatter(lw.parse_frontmatter(p), SCHEMA, p)
            self.assertTrue(any("TYPE" in i and "title" in i for i in issues), issues)
            self.assertTrue(any("TYPE" in i and "tags" in i for i in issues), issues)

    def test_bad_pattern_flagged(self):
        bad = VALID.replace("type: source", "type: entity").replace("bibkey: lastname-2026-title", "wikidata_qid: NOPE")
        with tempfile.TemporaryDirectory() as d:
            p = _write(d, "a.md", bad)
            issues = lw.validate_frontmatter(lw.parse_frontmatter(p), SCHEMA, p)
            self.assertTrue(any("PATTERN" in i for i in issues), issues)

    def test_strict_date_format(self):
        # ISO week dates / basic format are valid for date.fromisoformat but the
        # schema requires YYYY-MM-DD — they must still be flagged.
        for bad_date in ('"2026-W15-3"', '"20260415"'):
            with tempfile.TemporaryDirectory() as d:
                p = _write(d, "a.md", VALID.replace("2026-04-15", bad_date, 1))
                issues = lw.validate_frontmatter(lw.parse_frontmatter(p), SCHEMA, p)
                self.assertTrue(any("DATE" in i for i in issues), f"{bad_date}: {issues}")

    def test_missing_required_flagged(self):
        bad = VALID.replace("status: review\n", "")
        with tempfile.TemporaryDirectory() as d:
            p = _write(d, "a.md", bad)
            issues = lw.validate_frontmatter(lw.parse_frontmatter(p), SCHEMA, p)
            self.assertTrue(any("MISSING" in i and "status" in i for i in issues), issues)


class DuplicateSlugs(unittest.TestCase):
    def test_duplicate_slug_detected(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "sources/dup.md", VALID)
            _write(d, "entities/dup.md", VALID)
            dups = lw.find_duplicate_slugs(pathlib.Path(d))
            self.assertIn("dup", dups)
            self.assertEqual(len(dups["dup"]), 2)

    def test_unique_slugs_ok(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "sources/a.md", VALID)
            _write(d, "entities/b.md", VALID)
            self.assertEqual(lw.find_duplicate_slugs(pathlib.Path(d)), {})


class GateOverrides(unittest.TestCase):
    def test_override_count_not_fake_rate(self):
        with tempfile.TemporaryDirectory() as d:
            log = pathlib.Path(d) / "gate-overrides.log"
            log.write_text("- 2026-04-15 · ingest · stable · reason\n- 2026-04-16 · draft · synth · reason\n", encoding="utf-8")
            original = lw.OVERRIDES_LOG
            try:
                lw.OVERRIDES_LOG = log
                report = lw.report_gate_overrides()
            finally:
                lw.OVERRIDES_LOG = original
            joined = " ".join(report)
            self.assertIn("Total overrides logged: 2", joined)
            self.assertNotIn("100%", joined)

    def test_future_dated_override_not_counted_as_recent(self):
        with tempfile.TemporaryDirectory() as d:
            log = pathlib.Path(d) / "gate-overrides.log"
            log.write_text("- 2099-01-01 · ingest · stable · future entry\n", encoding="utf-8")
            original = lw.OVERRIDES_LOG
            try:
                lw.OVERRIDES_LOG = log
                report = lw.report_gate_overrides()
            finally:
                lw.OVERRIDES_LOG = original
            self.assertIn("In the last 30 days: 0", " ".join(report))


class GraphRobustness(unittest.TestCase):
    def test_bad_yaml_does_not_crash_split(self):
        fm, body = wg.split_frontmatter("---\ncreated: 2026-99-99\n---\nbody")
        self.assertIsInstance(fm, dict)
        self.assertIn("body", body)

    def test_communities_deterministic(self):
        nodes = [{"id": x, "type": "source"} for x in ("a", "b", "c", "d")]
        edges = [{"source": "a", "target": "b", "weight": 3},
                 {"source": "c", "target": "d", "weight": 3}]
        r1 = wg.compute_communities(nodes, edges)
        r2 = wg.compute_communities(nodes, edges)
        self.assertEqual(r1, r2)


ENTITY = """---
title: "An entity"
type: entity
created: 2026-04-15
updated: 2026-04-15
status: review
author: llm
---
Body.
"""

CONCEPT = """---
title: "A concept"
type: concept
created: 2026-04-15
updated: 2026-04-15
status: review
author: llm
---
Body.
"""


class LintExcludesGeneratedExports(unittest.TestCase):
    def test_graph_report_md_is_not_a_wiki_page(self):
        # GRAPH_REPORT.md is written by wiki-to-graph.py into _meta/graph/. It is
        # a build artefact, not a page — lint must not pick it up (it has no
        # frontmatter and no incoming links, so it would false-positive as an
        # error + orphan). Regression guard for the 0.18.0 report interaction.
        with tempfile.TemporaryDirectory() as d:
            kn = pathlib.Path(d) / "knowledge"
            _write(d, "knowledge/entities/foo.md", ENTITY)
            _write(d, "knowledge/_meta/graph/GRAPH_REPORT.md", "# Knowledge-graph report\n\nNo frontmatter.\n")
            pages = lw.collect_pages(kn)
            self.assertIn("foo", pages)
            self.assertNotIn("GRAPH_REPORT", pages)
            self.assertEqual(lw.find_duplicate_slugs(kn), {})


class AuthorityCoverage(unittest.TestCase):
    def test_reports_tagged_and_lists_untagged(self):
        with tempfile.TemporaryDirectory() as d:
            kn = pathlib.Path(d) / "knowledge"
            _write(d, "knowledge/entities/tagged.md",
                   ENTITY.replace("author: llm\n", 'author: llm\nidai_gazetteer_id: "2132671"\n'))
            _write(d, "knowledge/entities/untagged.md", ENTITY)
            pages = lw.collect_pages(kn)
            report = "\n".join(lw.report_authority_coverage(pages, verbose=True))
            self.assertIn("1 of 2 entity page(s) carry an authority ID", report)
            self.assertIn("untagged", report)              # the untagged slug is listed
            self.assertNotIn("- tagged", report)           # the tagged one is not in the worklist

    def test_advisory_only_no_entities(self):
        with tempfile.TemporaryDirectory() as d:
            kn = pathlib.Path(d) / "knowledge"
            _write(d, "knowledge/sources/a.md", VALID)     # a source, not an entity
            self.assertEqual(lw.report_authority_coverage(lw.collect_pages(kn)), ["  No entity pages."])

    def test_concept_vocabulary_coverage(self):
        with tempfile.TemporaryDirectory() as d:
            kn = pathlib.Path(d) / "knowledge"
            _write(d, "knowledge/concepts/tagged.md",
                   CONCEPT.replace("author: llm\n", 'author: llm\ngetty_aat_id: "300054327"\n'))
            _write(d, "knowledge/concepts/untagged.md", CONCEPT)
            report = "\n".join(lw.report_concept_coverage(lw.collect_pages(kn), verbose=True))
            self.assertIn("1 of 2 concept page(s) carry a vocabulary ID", report)
            self.assertIn("untagged", report)
            self.assertNotIn("- tagged", report)

    def test_meta_pages_are_not_counted_as_content(self):
        # _meta/log.md may carry `type: concept` to satisfy frontmatter validation;
        # it must not be counted as a content concept.
        with tempfile.TemporaryDirectory() as d:
            kn = pathlib.Path(d) / "knowledge"
            _write(d, "knowledge/_meta/log.md", CONCEPT)   # meta file typed as concept
            self.assertEqual(lw.report_concept_coverage(lw.collect_pages(kn)), ["  No concept pages."])


SOURCE_PAGE = """---
title: "A source"
type: source
created: 2026-04-15
updated: 2026-04-15
status: review
author: llm
bibkey: {key}
---
{body}
"""


class CitekeyIntegrity(unittest.TestCase):
    """`bibkey` is the cross-project JOIN KEY (wiki-global-graph.py matches sources
    on it). An audit of 17 wikis found the convention honoured by only 40% of 511
    keys — 17 missed joins, 2 false positives — because nothing checked it.
    """

    def _run(self, d, bibs: dict, pages: dict, qmds: dict = None):
        """Build a project in `d`, chdir into it, run lint_citekeys."""
        root = pathlib.Path(d)
        for rel, text in bibs.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        for rel, text in pages.items():
            p = root / "knowledge" / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        for rel, text in (qmds or {}).items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
        cwd = os.getcwd()
        try:
            os.chdir(root)
            collected = lw.collect_pages(pathlib.Path("knowledge"))
            return lw.lint_citekeys(collected, SCHEMA)
        finally:
            os.chdir(cwd)

    BIB = "@article{smith-2016-software,\n  author = {Smith, J},\n  title = {Software}, \n  year = {2016}\n}\n"

    def test_clean_project_has_no_issues(self):
        with tempfile.TemporaryDirectory() as d:
            hard, _ = self._run(d, {"output/bibtex/references.bib": self.BIB},
                                {"sources/a.md": SOURCE_PAGE.format(
                                    key="smith-2016-software", body="See [@smith-2016-software].")})
            self.assertEqual(hard, [])

    def test_offshape_bib_key_is_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            hard, _ = self._run(d, {"output/bibtex/references.bib":
                                    self.BIB.replace("smith-2016-software", "Smith2016")},
                                {"sources/a.md": SOURCE_PAGE.format(
                                    key="smith-2016-software", body="x")})
            self.assertTrue(any("CITEKEY" in h and "Smith2016" in h for h in hard), hard)

    def test_duplicate_key_in_one_bib(self):
        with tempfile.TemporaryDirectory() as d:
            hard, _ = self._run(d, {"output/bibtex/references.bib": self.BIB + self.BIB},
                                {"sources/a.md": SOURCE_PAGE.format(
                                    key="smith-2016-software", body="x")})
            self.assertTrue(any("DUPLICATE-KEY" in h for h in hard), hard)

    def test_unresolved_frontmatter_bibkey(self):
        with tempfile.TemporaryDirectory() as d:
            hard, _ = self._run(d, {"output/bibtex/references.bib": self.BIB},
                                {"sources/a.md": SOURCE_PAGE.format(
                                    key="ghost-2020-nothing", body="x")})
            self.assertTrue(any("UNRESOLVED-BIBKEY" in h for h in hard), hard)

    def test_broken_citation_in_the_wiki_body(self):
        # The time bomb: nothing rendered it, so nothing caught it — until
        # drafting-manuscript lifts the dead key into the manuscript weeks later.
        with tempfile.TemporaryDirectory() as d:
            hard, _ = self._run(d, {"output/bibtex/references.bib": self.BIB},
                                {"sources/a.md": SOURCE_PAGE.format(
                                    key="smith-2016-software", body="See [@dye-2015-ghost].")})
            self.assertTrue(any("BROKEN-CITATION" in h and "dye-2015-ghost" in h for h in hard), hard)

    def test_dead_bibliography_path(self):
        # Quarto resolves a missing bibliography SILENTLY, renders every citation
        # as ???, and exits 0. Nothing else catches this.
        with tempfile.TemporaryDirectory() as d:
            hard, _ = self._run(
                d, {"output/bibtex/references.bib": self.BIB},
                {"sources/a.md": SOURCE_PAGE.format(key="smith-2016-software", body="x")},
                {"output/article/main.qmd": "---\nbibliography: ../bibtex/gone.bib\n---\nx\n"})
            self.assertTrue(any("DEAD-BIBLIOGRAPHY" in h for h in hard), hard)

    def test_truncated_title_is_not_a_divergence(self):
        # The SAME work gets transcribed at different lengths. An archived bib carries
        # "Yahwistic Diversity and the Hebrew Bible" where the current one carries the
        # full "…: State of the Field, Desiderata and Research Perspectives…". Flagging
        # that as "different works" is a false positive — and a linter that cries wolf
        # gets switched off.
        full = self.BIB.replace("{Software}", "{Software Citation Principles: A Full Subtitle}")
        with tempfile.TemporaryDirectory() as d:
            hard, _ = self._run(d, {"output/bibtex/references.bib": self.BIB,
                                    "output/bibtex/archive.bib": full},
                                {"sources/a.md": SOURCE_PAGE.format(
                                    key="smith-2016-software", body="x")})
            self.assertEqual([h for h in hard if "KEY-DIVERGENCE" in h], [])

    def test_key_divergence_across_two_bibs(self):
        with tempfile.TemporaryDirectory() as d:
            other = self.BIB.replace("{Software}", "{A completely different work}")
            hard, _ = self._run(d, {"output/bibtex/references.bib": self.BIB,
                                    "output/article/references.bib": other},
                                {"sources/a.md": SOURCE_PAGE.format(
                                    key="smith-2016-software", body="x")})
            self.assertTrue(any("KEY-DIVERGENCE" in h for h in hard), hard)

    def test_single_line_bib_entries_are_parsed(self):
        # Real bibs mix shapes; a '\n}'-anchored parser hid 98 of 122 entries in
        # one project. A key it cannot see is a key it reports as broken.
        one_liner = "@inproceedings{kirillov-2023-segment, title={Segment Anything}, author={Kirillov, A}, year={2023} }\n"
        with tempfile.TemporaryDirectory() as d:
            hard, _ = self._run(d, {"output/bibtex/references.bib": one_liner},
                                {"sources/a.md": SOURCE_PAGE.format(
                                    key="kirillov-2023-segment",
                                    body="See [@kirillov-2023-segment].")})
            self.assertEqual(hard, [])

    def test_no_false_positives(self):
        """Quarto cross-refs, escaped @, code, _meta and _example- are NOT citations.

        Each of these produced real noise against the 17 live wikis. A linter that
        cries wolf gets switched off.
        """
        body = ("See @sec-methods and @fig-map.\n"           # Quarto cross-references
                "Metric written AP\\@IoU0.5 here.\n"          # escaped at-sign
                "Inline `@ghost-2020-code` and:\n"
                "```\n@ghost-2020-fence\n```\n"
                "Mail: foo@ghost-2020-mail\n")                # e-mail
        with tempfile.TemporaryDirectory() as d:
            hard, _ = self._run(
                d, {"output/bibtex/references.bib": self.BIB},
                {"sources/a.md": SOURCE_PAGE.format(key="smith-2016-software", body=body),
                 "_meta/log.md": "durchgehend mit @citekeys belegt\n",
                 "concepts/_example-x.md": SOURCE_PAGE.format(
                     key="smith-2016-software", body="[@finkelstein2003]")})
            self.assertEqual(hard, [], f"false positives: {hard}")


class WikilinkResolution(unittest.TestCase):
    def test_alias_and_heading_links_resolve(self):
        # `[[b|alias]]` and `[[b#heading]]` are valid links to b — they must not
        # be flagged BROKEN, and b (being linked) must not be an orphan.
        with tempfile.TemporaryDirectory() as d:
            kn = pathlib.Path(d) / "knowledge"
            _write(d, "knowledge/a.md", ENTITY.replace("Body.", "See [[b|the B page]] and [[b#Intro]]."))
            _write(d, "knowledge/b.md", ENTITY)
            broken, orphans = lw.lint_wikilinks(lw.collect_pages(kn))
            self.assertEqual(broken, [], f"aliased/anchored links wrongly flagged: {broken}")
            self.assertFalse(any(o.endswith("b.md (no incoming links)") for o in orphans),
                             "b is linked via alias/anchor → not an orphan")

    def test_dangling_link_still_broken(self):
        with tempfile.TemporaryDirectory() as d:
            kn = pathlib.Path(d) / "knowledge"
            _write(d, "knowledge/a.md", ENTITY.replace("Body.", "[[does-not-exist]]"))
            broken, _ = lw.lint_wikilinks(lw.collect_pages(kn))
            self.assertTrue(any("does-not-exist" in b for b in broken))

    def test_self_link_does_not_hide_orphan(self):
        # A page linking only to itself has no real incoming link → still an orphan.
        with tempfile.TemporaryDirectory() as d:
            kn = pathlib.Path(d) / "knowledge"
            _write(d, "knowledge/a.md", ENTITY.replace("Body.", "[[a]] refers to itself"))
            broken, orphans = lw.lint_wikilinks(lw.collect_pages(kn))
            self.assertEqual(broken, [])
            self.assertTrue(any(o.endswith("a.md (no incoming links)") for o in orphans),
                            "a self-link must not save a page from orphan status")


if __name__ == "__main__":
    unittest.main()
