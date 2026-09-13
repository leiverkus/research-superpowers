"""The depth contract must hold across schema, skill and project template.

These three drift apart easily: the schema knows the enum, `ingest-source`
tells the agent what to write, and the project's CLAUDE.md decides which
sources get which depth. A change to one and not the others produces a skill
that asks for something the schema rejects, or a project setting nobody reads.

The failure this guards against is specific and was observed: an instruction
given once in conversation ("for my own articles, write long excerpts") is gone
by the next session. It only survives if it lives in the project template AND
the skill points at it.

Stdlib unittest. Run: python -m unittest discover -s tests
"""
import importlib.util
import json
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "templates" / "research-project-template"
SKILL = ROOT / "skills" / "ingest-source" / "SKILL.md"
PROJECT_CLAUDE = TEMPLATE / "CLAUDE.md"
SCHEMA = TEMPLATE / "schema" / "knowledge-frontmatter.schema.json"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


lw = _load("lint_wiki_contract", TEMPLATE / "scripts" / "lint-wiki.py")


class TheThreeAgree(unittest.TestCase):
    def setUp(self):
        self.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.skill = SKILL.read_text(encoding="utf-8")
        self.claude = PROJECT_CLAUDE.read_text(encoding="utf-8")

    def test_every_enum_value_is_explained_in_the_skill(self):
        for value in self.schema["properties"]["depth"]["enum"]:
            self.assertIn(f"`{value}`", self.skill,
                          f"ingest-source never mentions depth `{value}`")

    def test_project_template_carries_an_ingest_depth_block(self):
        self.assertIn("### Ingest depth", self.claude)

    def test_skill_sends_the_agent_to_that_block(self):
        self.assertRegex(self.skill, r"Ingest depth.{0,80}CLAUDE\.md|CLAUDE\.md.{0,80}Ingest depth")

    def test_thesis_floors_agree_between_skill_and_linter(self):
        """The numbers in prose and the numbers the linter enforces are the same."""
        for depth, floor in lw.DEPTH_MIN_THESES.items():
            if not floor:
                continue
            self.assertRegex(
                self.skill, rf"\*\*{floor}\*\*.{{0,60}}`depth: {depth}`|"
                            rf"`depth: {depth}`.{{0,80}}\*\*{floor}\*\*|"
                            rf"at least \*\*{floor}\*\*",
                f"the skill does not state the {floor}-thesis floor for {depth}")

    def test_map_depth_asks_for_no_theses(self):
        self.assertEqual(lw.DEPTH_MIN_THESES["map"], 0)


class TheTemplateKeepsBothHalves(unittest.TestCase):
    """Erschließung and Focus must both survive — dropping either defeats the design."""

    def setUp(self):
        self.skill = SKILL.read_text(encoding="utf-8")

    def test_erschliessung_sections_are_in_the_template(self):
        for heading in ("## Section map", "## Kernthesen",
                        "## What this source does not address"):
            self.assertIn(heading, self.skill, f"{heading} missing from the source template")

    def test_focus_block_survives_as_a_pointer(self):
        self.assertIn("## Focus:", self.skill)
        self.assertRegex(self.skill, r"Carries Kernthesen",
                         "the focus block must point at the Kernthesen, not repeat them")

    def test_kernthesen_are_the_sources_not_the_projects(self):
        self.assertRegex(
            self.skill, r"SOURCE's theses, not the project's",
            "the one misreading that turns Kernthesen into a second focus block")

    def test_coverage_column_is_explained(self):
        self.assertIn("Covered", self.skill)
        self.assertRegex(self.skill, r"—.{0,80}not yet worked up|not yet worked up.{0,80}—")


class ReIngestRulesAreStated(unittest.TestCase):
    def setUp(self):
        self.skill = SKILL.read_text(encoding="utf-8")

    def test_depth_is_never_lowered(self):
        self.assertRegex(self.skill, r"never lowered|never lower")

    def test_kernthesen_are_not_renumbered(self):
        """Focus blocks point at theses by number; renumbering breaks every pointer."""
        self.assertRegex(self.skill, r"never renumbered")


if __name__ == "__main__":
    unittest.main()
