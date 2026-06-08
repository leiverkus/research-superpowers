"""Unit tests for the wiki tooling (stdlib unittest — no pytest dependency).

Covers the robustness cases from the engineering review: invalid frontmatter
(bad dates, wrong types, bad patterns, non-list arrays), duplicate slugs, the
gate-override count, and that bad YAML never crashes the parsers.

Run: python -m unittest discover -s tests
"""
import importlib.util
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
SCHEMA = json.loads((ROOT / "schema" / "knowledge-frontmatter.schema.json").read_text())

VALID = """---
title: "A page"
type: source
created: 2026-04-15
updated: 2026-04-15
status: review
author: llm
bibkey: lastname-2026
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
        bad = VALID.replace("type: source", "type: entity").replace("bibkey: lastname-2026", "wikidata_qid: NOPE")
        with tempfile.TemporaryDirectory() as d:
            p = _write(d, "a.md", bad)
            issues = lw.validate_frontmatter(lw.parse_frontmatter(p), SCHEMA, p)
            self.assertTrue(any("PATTERN" in i for i in issues), issues)

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
            log.write_text("- 2026-04-15 · ingest · stable · reason\n- 2026-04-16 · draft · synth · reason\n")
            original = lw.OVERRIDES_LOG
            try:
                lw.OVERRIDES_LOG = log
                report = lw.report_gate_overrides()
            finally:
                lw.OVERRIDES_LOG = original
            joined = " ".join(report)
            self.assertIn("Total overrides logged: 2", joined)
            self.assertNotIn("100%", joined)


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


if __name__ == "__main__":
    unittest.main()
