"""Unit tests for the release helper (scripts/release.py, roadmap P3).

Covers changelog-section extraction, tag normalisation, and that the live
repo metadata is self-consistent. Stdlib unittest — no pytest.
"""
import argparse
import contextlib
import importlib.util
import io
import json
import pathlib
import re
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rel = _load("release_helper", ROOT / "scripts" / "release.py")


def _quiet(fn, *args, **kwargs):
    """Run a release.py command with stdout+stderr captured, returning its exit
    code. release.py deliberately emits ``::error::`` GitHub-Actions annotations
    on its failure paths (so a real release run surfaces problems); the negative
    tests below exercise exactly those paths, so without capture a *green* test
    job would print real error annotations into the Actions log."""
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*args, **kwargs)

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
        rc = _quiet(rel.cmd_bump,argparse.Namespace(version="0.2.0", date="2026-02-02"))
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(self.plugin.read_text(encoding="utf-8"))["version"], "0.2.0")
        self.assertEqual(json.loads(self.market.read_text(encoding="utf-8"))["plugins"][0]["version"], "0.2.0")
        self.assertIn("badge/version-0.2.0-", self.readme.read_text(encoding="utf-8"))
        self.assertNotIn("badge/version-0.1.0-", self.readme.read_text(encoding="utf-8"))
        # a skeleton section was inserted for the new version
        self.assertIsNotNone(rel.extract_changelog_section("0.2.0"))

    def test_bump_is_idempotent_no_duplicate_section(self):
        _quiet(rel.cmd_bump,argparse.Namespace(version="0.2.0", date="2026-02-02"))
        first = self.changelog.read_text(encoding="utf-8")
        rc = _quiet(rel.cmd_bump,argparse.Namespace(version="0.2.0", date="2026-02-02"))
        self.assertEqual(rc, 0)
        # second bump must not insert a second 0.2.0 heading
        self.assertEqual(self.changelog.read_text(encoding="utf-8").count("## [0.2.0]"), 1)
        self.assertEqual(first.count("## [0.2.0]"), 1)

    def test_bump_fails_when_badge_missing_leaves_repo_unchanged(self):
        self.readme.write_text("# x\n\nno badge here\n", encoding="utf-8")
        before = {f: f.read_text(encoding="utf-8")
                  for f in (self.plugin, self.market, self.readme, self.changelog)}
        rc = _quiet(rel.cmd_bump,argparse.Namespace(version="0.2.0", date="2026-02-02"))
        self.assertEqual(rc, 1)                       # fail-closed, not silent no-op
        # atomic: a failed bump must not leave a half-updated repo
        for f, text in before.items():
            self.assertEqual(f.read_text(encoding="utf-8"), text,
                             f"{f.name} was modified by a failed bump")

    def test_bump_rejects_bad_semver(self):
        self.assertEqual(_quiet(rel.cmd_bump,argparse.Namespace(version="0.2", date=None)), 1)


class ReleasedVersions(unittest.TestCase):
    def test_newest_first_and_unreleased_skipped(self):
        text = "# Changelog\n\n## [Unreleased]\n\nwip\n\n" + SAMPLE.split("\n", 2)[2]
        self.assertEqual(rel.released_versions(text), ["0.12.0", "0.11.1", "0.11.0"])

    def test_version_tuple_orders_numerically(self):
        # '0.10.0' < '0.9.0' as strings — the audit floor must not be fooled.
        self.assertGreater(rel.version_tuple("0.10.0"), rel.version_tuple("0.9.0"))


