"""Tests for the project-sync return channel (scripts/sync-project.py) and the
drift-check finding that points at it (hooks/drift_check.py).

The schema and eleven scripts are COPIED into a project at scaffold time. CI
guards the copies inside this repo; nothing guarded the copies that actually
run, which is the gap this script closes. Two properties matter most and are
pinned hardest here:

  * the synced-file list must not drift from the lint.yml loop that gates the
    build — that loop is an allowlist, so a file missing from either side fails
    OPEN and the mirror rots while CI stays green;
  * `--apply` must never overwrite a file a project edited. Losing a local patch
    is the one failure that makes a sync tool worse than no sync tool.

Stdlib unittest. Run: python -m unittest discover -s tests
"""
import contextlib
import importlib.util
import io
import pathlib
import re
import shutil
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "sync-project.py"
HOOK = ROOT / "hooks" / "drift_check.py"
LINT_YML = ROOT / ".github" / "workflows" / "lint.yml"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sp = _load("sync_project", SCRIPT)
dc = _load("drift_check_sync", HOOK)


def _fake_project(root: pathlib.Path, *, version: str | None, files: dict[str, str] | None = None):
    """A minimal project: CLAUDE.md frontmatter + the synced paths, each a copy
    of the template unless `files` overrides its content."""
    root.mkdir(parents=True, exist_ok=True)
    fm = ["---", "methodology: hermeneutic", 'discipline: ""']
    if version is not None:
        fm.append(f'plugin_version: "{version}"')
    fm += ["---", "", "# Project"]
    (root / "CLAUDE.md").write_text("\n".join(fm) + "\n", encoding="utf-8")
    (root / "knowledge").mkdir(exist_ok=True)
    for rel in sp.SYNCED_PATHS:
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if files and rel in files:
            dst.write_text(files[rel], encoding="utf-8")
        else:
            shutil.copy2(sp.TEMPLATE / rel, dst)
    return root


class SyncedListMatchesCI(unittest.TestCase):
    """The list in the script and the loop in lint.yml are the same allowlist.

    CONTRIBUTING.md asks for this in prose ("Adding a mirrored script? Add it to
    the lint.yml loop in the same commit") and prose does not fail a build.
    """

    def test_script_half_matches_lint_yml_loop(self):
        text = LINT_YML.read_text(encoding="utf-8")
        block = re.search(r"for rel in (.+?); do", text, re.DOTALL)
        self.assertIsNotNone(block, "the mirror loop in lint.yml moved or was renamed")
        in_ci = set(re.findall(r"(scripts/[\w./-]+)", block.group(1)))
        in_script = {p for p in sp.SYNCED_PATHS if p.startswith("scripts/")}
        self.assertEqual(
            in_ci, in_script,
            "sync-project.py's SYNCED_PATHS and the lint.yml mirror loop disagree — "
            "a file in neither is mirrored by nobody and nothing reports it")

    def test_schema_is_synced_but_not_in_the_script_loop(self):
        # The schema has its own CI step ("Schema mirror is in sync"), so it is
        # absent from the scripts loop but must still reach a project.
        self.assertIn("schema/knowledge-frontmatter.schema.json", sp.SYNCED_PATHS)

    def test_every_synced_path_exists_in_the_template(self):
        for rel in sp.SYNCED_PATHS:
            self.assertTrue((sp.TEMPLATE / rel).is_file(), f"{rel} missing from the template")


class VersionComparison(unittest.TestCase):
    def test_numeric_not_lexicographic(self):
        self.assertLess(sp.version_tuple("0.9.0"), sp.version_tuple("0.10.0"))
        self.assertLess(sp.version_tuple("0.39.0"), sp.version_tuple("0.40.0"))

    def test_garbage_sorts_low_instead_of_raising(self):
        self.assertEqual(sp.version_tuple("not-a-version"), (0,))


