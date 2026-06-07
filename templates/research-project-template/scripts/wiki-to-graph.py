#!/usr/bin/env python3
"""
Wiki → graph: turn the Markdown knowledge wiki into a queryable knowledge graph.

The wiki is already a graph implicitly: source/entity/concept/synthesis pages
linked by wikilinks. This script makes that graph explicit and serialisable, so
it can be opened in Gephi/yEd (GraphML) or queried programmatically (JSON).

What it produces (under --out-dir, default ``knowledge/_meta/graph/``):
  * ``graph.json``    — nodes, edges, and two derived lists (god_nodes, bridges)
  * ``graph.graphml`` — the same graph for Gephi / yEd / Cytoscape

Nodes
  One node per wiki page. ``type`` is taken verbatim from the page frontmatter
  (entity | concept | source | synthesis). An optional ``subtype`` is derived
  only from unambiguous signals (gnd_id → person, idai_gazetteer_id → place).
  Meta pages (``_meta/``) and template examples (``_example-`` / ``_beispiel-``)
  are excluded.

Edges
  * from wikilinks ``[[target]]`` in the body and in the ``sources:`` frontmatter
    list — relation_type ``wikilink``, default confidence ``extracted``;
  * from the optional structured ``relations:`` frontmatter block — relation_type
    and confidence taken from each entry.
  Edges whose target does not resolve to a node are not emitted (the linter
  reports those as broken wikilinks); they are counted under ``stats.dangling``.

Derived views
  * ``god_nodes`` — the most connected nodes, by total degree (``--top-n``).
  * ``bridges``   — entities that join ≥2 otherwise-unconnected source clusters.

Pure standard library + PyYAML. No LLM calls, no network access.

Usage:
    python scripts/wiki-to-graph.py
    python scripts/wiki-to-graph.py --knowledge-dir knowledge --out-dir knowledge/_meta/graph --top-n 15
"""

import argparse
import json
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

import yaml

DEFAULT_WIKI_DIR = Path("knowledge")
DEFAULT_OUT_DIR = Path("knowledge/_meta/graph")
DEFAULT_TOP_N = 15

EXAMPLE_PREFIXES = ("_example-", "_beispiel-")
CONFIDENCE_VALUES = ("extracted", "inferred", "ambiguous")
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
def split_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter dict, body) for a wiki page. Empty dict if none."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    try:
        fm = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        fm = {}
    body = text[match.end():]
    return (fm if isinstance(fm, dict) else {}), body


def normalise_target(raw: str) -> str:
    """Reduce a wikilink/relation target to a bare page slug.

    Handles ``[[slug]]``, ``[[slug|alias]]``, ``[[slug#heading]]`` and bare
    ``slug`` forms.
    """
    target = raw.strip()
    if target.startswith("[[") and target.endswith("]]"):
        target = target[2:-2]
    target = target.split("|", 1)[0]
    target = target.split("#", 1)[0]
    return target.strip()


def derive_subtype(fm: dict) -> str | None:
    """Best-effort entity subtype from unambiguous authority IDs only.

    We do not guess from free-text tags; absence of a signal yields None.
    """
    if fm.get("type") != "entity":
        return None
    if fm.get("idai_gazetteer_id"):
        return "place"
    if fm.get("gnd_id"):
        return "person"
    return None


# --------------------------------------------------------------------------- #
# Collection
# --------------------------------------------------------------------------- #
def collect_pages(wiki_dir: Path) -> dict[str, dict]:
    """Map page slug → {path, fm, body}. Skips _meta/ and template examples."""
    pages: dict[str, dict] = {}
    for path in sorted(wiki_dir.rglob("*.md")):
        if path.name.startswith(EXAMPLE_PREFIXES):
            continue
        if "_meta" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        fm, body = split_frontmatter(text)
        pages[path.stem] = {"path": path, "fm": fm, "body": body}
    return pages


def build_nodes(pages: dict[str, dict]) -> list[dict]:
    nodes = []
    for slug, page in sorted(pages.items()):
        fm = page["fm"]
        nodes.append(
            {
                "id": slug,
                "type": fm.get("type", "unknown"),
                "subtype": derive_subtype(fm),
                "title": fm.get("title", slug),
                "status": fm.get("status", "unknown"),
            }
        )
    return nodes