class CmdAudit(_TempRepo):
    """The bug this exists for: 0.27.0–0.30.0 were bumped, changelogged and
    merged, but never tagged. `check` could not catch it — it only runs on tag
    push, so a forgotten tag means it never runs at all."""

    def _changelog(self, *versions):
        body = "# Changelog\n\n## [Unreleased]\n\n"
        for v in versions:
            body += f"## [{v}] — 2026-01-01\n\nNotes for {v}.\n\n"
        self.changelog.write_text(body, encoding="utf-8")

    def setUp(self):
        super().setUp()
        self._saved_tags = rel.git_tags

    def tearDown(self):
        rel.git_tags = self._saved_tags
        super().tearDown()

    def test_all_tagged_passes(self):
        self._changelog("0.6.0", "0.5.0", "0.4.0")
        rel.git_tags = lambda: {"v0.6.0", "v0.5.0", "v0.4.0"}
        self.assertEqual(_quiet(rel.cmd_audit, argparse.Namespace()), 0)

    def test_untagged_older_version_fails(self):
        self._changelog("0.6.0", "0.5.0", "0.4.0")
        rel.git_tags = lambda: {"v0.6.0", "v0.4.0"}          # 0.5.0 never released
        self.assertEqual(_quiet(rel.cmd_audit, argparse.Namespace()), 1)

    def test_newest_untagged_passes_release_in_flight(self):
        # The release PR bumps the manifest and writes the notes BEFORE the tag
        # exists. Failing here would redden every release PR.
        self._changelog("0.6.0", "0.5.0", "0.4.0")
        rel.git_tags = lambda: {"v0.5.0", "v0.4.0"}
        self.assertEqual(_quiet(rel.cmd_audit, argparse.Namespace()), 0)

    def test_versions_below_floor_are_not_audited(self):
        # 0.1.0/0.2.0 predate the first tag (v0.3.0); 0.3.1 is a section for a
        # release that never happened. Immutable history, not a finding.
        self._changelog("0.5.0", "0.4.0", "0.3.1", "0.2.0", "0.1.0")
        rel.git_tags = lambda: {"v0.5.0", "v0.4.0"}
        self.assertEqual(_quiet(rel.cmd_audit, argparse.Namespace()), 0)

    def test_gap_at_the_floor_is_still_caught(self):
        self._changelog("0.5.0", "0.4.0", "0.2.0")
        rel.git_tags = lambda: {"v0.5.0", "v0.2.0"}          # 0.4.0 == floor, missing
        self.assertEqual(_quiet(rel.cmd_audit, argparse.Namespace()), 1)

    def test_no_tags_visible_fails_loudly_not_vacuously(self):
        # A shallow checkout sees no tags, so EVERY version looks untagged. The
        # dangerous answer here is a silent pass.
        self._changelog("0.6.0", "0.5.0", "0.4.0")
        rel.git_tags = lambda: set()
        self.assertEqual(_quiet(rel.cmd_audit, argparse.Namespace()), 1)


class LiveRepoIsFullyTagged(unittest.TestCase):
    def test_every_documented_version_is_tagged(self):
        """Guards the real repo, not a fixture — this is what went wrong."""
        self.assertEqual(_quiet(rel.cmd_audit, argparse.Namespace()), 0)


