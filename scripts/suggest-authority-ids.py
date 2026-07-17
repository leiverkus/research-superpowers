#!/usr/bin/env python3
"""
Suggest authority / vocabulary IDs for untagged entity and concept pages.

A CURATION AID, NOT AN AUTO-TAGGER.
----------------------------------
It reads a project's wiki, finds the ``type=entity`` and ``type=concept`` pages
that carry no cross-project join key yet, and for each queries Wikidata for
candidate matches — printing the label and description you need to VERIFY the
match yourself. It never writes a single id: the whole point is that a human or
LLM confirms the candidate is the right one before it goes in.

Verification is not optional. Wikidata search returns namesakes:

    "Cloud Computing"  → also a Thoroughbred racehorse (Q30608984)
    "European Union"   → also a WW2 antifascist resistance group (Q319328)
    "Vendor Lock-In"   → also AI-generated documentation artefacts

The description column is there so you can tell them apart. A tool that picked
the top hit blindly would silently assert a racehorse is a computing concept.

WHAT IT SUGGESTS
----------------
  * ``type=entity``  → ``wikidata_qid`` (the primary key). It also reports the
    candidate's ORCID (P496) and GND (P227) if it carries them, so you can
    prefer ``orcid`` for a living researcher or ``gnd_id`` for a person in
    German scholarship where those fit better.
  * ``type=concept`` → ``wikidata_qid`` (the primary key — Wikidata covers
    concepts as well as entities). It also reports the candidate's Getty AAT id
    (P1014) as an OPTIONAL extra where that art/architecture/heritage thesaurus
    has a precise term. Most modern / DH / method concepts have none (measured:
    2 of 19 in one project), which is why wikidata_qid is primary. Quote a
    getty_aat_id in the frontmatter ('300xxxxxx') so YAML keeps it a string.

Requires network (Wikidata API) and PyYAML. This is plugin-maintainer tooling;
it is NOT mirrored into the scaffolded template/example and is not run by CI.

USAGE
-----
    python scripts/suggest-authority-ids.py <project-root>
    python scripts/suggest-authority-ids.py <project-root> --type concept
    python scripts/suggest-authority-ids.py <project-root> --limit 5 --json
"""
import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except AttributeError:  # pragma: no cover
        pass

UA = "research-superpowers suggest-authority-ids (github.com/leiverkus/research-superpowers)"

# Mirrors lint-wiki.py's field lists. Duplicated (not imported) because this is
# an unshipped maintainer tool and lint-wiki lives in the template tree; the two
# lists are small and change rarely. Order = suggestion priority.
ENTITY_FIELDS = ("wikidata_qid", "orcid", "gnd_id", "idai_gazetteer_id")
CONCEPT_FIELDS = ("wikidata_qid", "getty_aat_id", "gnd_id")

# Wikidata properties worth surfacing on a candidate, by page type.
PROPS = {
    "entity": [("P496", "ORCID"), ("P227", "GND")],
    "concept": [("P1014", "Getty AAT")],
}

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


def parse_frontmatter(path: Path) -> dict:
    m = FRONTMATTER_RE.match(path.read_text(encoding="utf-8", errors="replace"))
    if not m:
        return {}
    try:
        fm = yaml.safe_load(m.group(1))
        return fm if isinstance(fm, dict) else {}
    except yaml.YAMLError:
        return {}


def untagged_pages(root: Path, want_type: str | None) -> list[tuple[str, str, str]]:
    """(type, slug, title) for every entity/concept page with no join key yet."""
    out = []
    for md in sorted((root / "knowledge").rglob("*.md")):
        if md.name.startswith(("_example-", "_beispiel-")) or "_meta" in md.parts:
            continue
        fm = parse_frontmatter(md)
        t = fm.get("type")
        if t not in ("entity", "concept"):
            continue
        if want_type and t != want_type:
            continue
        fields = ENTITY_FIELDS if t == "entity" else CONCEPT_FIELDS
        if any(str(fm.get(f, "")).strip() for f in fields):
            continue                                   # already tagged
        out.append((t, md.stem, str(fm.get("title", md.stem))))
    return out


