"""Hook dispatch test, cross-platform (roadmap P7).

Exercises the real SessionStart entry point — `hooks/run-hook.cmd session-start`
— the same command `hooks.json` registers. The wrapper is a polyglot: on POSIX
bash runs it directly; on Windows cmd.exe runs the batch portion which locates
Git bash. Either way the `session-start` script must emit valid JSON whose
additionalContext carries the wrapped skill index.

Runs on ubuntu / macOS / windows via the matrix `tests` job.
"""
import json
import os
import pathlib
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
RUN_HOOK = ROOT / "hooks" / "run-hook.cmd"


class HookDispatch(unittest.TestCase):
    def _invoke(self):
        env = dict(os.environ)
        env["CLAUDE_PLUGIN_ROOT"] = str(ROOT)
        env.pop("COPILOT_CLI", None)
        env.pop("CURSOR_PLUGIN_ROOT", None)
        if os.name == "nt":
            cmd = ["cmd", "/c", str(RUN_HOOK), "session-start"]
        else:
            cmd = ["bash", str(RUN_HOOK), "session-start"]
        return subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env)

    def test_emits_valid_session_context_json(self):
        r = self._invoke()
        self.assertEqual(r.returncode, 0, f"hook failed:\n{r.stdout}\n{r.stderr}")
        data = json.loads(r.stdout)                       # must be valid JSON
        ctx = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn("<research-superpowers>", ctx)
        # the index must actually carry skill names, not an error string
        self.assertIn("writing-research-plan", ctx)
        self.assertNotIn("Error reading session-context.md", ctx)


if __name__ == "__main__":
    unittest.main()
