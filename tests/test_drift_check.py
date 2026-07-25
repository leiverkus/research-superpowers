"""Tests for the state-triggered session-start drift check.

The failure modes worth pinning are the QUIET ones:

  * the first run must be a silent baseline — a wall of findings on install is
    the fast way to get the hook disabled
  * an unchanged world must run NO checks and print NOTHING — silence is the
    report, and a chatty hook trains the user to ignore it
  * a broken sub-check (missing script, dead python) must never break session
    start — degrade to a note, exit 0
  * the kill switch must suppress everything INCLUDING the state write
  * drift detection must be caused by observed state, never by elapsed time —
    there is deliberately no timestamp comparison anywhere

Stdlib unittest. Run: python -m unittest tests.test_drift_check
"""
import contextlib
import importlib.util
import io
import json
import os
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


dc = _load("drift_check", ROOT / "hooks" / "drift_check.py")


class _Sandbox:
    """Isolated HOME-ish env: private cache/config dirs, a fake library, an
    optional fake research project. All check runners are stubbed and their
    calls recorded — the real scripts are exercised by their own test files."""

    def __init__(self, with_project=True):
        self.with_project = with_project
        self.calls = []
        self.lint_result = (0, "Total: 0 issue(s) found")
        self.index_result = (0, "")
        self.status_result = (0, json.dumps({"docs": 3, "pages": 30, "no_text": [], "failed": []}))
        self.bibkeys_result = (0, "all clean")

    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        d = pathlib.Path(self._tmp.name)
        self.lib = d / "Bibliothek"
        (self.lib / "pdf").mkdir(parents=True)
        (self.lib / "references.bib").write_text(
            "@article{known-2020-thing,\n  keywords = {alpha; beta}\n}\n", encoding="utf-8")

        self.project = d / "proj"
        if self.with_project:
            (self.project / "knowledge").mkdir(parents=True)
            (self.project / "scripts").mkdir()
            (self.project / "scripts" / "lint-wiki.py").write_text("# stub", encoding="utf-8")
            (self.project / "scripts" / "bib-search.py").write_text("# stub", encoding="utf-8")
            (self.project / "output" / "bibtex").mkdir(parents=True)
            (self.project / "output" / "bibtex" / "references.bib").write_text(
                "@article{known-2020-thing,\n  keywords = {alpha; beta}\n}\n", encoding="utf-8")
        else:
            self.project.mkdir()

        self._env = {}
        for k, v in (("XDG_CACHE_HOME", str(d / "cache")),
                     ("XDG_CONFIG_HOME", str(d / "config")),
                     ("RESEARCH_LIBRARY", str(self.lib))):
            self._env[k] = os.environ.get(k)
            os.environ[k] = v
        for k in ("RESEARCH_SUPERPOWERS_NO_DRIFT_CHECK", "CLAUDE_PLUGIN_ROOT",
                  "CURSOR_PLUGIN_ROOT", "COPILOT_CLI"):
            self._env[k] = os.environ.pop(k, None)

        self._cwd = os.getcwd()
        os.chdir(self.project)

        self._real = {}
        sandbox = self

        def stub(name, result_attr):
            def f(*a, **kw):
                sandbox.calls.append(name)
                return getattr(sandbox, result_attr)
            return f

        for name, attr in (("run_lint", "lint_result"), ("run_index", "index_result"),
                           ("run_status", "status_result"), ("run_bibkeys", "bibkeys_result")):
            self._real[name] = getattr(dc, name)
            setattr(dc, name, stub(name, attr))
        return self

    def __exit__(self, *a):
        os.chdir(self._cwd)
        for name, fn in self._real.items():
            setattr(dc, name, fn)
        for k, v in self._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self._tmp.cleanup()

    # helpers
    def run_main(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = dc.main(list(argv))
        return code, out.getvalue()

    def add_pdf(self, name):
        (self.lib / "pdf" / f"{name}.pdf").write_bytes(b"%PDF-1.4 " + name.encode())

    def fake_index(self):
        import hashlib
        h = hashlib.sha1(str(self.lib.resolve()).encode()).hexdigest()[:8]
        p = dc.cache_dir() / f"index-{h}.sqlite"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"stub")


class Baseline(unittest.TestCase):
    def test_first_run_is_silent_and_writes_state(self):
        with _Sandbox() as s:
            code, out = s.run_main()
            self.assertEqual((code, out), (0, ""))
            self.assertEqual(s.calls, [])                 # no checks on baseline
            state = json.loads(dc.state_path().read_text())
            self.assertIn("library", state)

    def test_unchanged_world_runs_nothing_and_says_nothing(self):
        with _Sandbox() as s:
            s.run_main()
            code, out = s.run_main()
            self.assertEqual((code, out), (0, ""))
            self.assertEqual(s.calls, [])

    def test_corrupt_state_is_treated_as_baseline_not_a_crash(self):
        with _Sandbox() as s:
            dc.cache_dir().mkdir(parents=True, exist_ok=True)
            dc.state_path().write_text("{not json", encoding="utf-8")
            code, out = s.run_main()
            self.assertEqual((code, out), (0, ""))