class PlanChangelog(unittest.TestCase):
    """Where a new version section goes, and what happens to the notes already
    written under [Unreleased].

    The bug: inserting before the first `## [` heading files the new version
    ABOVE [Unreleased] and strands the notes there — so `notes` finds only the
    empty skeleton and the release ships "_Describe the release here._" while
    the real notes sit orphaned one heading up.
    """

    WITH_NOTES = ("# Changelog\n\n## [Unreleased]\n\n### Fixed\n\n- a note\n\n"
                  "## [0.1.0] — 2026-01-01\n\nFirst.\n")
    EMPTY_UNRELEASED = "# Changelog\n\n## [Unreleased]\n\n## [0.1.0] — 2026-01-01\n\nFirst.\n"
    NO_UNRELEASED = "# Changelog\n\n## [0.1.0] — 2026-01-01\n\nFirst.\n"

    def _headings(self, text):
        return re.findall(r"^##\s*\[([^\]]+)\]", text, re.MULTILINE)

    def test_unreleased_notes_are_promoted_not_stranded(self):
        out, what = rel.plan_changelog(self.WITH_NOTES, "0.2.0", "2026-07-17")
        self.assertIn("promoted", what)
        # the notes now live under 0.2.0 — which is what `notes` will publish
        self.assertIn("- a note", rel.extract_changelog_section("0.2.0", out))
        # ...and no longer under [Unreleased]
        self.assertNotIn("- a note", out.split("## [0.2.0]")[0])

    def test_new_version_goes_below_unreleased(self):
        out, _ = rel.plan_changelog(self.WITH_NOTES, "0.2.0", "2026-07-17")
        self.assertEqual(self._headings(out), ["Unreleased", "0.2.0", "0.1.0"])

    def test_unreleased_survives_and_is_left_empty(self):
        out, _ = rel.plan_changelog(self.WITH_NOTES, "0.2.0", "2026-07-17")
        head = out.split("## [0.2.0]")[0]
        self.assertIn("## [Unreleased]", head)
        self.assertNotIn("###", head)          # nothing left under it

    def test_blank_line_after_the_heading(self):
        # `\s*$` in the [Unreleased] pattern would eat it and glue the notes on.
        out, _ = rel.plan_changelog(self.WITH_NOTES, "0.2.0", "2026-07-17")
        self.assertIn("## [0.2.0] — 2026-07-17\n\n### Fixed", out)

    def test_empty_unreleased_gets_a_skeleton_below_it(self):
        out, what = rel.plan_changelog(self.EMPTY_UNRELEASED, "0.2.0", "2026-07-17")
        self.assertIn("skeleton", what)
        self.assertEqual(self._headings(out), ["Unreleased", "0.2.0", "0.1.0"])
        self.assertIn("## [0.2.0] — 2026-07-17\n\n_Describe", out)

    def test_no_unreleased_section_still_files_newest_first(self):
        out, what = rel.plan_changelog(self.NO_UNRELEASED, "0.2.0", "2026-07-17")
        self.assertIn("skeleton", what)
        self.assertEqual(self._headings(out), ["0.2.0", "0.1.0"])

    def test_existing_section_is_left_alone(self):
        once, _ = rel.plan_changelog(self.WITH_NOTES, "0.2.0", "2026-07-17")
        twice, what = rel.plan_changelog(once, "0.2.0", "2026-07-17")
        self.assertEqual(once, twice)
        self.assertIn("already present", what)


class CmdCheck(_TempRepo):
    def _bump_all_to(self, v):
        # set both manifests + a changelog section so only the tag varies
        _quiet(rel.cmd_bump,argparse.Namespace(version=v, date="2026-02-02"))

    def test_all_agree_passes(self):
        self._bump_all_to("0.2.0")
        self.assertEqual(_quiet(rel.cmd_check,argparse.Namespace(tag="v0.2.0")), 0)

    def test_tag_mismatch_fails(self):
        self._bump_all_to("0.2.0")
        self.assertEqual(_quiet(rel.cmd_check,argparse.Namespace(tag="v0.3.0")), 1)

    def test_manifest_mismatch_fails(self):
        self._bump_all_to("0.2.0")
        self.market.write_text(json.dumps({"plugins": [{"version": "0.9.9"}]}, indent=2) + "\n", encoding="utf-8")
        self.assertEqual(_quiet(rel.cmd_check,argparse.Namespace(tag="v0.2.0")), 1)

    def test_missing_changelog_section_fails(self):
        # manifests at 0.2.0 but no changelog entry for it
        self.plugin.write_text(json.dumps({"name": "x", "version": "0.2.0"}, indent=2) + "\n", encoding="utf-8")
        self.market.write_text(json.dumps({"plugins": [{"version": "0.2.0"}]}, indent=2) + "\n", encoding="utf-8")
        self.assertEqual(_quiet(rel.cmd_check,argparse.Namespace(tag="v0.2.0")), 1)

    def test_non_semver_tag_fails(self):
        self._bump_all_to("0.2.0")
        self.assertEqual(_quiet(rel.cmd_check,argparse.Namespace(tag="v0.2")), 1)


if __name__ == "__main__":
    unittest.main()
