"""Gate-semantics tests for scripts/lint-plugin.py.

Structural contract violations (missing `implements:`, broken agent↔skill
symmetry) FAIL the gate (exit 1); the checklist-depth heuristic is advisory
(reported, exit 0). Stdlib unittest — no pytest.

Run: python -m unittest discover -s tests
"""
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
LINT = ROOT / "scripts" / "lint-plugin.py"


def _skill(root, name, agents=()):
    p = pathlib.Path(root) / "skills" / name / "SKILL.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    fm = ["---", f"name: {name}", "description: x"]
    if agents:
        fm.append("agents:")
        fm += [f"  - {a}" for a in agents]
    fm.append("---")
    p.write_text("\n".join(fm) + "\nbody\n", encoding="utf-8")


def _agent(root, name, implements=None, body="body"):
    p = pathlib.Path(root) / "agents" / f"{name}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    fm = ["---", f"name: {name}", "description: x"]
    if implements is not None:
        fm.append(f"implements: {implements}")
    fm.append("---")
    p.write_text("\n".join(fm) + "\n" + body + "\n", encoding="utf-8")


def _run(root):
    r = subprocess.run([sys.executable, str(LINT), "--root", str(root)],
                       capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


class GateSemantics(unittest.TestCase):
    def test_clean_contract_passes(self):
        with tempfile.TemporaryDirectory() as d:
            _skill(d, "s", agents=["a"])
            _agent(d, "a", implements="s")
            rc, out = _run(d)
            self.assertEqual(rc, 0, out)

    def test_missing_implements_is_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            _skill(d, "s")
            _agent(d, "a", implements=None)      # no implements: → structural violation
            rc, out = _run(d)
            self.assertEqual(rc, 1, out)
            self.assertIn("[ERR]", out)

    def test_broken_symmetry_is_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            _skill(d, "s")                        # skill does NOT list agent a
            _agent(d, "a", implements="s")        # but a implements s → asymmetry
            rc, out = _run(d)
            self.assertEqual(rc, 1, out)

    def test_deep_checklist_is_advisory_not_fatal(self):
        with tempfile.TemporaryDirectory() as d:
            _skill(d, "s", agents=["a"])
            _agent(d, "a", implements="s", body="1. one\n2. two\n3. three\n4. four")
            rc, out = _run(d)
            self.assertEqual(rc, 0, out)          # heuristic warns but does not fail
            self.assertIn("warning", out.lower())


if __name__ == "__main__":
    unittest.main()
