"""The macOS setup (setup/macos/) stays in step with what the plugin uses.

Three things in it are copies of facts that live elsewhere, and each would go
stale silently:

  * the dao-paper-search-mcp version the script configures — the pin lives in
    docs/recommended-mcps.md;
  * the font casks in the Brewfile — the fonts are set by the templates
    (mainfont/sansfont/monofont, and \\babelfont for Hebrew), and a missing one
    makes Quarto fall back to a substitute without failing;
  * the Brewfile's first line — the script recognises its own Brewfile by it
    when run through `curl | bash`.

Stdlib unittest. Run: python -m unittest tests.test_macos_setup
"""
import pathlib
import re
import shutil
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SETUP = ROOT / "setup" / "macos"
SCRIPT = SETUP / "setup-macos.sh"
BREWFILE = SETUP / "Brewfile"
TEMPLATE_OUTPUT = ROOT / "templates" / "research-project-template" / "output"


def _brewfile_casks() -> set[str]:
    return set(re.findall(r'^cask "([^"]+)"', BREWFILE.read_text(encoding="utf-8"), re.M))


def _template_fonts() -> set[str]:
    fonts = set()
    for p in TEMPLATE_OUTPUT.rglob("*"):
        if p.suffix not in (".qmd", ".yml", ".tex"):
            continue
        text = p.read_text(encoding="utf-8")
        fonts |= set(re.findall(r'^\s*(?:main|sans|mono)font:\s*"([^"]+)"', text, re.M))
        fonts |= set(re.findall(r"\\babelfont(?:\[[^\]]*\])?\{[a-z]+\}\{([^}]+)\}", text))
    return fonts


class MacosSetup(unittest.TestCase):
    def test_mcp_version_matches_the_documented_pin(self):
        script = re.search(r'^DAO_MCP_VERSION="([\d.]+)"', SCRIPT.read_text(encoding="utf-8"), re.M)
        docs = set(re.findall(r"dao-paper-search-mcp==([\d.]+)",
                              (ROOT / "docs" / "recommended-mcps.md").read_text(encoding="utf-8")))
        self.assertIsNotNone(script)
        self.assertEqual({script.group(1)}, docs)

    def test_every_template_font_has_a_cask(self):
        fonts = _template_fonts()
        self.assertTrue(fonts, "no fonts found in the templates — the scan is broken")
        casks = _brewfile_casks()
        for font in sorted(fonts):
            cask = "font-" + font.lower().replace(" ", "-")
            with self.subTest(font=font):
                self.assertIn(cask, casks, f"template font '{font}' has no '{cask}' in the Brewfile")

    def test_brewfile_header_is_what_the_script_looks_for(self):
        first = BREWFILE.read_text(encoding="utf-8").splitlines()[0]
        self.assertTrue(first.startswith("# Brewfile for research-superpowers"))
        self.assertIn("'^# Brewfile for research-superpowers'", SCRIPT.read_text(encoding="utf-8"))

    @unittest.skipUnless(shutil.which("bash"), "bash not available")
    def test_script_parses(self):
        r = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
