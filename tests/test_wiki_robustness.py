"""Negative & integration tests for the wiki graph tooling (roadmap P4).

Adversarial inputs the happy-path suite doesn't cover: empty / degenerate
wikis, malformed wikilinks, corrupt frontmatter, MCP error paths, a larger
generated wiki (scale + determinism), and path handling. Stdlib unittest —
no pytest.

Run: python -m unittest discover -s tests
"""
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "templates" / "research-project-template" / "scripts"
MCP = SCRIPTS / "graph_mcp.py"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


wg = _load("wiki_to_graph", SCRIPTS / "wiki-to-graph.py")


def _page(title="P", typ="source", body="", **extra):
    fm = {"title": title, "type": typ, "created": "2026-04-15",
          "updated": "2026-04-15", "status": "review", "author": "llm"}
    if typ == "source":
        fm.setdefault("bibkey", "x-2026")
    fm.update(extra)
    lines = ["---"]
    for k, v in fm.items():
        lines.append(f"{k}: {json.dumps(v)}" if not isinstance(v, str) else f'{k}: "{v}"')
    lines.append("---")
    return "\n".join(lines) + "\n" + body + "\n"


def _write(d, rel, text):
    p = pathlib.Path(d) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _graph(d):
    pages = wg.collect_pages(pathlib.Path(d))
    nodes = wg.build_nodes(pages)
    edges, stats = wg.build_edges(pages)
    return pages, nodes, edges, stats


class EmptyAndDegenerate(unittest.TestCase):
    def test_empty_wiki_builds_cleanly(self):
        with tempfile.TemporaryDirectory() as d:
            pages, nodes, edges, stats = _graph(d)
            self.assertEqual(pages, {})
            self.assertEqual(nodes, [])
            self.assertEqual(edges, [])
            # derived views must not crash on the empty graph
            self.assertEqual(wg.compute_god_nodes(nodes, edges, 10), [])
            self.assertEqual(wg.compute_bridges(nodes, edges), [])
            node_comm, comms = wg.compute_communities(nodes, edges)
            self.assertEqual((node_comm, comms), ({}, []))

    def test_single_page_no_links(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "a.md", _page("A"))
            _, nodes, edges, _ = _graph(d)
            self.assertEqual(len(nodes), 1)
            self.assertEqual(edges, [])
            self.assertEqual(wg.compute_god_nodes(nodes, edges, 10), [])
            node_comm, comms = wg.compute_communities(nodes, edges)
            # one isolated node: no edges → its own (singleton) community
            self.assertIn(nodes[0]["id"], node_comm)

    def test_all_orphan_pages(self):
        with tempfile.TemporaryDirectory() as d:
            for n in "abc":
                _write(d, f"{n}.md", _page(n.upper()))
            _, nodes, edges, _ = _graph(d)
            self.assertEqual(len(nodes), 3)
            self.assertEqual(edges, [])


class MalformedWikilinks(unittest.TestCase):
    def test_empty_bracket_link_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "a.md", _page("A", body="see [[ ]] and [[]]"))
            _write(d, "b.md", _page("B"))
            _, _, edges, _ = _graph(d)
            self.assertEqual(edges, [])

    def test_alias_and_heading_resolve_to_slug(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "a.md", _page("A", body="[[b|the B page]] and [[b#section]]"))
            _write(d, "b.md", _page("B"))
            _, _, edges, _ = _graph(d)
            wl = [e for e in edges if e["relation_type"] == "wikilink"]
            self.assertTrue(any(e["source"] == "a" and e["target"] == "b" for e in wl))

    def test_dangling_link_counted_not_edged(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "a.md", _page("A", body="[[does-not-exist]]"))
            _, _, edges, stats = _graph(d)
            self.assertEqual(edges, [])
            self.assertGreaterEqual(stats["dangling"], 1)

    def test_self_link_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "a.md", _page("A", body="[[a]] referring to itself"))
            _, _, edges, _ = _graph(d)
            self.assertEqual(edges, [])

    def test_duplicate_links_increment_weight(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "a.md", _page("A", body="[[b]] and again [[b]] and [[b]]"))
            _write(d, "b.md", _page("B"))
            _, _, edges, _ = _graph(d)
            wl = [e for e in edges if e["source"] == "a" and e["target"] == "b"]
            self.assertEqual(len(wl), 1)
            self.assertEqual(wl[0]["weight"], 3)


class CorruptFrontmatter(unittest.TestCase):
    def test_unterminated_frontmatter_no_crash(self):
        fm, body = wg.split_frontmatter("---\ntitle: A\nstatus: review\n(no close)\nbody")
        self.assertEqual(fm, {})            # no closing --- → treated as no frontmatter
        self.assertIn("body", body)

    def test_non_dict_root_yields_empty(self):
        fm, _ = wg.split_frontmatter("---\n- one\n- two\n---\nbody")
        self.assertEqual(fm, {})            # a YAML list root is not a mapping

    def test_tab_indented_yaml_no_crash(self):
        fm, _ = wg.split_frontmatter("---\ntitle: A\n\tbad: 1\n---\nbody")
        self.assertIsInstance(fm, dict)     # YAMLError is caught → {}

    def test_bom_prefixed_no_crash(self):
        fm, body = wg.split_frontmatter("﻿---\ntitle: A\n---\nbody")
        self.assertIsInstance(fm, dict)
        self.assertIn("body", body)

    def test_page_with_corrupt_fm_still_becomes_a_node(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "a.md", "---\n- not\n- a dict\n---\n[[b]]\n")
            _write(d, "b.md", _page("B"))
            _, nodes, edges, _ = _graph(d)
            ids = {n["id"] for n in nodes}
            self.assertEqual(ids, {"a", "b"})
            # corrupt fm → type unknown, but wikilink in body still resolves
            self.assertTrue(any(e["source"] == "a" and e["target"] == "b" for e in edges))