def build_edges(
    pages: dict[str, dict],
) -> tuple[list[dict], dict[str, int]]:
    """Build deduplicated edges plus a small stats dict.

    Wikilink edges are collapsed per (source, target) with a ``weight`` count.
    Structured ``relations`` produce one edge each, keyed by relation_type so a
    typed relation never overwrites a plain wikilink between the same pages.
    """
    known = set(pages)
    edges: dict[tuple[str, str, str], dict] = {}
    dangling = 0
    relations_total = 0
    inferred_or_ambiguous = 0

    for slug, page in sorted(pages.items()):
        fm, body = page["fm"], page["body"]

        # (a) wikilinks from the body and the `sources:` frontmatter list
        wikilink_raw = list(WIKILINK_RE.findall(body))
        for item in fm.get("sources", []) or []:
            if isinstance(item, str):
                wikilink_raw.append(item)
        for raw in wikilink_raw:
            target = normalise_target(raw)
            if not target or target == slug:
                continue
            if target not in known:
                dangling += 1
                continue
            key = (slug, target, "wikilink")
            if key in edges:
                edges[key]["weight"] += 1
            else:
                edges[key] = {
                    "source": slug,
                    "target": target,
                    "relation_type": "wikilink",
                    "confidence": "extracted",
                    "weight": 1,
                }

        # (b) structured, confidence-tagged relations
        for rel in fm.get("relations", []) or []:
            if not isinstance(rel, dict):
                continue
            target = normalise_target(str(rel.get("target", "")))
            if not target or target == slug:
                continue
            rel_type = str(rel.get("type", "related"))
            confidence = str(rel.get("confidence", "extracted")).lower()
            if confidence not in CONFIDENCE_VALUES:
                confidence = "ambiguous"
            relations_total += 1
            if confidence in ("inferred", "ambiguous"):
                inferred_or_ambiguous += 1
            if target not in known:
                dangling += 1
                continue
            key = (slug, target, rel_type)
            edges[key] = {
                "source": slug,
                "target": target,
                "relation_type": rel_type,
                "confidence": confidence,
                "weight": 1,
            }

    stats = {
        "dangling": dangling,
        "relations_total": relations_total,
        "relations_inferred_or_ambiguous": inferred_or_ambiguous,
    }
    return list(edges.values()), stats


# --------------------------------------------------------------------------- #
# Derived views
# --------------------------------------------------------------------------- #
def compute_god_nodes(nodes: list[dict], edges: list[dict], top_n: int) -> list[dict]:
    """Nodes ranked by total degree (incident edges, in + out)."""
    degree = {node["id"]: 0 for node in nodes}
    for edge in edges:
        degree[edge["source"]] = degree.get(edge["source"], 0) + 1
        degree[edge["target"]] = degree.get(edge["target"], 0) + 1
    ranked = sorted(degree.items(), key=lambda kv: (-kv[1], kv[0]))
    type_by_id = {node["id"]: node["type"] for node in nodes}
    return [
        {"id": slug, "type": type_by_id.get(slug, "unknown"), "degree": deg}
        for slug, deg in ranked[:top_n]
        if deg > 0
    ]


class _UnionFind:
    def __init__(self, items):
        self.parent = {item: item for item in items}

    def find(self, item):
        root = item
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[item] != root:
            self.parent[item], item = root, self.parent[item]
        return root

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def compute_bridges(nodes: list[dict], edges: list[dict]) -> list[dict]:
    """Entities that join ≥2 otherwise-unconnected source clusters.

    Heuristic (no community-detection dependency): for each entity E, take the
    set of source pages adjacent to it. Cluster those sources by whether they
    share *another* entity (≠ E). If E's sources fall into ≥2 such clusters,
    E is the bridge between them.
    """
    types = {node["id"]: node["type"] for node in nodes}
    entities = [n for n in types if types[n] == "entity"]
    sources = {n for n in types if types[n] == "source"}

    # Undirected source ↔ entity adjacency.
    entity_sources: dict[str, set[str]] = {e: set() for e in entities}
    source_entities: dict[str, set[str]] = {s: set() for s in sources}
    for edge in edges:
        a, b = edge["source"], edge["target"]
        for x, y in ((a, b), (b, a)):
            if types.get(x) == "entity" and types.get(y) == "source":
                entity_sources[x].add(y)
                source_entities[y].add(x)

    bridges = []
    for entity in sorted(entities):
        linked_sources = entity_sources[entity]
        if len(linked_sources) < 2:
            continue
        uf = _UnionFind(linked_sources)
        linked = sorted(linked_sources)
        for i, s1 in enumerate(linked):
            for s2 in linked[i + 1:]:
                # connected if they share any entity other than the candidate
                if (source_entities[s1] & source_entities[s2]) - {entity}:
                    uf.union(s1, s2)
        clusters: dict[str, list[str]] = {}
        for s in linked:
            clusters.setdefault(uf.find(s), []).append(s)
        if len(clusters) >= 2:
            bridges.append(
                {
                    "id": entity,
                    "connects": len(clusters),
                    "sources": sorted(linked_sources),
                }
            )
    bridges.sort(key=lambda b: (-b["connects"], -len(b["sources"]), b["id"]))
    return bridges


