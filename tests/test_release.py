"""Unit tests for the release helper (scripts/release.py, roadmap P3).

Covers changelog-section extraction, tag normalisation, and that the live
repo metadata is self-consistent. Stdlib unittest — no pytest.
"""
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rel = _load("release_helper", ROOT / "scripts" / "release.py")

SAMPLE = """# Changelog

## [0.12.0] — 2026-06-08

Headline for twelve.

### Added
- a thing

## [0.11.1] — 2026-06-08

Eleven-one body.

## [0.11.0] — 2026-06-08

Eleven body.
"""


class StripV(unittest.TestCase):
    def test_plain_and_ref_forms(self):
        self.assertEqual(rel.strip_v("v0.12.0"), "0.12.0")
        self.assertEqual(rel.strip_v("refs/tags/v0.12.0"), "0.12.0")
        self.assertEqual(rel.strip_v("0.12.0"), "0.12.0")


class ExtractChangelogSection(unittest.TestCase):
    def test_extracts_only_that_section(self):
        body = rel.extract_changelog_section("0.12.0", SAMPLE)
        self.assertIn("Headline for twelve.", body)
        self.assertIn("a thing", body)
        self.assertNotIn("Eleven-one", body)        # stops at next heading

    def test_middle_section(self):
        body = rel.extract_changelog_section("0.11.1", SAMPLE)
        self.assertIn("Eleven-one body.", body)
        self.assertNotIn("Eleven body.", body)
        self.assertNotIn("Headline for twelve.", body)

    def test_last_section_runs_to_eof(self):
        body = rel.extract_changelog_section("0.11.0", SAMPLE)
        self.assertIn("Eleven body.", body)

    def test_missing_section_is_none(self):
        self.assertIsNone(rel.extract_changelog_section("9.9.9", SAMPLE))


class LiveRepoMetadata(unittest.TestCase):
    def test_manifests_match_and_changelog_present(self):
        pv = rel._plugin_version()
        self.assertEqual(pv, rel._marketplace_version())
        self.assertIsNotNone(rel.extract_changelog_section(pv),
                             f"CHANGELOG.md has no section for current version {pv}")


if __name__ == "__main__":
    unittest.main()
