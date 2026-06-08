#!/usr/bin/env python3
"""
Minimal MCP server for the wiki knowledge graph (stdio, JSON-RPC 2.0).

A thin wrapper over ``scripts/wiki-to-graph.py``: every tool shells out to the
CLI with ``--json`` against the **live** wiki (recomputed each call, always
current). Pure standard library — no `pip install mcp`, no network — so it
ships and runs inside each research project unchanged.

Register it per project (Claude Code reads `.mcp.json` at the project root):

    {
      "mcpServers": {
        "wiki-graph": { "command": "python3", "args": ["scripts/graph_mcp.py"] }
      }
    }

The knowledge dir is resolved relative to this file (``<project>/knowledge``),
so it works regardless of the launch cwd. Pass a path as argv[1] to override
(useful for testing).
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLI = HERE / "wiki-to-graph.py"
KNOWLEDGE = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / "knowledge"
PROTOCOL_FALLBACK = "2025-06-18"
SERVER_INFO = {"name": "wiki-graph", "version": "0.1.0"}

# name -> (cli sub-command, positionals, [(arg, flag)] optionals, description, inputSchema)
TOOLS = {
    "graph_neighbors": {
        "cmd": "neighbors", "pos": ["node"],
        "opt": [("depth", "--depth"), ("relation", "--relation")],
        "description": "Neighbours of a wiki page (1 hop by default). Optionally limit depth or a single relation type.",
        "schema": {
            "type": "object",
            "properties": {
                "node": {"type": "string", "description": "Page slug or a unique substring."},
                "depth": {"type": "integer", "description": "Hops to expand (default 1)."},
                "relation": {"type": "string", "description": "Only follow this relation type (e.g. gap-in, builds-on)."},
            },
            "required": ["node"],
        },
    },
    "graph_path": {
        "cmd": "path", "pos": ["a", "b"], "opt": [],
        "description": "Shortest connection between two pages.",
        "schema": {
            "type": "object",
            "properties": {"a": {"type": "string"}, "b": {"type": "string"}},
            "required": ["a", "b"],
        },
    },
    "graph_god_nodes": {
        "cmd": "god-nodes", "pos": [], "opt": [("top_n", "--top-n")],
        "description": "Most-connected pages (hubs), ranked by degree.",
        "schema": {"type": "object", "properties": {"top_n": {"type": "integer", "description": "How many (default 15)."}}},
    },
    "graph_bridges": {
        "cmd": "bridges", "pos": [], "opt": [],
        "description": "Entities that join otherwise-unconnected source clusters.",
        "schema": {"type": "object", "properties": {}},
    },
    "graph_relations": {
        "cmd": "relations", "pos": [],
        "opt": [("type", "--type"), ("confidence", "--confidence"), ("node", "--node")],
        "description": "List typed relations, optionally filtered by type / confidence / a node.",
        "schema": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "description": "e.g. cites, contradicts, builds-on."},
                "confidence": {"type": "string", "enum": ["extracted", "inferred", "ambiguous"]},
                "node": {"type": "string", "description": "Restrict to relations touching this page."},
            },
        },
    },
    "graph_search": {
        "cmd": "search", "pos": ["term"], "opt": [],
        "description": "Find wiki pages by id or title substring.",
        "schema": {"type": "object", "properties": {"term": {"type": "string"}}, "required": ["term"]},
    },
    "graph_stats": {
        "cmd": "stats", "pos": [], "opt": [],
        "description": "Graph counts by type plus the inference-rate of structured relations.",
        "schema": {"type": "object", "properties": {}},
    },
    "graph_communities": {
        "cmd": "communities", "pos": [], "opt": [("min_size", "--min-size")],
        "description": "Detected thematic clusters (greedy-modularity communities), each with its node types and members.",
        "schema": {"type": "object", "properties": {"min_size": {"type": "integer", "description": "Hide communities smaller than this."}}},
    },
}


def run_cli(spec: dict, arguments: dict) -> tuple[str, bool]:
    """Run the CLI for a tool. Returns (text, is_error)."""
    tokens = [spec["cmd"]]
    for name in spec["pos"]:
        val = arguments.get(name)
        if val is None:
            return f"missing required argument '{name}'", True
        tokens.append(str(val))
    for name, flag in spec["opt"]:
        if arguments.get(name) is not None:
            tokens += [flag, str(arguments[name])]
    cmd = [sys.executable, str(CLI), "--knowledge-dir", str(KNOWLEDGE), *tokens, "--json"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except Exception as exc:  # pragma: no cover
        return f"failed to run query: {exc}", True
    if proc.returncode != 0:
        return (proc.stdout + proc.stderr).strip() or "query failed", True
    return proc.stdout.strip(), False


def send(message: dict) -> None:
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


def reply(mid, result: dict) -> None:
    send({"jsonrpc": "2.0", "id": mid, "result": result})


def reply_error(mid, code: int, message: str) -> None:
    send({"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}})


def handle(msg: dict) -> None:
    method = msg.get("method")
    mid = msg.get("id")

    if method == "initialize":
        params = msg.get("params") or {}
        reply(mid, {
            "protocolVersion": params.get("protocolVersion", PROTOCOL_FALLBACK),
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO,
            "instructions": "Query the research wiki's knowledge graph (live). "
                            "Use graph_search/neighbors/path/god_nodes/bridges/relations/stats.",
        })
    elif method == "tools/list":
        reply(mid, {"tools": [
            {"name": n, "description": s["description"], "inputSchema": s["schema"]}
            for n, s in TOOLS.items()
        ]})
    elif method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name")
        spec = TOOLS.get(name)
        if spec is None:
            reply(mid, {"content": [{"type": "text", "text": f"unknown tool: {name}"}], "isError": True})
            return
        text, is_error = run_cli(spec, params.get("arguments") or {})
        reply(mid, {"content": [{"type": "text", "text": text}], "isError": is_error})
    elif method == "ping":
        reply(mid, {})
    elif mid is not None:
        # Unknown *request* (notifications like notifications/initialized are ignored).
        reply_error(mid, -32601, f"method not found: {method}")


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            handle(msg)
        except Exception as exc:  # never crash the server on one bad message
            mid = msg.get("id") if isinstance(msg, dict) else None
            if mid is not None:
                reply_error(mid, -32603, f"internal error: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