class GraphMCPErrors(unittest.TestCase):
    def _mcp(self, reqs, wiki):
        inp = "".join(json.dumps(r) + "\n" for r in reqs)
        out = subprocess.run([sys.executable, str(MCP), str(wiki)],
                             input=inp, capture_output=True, text=True, timeout=60).stdout
        return {m.get("id"): m for m in (json.loads(l) for l in out.splitlines() if l.strip())}

    def test_unknown_tool_is_error(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "a.md", _page("A"))
            by_id = self._mcp([{"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                "params": {"name": "no_such_tool", "arguments": {}}}], d)
            self.assertTrue(by_id[1]["result"]["isError"])
            self.assertIn("unknown tool", by_id[1]["result"]["content"][0]["text"])

    def test_missing_required_argument_is_error(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "a.md", _page("A"))
            by_id = self._mcp([{"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                "params": {"name": "graph_neighbors", "arguments": {}}}], d)
            self.assertTrue(by_id[1]["result"]["isError"])
            self.assertIn("missing required argument", by_id[1]["result"]["content"][0]["text"])

    def test_malformed_frame_is_skipped_not_fatal(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "a.md", _page("A"))
            # a junk line between two valid requests: server must skip it and answer the rest
            inp = "this is not json\n" + json.dumps(
                {"jsonrpc": "2.0", "id": 7, "method": "tools/list"}) + "\n"
            out = subprocess.run([sys.executable, str(MCP), str(d)],
                                 input=inp, capture_output=True, text=True, timeout=60).stdout
            by_id = {m.get("id"): m for m in (json.loads(l) for l in out.splitlines() if l.strip())}
            self.assertIn(7, by_id)
            self.assertTrue(by_id[7]["result"]["tools"])

    def test_unknown_method_returns_jsonrpc_error(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "a.md", _page("A"))
            by_id = self._mcp([{"jsonrpc": "2.0", "id": 3, "method": "no/such/method"}], d)
            self.assertIn("error", by_id[3])
            self.assertEqual(by_id[3]["error"]["code"], -32601)

    def test_query_for_nonexistent_node_is_error(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "a.md", _page("A"))
            by_id = self._mcp([{"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                                "params": {"name": "graph_neighbors",
                                           "arguments": {"node": "ghost"}}}], d)
            self.assertTrue(by_id[4]["result"]["isError"])

    def test_stats_call_succeeds_on_valid_wiki(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "a.md", _page("A", body="[[b]]"))
            _write(d, "b.md", _page("B"))
            by_id = self._mcp([{"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                                "params": {"name": "graph_stats", "arguments": {}}}], d)
            self.assertFalse(by_id[5]["result"]["isError"])


class ScaleAndDeterminism(unittest.TestCase):
    def test_larger_wiki_builds_and_is_deterministic(self):
        import time
        with tempfile.TemporaryDirectory() as d:
            n = 1000                                       # roadmap P4 lower bound
            for i in range(n):
                # chain + cross-links at several strides → real community structure
                links = f"[[p{(i + 1) % n}]] [[p{(i + 5) % n}]] [[p{(i + 37) % n}]]"
                _write(d, f"p{i}.md", _page(f"P{i}", body=links))
            t0 = time.time()
            _, nodes, edges, _ = _graph(d)
            node_comm, comms = wg.compute_communities(nodes, edges)
            gn = wg.compute_god_nodes(nodes, edges, 10)
            elapsed = time.time() - t0
            self.assertEqual(len(nodes), n)
            self.assertEqual(len(edges), 3 * n)            # all links resolve (no dangling)
            self.assertTrue(comms)
            self.assertTrue(gn)
            # full build + community detection on 1k pages stays well under budget
            # (≈0.5s locally; generous ceiling absorbs slow CI runners)
            self.assertLess(elapsed, 30.0, f"1k-page build took {elapsed:.1f}s")
            r1 = wg.compute_communities(nodes, edges)
            r2 = wg.compute_communities(nodes, edges)
            self.assertEqual(r1, r2)                        # deterministic partition


class PathHandling(unittest.TestCase):
    def test_slug_is_stem_regardless_of_subdir(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "entities/a.md", _page("A", typ="entity", body="[[b]]"))
            _write(d, "sources/b.md", _page("B"))
            pages, _, edges, _ = _graph(d)
            self.assertIn("a", pages)
            self.assertIn("b", pages)                      # nested dirs → slug by stem
            self.assertTrue(any(e["source"] == "a" and e["target"] == "b" for e in edges))


if __name__ == "__main__":
    unittest.main()
