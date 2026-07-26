"""Tests for the pressure-test harness.

The harness is the thing that tells us whether the plugin's gates hold, so its
own failure modes are the quiet kind — a prompt that silently omits the skill
would make every GREEN result meaningless, and a scenario whose declared rule
drifted from the skill it claims to test would score against nothing.

  * every shipped scenario must validate (frontmatter, skill reference, >= 3
    pressures) — CI runs this
  * the RED prompt must NOT contain the skill: it is the baseline
  * the GREEN prompt must contain the skill VERBATIM, not a reference to it
  * neither prompt may leak the frontmatter — a scenario that tells the model
    the rule measures the scenario, not the skill

Stdlib unittest + PyYAML (already a plugin prerequisite).
Run: python -m unittest tests.test_pressure_test
"""
import contextlib
import importlib.util
import io
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pt = _load("pressure_test", ROOT / "scripts" / "pressure-test.py")


def _run(*argv) -> str:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        pt.main(list(argv))
    return out.getvalue()


class ShippedScenarios(unittest.TestCase):
    def test_every_scenario_validates(self):
        scenarios = pt.load_all()
        self.assertTrue(scenarios, "no scenarios found")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = pt.validate(scenarios)
        self.assertEqual(code, 0, out.getvalue())

    def test_each_scenario_names_a_skill_that_exists(self):
        for s in pt.load_all():
            with self.subTest(scenario=s["id"]):
                self.assertTrue((ROOT / "skills" / s["skill"] / "SKILL.md").is_file())

    def test_the_discipline_critical_skills_are_covered(self):
        # These four carry the gates the README sells the plugin on. If one
        # loses its coverage, that should fail loudly rather than quietly.
        covered = {s["skill"] for s in pt.load_all()}
        for skill in ("ingest-source", "drafting-manuscript",
                      "add-to-library", "requesting-peer-review"):
            self.assertIn(skill, covered)

    def test_scenarios_force_a_decision_rather_than_a_discussion(self):
        for s in pt.load_all():
            with self.subTest(scenario=s["id"]):
                self.assertIn("not a hypothetical", s["body"].lower())


class Prompts(unittest.TestCase):
    ID = "ingest-source/substitute-original"

    def test_red_prompt_does_not_carry_the_skill(self):
        red = _run("prompt", self.ID, "--phase", "red")
        self.assertNotIn("<skill", red)
        self.assertNotIn("HARD-STOP", red)     # the rule must not leak in
        self.assertIn("Kloner", red)           # but the scenario is there

    def test_green_prompt_inlines_the_skill_verbatim(self):
        green = _run("prompt", self.ID, "--phase", "green")
        skill = (ROOT / "skills" / "ingest-source" / "SKILL.md").read_text(encoding="utf-8")
        # a distinctive line from the middle of the skill, not just the title
        marker = [l for l in skill.splitlines() if "HARD-STOP" in l][0]
        self.assertIn(marker.strip()[:60], green)
        self.assertIn("Kloner", green)         # scenario still present

    def test_no_prompt_leaks_the_frontmatter(self):
        # The frontmatter states the rule and the scoring. A model that reads it
        # is answering an exam with the answer key attached.
        for phase in ("red", "green"):
            with self.subTest(phase=phase):
                text = _run("prompt", self.ID, "--phase", phase)
                self.assertNotIn("compliant:", text)
                self.assertNotIn("violation:", text)
                self.assertNotIn("pressures:", text)

    def test_both_prompts_ask_for_the_reasoning_verbatim(self):
        # The rationalisation IS the finding — a verdict without it gives the
        # REFACTOR phase nothing to write a red-flag row from.
        for phase in ("red", "green"):
            self.assertIn("as you actually reasoned it",
                          _run("prompt", self.ID, "--phase", phase))

    def test_both_prompts_forbid_inspecting_the_repository(self):
        """Round 1 of the 2026-07-25 run was invalidated by the absence of this
        clause: subagents inherit the dispatching session's working directory —
        the plugin repo — and read the skill, the schema, and the scenario
        file's own `compliant:` criteria before answering. A clean prompt in a
        dirty room is not a baseline."""
        for phase in ("red", "green"):
            with self.subTest(phase=phase):
                text = _run("prompt", self.ID, "--phase", phase)
                self.assertIn("Do not inspect the filesystem", text)
                self.assertIn("skills, schemas", text)

    def test_the_isolation_clause_gives_away_no_part_of_the_rule(self):
        # It must constrain where the model may look, never hint at the answer.
        clause = pt.ISOLATION.lower()
        for leak in ("hard-stop", "substitut", "forbidden", "must not ingest",
                     "verify", "stable", "adversarial"):
            self.assertNotIn(leak, clause)

    def test_an_unknown_id_lists_the_known_ones_instead_of_crashing(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = pt.main(["prompt", "nope/nope", "--phase", "red"])
        self.assertEqual(code, 1)
        self.assertIn("ingest-source/substitute-original", err.getvalue())


class Validation(unittest.TestCase):
    def _scenario(self, tmp: pathlib.Path, fm: str) -> list[dict]:
        d = tmp / "ingest-source"
        d.mkdir(parents=True, exist_ok=True)
        p = d / "synthetic.md"
        p.write_text(f"---\n{fm}---\n\nBody text, not a hypothetical.\n", encoding="utf-8")
        return [pt.parse(p)]

    def test_too_few_pressures_is_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as t:
            s = self._scenario(pathlib.Path(t),
                               "skill: ingest-source\nrule: r\npressures: [deadline]\n"
                               "compliant: [a]\nviolation: [b]\n")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = pt.validate(s)
            self.assertEqual(code, 1)
            self.assertIn("not a test", out.getvalue())

    def test_a_nonexistent_skill_is_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as t:
            s = self._scenario(pathlib.Path(t),
                               "skill: no-such-skill\nrule: r\n"
                               "pressures: [a, b, c]\ncompliant: [a]\nviolation: [b]\n")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = pt.validate(s)
            self.assertEqual(code, 1)
            self.assertIn("does not exist", out.getvalue())

    def test_missing_scoring_keys_are_rejected(self):
        import tempfile
        with tempfile.TemporaryDirectory() as t:
            s = self._scenario(pathlib.Path(t),
                               "skill: ingest-source\nrule: r\npressures: [a, b, c]\n")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = pt.validate(s)
            self.assertEqual(code, 1)
            self.assertIn("compliant", out.getvalue())


if __name__ == "__main__":
    unittest.main()
