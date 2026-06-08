#!/usr/bin/env python3
"""
Wiki → graph: turn the Markdown knowledge wiki into a queryable knowledge graph.

The wiki is already a graph implicitly: source/entity/concept/synthesis pages
linked by wikilinks. This script makes that graph explicit and serialisable, so
it can be opened in Gephi/yEd (GraphML) or queried programmatically (JSON).

What it produces (under --out-dir, default ``knowledge/_meta/graph/``):
  * ``graph.json``    — nodes, edges, and two derived lists (god_nodes, bridges)
  * ``graph.graphml`` — the same graph for Gephi / yEd / Cytoscape
  * ``graph.html``    — a self-contained interactive viz (open in any browser;
    no install, no network) — written only if ``scripts/vendor/cytoscape.min.js``
    is present. Filter by node type / relation type / confidence, search, click
    a node to highlight its neighbourhood. Covers everyday exploration without
    Gephi/yEd.

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
    # Build the exports (default — no sub-command):
    python scripts/wiki-to-graph.py
    python scripts/wiki-to-graph.py --out-dir knowledge/_meta/graph --no-html

    # Query the live wiki (recomputed each call — always current):
    python scripts/wiki-to-graph.py neighbors source-herzog-2014 --depth 2
    python scripts/wiki-to-graph.py path entity-itinera source-minetti-2002
    python scripts/wiki-to-graph.py god-nodes --top-n 10
    python scripts/wiki-to-graph.py bridges
    python scripts/wiki-to-graph.py communities --min-size 2
    python scripts/wiki-to-graph.py relations --type contradicts
    python scripts/wiki-to-graph.py relations --node entity-itinera --confidence inferred
    python scripts/wiki-to-graph.py search herzog
    python scripts/wiki-to-graph.py stats
    # add --json to any query for machine-readable output
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


class _NoDatesLoader(yaml.SafeLoader):
    """SafeLoader that keeps ISO dates as strings — so an invalid date like
    `2026-99-99` is parsed as text instead of raising ValueError mid-parse."""


_NoDatesLoader.yaml_implicit_resolvers = {
    ch: [(tag, rx) for (tag, rx) in res if tag != "tag:yaml.org,2002:timestamp"]
    for ch, res in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
def split_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter dict, body) for a wiki page. Empty dict if none."""
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    try:
        fm = yaml.load(match.group(1), Loader=_NoDatesLoader) or {}
    except (yaml.YAMLError, ValueError, TypeError):
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
                "because": str(rel.get("because", "")).strip(),
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


def compute_communities(nodes, edges):
    """Detect communities by greedy modularity maximisation (Clauset–Newman–
    Moore), dependency-free and deterministic.

    Agglomerative: every node starts in its own community; the pair of
    communities whose merge most increases modularity Q is merged repeatedly
    until no merge helps (ΔQ ≤ 0). Robust to dense graphs and hubs (where
    label propagation collapses to one blob). Ties broken by sorted community
    key for reproducibility. Returns ``(node_community, communities)`` with
    ids assigned by descending size.
    """
    ids = [n["id"] for n in nodes]
    # Undirected weighted adjacency between communities (start = singletons).
    deg: dict[str, float] = {i: 0.0 for i in ids}
    between: dict[str, dict[str, float]] = {i: {} for i in ids}
    total = 0.0
    for e in edges:
        a, b, w = e["source"], e["target"], float(e.get("weight", 1))
        if a == b or a not in deg or b not in deg:
            continue
        deg[a] += w; deg[b] += w; total += w
        between[a][b] = between[a].get(b, 0.0) + w
        between[b][a] = between[b].get(a, 0.0) + w
    members: dict[str, list[str]] = {i: [i] for i in ids}

    if total > 0:
        twom = 2.0 * total
        a_frac = {i: deg[i] / twom for i in ids}          # Σk_i / 2m per community
        e_frac = {i: {j: between[i][j] / twom for j in between[i]} for i in ids}
        live = set(ids)
        while True:
            best_gain, best_pair = 0.0, None
            for i in sorted(live):
                ai = a_frac[i]
                for j, eij in e_frac[i].items():
                    if j <= i:                            # each unordered pair once
                        continue
                    gain = 2.0 * (eij - ai * a_frac[j])
                    if gain > best_gain + 1e-12:
                        best_gain, best_pair = gain, (i, j)
            if best_pair is None:
                break
            i, j = best_pair                              # merge j into i
            members[i].extend(members[j]); members[j] = []
            a_frac[i] += a_frac[j]
            for k, val in e_frac[j].items():
                if k == i:
                    continue
                e_frac[i][k] = e_frac[i].get(k, 0.0) + val
                e_frac[k][i] = e_frac[k].get(i, 0.0) + val
                e_frac[k].pop(j, None)
            e_frac[i].pop(j, None)
            e_frac.pop(j, None); a_frac.pop(j, None); live.discard(j)

    groups = [m for m in members.values() if m]
    ordered = sorted(groups, key=lambda m: (-len(m), sorted(m)[0]))

    node_community: dict[str, int] = {}
    communities = []
    type_of = {n["id"]: n["type"] for n in nodes}
    for cid, members in enumerate(ordered):
        members = sorted(members)
        for m in members:
            node_community[m] = cid
        by_type: dict[str, int] = {}
        for m in members:
            by_type[type_of[m]] = by_type.get(type_of[m], 0) + 1
        communities.append({"community": cid, "size": len(members),
                            "by_type": by_type, "members": members})
    return node_community, communities


