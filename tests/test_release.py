"""Unit tests for the release helper (scripts/release.py, roadmap P3).

Covers changelog-section extraction, tag normalisation, and that the live
repo metadata is self-consistent. Stdlib unittest — no pytest.
"""
import argparse
import importlib.util
import json
import pathlib
import tempfile
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


class _TempRepo(unittest.TestCase):
    """Point the release helper's module globals at a throwaway repo."""

    BADGE = "[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](CHANGELOG.md)"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        d = pathlib.Path(self._tmp.name)
        (d / ".claude-plugin").mkdir()
        self.plugin = d / ".claude-plugin" / "plugin.json"
        self.market = d / ".claude-plugin" / "marketplace.json"
        self.readme = d / "README.md"
        self.changelog = d / "CHANGELOG.md"
        self.plugin.write_text(json.dumps({"name": "x", "version": "0.1.0"}, indent=2) + "\n", encoding="utf-8")
        self.market.write_text(json.dumps({"plugins": [{"version": "0.1.0"}]}, indent=2) + "\n", encoding="utf-8")
        self.readme.write_text(f"# x\n\n{self.BADGE}\n", encoding="utf-8")
        self.changelog.write_text("# Changelog\n\n## [0.1.0] — 2026-01-01\n\nFirst.\n", encoding="utf-8")
        self._saved = (rel.PLUGIN, rel.MARKETPLACE, rel.README, rel.CHANGELOG)
        rel.PLUGIN, rel.MARKETPLACE, rel.README, rel.CHANGELOG = (
            self.plugin, self.market, self.readme, self.changelog)

    def tearDown(self):
        rel.PLUGIN, rel.MARKETPLACE, rel.README, rel.CHANGELOG = self._saved
        self._tmp.cleanup()


class CmdBump(_TempRepo):
    def test_full_bump_updates_everything(self):
        rc = rel.cmd_bump(argparse.Namespace(version="0.2.0", date="2026-02-02"))
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(self.plugin.read_text(encoding="utf-8"))["version"], "0.2.0")
        self.assertEqual(json.loads(self.market.read_text(encoding="utf-8"))["plugins"][0]["version"], "0.2.0")
        self.assertIn("badge/version-0.2.0-", self.readme.read_text(encoding="utf-8"))
        self.assertNotIn("badge/version-0.1.0-", self.readme.read_text(encoding="utf-8"))
        # a skeleton section was inserted for the new version
        self.assertIsNotNone(rel.extract_changelog_section("0.2.0"))

    def test_bump_is_idempotent_no_duplicate_section(self):
        rel.cmd_bump(argparse.Namespace(version="0.2.0", date="2026-02-02"))
        first = self.changelog.read_text(encoding="utf-8")
        rc = rel.cmd_bump(argparse.Namespace(version="0.2.0", date="2026-02-02"))
        self.assertEqual(rc, 0)
        # second bump must not insert a second 0.2.0 heading
        self.assertEqual(self.changelog.read_text(encoding="utf-8").count("## [0.2.0]"), 1)
        self.assertEqual(first.count("## [0.2.0]"), 1)

    def test_bump_fails_when_badge_missing(self):
        self.readme.write_text("# x\n\nno badge here\n", encoding="utf-8")
        rc = rel.cmd_bump(argparse.Namespace(version="0.2.0", date="2026-02-02"))
        self.assertEqual(rc, 1)                       # fail-closed, not silent no-op

    def test_bump_rejects_bad_semver(self):
        self.assertEqual(rel.cmd_bump(argparse.Namespace(version="0.2", date=None)), 1)


class CmdCheck(_TempRepo):
    def _bump_all_to(self, v):
        # set both manifests + a changelog section so only the tag varies
        rel.cmd_bump(argparse.Namespace(version=v, date="2026-02-02"))

    def test_all_agree_passes(self):
        self._bump_all_to("0.2.0")
        self.assertEqual(rel.cmd_check(argparse.Namespace(tag="v0.2.0")), 0)

    def test_tag_mismatch_fails(self):
        self._bump_all_to("0.2.0")
        self.assertEqual(rel.cmd_check(argparse.Namespace(tag="v0.3.0")), 1)

    def test_manifest_mismatch_fails(self):
        self._bump_all_to("0.2.0")
        self.market.write_text(json.dumps({"plugins": [{"version": "0.9.9"}]}, indent=2) + "\n", encoding="utf-8")
        self.assertEqual(rel.cmd_check(argparse.Namespace(tag="v0.2.0")), 1)

    def test_missing_changelog_section_fails(self):
        # manifests at 0.2.0 but no changelog entry for it
        self.plugin.write_text(json.dumps({"name": "x", "version": "0.2.0"}, indent=2) + "\n", encoding="utf-8")
        self.market.write_text(json.dumps({"plugins": [{"version": "0.2.0"}]}, indent=2) + "\n", encoding="utf-8")
        self.assertEqual(rel.cmd_check(argparse.Namespace(tag="v0.2.0")), 1)

    def test_non_semver_tag_fails(self):
        self._bump_all_to("0.2.0")
        self.assertEqual(rel.cmd_check(argparse.Namespace(tag="v0.2")), 1)


if __name__ == "__main__":
    unittest.main()