def search_terms(title: str) -> list[str]:
    """A bilingual title like 'Datensouveränität (Data Sovereignty)' searches
    best on its English parenthetical; fall back to the whole title."""
    title = title.strip().strip('"')
    terms = []
    m = re.search(r"\(([^)]+)\)", title)
    if m:
        terms.append(m.group(1).strip())
    terms.append(re.sub(r"\s*\([^)]*\)", "", title).strip())
    seen, uniq = set(), []
    for t in terms:
        if t and t.lower() not in seen:
            seen.add(t.lower()); uniq.append(t)
    return uniq


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def wd_search(term: str, limit: int) -> list[dict]:
    url = ("https://www.wikidata.org/w/api.php?action=wbsearchentities"
           f"&search={urllib.parse.quote(term)}&language=en&format=json&limit={limit}")
    return _get(url).get("search", [])


def wd_props(qid: str, props: list[tuple[str, str]]) -> dict[str, str]:
    """{label: value} for the given properties the entity actually has.

    Uses wbgetentities, not wbgetclaims: the latter takes only ONE property, so
    a piped `P227|P496` silently returns an API error and no claims."""
    url = ("https://www.wikidata.org/w/api.php?action=wbgetentities"
           f"&ids={qid}&props=claims&format=json")
    claims = _get(url).get("entities", {}).get(qid, {}).get("claims", {})
    out = {}
    for pid, label in props:
        for c in claims.get(pid, []):
            try:
                out[label] = c["mainsnak"]["datavalue"]["value"]
                break
            except (KeyError, TypeError):
                pass
    return out


def suggest(root: Path, want_type: str | None, limit: int) -> list[dict]:
    pages = untagged_pages(root, want_type)
    results = []
    for ptype, slug, title in pages:
        cands = []
        for term in search_terms(title):
            try:
                hits = wd_search(term, limit)
            except Exception as e:
                hits = []
                print(f"  ! Wikidata search failed for «{term}»: {e}", file=sys.stderr)
            for h in hits:
                if h["id"] not in {c["qid"] for c in cands}:
                    cands.append({"qid": h["id"], "label": h.get("label", ""),
                                  "description": h.get("description", "")})
            time.sleep(0.4)
        # extra ids only for the top candidate (keeps the request count sane)
        if cands:
            try:
                cands[0]["props"] = wd_props(cands[0]["qid"], PROPS[ptype])
            except Exception:
                cands[0]["props"] = {}
            time.sleep(0.4)
        results.append({"type": ptype, "slug": slug, "title": title,
                        "primary_field": "wikidata_qid", "candidates": cands})
    return results


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Suggest Wikidata / Getty AAT ids for untagged entity & concept pages.",
        epilog="A curation aid — it prints candidates for you to verify, and writes nothing.")
    ap.add_argument("root", type=Path, help="project root (the folder with knowledge/)")
    ap.add_argument("--type", choices=("entity", "concept"), help="restrict to one page type")
    ap.add_argument("--limit", type=int, default=3, help="candidates per search (default 3)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not (args.root / "knowledge").is_dir():
        print(f"  ✗ no knowledge/ under {args.root}", file=sys.stderr)
        return 1

    results = suggest(args.root, args.type, args.limit)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 0

    if not results:
        print("  ✓ every entity and concept page already carries a join key.")
        return 0

    print(f"  {len(results)} untagged page(s). VERIFY each candidate against its "
          f"description before entering an id — search returns namesakes.\n")
    for r in results:
        print(f"── {r['type']}: {r['slug']}  «{r['title']}»")
        if not r["candidates"]:
            print("     no Wikidata candidates — look it up by hand, or leave untagged")
            continue
        for i, c in enumerate(r["candidates"]):
            mark = "→" if i == 0 else " "
            extra = "  ".join(f"{k} {v}" for k, v in c.get("props", {}).items())
            extra = f"   [{extra}]" if extra else ""
            print(f"   {mark} {c['qid']:11s} {c['label'][:34]:34s} — {c['description'][:46]}{extra}")
        print(f"     → if the top hit is right:  wikidata_qid: {r['candidates'][0]['qid']}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