# --------------------------------------------------------------------------- #
# Serialisation
# --------------------------------------------------------------------------- #
def write_json(out_dir: Path, nodes, edges, god_nodes, bridges, communities, stats) -> Path:
    payload = {
        "stats": {
            "nodes": len(nodes),
            "edges": len(edges),
            "communities": len(communities),
            **stats,
        },
        "nodes": nodes,
        "edges": edges,
        "god_nodes": god_nodes,
        "bridges": bridges,
        "communities": communities,
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
        ("d_community", "node", "community", "int"),
        ("e_relation", "edge", "relation_type", "string"),
        ("e_confidence", "edge", "confidence", "string"),
        ("e_because", "edge", "because", "string"),
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
        "community": "d_community",
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
        "because": "e_because",
        "weight": "e_weight",
    }
    for i, edge in enumerate(edges):
        el = ET.SubElement(graph, f"{{{ns}}}edge")
        el.set("id", f"e{i}")
        el.set("source", edge["source"])
        el.set("target", edge["target"])
        for field, key_id in edge_keys.items():
            value = edge.get(field)
            if value in (None, ""):
                continue
            data = ET.SubElement(el, f"{{{ns}}}data")
            data.set("key", key_id)
            data.text = str(value)

    path = out_dir / "graph.graphml"
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    return path


def _short_label(node: dict) -> str:
    """Compact node label for the viz.

    Sources → "Author Year" (the title up to the first dash separator, or a
    slug fallback). Other types → the title, capped to keep the graph readable
    (the full title is always in the info panel).
    """
    title = (node.get("title") or node["id"]).strip()
    if node.get("type") == "source":
        head = re.split(r"\s[—–-]\s", title, maxsplit=1)[0].strip()
        if head:
            return head
        parts = node["id"].split("-")[1:]  # drop the "source" prefix
        return " ".join(p if p.isdigit() else p.capitalize() for p in parts)
    return title if len(title) <= 26 else title[:25].rstrip() + "…"