class KillSwitch(unittest.TestCase):
    def test_kill_switch_suppresses_everything_including_the_state_write(self):
        with _Sandbox() as s:
            os.environ["RESEARCH_SUPERPOWERS_NO_DRIFT_CHECK"] = "1"
            code, out = s.run_main()
            self.assertEqual((code, out), (0, ""))
            self.assertFalse(dc.state_path().exists())


class LibraryDrift(unittest.TestCase):
    def test_a_new_pdf_triggers_the_library_check(self):
        with _Sandbox() as s:
            s.run_main()
            s.add_pdf("neu-2026-quelle")
            s.fake_index()
            code, out = s.run_main("--human")
            self.assertIn("run_index", s.calls)
            self.assertIn("search index updated", out)

    def test_without_an_existing_index_nothing_is_built_only_reported(self):
        # A first build can take ~11 s and 100+ MB — that is a decision, not a
        # side effect of starting a session.
        with _Sandbox() as s:
            s.run_main()
            s.add_pdf("neu-2026-quelle")
            code, out = s.run_main("--human")
            self.assertNotIn("run_index", s.calls)
            self.assertIn("no search index exists yet", out)

    def test_scans_without_text_layer_land_in_act_now(self):
        with _Sandbox() as s:
            s.run_main()
            s.add_pdf("scan-1999-alt")
            s.fake_index()
            s.status_result = (0, json.dumps(
                {"docs": 4, "pages": 30, "no_text": ["scan-1999-alt"], "failed": []}))
            code, out = s.run_main("--human")
            self.assertIn("⚠ Handeln", out)
            self.assertIn("scan-1999-alt", out)

    def test_a_failing_sub_check_degrades_to_a_note_never_a_crash(self):
        with _Sandbox() as s:
            s.run_main()
            s.add_pdf("neu-2026-quelle")
            s.fake_index()

            def boom(*a, **kw):
                raise RuntimeError("python exploded")
            dc.run_index = boom
            code, out = s.run_main("--human")
            self.assertEqual(code, 0)
            self.assertIn("failed to run", out)


class ProjectDrift(unittest.TestCase):
    def test_out_of_band_wiki_edit_runs_lint_and_reports_only_failures(self):
        with _Sandbox() as s:
            s.run_main()
            (s.project / "knowledge" / "neu.md").write_text("x", encoding="utf-8")
            code, out = s.run_main("--human")
            self.assertIn("run_lint", s.calls)
            self.assertNotIn("lint now FAILS", out)        # clean lint stays quiet
            s.calls.clear()
            (s.project / "knowledge" / "neu2.md").write_text("x", encoding="utf-8")
            s.lint_result = (1, "ERROR broken wikilink\nTotal: 1 issue(s) found")
            code, out = s.run_main("--human")
            self.assertIn("lint now FAILS", out)

    def test_a_non_project_cwd_never_runs_lint(self):
        with _Sandbox(with_project=False) as s:
            s.run_main()
            s.add_pdf("neu-2026-quelle")
            s.run_main()
            self.assertNotIn("run_lint", s.calls)

    def test_the_current_project_registers_itself_exactly_once(self):
        with _Sandbox() as s:
            s.run_main()
            s.run_main()
            lines = [l for l in dc.registry_path().read_text().splitlines()
                     if l.strip() and not l.startswith("#")]
            self.assertEqual(lines, [str(s.project.resolve())])


class CrossProjectDrift(unittest.TestCase):
    def _second_project(self, s, name, bib_text):
        p = pathlib.Path(s._tmp.name) / name
        (p / "output" / "bibtex").mkdir(parents=True)
        (p / "output" / "bibtex" / "references.bib").write_text(bib_text, encoding="utf-8")
        with dc.registry_path().open("a", encoding="utf-8") as f:
            f.write(str(p) + "\n")
        return p

    def test_a_changed_project_bib_triggers_merge_drift_and_bibkey_audit(self):
        with _Sandbox() as s:
            s.run_main()
            self._second_project(
                s, "proj2",
                "@article{brandneu-2026-paper,\n  keywords = {gamma}\n}\n"
                "@article{known-2020-thing,\n  keywords = {alpha; beta; NEUES-wort}\n}\n")
            code, out = s.run_main("--human")
            self.assertIn("run_bibkeys", s.calls)
            self.assertIn("merge drift", out)
            self.assertIn("brandneu-2026-paper", out)

    def test_a_bibkey_collision_lands_in_act_now(self):
        with _Sandbox() as s:
            s.run_main()
            self._second_project(s, "proj2", "@article{x-2020-y,\n}\n")
            s.bibkeys_result = (1, "COLLISION: x-2020-y denotes two different works")
            code, out = s.run_main("--human")
            self.assertIn("⚠ Handeln", out)
            self.assertIn("COLLISION", out)


