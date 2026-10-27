"""Every skill and agent frontmatter parses as real YAML.

`scripts/lint-plugin.py` reads frontmatter with a tolerant line parser, so it
accepts text that YAML rejects — a plain scalar with `: ` inside, an unclosed
quote. Claude Code does not: a skill whose frontmatter fails to parse loads
with empty metadata, every field silently dropped, including the description
that makes it trigger. This test is the strict counterpart.

PyYAML is a CI/dev dependency (see requirements-dev.txt); the test skips
cleanly when it isn't installed.

Run: python -m unittest discover -s tests
"""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent

try:
    import yaml
    HAVE_YAML = True
except Exception:                       # pragma: no cover - exercised via skip
    HAVE_YAML = False


def _frontmatter(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines and lines[0].strip() == "---", f"{path}: no frontmatter"
    end = next(i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    return "\n".join(lines[1:end])


@unittest.skipUnless(HAVE_YAML, "PyYAML not installed")
class PluginFrontmatterIsYaml(unittest.TestCase):
    def _check(self, path):
        with self.subTest(path=str(path.relative_to(ROOT))):
            try:
                fm = yaml.safe_load(_frontmatter(path))
            except yaml.YAMLError as e:
                self.fail(f"{path.relative_to(ROOT)}: frontmatter is not valid YAML — {e}")
            self.assertIsInstance(fm, dict)
            self.assertIsInstance(fm.get("name"), str)
            self.assertIsInstance(fm.get("description"), str)

    def test_skills(self):
        paths = sorted((ROOT / "skills").glob("*/SKILL.md"))
        self.assertTrue(paths)
        for p in paths:
            self._check(p)

    def test_agents(self):
        paths = sorted((ROOT / "agents").glob("*.md"))
        self.assertTrue(paths)
        for p in paths:
            self._check(p)


if __name__ == "__main__":
    unittest.main()
