"""Schema conformance cross-check: hand-rolled validator vs. jsonschema (P5).

The runtime validator in lint-wiki.py is a deliberate stdlib subset of JSON
Schema Draft-07 (so scaffolded projects need no `pip install`). These tests pin
it in agreement with the real `jsonschema` engine on every rule it claims to
implement, and validate the shipped wiki pages with the authoritative engine —
so a future schema feature the subset can't express, or a divergence bug, is
caught in CI.

`jsonschema` is a CI/dev-only dependency (see requirements-dev.txt); these tests
skip cleanly when it isn't installed.
"""
import importlib.util
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "templates" / "research-project-template" / "scripts"
SCHEMA = json.loads((ROOT / "schema" / "knowledge-frontmatter.schema.json").read_text(encoding="utf-8"))

try:
    import jsonschema
    from jsonschema import Draft7Validator
    _VALIDATOR = Draft7Validator(SCHEMA, format_checker=Draft7Validator.FORMAT_CHECKER)
    HAVE_JSONSCHEMA = True
except Exception:                       # pragma: no cover - exercised via skip
    HAVE_JSONSCHEMA = False


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


lw = _load("lint_wiki", SCRIPTS / "lint-wiki.py")

VALID = {
    "title": "A page", "type": "source",
    "created": "2026-04-15", "updated": "2026-04-15",
    "status": "review", "author": "llm", "bibkey": "x-2026",
}


def _variant(**changes):
    d = dict(VALID)
    for k, v in changes.items():
        if v is _DELETE:
            d.pop(k, None)
        else:
            d[k] = v
    return d


_DELETE = object()

# (label, frontmatter, is_valid) — each invalid case violates exactly one rule
# that the stdlib subset *does* implement, so both validators must agree.
CASES = [
    ("valid", VALID, True),
    ("missing-required", _variant(status=_DELETE), False),
    ("bad-enum", _variant(type="bogus"), False),
    ("bad-date", _variant(created="2026-99-99"), False),
    ("bad-pattern", _variant(type="entity", bibkey=_DELETE, wikidata_qid="NOPE"), False),
    ("wrong-type", _variant(title=42), False),
    ("source-missing-bibkey", _variant(bibkey=_DELETE), False),
    ("array-item-type", _variant(tags=[1, 2]), False),
    # nested relations[] object rules — the blind spot before v0.14.0
    ("relations-valid",
     _variant(relations=[{"target": "x", "type": "cites", "confidence": "extracted", "because": "q"}]), True),
    ("relations-type-not-string",
     _variant(relations=[{"target": "x", "type": 42, "confidence": "extracted"}]), False),
    ("relations-because-not-string",
     _variant(relations=[{"target": "x", "type": "cites", "confidence": "extracted", "because": 42}]), False),
    ("relations-bad-confidence-enum",
     _variant(relations=[{"target": "x", "type": "cites", "confidence": "maybe"}]), False),
    ("relations-missing-required",
     _variant(relations=[{"target": "x", "type": "cites"}]), False),
    ("relations-unknown-key",
     _variant(relations=[{"target": "x", "type": "cites", "confidence": "extracted", "bogus": 1}]), False),
]


@unittest.skipUnless(HAVE_JSONSCHEMA, "jsonschema not installed (CI/dev only)")
class ValidatorsAgree(unittest.TestCase):
    def test_each_case_agrees_with_jsonschema(self):
        for label, fm, expected_valid in CASES:
            with self.subTest(case=label):
                stdlib_valid = not lw.validate_frontmatter(fm, SCHEMA, pathlib.Path(label))
                js_valid = _VALIDATOR.is_valid(fm)
                self.assertEqual(stdlib_valid, expected_valid,
                                 f"stdlib disagrees on {label}")
                self.assertEqual(js_valid, expected_valid,
                                 f"jsonschema disagrees on {label}")


@unittest.skipUnless(HAVE_JSONSCHEMA, "jsonschema not installed (CI/dev only)")
class ShippedPagesConform(unittest.TestCase):
    def _pages(self):
        out = []
        ex = ROOT / "examples" / "example-project" / "knowledge"
        out += [p for p in ex.rglob("*.md") if "_meta" not in p.parts]
        tpl = ROOT / "templates" / "research-project-template" / "knowledge"
        out += [p for p in tpl.rglob("_example-*.md")]
        return out

    def test_all_shipped_pages_validate_under_jsonschema(self):
        pages = self._pages()
        self.assertTrue(pages, "no wiki pages found to validate")
        for page in pages:
            with self.subTest(page=str(page.relative_to(ROOT))):
                fm = lw.parse_frontmatter(page)
                self.assertIsInstance(fm, dict)
                errors = sorted(_VALIDATOR.iter_errors(fm), key=lambda e: e.path)
                self.assertEqual(errors, [],
                                 f"{page.name}: " + "; ".join(e.message for e in errors))


if __name__ == "__main__":
    unittest.main()
