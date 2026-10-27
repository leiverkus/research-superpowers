"""Every dao-paper-search-mcp call written in the skills uses real parameter names.

The skills tell the model how to call the MCP — `search_crossref(query=<doi>)`,
`resolve_author(name_string=…)`. Until 0.42.2 four skills wrote
`search_crossref(doi=…)` and `ingest-source` wrote `resolve_author(name=…)` and
`resolve_site(name=…)`: parameters the tools never had. A call written exactly as
documented failed, and the model had to guess its way back.

`tests/fixtures/dao-paper-search-mcp-tools.json` is the tools/list of the version
`docs/recommended-mcps.md` pins. Regenerate it when that pin moves.

Stdlib unittest. Run: python -m unittest tests.test_mcp_call_signatures
"""
import json
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SNAPSHOT = json.loads((ROOT / "tests" / "fixtures" / "dao-paper-search-mcp-tools.json").read_text(encoding="utf-8"))
TOOLS = SNAPSHOT["tools"]
SCANNED = ("skills", "agents", "docs", "templates", "hooks")

_CALL = re.compile(r"(?<![\w-])(" + "|".join(sorted(TOOLS, key=len, reverse=True)) + r")\(([^)]*)\)")
_KWARG = re.compile(r"\b([a-z_]+)\s*=")


def _calls():
    for d in SCANNED:
        for path in sorted((ROOT / d).rglob("*.md")):
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                for m in _CALL.finditer(line):
                    yield path.relative_to(ROOT), n, m.group(1), _KWARG.findall(m.group(2))


class McpCallSignatures(unittest.TestCase):
    def test_the_scan_finds_the_documented_calls(self):
        # Guard the guard: a regex that matches nothing passes vacuously.
        names = {name for _, _, name, _ in _calls()}
        for tool in ("search_crossref", "resolve_author", "resolve_site"):
            self.assertIn(tool, names)

    def test_every_keyword_argument_exists_on_the_tool(self):
        for path, line, name, kwargs in _calls():
            for kw in kwargs:
                with self.subTest(at=f"{path}:{line}", call=f"{name}({kw}=…)"):
                    self.assertIn(kw, TOOLS[name]["params"],
                                  f"{name} has no parameter '{kw}'; it takes {TOOLS[name]['params']}")

    def test_snapshot_matches_the_pinned_install(self):
        pinned = re.findall(r"dao-paper-search-mcp==([\d.]+)",
                            (ROOT / "docs" / "recommended-mcps.md").read_text(encoding="utf-8"))
        self.assertTrue(pinned)
        self.assertEqual(set(pinned), {SNAPSHOT["version"]},
                         "docs/recommended-mcps.md pins a different version than the signature snapshot")


if __name__ == "__main__":
    unittest.main()
