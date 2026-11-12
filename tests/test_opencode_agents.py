"""opencode/agents/ is generated from agents/ and usable as OpenCode subagents.

OpenCode registers an agent without `mode:` as a primary agent (the `subagent`
tool cannot launch it) and ignores Claude Code's `disallowedTools`. The
generator fixes both; these tests pin that, plus the sync CI relies on.

Run: python -m unittest discover -s tests
"""
import importlib.util
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "build-opencode-agents.py"

spec = importlib.util.spec_from_file_location("build_opencode_agents", SCRIPT)
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

try:
    import yaml
    HAVE_YAML = True
except Exception:  # pragma: no cover
    HAVE_YAML = False


def frontmatter(text):
    lines = text.splitlines()
    end = next(i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    return "\n".join(lines[1:end])


class OpencodeAgents(unittest.TestCase):
    def test_in_sync(self):
        r = subprocess.run([sys.executable, str(SCRIPT), "--check"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_one_generated_agent_per_source(self):
        src = sorted(p.name for p in (ROOT / "agents").glob("*.md"))
        dst = sorted(p.name for p in (ROOT / "opencode" / "agents").glob("*.md"))
        self.assertEqual(src, dst)

    @unittest.skipUnless(HAVE_YAML, "PyYAML not installed")
    def test_subagent_mode_and_permissions(self):
        for src in sorted((ROOT / "agents").glob("*.md")):
            with self.subTest(agent=src.name):
                fm_src, _ = build.split(src.read_text(encoding="utf-8"))
                gen = (ROOT / "opencode" / "agents" / src.name).read_text(encoding="utf-8")
                fm = yaml.safe_load(frontmatter(gen))
                self.assertEqual(fm["mode"], "subagent")
                self.assertEqual(fm["description"], fm_src["description"])
                # Only OpenCode fields — Claude keys would land in the request body.
                self.assertLessEqual(set(fm), {"description", "mode", "permission"})
                denied = {t.strip() for t in fm_src.get("disallowedTools", "").split(",") if t.strip()}
                perm = fm.get("permission", {})
                if "Agent" in denied:
                    self.assertEqual(perm.get("subagent"), "deny")
                if denied & {"Write", "Edit", "NotebookEdit"}:
                    self.assertEqual(perm.get("edit"), "deny")
                self.assertTrue(all(v == "deny" for v in perm.values()))

    def test_body_is_carried_over(self):
        for src in sorted((ROOT / "agents").glob("*.md")):
            with self.subTest(agent=src.name):
                _, body = build.split(src.read_text(encoding="utf-8"))
                gen = (ROOT / "opencode" / "agents" / src.name).read_text(encoding="utf-8")
                self.assertTrue(gen.endswith(body))

    def test_unknown_disallowed_tool_is_an_error(self):
        tmp = ROOT / "tests" / "_tmp_agent.md"
        try:
            tmp.write_text("---\nname: x\ndescription: y\ndisallowedTools: Agent, Teleport\n---\nbody\n",
                           encoding="utf-8")
            with self.assertRaises(ValueError):
                build.render(tmp)
        finally:
            tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
