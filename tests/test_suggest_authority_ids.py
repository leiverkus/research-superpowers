"""Tests for the network-free logic of scripts/suggest-authority-ids.py.

The Wikidata calls are not exercised here — CI has no business hitting a live
API, and the tool writes nothing regardless. What must stay correct is which
pages it flags as untagged (a false negative hides a real gap; a false positive
sends you looking up an id a page already has) and how it turns a bilingual
title into search terms.

Stdlib unittest. Run: python -m unittest discover -s tests
"""
import email.message
import importlib.util
import io
import json
import pathlib
import tempfile
import unittest
import urllib.error
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "suggest-authority-ids.py"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sa = _load("suggest_authority_ids", SCRIPT)


def _page(d, folder, slug, fm_lines):
    p = pathlib.Path(d) / "knowledge" / folder
    p.mkdir(parents=True, exist_ok=True)
    (p / f"{slug}.md").write_text("---\n" + "\n".join(fm_lines) + "\n---\n", encoding="utf-8")


class Untagged(unittest.TestCase):
    def test_flags_an_entity_and_concept_with_no_join_key(self):
        with tempfile.TemporaryDirectory() as d:
            _page(d, "entities", "gaia-x", ["title: Gaia-X", "type: entity"])
            _page(d, "concepts", "interoperability", ["title: Interop", "type: concept"])
            slugs = {slug for _, slug, _ in sa.untagged_pages(pathlib.Path(d), None)}
            self.assertEqual(slugs, {"gaia-x", "interoperability"})

    def test_a_concept_with_wikidata_qid_is_not_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            _page(d, "concepts", "tagged", ["title: T", "type: concept", "wikidata_qid: Q2539"])
            self.assertEqual(sa.untagged_pages(pathlib.Path(d), None), [])

    def test_a_concept_with_only_getty_aat_id_is_not_flagged(self):
        # getty_aat_id still counts as coverage, even though it is now the optional one.
        with tempfile.TemporaryDirectory() as d:
            _page(d, "concepts", "preservation",
                  ["title: P", "type: concept", 'getty_aat_id: "300379431"'])
            self.assertEqual(sa.untagged_pages(pathlib.Path(d), None), [])

    def test_an_entity_with_gnd_id_is_not_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            _page(d, "entities", "turing", ["title: Turing", "type: entity", "gnd_id: 118802976"])
            self.assertEqual(sa.untagged_pages(pathlib.Path(d), None), [])

    def test_example_and_meta_pages_are_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            _page(d, "entities", "_example-tel-megiddo", ["title: Ex", "type: entity"])
            _page(d, "_meta", "index", ["title: Index", "type: entity"])
            self.assertEqual(sa.untagged_pages(pathlib.Path(d), None), [])

    def test_source_and_synthesis_pages_are_ignored(self):
        # only entity/concept carry vocabulary/authority join keys.
        with tempfile.TemporaryDirectory() as d:
            _page(d, "sources", "smith-2016", ["title: S", "type: source", "bibkey: smith-2016-x"])
            _page(d, "synthesis", "debate", ["title: D", "type: synthesis"])
            self.assertEqual(sa.untagged_pages(pathlib.Path(d), None), [])

    def test_type_filter_restricts_to_concepts(self):
        with tempfile.TemporaryDirectory() as d:
            _page(d, "entities", "gaia-x", ["title: Gaia-X", "type: entity"])
            _page(d, "concepts", "interop", ["title: I", "type: concept"])
            got = sa.untagged_pages(pathlib.Path(d), "concept")
            self.assertEqual([(t, s) for t, s, _ in got], [("concept", "interop")])


class SearchTerms(unittest.TestCase):
    def test_bilingual_title_prefers_the_english_parenthetical(self):
        self.assertEqual(sa.search_terms("Datensouveränität (Data Sovereignty)"),
                         ["Data Sovereignty", "Datensouveränität"])

    def test_a_plain_title_yields_just_itself(self):
        self.assertEqual(sa.search_terms("Alan Turing"), ["Alan Turing"])

    def test_quotes_are_stripped(self):
        self.assertEqual(sa.search_terms('"Gaia-X"'), ["Gaia-X"])

    def test_identical_paren_and_stripped_title_dedupe(self):
        # "X (X)" must not search the same term twice.
        self.assertEqual(sa.search_terms("FORCE11 (FORCE11)"), ["FORCE11"])


class RetryWithBackoff(unittest.TestCase):
    """`_get` must survive Wikidata's 429 throttling. A dropped query is worse than
    a slow one: it is silently miscounted as 'no candidate', so the whole point of
    the tool — surfacing candidates to verify — fails quietly on any large batch.
    Network is mocked; time.sleep is patched so the backoff costs no wall-clock."""

    def _err(self, code, retry_after=None):
        hdrs = email.message.Message()
        if retry_after is not None:
            hdrs["Retry-After"] = retry_after
        return urllib.error.HTTPError("http://x", code, "err", hdrs, None)

    def _ok(self, payload):
        return io.BytesIO(json.dumps(payload).encode())     # a context-managed, json.load-able body

    def _run(self, sequence, **kw):
        seq = list(sequence)
        def fake_urlopen(req, timeout=30):
            item = seq.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        with mock.patch.object(sa.urllib.request, "urlopen", fake_urlopen), \
             mock.patch.object(sa.time, "sleep") as slept:
            result = sa._get("http://x", **kw)
        return result, slept

    def test_retries_a_429_then_succeeds(self):
        result, slept = self._run([self._err(429), self._err(429), self._ok({"search": [{"id": "Q1"}]})])
        self.assertEqual(result, {"search": [{"id": "Q1"}]})
        self.assertEqual(slept.call_count, 2)               # two backoffs before the win

    def test_exponential_backoff_growth(self):
        _, slept = self._run([self._err(429), self._err(429), self._err(429), self._ok({"search": []})],
                             base=1.0)
        self.assertEqual([c.args[0] for c in slept.call_args_list], [1.0, 2.0, 4.0])

    def test_gives_up_after_the_retry_budget_and_raises(self):
        def fake(req, timeout=30):
            raise self._err(429)
        with mock.patch.object(sa.urllib.request, "urlopen", fake), \
             mock.patch.object(sa.time, "sleep"):
            with self.assertRaises(urllib.error.HTTPError):
                sa._get("http://x", retries=3)

    def test_a_non_retriable_status_raises_at_once(self):
        calls = []
        def fake(req, timeout=30):
            calls.append(1)
            raise self._err(404)
        with mock.patch.object(sa.urllib.request, "urlopen", fake), \
             mock.patch.object(sa.time, "sleep") as slept:
            with self.assertRaises(urllib.error.HTTPError):
                sa._get("http://x")
        self.assertEqual(len(calls), 1)                     # no retry on a real 404
        slept.assert_not_called()

    def test_retry_after_header_is_honoured_over_the_backoff(self):
        _, slept = self._run([self._err(429, retry_after="7"), self._ok({"search": []})])
        slept.assert_called_once_with(7.0)

    def test_an_absurd_retry_after_is_capped(self):
        _, slept = self._run([self._err(429, retry_after="99999"), self._ok({"search": []})])
        slept.assert_called_once_with(60.0)


if __name__ == "__main__":
    unittest.main()