class FrontmatterRoundTrip(unittest.TestCase):
    def test_reads_quoted_and_unquoted(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / "CLAUDE.md").write_text(
                '---\nplugin_version: "1.2.3"\n---\n', encoding="utf-8")
            self.assertEqual(sp.read_project_version(root), "1.2.3")
            (root / "CLAUDE.md").write_text(
                "---\nplugin_version: 1.2.3   # trailing comment\n---\n", encoding="utf-8")
            self.assertEqual(sp.read_project_version(root), "1.2.3")

    def test_adds_the_key_when_absent(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / "CLAUDE.md").write_text(
                "---\nmethodology: hermeneutic\n---\n\n# Body\n", encoding="utf-8")
            self.assertTrue(sp.write_project_version(root, "0.40.0"))
            self.assertEqual(sp.read_project_version(root), "0.40.0")
            self.assertIn("# Body", (root / "CLAUDE.md").read_text(encoding="utf-8"))

    def test_no_frontmatter_is_refused_not_guessed(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            (root / "CLAUDE.md").write_text("# No frontmatter here\n", encoding="utf-8")
            self.assertIsNone(sp.read_project_version(root))
            self.assertFalse(sp.write_project_version(root, "0.40.0"))


class Classification(unittest.TestCase):
    def test_identical_files_are_in_sync(self):
        with tempfile.TemporaryDirectory() as td:
            root = _fake_project(pathlib.Path(td) / "p", version=sp.plugin_version())
            _, rows = sp.classify(root, sp.plugin_version())
            self.assertTrue(all(s == "same" for _, s in rows), rows)

    def test_behind_plus_differing_is_outdated(self):
        with tempfile.TemporaryDirectory() as td:
            root = _fake_project(pathlib.Path(td) / "p", version="0.1.0",
                                 files={"scripts/lint-wiki.py": "# old\n"})
            _, rows = sp.classify(root, "0.40.0")
            self.assertIn(("scripts/lint-wiki.py", "outdated"), rows)

    def test_current_plus_differing_is_a_local_edit(self):
        with tempfile.TemporaryDirectory() as td:
            root = _fake_project(pathlib.Path(td) / "p", version="0.40.0",
                                 files={"scripts/lint-wiki.py": "# patched locally\n"})
            _, rows = sp.classify(root, "0.40.0")
            self.assertIn(("scripts/lint-wiki.py", "local-edit"), rows)

    def test_unrecorded_version_counts_as_behind(self):
        # Every project scaffolded before the field existed lands here; calling
        # those "local edits" would bury the real ones in noise.
        with tempfile.TemporaryDirectory() as td:
            root = _fake_project(pathlib.Path(td) / "p", version=None,
                                 files={"scripts/lint-wiki.py": "# old\n"})
            recorded, rows = sp.classify(root, "0.40.0")
            self.assertIsNone(recorded)
            self.assertIn(("scripts/lint-wiki.py", "outdated"), rows)

    def test_missing_file_is_reported_separately(self):
        with tempfile.TemporaryDirectory() as td:
            root = _fake_project(pathlib.Path(td) / "p", version="0.1.0")
            (root / "scripts" / "bib-subset.py").unlink()
            _, rows = sp.classify(root, "0.40.0")
            self.assertIn(("scripts/bib-subset.py", "missing"), rows)


class ApplyProtectsLocalEdits(unittest.TestCase):
    def _run(self, argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            try:
                code = sp.main()
            except SystemExit as e:            # pragma: no cover - argparse paths
                code = e.code
        return code, buf.getvalue()

    def test_apply_refuses_a_local_edit_and_says_so(self):
        with tempfile.TemporaryDirectory() as td:
            patched = "# patched locally\n"
            root = _fake_project(pathlib.Path(td) / "p", version=sp.plugin_version(),
                                 files={"scripts/lint-wiki.py": patched})
            import sys
            argv = sys.argv
            sys.argv = ["sync-project.py", "--roots", str(root), "--apply"]
            try:
                code, out = self._run(argv)
            finally:
                sys.argv = argv
            self.assertEqual((root / "scripts" / "lint-wiki.py").read_text(encoding="utf-8"),
                             patched, "a local edit was overwritten without --force")
            self.assertIn("LOCAL EDIT", out)
            self.assertNotEqual(code, 0, "an unresolved local edit must not exit clean")

    def test_force_overwrites_and_records_the_version(self):
        with tempfile.TemporaryDirectory() as td:
            root = _fake_project(pathlib.Path(td) / "p", version=sp.plugin_version(),
                                 files={"scripts/lint-wiki.py": "# patched locally\n"})
            import sys
            argv = sys.argv
            sys.argv = ["sync-project.py", "--roots", str(root), "--apply", "--force"]
            try:
                code, _ = self._run(argv)
            finally:
                sys.argv = argv
            self.assertEqual(code, 0)
            self.assertEqual(
                (root / "scripts" / "lint-wiki.py").read_bytes(),
                (sp.TEMPLATE / "scripts" / "lint-wiki.py").read_bytes())
            self.assertEqual(sp.read_project_version(root), sp.plugin_version())

    def test_outdated_sync_sets_the_version(self):
        with tempfile.TemporaryDirectory() as td:
            root = _fake_project(pathlib.Path(td) / "p", version="0.1.0",
                                 files={"scripts/lint-wiki.py": "# old\n"})
            import sys
            argv = sys.argv
            sys.argv = ["sync-project.py", "--roots", str(root), "--apply"]
            try:
                code, _ = self._run(argv)
            finally:
                sys.argv = argv
            self.assertEqual(code, 0)
            self.assertEqual(sp.read_project_version(root), sp.plugin_version())

    def test_report_only_writes_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            root = _fake_project(pathlib.Path(td) / "p", version="0.1.0",
                                 files={"scripts/lint-wiki.py": "# old\n"})
            import sys
            argv = sys.argv
            sys.argv = ["sync-project.py", "--roots", str(root)]
            try:
                self._run(argv)
            finally:
                sys.argv = argv
            self.assertEqual((root / "scripts" / "lint-wiki.py").read_text(encoding="utf-8"),
                             "# old\n")
            self.assertEqual(sp.read_project_version(root), "0.1.0")


class Labels(unittest.TestCase):
    def test_duplicate_basenames_get_their_parent(self):
        roots = [pathlib.Path("/a/Choros/paper"), pathlib.Path("/a/Aoristos/paper"),
                 pathlib.Path("/a/Monotheism")]
        labels = sp.labels_for(roots)
        self.assertEqual(labels[roots[0]], "Choros/paper")
        self.assertEqual(labels[roots[1]], "Aoristos/paper")
        self.assertEqual(labels[roots[2]], "Monotheism", "a unique name needs no parent")


class DriftFinding(unittest.TestCase):
    def test_behind_project_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            root = _fake_project(pathlib.Path(td) / "p", version="0.1.0")
            stale = dc.project_sync_drift([root])
            self.assertEqual(stale, [("p", "0.1.0")])

    def test_current_project_is_silent(self):
        with tempfile.TemporaryDirectory() as td:
            root = _fake_project(pathlib.Path(td) / "p", version=dc.plugin_version())
            self.assertEqual(dc.project_sync_drift([root]), [])

    def test_unrecorded_version_is_reported_as_such(self):
        with tempfile.TemporaryDirectory() as td:
            root = _fake_project(pathlib.Path(td) / "p", version=None)
            self.assertEqual(dc.project_sync_drift([root]), [("p", "not recorded")])

    def test_non_project_directories_are_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            plain = pathlib.Path(td) / "not-a-project"
            plain.mkdir()
            self.assertEqual(dc.project_sync_drift([plain]), [])

    def test_fingerprint_survives_a_json_round_trip(self):
        """The finding is state-triggered, and state goes through json.

        A tuple comes back from json.load as a list, so a fingerprint built from
        tuples never equals the stored one and the check reports every single
        session — the exact "daily all-quiet ceremony" this hook exists to avoid.
        """
        import json
        with tempfile.TemporaryDirectory() as td:
            root = _fake_project(pathlib.Path(td) / "p", version="0.1.0")
            fp = dc.fp_project_sync([root])
            self.assertEqual(json.loads(json.dumps(fp)), fp,
                             "fingerprint changes shape when persisted")


if __name__ == "__main__":
    unittest.main()
