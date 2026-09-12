"""Tests for `confidence: asserted` (schema + lint-wiki.py reporting).

`asserted` marks an edge the project puts there on its OWN authority — a
position taken while writing, a controversy the work decides — and it exists
because the three original values all say something false about such an edge:
`extracted` claims a source, `inferred` blames the model, `ambiguous` calls the
most deliberate edge in the wiki unclear.

Two properties keep it honest and are pinned here:

  * it must never be folded into the inference-rate. That metric answers "how
    much did the model add?", and an editorial decision is the opposite of model
    noise; summing them would make both numbers meaningless.
  * an `asserted` edge without a `because` must be flagged. Without that, the
    value is simply the cheapest way to avoid sourcing anything.

Stdlib unittest. Run: python -m unittest discover -s tests
"""
import importlib.util
import json
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "templates" / "research-project-template"
SCHEMA = TEMPLATE / "schema" / "knowledge-frontmatter.schema.json"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


lw = _load("lint_wiki_asserted", TEMPLATE / "scripts" / "lint-wiki.py")


def _page(dirpath: pathlib.Path, slug: str, relations: list[dict]) -> pathlib.Path:
    rel_yaml = ""
    for r in relations:
        rel_yaml += f"  - target: {r['target']}\n    type: {r['type']}\n"
        rel_yaml += f"    confidence: {r['confidence']}\n"
        if r.get("because"):
            rel_yaml += f"    because: \"{r['because']}\"\n"
    p = dirpath / f"{slug}.md"
    p.write_text(
        "---\n"
        f'title: "{slug}"\n'
        "type: synthesis\n"
        "created: 2026-01-01\n"
        "updated: 2026-01-01\n"
        "status: draft\n"
        "author: llm\n"
        "relations:\n" + rel_yaml +
        "---\n\n# " + slug + "\n",
        encoding="utf-8")
    return p


class SchemaAcceptsIt(unittest.TestCase):
    def test_enum_carries_all_four_values(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        enum = schema["properties"]["relations"]["items"]["properties"]["confidence"]["enum"]
        self.assertEqual(enum, ["extracted", "inferred", "ambiguous", "asserted"])

    def test_description_says_what_it_is_for(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        desc = schema["properties"]["relations"]["items"]["properties"]["confidence"]["description"]
        self.assertIn("asserted", desc)
        self.assertIn("because", desc, "the description must name the `because` requirement")


class LinterAcceptsIt(unittest.TestCase):
    def test_asserted_is_a_valid_confidence(self):
        self.assertIn("asserted", lw.RELATION_CONFIDENCE)

    def test_page_with_asserted_relation_raises_no_relation_issue(self):
        with tempfile.TemporaryDirectory() as td:
            d = pathlib.Path(td)
            p = _page(d, "decisions", [{"target": "tour-7", "type": "extends",
                                        "confidence": "asserted",
                                        "because": "the band follows position B"}])
            issues = lw.lint_relations({"decisions": p, "tour-7": p})
            self.assertEqual([i for i in issues if "confidence" in i], [])


class ReportedBesideNotInside(unittest.TestCase):
    def _rate(self, relations):
        with tempfile.TemporaryDirectory() as td:
            d = pathlib.Path(td)
            p = _page(d, "s", relations)
            return "\n".join(lw.report_inference_rate({"s": p}))

    def test_asserted_does_not_count_as_inferred(self):
        out = self._rate([{"target": "x", "type": "extends", "confidence": "asserted",
                           "because": "a decision"}])
        self.assertIn("inferred/ambiguous: 0", out,
                      "an asserted edge must not inflate the inference-rate")
        self.assertIn("asserted: 1", out)

    def test_asserted_is_absent_from_the_line_when_unused(self):
        out = self._rate([{"target": "x", "type": "cites", "confidence": "extracted",
                           "because": "p. 12"}])
        self.assertNotIn("asserted", out,
                         "a wiki that never asserts should not carry the column")

    def test_asserted_without_because_is_flagged(self):
        out = self._rate([{"target": "x", "type": "extends", "confidence": "asserted"}])
        self.assertIn("WARNING", out)
        self.assertIn("no `because`", out)

    def test_asserted_with_because_is_not_flagged(self):
        out = self._rate([{"target": "x", "type": "extends", "confidence": "asserted",
                           "because": "the band decides the harbour question against Stern"}])
        self.assertNotIn("WARNING", out)


if __name__ == "__main__":
    unittest.main()