class MergeDriftPure(unittest.TestCase):
    def test_missing_keys_and_new_terms_are_detected_case_insensitively(self):
        with _Sandbox() as s:
            d = dc.merge_drift(s.lib / "references.bib", [s.project])
            self.assertEqual(d["missing_keys"], [])
            self.assertEqual(d["keys_with_new_terms"], [])
            (s.project / "output" / "bibtex" / "references.bib").write_text(
                "@article{neu-2026-key,\n  keywords = {x}\n}\n"
                "@article{known-2020-thing,\n  keywords = {ALPHA; delta}\n}\n",
                encoding="utf-8")
            d = dc.merge_drift(s.lib / "references.bib", [s.project])
            self.assertEqual(d["missing_keys"], ["neu-2026-key"])
            self.assertEqual(d["keys_with_new_terms"], ["known-2020-thing"])  # delta, not ALPHA

    def test_an_unreadable_master_is_reported_not_raised(self):
        with _Sandbox() as s:
            d = dc.merge_drift(s.lib / "nope.bib", [s.project])
            self.assertTrue(d["unreadable"])


class SuggestedCommandsAreRunnable(unittest.TestCase):
    """A finding that names a command the user cannot run is worse than no
    finding: it sends them to 'No such file or directory' and costs the report
    its credibility. `merge-bibs.py` / `migrate-citekeys.py` are plugin-only —
    they operate ACROSS projects and are deliberately not mirrored into the
    template — so their hints must carry the absolute plugin path, never the
    project-relative `scripts/` form that works for template-mirrored tools.
    """

    def test_plugin_only_scripts_are_named_with_an_absolute_plugin_path(self):
        for script in ("merge-bibs.py", "migrate-citekeys.py"):
            with self.subTest(script=script):
                cmd = dc.plugin_cmd(script)
                self.assertNotIn(" scripts/", cmd)          # not project-relative
                path = pathlib.Path(cmd.split(" ", 1)[1])
                self.assertTrue(path.is_absolute())
                self.assertTrue(path.is_file(), f"{path} does not exist")

    def test_those_scripts_really_are_absent_from_the_template(self):
        # Pins the premise: if a future release mirrors them into the template,
        # this test fails and the absolute-path handling can be reconsidered.
        tpl = ROOT / "templates" / "research-project-template" / "scripts"
        for script in ("merge-bibs.py", "migrate-citekeys.py"):
            self.assertFalse((tpl / script).exists(), f"{script} is in the template now")

    def test_the_registry_is_passed_by_command_substitution_not_a_variable(self):
        # `--roots $VAR` does not word-split in zsh (the user's shell) and
        # arrives as ONE path; $(...) splits in both bash and zsh.
        exp = dc.registry_expansion()
        self.assertTrue(exp.startswith("$("), exp)
        self.assertIn(str(dc.registry_path()), exp)

    def test_a_merge_drift_finding_carries_the_runnable_command(self):
        with _Sandbox() as s:
            s.run_main()
            (s.project / "output" / "bibtex" / "references.bib").write_text(
                "@article{neu-2026-key,\n  keywords = {x}\n}\n", encoding="utf-8")
            code, out = s.run_main("--human")
            self.assertIn("merge drift", out)
            self.assertIn(str(ROOT / "scripts" / "merge-bibs.py"), out)


class HookOutput(unittest.TestCase):
    def test_claude_env_gets_hookSpecificOutput_json(self):
        with _Sandbox() as s:
            os.environ["CLAUDE_PLUGIN_ROOT"] = str(ROOT)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                dc.emit_hook_json("# Drift-Report\n- something\n")
            data = json.loads(out.getvalue())
            ctx = data["hookSpecificOutput"]["additionalContext"]
            self.assertIn("<research-drift-report>", ctx)
            self.assertIn("do not interrupt", ctx)

    def test_findings_are_persisted_to_last_drift_report(self):
        with _Sandbox() as s:
            s.run_main()
            s.add_pdf("neu-2026-quelle")
            s.run_main("--human")
            report = (dc.cache_dir() / "last-drift-report.md").read_text(encoding="utf-8")
            self.assertIn("Drift-Report", report)


if __name__ == "__main__":
    unittest.main()