def write_html(out_dir: Path, nodes, edges, bridges, stats, vendor_path: Path) -> Path | None:
    """Write a self-contained interactive HTML viz (cytoscape.js, inlined).

    Returns the path, or None if the vendored library is missing (the script
    still produces graph.json / graph.graphml in that case).
    """
    if not vendor_path.exists():
        return None
    lib = vendor_path.read_text(encoding="utf-8").replace("</script", "<\\/script")

    # Degree per node + bridge flag, baked into cytoscape element data.
    degree: dict[str, int] = {n["id"]: 0 for n in nodes}
    for e in edges:
        degree[e["source"]] = degree.get(e["source"], 0) + 1
        degree[e["target"]] = degree.get(e["target"], 0) + 1
    bridge_ids = {b["id"] for b in bridges}

    # Compound parents per community (≥2 members) so the layout groups clusters
    # spatially. Singletons stay top-level (no box).
    comm_size: dict[int, int] = {}
    for n in nodes:
        c = n.get("community", -1)
        comm_size[c] = comm_size.get(c, 0) + 1
    parent_of = {c: f"c{c}" for c, sz in comm_size.items() if c >= 0 and sz >= 2}
    parent_nodes = [
        {"data": {"id": parent_of[c], "isCommunity": 1, "community": c,
                  "label": f"community {c} ({comm_size[c]})"}}
        for c in sorted(parent_of)
    ]
    cy_nodes = []
    for n in nodes:
        data = {
            "id": n["id"], "type": n["type"], "subtype": n.get("subtype"),
            "title": n.get("title", n["id"]), "label": _short_label(n),
            "status": n.get("status", ""), "community": n.get("community", -1),
            "degree": degree.get(n["id"], 0), "bridge": 1 if n["id"] in bridge_ids else 0,
        }
        pid = parent_of.get(n.get("community", -1))
        if pid:
            data["parent"] = pid
        cy_nodes.append({"data": data})
    cy_nodes = parent_nodes + cy_nodes
    cy_edges = [
        {"data": {
            "id": f"e{i}", "source": e["source"], "target": e["target"],
            "relation_type": e["relation_type"], "confidence": e["confidence"],
            "because": e.get("because", ""), "weight": e.get("weight", 1),
        }}
        for i, e in enumerate(edges)
    ]
    data_json = json.dumps(
        {"nodes": cy_nodes, "edges": cy_edges, "stats": {**stats, "nodes": len(nodes), "edges": len(edges)}},
        ensure_ascii=False,
    ).replace("</", "<\\/")

    html = (
        _HTML_HEAD
        + "<script>\n" + lib + "\n</script>\n"
        + "<script>const GRAPH = " + data_json + ";</script>\n"
        + "<script>\n" + _APP_JS + "\n</script>\n"
        + _HTML_TAIL
    )
    path = out_dir / "graph.html"
    path.write_text(html, encoding="utf-8")
    return path


