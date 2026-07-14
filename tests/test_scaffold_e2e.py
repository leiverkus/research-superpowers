"""End-to-end test of the SHIPPED template (roadmap P6, tier 1).

Materialise a project from templates/research-project-template/ exactly as a
user would scaffold it, drop in a small connected wiki, then exercise the real
user path against the copied scripts: lint → graph build → query → MCP. This
proves the shipped template (not just the in-repo example) is self-consistent
and that its scripts run from a fresh project with no repo context.

Pure stdlib + subprocess; no Claude CLI (that is P6 tier 2).
"""
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "templates" / "research-project-template"


def _page(title, typ, body, **extra):
    fm = {"title": title, "type": typ, "created": "2026-04-15",
          "updated": "2026-04-15", "status": "review", "author": "llm"}
    if typ == "source":
        fm.setdefault("bibkey", "x-2026-title")
    fm.update(extra)
    head = "\n".join(f'{k}: "{v}"' if isinstance(v, str) else f"{k}: {json.dumps(v)}"
                     for k, v in fm.items())
    return f"---\n{head}\n---\n{body}\n"


class ScaffoldEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.proj = pathlib.Path(cls._tmp.name) / "my-project"
        shutil.copytree(TEMPLATE, cls.proj)
        k = cls.proj / "knowledge"
        # A small connected cluster (no orphans, no broken links) so lint is clean.
        (k / "synthesis" / "hub.md").write_text(
            _page("Hub", "synthesis", "Connects [[src-a]] and [[ent-b]]."), encoding="utf-8")
        (k / "sources" / "src-a.md").write_text(
            _page("Source A", "source", "Discussed in [[hub]].", bibkey="a-2026-alpha"), encoding="utf-8")
        (k / "entities" / "ent-b.md").write_text(
            _page("Entity B", "entity", "Appears in [[hub]]."), encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def _run(self, *args, **kw):
        return subprocess.run([sys.executable, *args], cwd=self.proj,
                              capture_output=True, text=True, encoding="utf-8", timeout=120, **kw)

    def test_1_lint_is_clean(self):
        r = self._run("scripts/lint-wiki.py")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("Total: 0 issue(s) found", r.stdout)

    def test_2_graph_build_produces_json(self):
        r = self._run("scripts/wiki-to-graph.py", "--no-html")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        graph = json.loads((self.proj / "knowledge" / "_meta" / "graph" / "graph.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(graph["stats"]["nodes"], 3)
        self.assertGreaterEqual(graph["stats"]["edges"], 1)
        self.assertTrue(graph["communities"])

    def test_3_query_runs(self):
        r = self._run("scripts/wiki-to-graph.py", "neighbors", "hub", "--json")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        out = json.loads(r.stdout)
        self.assertTrue(out["neighbors"])

    def test_4_mcp_handshake_and_stats(self):
        reqs = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                        "clientInfo": {"name": "e2e", "version": "1"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "graph_stats", "arguments": {}}},
        ]
        inp = "".join(json.dumps(r) + "\n" for r in reqs)
        r = subprocess.run([sys.executable, "scripts/graph_mcp.py", "knowledge"],
                           cwd=self.proj, input=inp, capture_output=True, text=True, encoding="utf-8", timeout=120)
        by_id = {m.get("id"): m for m in (json.loads(l) for l in r.stdout.splitlines() if l.strip())}
        self.assertEqual(by_id[1]["result"]["serverInfo"]["name"], "wiki-graph")
        self.assertIn("graph_stats", [t["name"] for t in by_id[2]["result"]["tools"]])
        self.assertFalse(by_id[3]["result"]["isError"])


if __name__ == "__main__":
    unittest.main()
