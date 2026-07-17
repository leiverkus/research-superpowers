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
  * ``type=concept``: ``wikidata_qid`` — the primary key, since Wikidata covers
    concepts as well as entities — with ``getty_aat_id`` (Getty AAT) as an
    optional extra where that heritage thesaurus has a precise term (measured:
    2 of 19 concepts in one project). This is what makes concept-level
    cross-project links — the deepest tissue of a methods portfolio —
    mechanically visible.
  * ``type=source`` : ``bibkey`` (BibTeX key; stable via the surname-year-shorttitle
    convention, which ``lint-wiki.py`` enforces. This docstring used to claim the
    keys were "stable via Better BibTeX" — they never were. An audit of 17 wikis
    found the convention honoured by only 40% of 511 keys, which cost 17 missed
    joins and produced 3 false positives. The ``bibkeys`` sub-command below exists
    to make exactly that failure visible.)

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
import unicodedata
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
    ("getty_aat_id", "Getty AAT (concepts)"),
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
    """Display label per root = its directory name, disambiguated on collision by
    walking UP the path, not by appending a counter.

    A nested layout — `<Module>/paper/` per module — makes every basename `paper`.
    A counter would label them `paper#1 … paper#9`, which tells the reader nothing
    about which project a finding belongs to and makes the whole report useless.
    Prepending the parent yields `Aoristos/paper`, `Signa/paper`.
    """
    resolved = [root.resolve() for root in roots]
    depth = 1
    while depth < 5:
        labels = ["/".join(p.parts[-depth:]) or str(p) for p in resolved]
        if len(set(labels)) == len(labels):
            return labels
        depth += 1
    return [str(p) for p in resolved]


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
        con_with_id = [p for p in concepts if p["ids"]]
        projects.append({
            "project": label, "path": str(root), "missing": False,
            "pages": len(pages), "entities": len(entities),
            "entities_with_authority_id": len(ent_with_id),
            "concepts": len(concepts),
            "concepts_with_vocab_id": len(con_with_id),
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

    # Honest blind spot: only *untagged* pages are invisible to an ID-only match.
    # Concepts can now carry a vocabulary id (wikidata_qid primary, getty_aat_id /
    # gnd_id optional); those that don't are the remaining blind spot.
    con_without_id = sum(p.get("concepts", 0) - p.get("concepts_with_vocab_id", 0)
                         for p in present)
    ent_without_id = sum(p.get("entities", 0) - p.get("entities_with_authority_id", 0)
                         for p in present)
    print("Blind spot: pages without a join id are not eligible for matching.")
    print(f"  {con_without_id} concept page(s) without a vocabulary id (wikidata_qid / "
          f"getty_aat_id / gnd_id) and {ent_without_id} entity page(s) without an authority id.")


# ---------------------------------------------------------------------------
# bibkeys — the check that `overlap` structurally cannot perform
# ---------------------------------------------------------------------------
#
# `overlap` compares bibkey STRINGS. It therefore reports a shared key as a win —
# a same_as edge — and is blind to the two ways that can be wrong:
#
#   COLLISION  one key, two different works. `overlap` asserts a shared source
#              where none exists. (Real: `hensel-2024` meant "Reconsidering
#              Yahwism…" in one project and "Transjordan and Judah…" in another.)
#   SPLIT      one work, two different keys. `overlap` never sees the link.
#              (Real: `Smith2016` vs `smith2016` — a join lost to capitalisation.)
#
# Neither is visible from a single wiki, so this cannot be a CI gate: no one
# repo's CI can see the others. It is a portfolio command, run by hand.
#
# It needs the .bib (the work behind the key), which `overlap` never reads.

BUILD_DIRS = ("_output", "_files", ".quarto", "node_modules")
_STOP = {"the", "a", "an", "of", "and", "in", "on", "for", "to", "from", "der",
         "die", "das", "und", "von", "im", "zur", "zum", "des", "ein", "eine"}


def _bib_field(body: str, name: str) -> str:
    """One BibTeX field, brace-balanced, case-insensitive."""
    for m in re.finditer(rf"(?:^|[,{{\s]){name}\s*=\s*", body, re.I):
        i = m.end()
        if i >= len(body):
            continue
        if body[i] == "{":
            depth = 0
            for j in range(i, len(body)):
                if body[j] == "{":
                    depth += 1
                elif body[j] == "}":
                    depth -= 1
                    if depth == 0:
                        return body[i + 1:j].strip()
        elif body[i] == '"':
            j = body.find('"', i + 1)
            if j > 0:
                return body[i + 1:j].strip()
        else:
            mm = re.match(r"[^,\s}]+", body[i:])
            if mm:
                return mm.group(0).strip()
    return ""


def _iter_bib_entries(text: str):
    """(key, body) per entry, brace-balanced — real bibs mix multi-line and
    single-line entries, and a '\\n}' anchor silently drops the latter."""
    for m in re.finditer(r"@([a-zA-Z]+)\s*\{\s*([^,\s{}]+)\s*,", text):
        opened = text.find("{", m.start())
        depth = 0
        for j in range(opened, len(text)):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    yield m.group(2), text[m.end():j]
                    break


def _work_id(title: str, year: str) -> str:
    """A conservative fingerprint of the work, for spotting the same paper under
    two keys. Title words + year — never fuzzy, just normalised.

    Titles must be de-LaTeX'd and folded to ASCII BEFORE tokenising, or one work
    yields several fingerprints and is reported as a collision that isn't. Both of
    these bit in practice:

      * brace protection — ``{I}ron {A}ge {J}erusalem`` vs ``{Iron} {Age}
        {Jerusalem}``: tokenising on ``[a-z0-9]+`` without stripping braces splits
        the first into ``i, ron, a, ge`` and the second into ``iron, age``.
      * accents — the SAME paper appears as ``{\\c{C}}atalh{\\"o}y{\\"u}k``,
        ``{Çatalhöyük}`` and ``Çatalhöyük`` in three bibs. Non-ASCII characters are
        not in ``[a-z0-9]``, so ``çatalhöyük`` shatters into ``atalh, y, k``.
    """
    text = re.sub(r"\\[a-zA-Z]+", " ", title)        # LaTeX commands: \c, \"o, \'a
    text = re.sub(r"[{}$\\\"'`^~]", "", text)         # brace protection + accent marks
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    words = [w for w in re.findall(r"[a-z0-9]+", text)
             if w not in _STOP and len(w) > 2]
    return " ".join(words[:8]) + "|" + year


def _same_work(a: str, b: str) -> bool:
    """Do two title fingerprints denote the same work?

    Same year, and one title is a prefix of the other — which is what a truncated
    vs. full transcription of the same paper looks like. Anything else counts as
    different. Deliberately conservative: never fuzzy-match, only tolerate
    truncation.
    """
    ta, _, ya = a.partition("|")
    tb, _, yb = b.partition("|")
    if ya and yb and ya != yb:
        return False
    return ta.startswith(tb) or tb.startswith(ta)


def read_bibs(root: Path) -> dict[str, dict]:
    """{key: {title, year, doi, work}} across every .bib under root/output/."""
    out: dict[str, dict] = {}
    outdir = root / "output"
    if not outdir.is_dir():
        return out
    for bib in sorted(outdir.glob("**/*.bib")):
        if any(d in bib.parts for d in BUILD_DIRS):
            continue
        text = bib.read_text(encoding="utf-8", errors="replace")
        for key, body in _iter_bib_entries(text):
            title = _bib_field(body, "title")
            year = _bib_field(body, "year")
            m = re.search(r"(1[0-9]{3}|20[0-9]{2})", year)
            year = m.group(1) if m else ""
            out[key] = {"title": title, "year": year,
                        "doi": _bib_field(body, "doi").lower(),
                        "work": _work_id(title, year)}
    return out


def build_bibkey_report(roots: list[Path]):
    """(collisions, splits) across N projects."""
    labels = _labels(roots)
    per: dict[str, dict[str, dict]] = {}
    for label, root in zip(labels, roots):
        per[label] = read_bibs(root)

    key_to: dict[str, list[tuple[str, dict]]] = {}
    work_to: dict[str, list[tuple[str, str]]] = {}     # work/doi -> [(project, key)]
    for label, entries in per.items():
        for key, e in entries.items():
            key_to.setdefault(key, []).append((label, e))
            ident = e["doi"] or e["work"]
            if ident and ident != "|":
                work_to.setdefault(ident, []).append((label, key))

    collisions = []
    for key, occ in sorted(key_to.items()):
        if len({p for p, _ in occ}) < 2:
            continue
        dois = [e["doi"] for _, e in occ if e["doi"]]
        if len(dois) >= 2 and len(set(dois)) == 1:
            # Two or more independent records agree on the DOI. A DOI identifies a
            # work uniquely, so this is decisive SAMENESS — even when the titles
            # disagree, which they do: the same Berlejung 2025 book is recorded as
            # "YHWH's Diversity: A Lot of Names and No Iconography?" in one project
            # and "YHWH's Diversity and the One God" in another. Same DOI, same
            # publisher, same series. One work, two transcriptions.
            differ = False
        else:
            # No agreeing DOI (or only one record has one — which proves nothing).
            # Fall back to the title fingerprint. Titles get transcribed at
            # different lengths for one work ("The Religion of Idumea" vs "…and Its
            # Relationship to Early Judaism"), so a prefix relation counts as
            # identity — otherwise every truncated title reads as a collision and
            # the signal drowns.
            works = [e["work"] for _, e in occ if e["work"] != "|"]
            differ = bool(works) and not all(_same_work(works[0], w) for w in works[1:])
        if differ:
            collisions.append({"key": key,
                               "occurrences": [{"project": p, "title": e["title"]}
                                               for p, e in sorted(occ)]})

    splits = []
    for ident, occ in sorted(work_to.items()):
        projects = {p for p, _ in occ}
        keys = {k for _, k in occ}
        if len(projects) > 1 and len(keys) > 1:
            title = next(per[p][k]["title"] for p, k in occ)
            splits.append({"work": title, "occurrences":
                           [{"project": p, "key": k} for p, k in sorted(occ)]})

    return collisions, splits, per


def cmd_bibkeys(args) -> int:
    roots = [Path(r).resolve() for r in args.roots]
    if len(roots) < 2:
        print("  Need at least two project roots.", file=sys.stderr)
        return 1
    collisions, splits, per = build_bibkey_report(roots)

    if args.json:
        print(json.dumps({"collisions": collisions, "splits": splits},
                         indent=2, ensure_ascii=False, sort_keys=True))
        return 1 if collisions else 0

    print("# Cross-project bibkey health\n")
    for label, entries in sorted(per.items()):
        print(f"  - {label}: {len(entries)} bib entries")

    print(f"\n## COLLISION — one key, DIFFERENT works ({len(collisions)})")
    print("   These make `overlap` assert a shared source where none exists.")
    if not collisions:
        print("   None. ✓")
    for c in collisions:
        print(f"\n   {c['key']}")
        for o in c["occurrences"]:
            print(f"      {o['project']:<24} {o['title'][:58]}")

    print(f"\n## SPLIT — one work, DIFFERENT keys ({len(splits)})")
    print("   These are cross-project joins `overlap` silently misses.")
    if not splits:
        print("   None. ✓")
    for s in splits:
        print(f"\n   \"{s['work'][:62]}\"")
        for o in s["occurrences"]:
            print(f"      {o['project']:<24} {o['key']}")

    return 1 if collisions else 0


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

    bk = sub.add_parser("bibkeys",
                        help="Audit the bibkey join key: COLLISION (one key, two "
                             "works) and SPLIT (one work, two keys)")
    bk.add_argument("roots", nargs="+", type=Path,
                    help="Project root directories (each containing knowledge/)")
    bk.add_argument("--json", action="store_true", help="Emit JSON instead of text")

    args = parser.parse_args()
    if args.cmd == "overlap":
        return cmd_overlap(args)
    if args.cmd == "bibkeys":
        return cmd_bibkeys(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