_HTML_HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Wiki knowledge graph</title>
<style>
  :root { --bg:#fafafa; --panel:#fff; --line:#e3e3e3; --ink:#333; }
  * { box-sizing: border-box; }
  html,body { margin:0; height:100%; font:13px/1.45 -apple-system,Segoe UI,Roboto,sans-serif; color:var(--ink); }
  #app { display:flex; height:100%; }
  #cy { flex:1; background:var(--bg); }
  #side { width:280px; border-left:1px solid var(--line); background:var(--panel); padding:14px; overflow-y:auto; }
  #side h1 { font-size:15px; margin:0 0 2px; }
  #side .muted { color:#888; font-size:11px; margin-bottom:12px; }
  fieldset { border:1px solid var(--line); border-radius:6px; margin:0 0 12px; padding:8px 10px; }
  legend { font-weight:600; font-size:11px; text-transform:uppercase; letter-spacing:.04em; color:#666; padding:0 4px; }
  label.row { display:flex; align-items:center; gap:7px; padding:2px 0; cursor:pointer; }
  .swatch { width:12px; height:12px; border-radius:3px; display:inline-block; flex:none; }
  #search { width:100%; padding:6px 8px; border:1px solid var(--line); border-radius:6px; font-size:13px; }
  .btn { display:inline-block; padding:5px 10px; margin:2px 4px 2px 0; border:1px solid var(--line);
         border-radius:6px; background:#fff; cursor:pointer; font-size:12px; }
  .btn:hover { background:#f0f0f0; }
  #info { font-size:12px; }
  #info .t { font-weight:600; font-size:13px; }
  #info .k { color:#888; }
  #info ul { margin:6px 0 0; padding-left:16px; }
  #info li { margin:1px 0; }
  .pill { display:inline-block; padding:0 6px; border-radius:10px; font-size:10px; background:#eee; color:#555; }
  .legend-note { font-size:11px; color:#777; margin-top:4px; }
</style>
</head>
<body>
<div id="app">
  <div id="cy"></div>
  <div id="side">
    <h1>Knowledge graph</h1>
    <div class="muted" id="stats"></div>

    <input id="search" placeholder="Search a page…" autocomplete="off">

    <div style="margin:8px 0">
      <span class="btn" id="fit">Fit</span>
      <span class="btn" id="relayout">Re-layout</span>
      <span class="btn" id="reset">Reset</span>
    </div>

    <fieldset>
      <legend>Node types</legend>
      <label class="row" style="margin-bottom:6px">Colour&nbsp;
        <select id="colour-by">
          <option value="type">by type</option>
          <option value="community">by community</option>
        </select></label>
      <div id="type-filters"></div>
    </fieldset>

    <fieldset>
      <legend>Edges</legend>
      <label class="row"><input type="checkbox" id="show-wikilinks"> Wikilinks (many — off by default)</label>
      <label class="row"><input type="checkbox" id="show-typed" checked> Typed relations</label>
      <label class="row"><input type="checkbox" id="show-inferred" checked> incl. inferred</label>
      <div class="legend-note">Typed = purple · inferred = dashed · gold ring = bridge</div>
    </fieldset>

    <fieldset>
      <legend>Selection</legend>
      <div id="info"><span class="k">Click a node.</span></div>
    </fieldset>
  </div>
</div>
"""

_APP_JS = r"""
const PALETTE = {entity:'#4e79a7', concept:'#59a14f', source:'#e15759', synthesis:'#b07aa1', unknown:'#9c9c9c'};
const sz = d => Math.min(5 + 1.3 * Math.sqrt(d || 1), 22);
const LABEL_ZOOM_FACTOR = 1.7;  // labels appear once zoomed to ~1.7× the overview
let LABEL_ZOOM = Infinity;
const LAYOUT = { name:'cose', animate:false, padding:50, randomize:true,
  nodeRepulsion:38000, nodeOverlap:40, idealEdgeLength:160, gravity:0.12,
  componentSpacing:160, numIter:2200, edgeElasticity:50 };

const cy = cytoscape({
  container: document.getElementById('cy'),
  elements: { nodes: GRAPH.nodes, edges: GRAPH.edges },
  wheelSensitivity: 0.25,
  style: [
    { selector: 'node:childless', style: {
        'background-color': e => PALETTE[e.data('type')] || PALETTE.unknown,
        'width': e => sz(e.data('degree')), 'height': e => sz(e.data('degree')),
        'label': 'data(label)', 'font-size': 8, 'color': '#222',
        'text-valign': 'bottom', 'text-halign': 'center', 'text-margin-y': 2,
        'text-wrap': 'wrap', 'text-max-width': 80, 'min-zoomed-font-size': 5,
        'border-width': 0 } },
    { selector: ':parent', style: {
        'background-color': e => communityColor(e.data('community')),
        'background-opacity': 0.08, 'border-width': 1, 'border-color': '#e0e0e0',
        'shape': 'round-rectangle', 'padding': 16,
        'label': 'data(label)', 'font-size': 10, 'color': '#999',
        'text-valign': 'top', 'text-halign': 'center', 'min-zoomed-font-size': 6 } },
    { selector: 'node[bridge = 1]', style: { 'border-width': 2, 'border-color': '#e6a000' } },
    { selector: 'node.sel', style: { 'border-width': 3, 'border-color': '#111' } },
    { selector: 'node.nolabel', style: { 'label': '' } },
    { selector: 'edge', style: {
        'curve-style': 'bezier', 'target-arrow-shape': 'triangle',
        'width': e => Math.min(0.3 + (e.data('weight')||1) * 0.12, 1.2),
        'line-color': '#dadada', 'target-arrow-color': '#dadada', 'opacity': 0.3,
        'arrow-scale': 0.45 } },
    { selector: 'edge[relation_type != "wikilink"]', style: {
        'line-color': '#7b5cff', 'target-arrow-color': '#7b5cff', 'width': 0.9, 'opacity': 0.85 } },
    { selector: 'edge[confidence = "inferred"]', style: { 'line-style': 'dashed' } },
    { selector: 'edge[confidence = "ambiguous"]', style: { 'line-style': 'dotted' } },
    { selector: 'edge.lbl', style: {
        'label': 'data(relation_type)', 'font-size': 6, 'color': '#444',
        'text-background-color': '#fff', 'text-background-opacity': 0.85, 'text-background-padding': 1 } },
    { selector: '.faded', style: { 'opacity': 0.07, 'text-opacity': 0.07 } }
  ],
  layout: LAYOUT
});

// Stats line
const s = GRAPH.stats;
const infRate = s.relations_total ? Math.round(100 * s.relations_inferred_or_ambiguous / s.relations_total) : 0;
document.getElementById('stats').textContent =
  `${s.nodes} nodes · ${s.edges} edges · ${s.relations_total||0} typed (${infRate}% inferred)`;

// Type filters (built from data)
const types = [...new Set(GRAPH.nodes.filter(n => !n.data.isCommunity).map(n => n.data.type))].sort();
const tf = document.getElementById('type-filters');
types.forEach(t => {
  const id = 'tf-' + t;
  const lab = document.createElement('label'); lab.className = 'row';
  lab.innerHTML = `<input type="checkbox" id="${id}" checked>
    <span class="swatch" style="background:${PALETTE[t]||PALETTE.unknown}"></span>${t}`;
  tf.appendChild(lab);
  lab.querySelector('input').addEventListener('change', () => applyFilters(false));
});
document.getElementById('show-wikilinks').addEventListener('change', () => applyFilters(true));
document.getElementById('show-typed').addEventListener('change', () => applyFilters(false));
document.getElementById('show-inferred').addEventListener('change', () => applyFilters(false));

function applyFilters(relayout) {
  const on = t => document.getElementById('tf-' + t).checked;
  cy.nodes(':childless').forEach(n => n.style('display', on(n.data('type')) ? 'element' : 'none'));
  const wl = document.getElementById('show-wikilinks').checked;
  const typed = document.getElementById('show-typed').checked;
  const inf = document.getElementById('show-inferred').checked;
  cy.edges().forEach(e => {
    const isWiki = e.data('relation_type') === 'wikilink';
    let show = isWiki ? wl : typed;
    if (show && !isWiki && !inf && e.data('confidence') !== 'extracted') show = false;
    e.style('display', show ? 'element' : 'none');
  });
  cy.nodes(':parent').forEach(p =>
    p.style('display', p.children().some(c => c.style('display') !== 'none') ? 'element' : 'none'));
  if (relayout) {
    cy.$(':visible').layout(LAYOUT).run();
    cy.fit(undefined, 40);
    LABEL_ZOOM = cy.zoom() * LABEL_ZOOM_FACTOR;  // calibrate label threshold to this overview
    refreshLabels();
  }
}

function refreshLabels() { cy.nodes(':childless').toggleClass('nolabel', cy.zoom() < LABEL_ZOOM); }
cy.on('zoom', refreshLabels);

function clearHi() { cy.elements().removeClass('faded lbl'); cy.nodes().removeClass('sel'); }

function selectNode(n) {
  clearHi();
  const nb = n.closedNeighborhood();
  cy.elements().difference(nb).addClass('faded');
  nb.edges().addClass('lbl');
  n.addClass('sel');
  showInfo(n);
}

function showInfo(n) {
  const id = n.id();
  const out = GRAPH.edges.filter(e => e.data.source === id && e.data.relation_type !== 'wikilink');
  const inc = GRAPH.edges.filter(e => e.data.target === id && e.data.relation_type !== 'wikilink');
  const why = e => e.data.because ? ` <span class="k">— ${e.data.because}</span>` : '';
  const li = e => `<li>${e.data.relation_type} <span class="k">(${e.data.confidence})</span> → ${e.data.target}${why(e)}</li>`;
  const liIn = e => `<li>${e.data.source} <span class="k">(${e.data.confidence})</span> → ${e.data.relation_type}${why(e)}</li>`;
  document.getElementById('info').innerHTML =
    `<div class="t">${n.data('title')}</div>
     <div class="k">${id}</div>
     <div style="margin:4px 0"><span class="pill">${n.data('type')}</span>
       <span class="pill">${n.data('status')}</span>
       <span class="pill">deg ${n.data('degree')}</span>
       ${n.data('bridge') ? '<span class="pill" style="background:#fbe7b2">bridge</span>' : ''}</div>
     ${out.length ? `<div class="k" style="margin-top:6px">Outgoing relations</div><ul>${out.map(li).join('')}</ul>` : ''}
     ${inc.length ? `<div class="k" style="margin-top:6px">Incoming relations</div><ul>${inc.map(liIn).join('')}</ul>` : ''}`;
}

cy.on('tap', 'node', e => selectNode(e.target));
cy.on('tap', e => { if (e.target === cy) { clearHi(); document.getElementById('info').innerHTML = '<span class="k">Click a node.</span>'; } });

document.getElementById('fit').onclick = () => cy.fit(undefined, 40);
document.getElementById('relayout').onclick = () => { cy.$(':visible').layout(LAYOUT).run(); cy.fit(undefined, 40); };
document.getElementById('reset').onclick = () => { clearHi(); applyFilters(true); };

const search = document.getElementById('search');
search.addEventListener('keydown', ev => {
  if (ev.key !== 'Enter') return;
  const q = search.value.trim().toLowerCase();
  if (!q) return;
  const hit = cy.nodes().filter(n =>
    n.id().toLowerCase().includes(q) || (n.data('title') || '').toLowerCase().includes(q));
  if (hit.length) { selectNode(hit[0]); cy.animate({ center: { eles: hit[0] }, zoom: Math.max(LABEL_ZOOM, 1.4) }, { duration: 300 }); }
});

// Colour nodes by type (default) or by detected community.
function communityColor(i) { return i < 0 ? '#9c9c9c' : `hsl(${(i * 137.508) % 360}, 62%, 58%)`; }
function setColouring(mode) {
  cy.nodes(':childless').forEach(n => n.style('background-color',
    mode === 'community' ? communityColor(n.data('community'))
                         : (PALETTE[n.data('type')] || PALETTE.unknown)));
}
document.getElementById('colour-by').addEventListener('change', e => setColouring(e.target.value));

// Default view: wikilinks hidden (typed relations only), laid out on the visible subgraph.
applyFilters(true);
"""

_HTML_TAIL = """</body>
</html>
"""


# --------------------------------------------------------------------------- #
# Queries (deterministic, run against the live wiki — no cached file)
# --------------------------------------------------------------------------- #
def _resolve(nodes, token: str):
    """Resolve a token to a node id. Returns (id, None) on a unique match, or
    (None, candidates) when ambiguous/absent."""
    ids = {n["id"] for n in nodes}
    if token in ids:
        return token, None
    t = token.lower()
    hits = sorted(n["id"] for n in nodes
                  if t in n["id"].lower() or t in (n.get("title", "").lower()))
    return (hits[0], None) if len(hits) == 1 else (None, hits)


def _adjacency(edges):
    adj: dict[str, list] = {}
    for e in edges:
        adj.setdefault(e["source"], []).append((e["target"], "→", e["relation_type"], e["confidence"]))
        adj.setdefault(e["target"], []).append((e["source"], "←", e["relation_type"], e["confidence"]))
    return adj


def q_neighbors(nodes, edges, node, depth=1, relation=None):
    adj = _adjacency(edges)
    seen = {node}
    frontier = [node]
    out = []
    for d in range(1, depth + 1):
        nxt = []
        for n in frontier:
            for tgt, arrow, rtype, conf in adj.get(n, []):
                if relation and rtype != relation:
                    continue
                if tgt not in seen:
                    seen.add(tgt); nxt.append(tgt)
                    out.append({"node": tgt, "depth": d, "from": n,
                                "dir": arrow, "relation_type": rtype, "confidence": conf})
        frontier = nxt
    return out


def q_path(edges, a, b):
    adj = _adjacency(edges)
    prev = {a: None}
    queue = [a]
    while queue:
        cur = queue.pop(0)
        if cur == b:
            break
        for tgt, arrow, rtype, conf in adj.get(cur, []):
            if tgt not in prev:
                prev[tgt] = (cur, arrow, rtype, conf)
                queue.append(tgt)
    if b not in prev:
        return None
    chain = []
    cur = b
    while prev[cur] is not None:
        src, arrow, rtype, conf = prev[cur]
        chain.append({"from": src, "to": cur, "dir": arrow, "relation_type": rtype, "confidence": conf})
        cur = src
    return list(reversed(chain))


def q_relations(edges, rtype=None, confidence=None, node=None):
    out = []
    for e in edges:
        if e["relation_type"] == "wikilink" and rtype != "wikilink":
            continue
        if rtype and e["relation_type"] != rtype:
            continue
        if confidence and e["confidence"] != confidence:
            continue
        if node and node not in (e["source"], e["target"]):
            continue
        out.append(e)
    return out


def q_search(nodes, term):
    t = term.lower()
    return [n for n in nodes
            if t in n["id"].lower() or t in (n.get("title", "").lower())]


def run_query(args, nodes, edges, stats) -> int:
    import json as _json
    as_json = getattr(args, "json", False)
    deg = {n["id"]: 0 for n in nodes}
    for e in edges:
        deg[e["source"]] += 1; deg[e["target"]] += 1
    type_of = {n["id"]: n["type"] for n in nodes}

    def need(token):
        nid, cands = _resolve(nodes, token)
        if nid is None:
            if cands:
                print(f"Ambiguous '{token}'. Candidates:\n  " + "\n  ".join(cands))
            else:
                print(f"No node matches '{token}'.")
        return nid

    if args.cmd == "neighbors":
        nid = need(args.node)
        if not nid:
            return 1
        res = q_neighbors(nodes, edges, nid, args.depth, args.relation)
        if as_json:
            print(_json.dumps({"node": nid, "neighbors": res}, ensure_ascii=False, indent=2)); return 0
        print(f"Neighbours of {nid} (depth {args.depth}{', ' + args.relation if args.relation else ''}): {len(res)}")
        for r in res:
            print(f"  [{r['depth']}] {r['dir']} {r['node']}  ({r['relation_type']}, {r['confidence']})")
        return 0

    if args.cmd == "path":
        a, b = need(args.a), need(args.b)
        if not (a and b):
            return 1
        chain = q_path(edges, a, b)
        if as_json:
            print(_json.dumps({"from": a, "to": b, "path": chain}, ensure_ascii=False, indent=2)); return 0
        if not chain:
            print(f"No path between {a} and {b}."); return 0
        print(f"Path {a} → {b} ({len(chain)} hop(s)):")
        print(f"  {a}")
        for h in chain:
            if h["dir"] == "→":
                print(f"    —{h['relation_type']} ({h['confidence']})→ {h['to']}")
            else:
                print(f"    ←{h['relation_type']} ({h['confidence']})— {h['to']}")
        return 0

    if args.cmd == "god-nodes":
        gn = compute_god_nodes(nodes, edges, args.top_n)
        if as_json:
            print(_json.dumps(gn, ensure_ascii=False, indent=2)); return 0
        print(f"God nodes (top {args.top_n} by degree):")
        for g in gn:
            print(f"  {g['degree']:3d}  {g['type']:9s} {g['id']}")
        return 0

    if args.cmd == "bridges":
        br = compute_bridges(nodes, edges)
        if as_json:
            print(_json.dumps(br, ensure_ascii=False, indent=2)); return 0
        print(f"Bridges: {len(br)}")
        for b in br:
            print(f"  {b['id']} — joins {b['connects']} source clusters ({len(b['sources'])} sources)")
        return 0

    if args.cmd == "relations":
        node = need(args.node) if args.node else None
        if args.node and not node:
            return 1
        rels = q_relations(edges, args.type, args.confidence, node)
        if as_json:
            print(_json.dumps(rels, ensure_ascii=False, indent=2)); return 0
        print(f"Relations: {len(rels)}")
        for e in rels:
            why = f"  — {e['because']}" if e.get("because") else ""
            print(f"  {e['source']} --{e['relation_type']} ({e['confidence']})--> {e['target']}{why}")
        return 0

    if args.cmd == "search":
        res = q_search(nodes, args.term)
        if as_json:
            print(_json.dumps([n["id"] for n in res], ensure_ascii=False, indent=2)); return 0
        print(f"Matches for '{args.term}': {len(res)}")
        for n in res:
            print(f"  {n['type']:9s} {n['id']}  ·  {n.get('title','')}")
        return 0

    if args.cmd == "stats":
        by_type = {}
        for n in nodes:
            by_type[n["type"]] = by_type.get(n["type"], 0) + 1
        rt = stats.get("relations_total", 0)
        ia = stats.get("relations_inferred_or_ambiguous", 0)
        payload = {"nodes": len(nodes), "edges": len(edges), "by_type": by_type,
                   "relations_total": rt, "inference_rate": round(ia / rt, 3) if rt else None,
                   "dangling": stats.get("dangling", 0)}
        if as_json:
            print(_json.dumps(payload, ensure_ascii=False, indent=2)); return 0
        print(f"nodes: {len(nodes)} · edges: {len(edges)} · dangling: {payload['dangling']}")
        print("by type: " + ", ".join(f"{k} {v}" for k, v in sorted(by_type.items())))
        print(f"typed relations: {rt} · inference-rate: {int(100 * ia / rt) if rt else 0}%")
        return 0

    if args.cmd == "communities":
        _, comms = compute_communities(nodes, edges)
        min_size = getattr(args, "min_size", 1) or 1
        comms = [c for c in comms if c["size"] >= min_size]
        if as_json:
            print(_json.dumps(comms, ensure_ascii=False, indent=2)); return 0
        print(f"Communities (size ≥ {min_size}): {len(comms)}")
        for c in comms:
            bt = ", ".join(f"{k} {v}" for k, v in sorted(c["by_type"].items()))
            preview = ", ".join(c["members"][:6]) + (" …" if c["size"] > 6 else "")
            print(f"  #{c['community']}  ({c['size']}: {bt})  {preview}")
        return 0

    return 1


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build and query a knowledge graph from the Markdown wiki")
    parser.add_argument("--knowledge-dir", type=Path, default=DEFAULT_WIKI_DIR,
                        help="Wiki directory to read (default: knowledge)")
    # Build flags live on the main parser so the default (no sub-command) call
    # — used by CI, the scaffold and the wiki-graph skill — stays unchanged.
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR,
                        help="Output directory (default: knowledge/_meta/graph)")
    parser.add_argument("--top-n", type=int, default=DEFAULT_TOP_N,
                        help="Number of god_nodes to report (default: 15)")
    parser.add_argument("--no-html", action="store_true",
                        help="Skip the interactive graph.html (JSON + GraphML only)")

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    sub = parser.add_subparsers(dest="cmd", metavar="QUERY")
    sp = sub.add_parser("neighbors", parents=[common], help="Neighbours of a node")
    sp.add_argument("node"); sp.add_argument("--depth", type=int, default=1)
    sp.add_argument("--relation", help="Only follow this relation type")
    sp = sub.add_parser("path", parents=[common], help="Shortest path between two nodes")
    sp.add_argument("a"); sp.add_argument("b")
    sp = sub.add_parser("god-nodes", parents=[common], help="Most-connected pages")
    sp.add_argument("--top-n", type=int, default=DEFAULT_TOP_N)
    sub.add_parser("bridges", parents=[common], help="Entities joining unconnected source clusters")
    sp = sub.add_parser("relations", parents=[common], help="List typed relations")
    sp.add_argument("--type"); sp.add_argument("--confidence"); sp.add_argument("--node")
    sp = sub.add_parser("search", parents=[common], help="Find nodes by id/title")
    sp.add_argument("term")
    sub.add_parser("stats", parents=[common], help="Counts + inference-rate")
    sp = sub.add_parser("communities", parents=[common], help="Detected thematic clusters (label propagation)")
    sp.add_argument("--min-size", type=int, default=1, help="Hide communities smaller than this")
    args = parser.parse_args()

    if not args.knowledge_dir.exists():
        print(f"Error: knowledge directory '{args.knowledge_dir}' not found.")
        return 1

    pages = collect_pages(args.knowledge_dir)
    if not pages:
        print(f"Error: no wiki pages found under '{args.knowledge_dir}'.")
        return 1

    # Page slugs must be unique — wikilinks resolve by slug, so duplicates would
    # silently collapse to one node. Fail loudly instead.
    seen: dict[str, list[str]] = {}
    for path in args.knowledge_dir.rglob("*.md"):
        if path.name.startswith(EXAMPLE_PREFIXES) or "_meta" in path.parts:
            continue
        seen.setdefault(path.stem, []).append(str(path))
    dupes = {s: p for s, p in seen.items() if len(p) > 1}
    if dupes:
        print("Error: duplicate page slugs (ambiguous wikilink/relation targets):")
        for slug, paths in sorted(dupes.items()):
            print(f"  {slug}: {', '.join(paths)}")
        return 1

    nodes = build_nodes(pages)
    edges, stats = build_edges(pages)

    # Query sub-commands run against this freshly-built (live) graph.
    if args.cmd is not None:
        return run_query(args, nodes, edges, stats)

    god_nodes = compute_god_nodes(nodes, edges, args.top_n)
    bridges = compute_bridges(nodes, edges)
    node_community, communities = compute_communities(nodes, edges)
    for n in nodes:
        n["community"] = node_community.get(n["id"], -1)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path = write_json(args.out_dir, nodes, edges, god_nodes, bridges, communities, stats)
    graphml_path = write_graphml(args.out_dir, nodes, edges)

    print(f"Graph built from {len(pages)} pages: {len(nodes)} nodes, {len(edges)} edges")
    if stats["dangling"]:
        print(f"  ({stats['dangling']} edge(s) to non-existent pages skipped — run lint-wiki.py)")
    print(f"  god_nodes: {len(god_nodes)} · bridges: {len(bridges)} · communities: {len(communities)}")
    print(f"  wrote {json_path}")
    print(f"  wrote {graphml_path}")

    if not args.no_html:
        vendor = Path(__file__).resolve().parent / "vendor" / "cytoscape.min.js"
        html_path = write_html(args.out_dir, nodes, edges, bridges, stats, vendor)
        if html_path:
            print(f"  wrote {html_path}")
        else:
            print(f"  (no graph.html — vendored library missing at {vendor})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
