#!/usr/bin/env python3
"""
Cross-project authority overlap — step 1 of the global-graph roadmap.

A single project's graph is built by ``wiki-to-graph.py``. A *global* graph
would merge several projects, drawing ``same_as`` edges where two projects
describe the same real-world entity or cite the same source. Identity across
projects cannot rely on slugs (they collide and drift); the robust join key is
the authority IDs the frontmatter already carries:

  * ``type=entity`` : ``orcid`` (living researchers — the key that actually
    covers working scientists), ``gnd_id`` (persons), ``idai_gazetteer_id``
    (places), ``wikidata_qid``
  * ``type=source`` : ``bibkey`` (BibTeX key; stable via Better BibTeX)

This tool is the first, high-precision step. It does **not** build the merged
graph yet — it reports which authority IDs occur in MORE THAN ONE project, i.e.
the exact set of cross-project ``same_as`` edges a global graph would draw. Run
it to decide *empirically* whether a global graph is worth building for your
projects before investing in the merge.

Roadmap (not yet implemented — see docs/ROADMAP.md → "Cross-project graph"):
  * ``merge`` — namespace each project's nodes and emit the overlap set as
    ``same_as`` edges into a combined graph.json / graph.html
  * ``serve`` — a cross-project MCP so ``neighbors`` / ``path`` span projects

Deliberately high-precision: only authority-ID and bibkey matches count. Two
concepts with no authority ID are **not** fuzzy-matched (that would invent
links); the report states how many entities/concepts lack an ID so the blind
spot is explicit, not silent.

Pure standard library + PyYAML. No LLM calls, no network access. Deterministic:
output is fully sorted and carries no timestamp, so an unchanged set of projects
reproduces it byte-for-byte.

Usage:
    python scripts/wiki-global-graph.py overlap ../proj-a ../proj-b ../proj-c
    python scripts/wiki-global-graph.py overlap ../proj-a ../proj-b --json
"""

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

# Force UTF-8 stdout/stderr regardless of platform locale (Windows → cp1252).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except AttributeError:  # pragma: no cover - non-reconfigurable stream
        pass

EXAMPLE_PREFIXES = ("_example-", "_beispiel-")
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)

# Authority fields → (human label, the page type they belong on). The value of
# each is a globally unique identifier, so an exact match across projects is a
# reliable "same real-world thing" signal.
AUTHORITY_FIELDS = (
    ("orcid", "ORCID (researchers)"),
    ("gnd_id", "GND (persons)"),
    ("idai_gazetteer_id", "iDAI.gazetteer (places)"),
    ("wikidata_qid", "Wikidata"),
    ("bibkey", "BibTeX key (sources)"),
)
ID_FIELDS = [f for f, _ in AUTHORITY_FIELDS]
LABEL_OF = dict(AUTHORITY_FIELDS)


def _frontmatter(path: Path) -> dict | None:
    """Parse a page's YAML frontmatter; return the dict or None (never raise)."""
    try:
        text = path.read_text(encoding="utf-8-sig")  # tolerate a BOM
    except OSError:
        return None
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None
    try:
        fm = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return None
    return fm if isinstance(fm, dict) else None


def read_project(root: Path) -> list[dict] | None:
    """Return the wiki pages of one project (excluding _example-/_meta), each as
    {slug, type, title, ids}. Return None if the project has no knowledge/ dir.
    """
    knowledge = root / "knowledge"
    if not knowledge.is_dir():
        return None
    pages = []
    for path in sorted(knowledge.rglob("*.md")):
        if path.name.startswith(EXAMPLE_PREFIXES) or "_meta" in path.parts:
            continue
        fm = _frontmatter(path)
        if not fm:
            continue
        ids = {f: str(fm[f]).strip() for f in ID_FIELDS
               if fm.get(f) not in (None, "")}
        pages.append({"slug": path.stem, "type": str(fm.get("type", "")),
                      "title": str(fm.get("title", path.stem)), "ids": ids})
    return pages


def _labels(roots: list[Path]) -> list[str]:
    """Display label per root = its directory name, disambiguated on collision
    so two projects that happen to share a basename stay distinct."""
    names = [root.resolve().name or str(root) for root in roots]
    out, seen = [], {}
    for name in names:
        if names.count(name) > 1:
            seen[name] = seen.get(name, 0) + 1
            out.append(f"{name}#{seen[name]}")
        else:
            out.append(name)
    return out