# --------------------------------------------------------------------------- #
# Serialisation
# --------------------------------------------------------------------------- #
def write_json(out_dir: Path, nodes, edges, god_nodes, bridges, stats) -> Path:
    payload = {
        "stats": {
            "nodes": len(nodes),
            "edges": len(edges),
            **stats,
        },
        "nodes": nodes,
        "edges": edges,
        "god_nodes": god_nodes,
        "bridges": bridges,
    }
    path = out_dir / "graph.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def write_graphml(out_dir: Path, nodes, edges) -> Path:
    ns = "http://graphml.graphdrawing.org/xmlns"
    ET.register_namespace("", ns)
    root = ET.Element(f"{{{ns}}}graphml")

    # Attribute declarations.
    keys = [
        ("d_type", "node", "type", "string"),
        ("d_subtype", "node", "subtype", "string"),
        ("d_title", "node", "title", "string"),
        ("d_status", "node", "status", "string"),
        ("e_relation", "edge", "relation_type", "string"),
        ("e_confidence", "edge", "confidence", "string"),
        ("e_weight", "edge", "weight", "int"),
    ]
    for key_id, domain, name, attr_type in keys:
        key = ET.SubElement(root, f"{{{ns}}}key")
        key.set("id", key_id)
        key.set("for", domain)
        key.set("attr.name", name)
        key.set("attr.type", attr_type)

    graph = ET.SubElement(root, f"{{{ns}}}graph")
    graph.set("id", "wiki")
    graph.set("edgedefault", "directed")

    node_keys = {
        "type": "d_type",
        "subtype": "d_subtype",
        "title": "d_title",
        "status": "d_status",
    }
    for node in nodes:
        el = ET.SubElement(graph, f"{{{ns}}}node")
        el.set("id", node["id"])
        for field, key_id in node_keys.items():
            value = node.get(field)
            if value in (None, ""):
                continue
            data = ET.SubElement(el, f"{{{ns}}}data")
            data.set("key", key_id)
            data.text = str(value)

    edge_keys = {
        "relation_type": "e_relation",
        "confidence": "e_confidence",
        "weight": "e_weight",
    }
    for i, edge in enumerate(edges):
        el = ET.SubElement(graph, f"{{{ns}}}edge")
        el.set("id", f"e{i}")
        el.set("source", edge["source"])
        el.set("target", edge["target"])
        for field, key_id in edge_keys.items():
            data = ET.SubElement(el, f"{{{ns}}}data")
            data.set("key", key_id)
            data.text = str(edge[field])

    path = out_dir / "graph.graphml"
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    return path


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(description="Build a knowledge graph from the Markdown wiki")
    parser.add_argument("--knowledge-dir", type=Path, default=DEFAULT_WIKI_DIR,
                        help="Wiki directory to read (default: knowledge)")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR,
                        help="Output directory (default: knowledge/_meta/graph)")
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N,
                        help="Number of god_nodes to report (default: 15)")
    args = parser.parse_args()

    if not args.knowledge_dir.exists():
        print(f"Error: knowledge directory '{args.knowledge_dir}' not found.")
        return 1

    pages = collect_pages(args.knowledge_dir)
    if not pages:
        print(f"Error: no wiki pages found under '{args.knowledge_dir}'.")
        return 1

    nodes = build_nodes(pages)
    edges, stats = build_edges(pages)
    god_nodes = compute_god_nodes(nodes, edges, args.top_n)
    bridges = compute_bridges(nodes, edges)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path = write_json(args.out_dir, nodes, edges, god_nodes, bridges, stats)
    graphml_path = write_graphml(args.out_dir, nodes, edges)

    print(f"Graph built from {len(pages)} pages: {len(nodes)} nodes, {len(edges)} edges")
    if stats["dangling"]:
        print(f"  ({stats['dangling']} edge(s) to non-existent pages skipped — run lint-wiki.py)")
    print(f"  god_nodes: {len(god_nodes)} · bridges: {len(bridges)}")
    print(f"  wrote {json_path}")
    print(f"  wrote {graphml_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