def build_overlap(roots: list[Path]):
    """Core computation. Returns (overlap, projects) where:
      * overlap: sorted list of {field, label, value, occurrences:[...]} for
        every authority id present in ≥2 distinct projects;
      * projects: per-project stats (pages, entities, entities_with_id,
        concepts, missing).
    """
    labels = _labels(roots)
    index: dict[tuple[str, str], list[dict]] = {}
    projects = []
    for i, root in enumerate(roots):
        label = labels[i]
        pages = read_project(root)
        if pages is None:
            projects.append({"project": label, "path": str(root), "missing": True})
            continue
        entities = [p for p in pages if p["type"] == "entity"]
        concepts = [p for p in pages if p["type"] == "concept"]
        ent_with_id = [p for p in entities if p["ids"]]
        projects.append({
            "project": label, "path": str(root), "missing": False,
            "pages": len(pages), "entities": len(entities),
            "entities_with_authority_id": len(ent_with_id),
            "concepts": len(concepts),
        })
        for page in pages:
            for field, value in page["ids"].items():
                index.setdefault((field, value), []).append(
                    {"project_index": i, "project": label,
                     "slug": page["slug"], "title": page["title"], "type": page["type"]})

    overlap = []
    for (field, value), occ in index.items():
        if len({o["project_index"] for o in occ}) >= 2:
            overlap.append({
                "field": field, "label": LABEL_OF[field], "value": value,
                "occurrences": sorted(occ, key=lambda o: (o["project"], o["slug"])),
            })
    # Deterministic order: by field (schema order), then value.
    field_rank = {f: n for n, f in enumerate(ID_FIELDS)}
    overlap.sort(key=lambda o: (field_rank[o["field"]], o["value"]))
    return overlap, projects


def _print_report(overlap, projects) -> None:
    print("# Cross-project authority overlap\n")
    present = [p for p in projects if not p.get("missing")]
    print(f"Projects: {len(projects)}")
    for p in projects:
        if p.get("missing"):
            print(f"  - {p['project']}: ⚠️ no knowledge/ directory at {p['path']} — skipped")
        else:
            print(f"  - {p['project']}: {p['pages']} pages "
                  f"({p['entities']} entities, {p['entities_with_authority_id']} with authority ID, "
                  f"{p['concepts']} concepts)")
    print()

    if not overlap:
        print("No authority IDs are shared across ≥2 projects.")
        print("A global graph would draw no cross-project same_as edges for the given set.")
    else:
        print(f"Shared identifiers (present in ≥2 projects): {len(overlap)}")
        print("These are the same_as edges a global graph would draw.\n")
        current = None
        for o in overlap:
            if o["label"] != current:
                current = o["label"]
                print(f"## {current}")
            occ = "  ·  ".join(f'{x["project"]} → [[{x["slug"]}]]' for x in o["occurrences"])
            title = o["occurrences"][0]["title"]
            print(f'  - {o["value"]} — "{title}"')
            print(f"      {occ}")
        print()

    # Honest blind spot: concept-level overlap is invisible to an ID-only match.
    total_concepts = sum(p.get("concepts", 0) for p in present)
    ent_without_id = sum(p.get("entities", 0) - p.get("entities_with_authority_id", 0)
                         for p in present)
    print("Blind spot: concepts carry no authority ID, so cross-project *concept* "
          "overlap is not detected here.")
    print(f"  {total_concepts} concept page(s) and {ent_without_id} entity page(s) "
          "without any authority ID were not eligible for matching.")


def cmd_overlap(args) -> int:
    if len(args.roots) < 2:
        print("Need at least two project roots to find overlap.")
        return 1
    overlap, projects = build_overlap(args.roots)
    if args.json:
        print(json.dumps({"projects": projects, "overlap": overlap},
                         ensure_ascii=False, indent=2))
    else:
        _print_report(overlap, projects)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cross-project authority overlap (step 1 of the global-graph roadmap)")
    sub = parser.add_subparsers(dest="cmd", metavar="COMMAND")
    sp = sub.add_parser("overlap",
                        help="Report authority IDs shared across ≥2 projects")
    sp.add_argument("roots", nargs="+", type=Path,
                    help="Project root directories (each containing knowledge/)")
    sp.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    args = parser.parse_args()
    if args.cmd != "overlap":
        parser.print_help()
        return 1
    return cmd_overlap(args)


if __name__ == "__main__":
    sys.exit(main())
