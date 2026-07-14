#!/usr/bin/env python3
"""
Generate ``output/bibtex/references.bib`` from a Zotero collection — with OUR keys.

WHY NOT BETTER BIBTEX
---------------------
The obvious design is: let Zotero own the bibliography and let Better BibTeX
auto-export ``references.bib``. A pilot on a 36-source project showed why that
does not work.

**BBX's key formula is not ours, and cannot be made to be.** Configured with
``auth.lower + '-' + year + '-' + shorttitle(1,1).lower`` — the closest BBX can
express to our convention — it still diverged on 8 of 36 entries:

    ours                                BBX
    ardissone-2013-information          ardissone-2013-3d
    dereu-2013-towards                  dereu-2013-threedimensional
    marinbuzon-2021-photogrammetry-sfm  marin-buzon-2021-photogrammetry
    massonmaclean-2021-digitally        masson-maclean2021

Three independent causes: BBX keeps two-character title words (``3D``) where we
drop them; it keeps hyphens in surnames where we fold them; its stopword list
differs. These live inside BBX's ``shorttitle``/``auth`` implementations — no
setting reaches them.

Worse, ``marin-buzon-2021-photogrammetry`` is what BBX produces for **both**
Marín-Buzón 2021 papers: it re-creates the very collision the citekey migration
removed. And ``bibkey`` is a cross-project JOIN KEY.

Pinning every key in Zotero would be the defensive fix, but it leaves BBX owning
key *generation* — every new item, every formula edit, every "refresh keys" can
re-take it. And BBX's auto-export does not fire on sync-originated changes, which
is how every write from an API client arrives. So the automated path is closed
anyway.

Hence this: **we own the key, Zotero owns everything else.** Zotero remains the
upstream for metadata, PDFs, annotations and cross-project dedup; the citekey
stays where ``lint-wiki.py`` can enforce it. That is the same rule the whole
citekey migration rests on — enforce an invariant with a tool; do not hope a
third party honours a convention.

The key is read from the item's ``Extra`` field (``Citation Key: <key>``), which
is where ``zotero_add_by_bibtex`` preserves it on import. The generated file is
deterministic (sorted by key) so a re-run produces a byte-identical file and
``git diff`` shows only real changes.

USAGE
-----
    python scripts/zotero-to-bib.py --collection "Projekte/Hazor" --out output/bibtex/references.bib
    python scripts/zotero-to-bib.py --collection AVXVVZJU --out … --check   # diff only, write nothing

Reads Zotero's local API (http://localhost:23119) — Zotero must be running.
Read-only: this never writes to Zotero.
"""

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except AttributeError:  # pragma: no cover
        pass

LOCAL_API = "http://localhost:23119/api/users/0"

# Zotero item type → BibTeX entry type, and which Zotero field carries the
# container title for that type.
TYPE_MAP = {
    "journalArticle":      ("article",       "publicationTitle", "journal"),
    "conferencePaper":     ("inproceedings", "proceedingsTitle", "booktitle"),
    "bookSection":         ("incollection",  "bookTitle",        "booktitle"),
    "encyclopediaArticle": ("incollection",  "encyclopediaTitle", "booktitle"),
    "dictionaryEntry":     ("incollection",  "dictionaryTitle",  "booktitle"),
    "book":                ("book",          None,               None),
    "thesis":              ("phdthesis",     None,               None),
    "manuscript":          ("unpublished",   None,               None),
    "report":              ("techreport",    None,               None),
    "preprint":            ("misc",          None,               None),
    "webpage":             ("misc",          None,               None),
    "document":            ("misc",          None,               None),
}

# Emission order — stable, so the file is diffable.
FIELD_ORDER = ["author", "editor", "title", "journal", "booktitle", "series",
               "school", "institution", "publisher", "address", "volume",
               "number", "pages", "year", "isbn", "issn", "url", "doi"]


def fetch(path: str):
    with urllib.request.urlopen(f"{LOCAL_API}/{path}", timeout=30) as r:
        return json.load(r)


def all_items() -> list[dict]:
    out, start = [], 0
    while True:
        batch = fetch(f"items?limit=100&start={start}")
        if not batch:
            break
        out += batch
        start += 100
        if start > 20000:                       # runaway guard
            break
    return [it["data"] for it in out]


def resolve_collection(spec: str) -> str:
    """Accept an 8-char key, a name, or a 'Parent/Child' path."""
    if re.fullmatch(r"[A-Z0-9]{8}", spec):
        return spec
    cols, start = [], 0
    while True:
        batch = fetch(f"collections?limit=100&start={start}")
        if not batch:
            break
        cols += [c["data"] for c in batch]
        start += 100
    by_key = {c["key"]: c for c in cols}

    def path_of(c):
        parts, cur = [c["name"]], c
        while cur.get("parentCollection"):
            cur = by_key.get(cur["parentCollection"])
            if not cur:
                break
            parts.insert(0, cur["name"])
        return "/".join(parts)

    wanted = spec.strip("/").lower()
    hits = [c for c in cols if path_of(c).lower() == wanted or c["name"].lower() == wanted]
    if len(hits) == 1:
        return hits[0]["key"]
    if not hits:
        raise SystemExit(f"  ✗ no collection matches '{spec}'")
    raise SystemExit(f"  ✗ '{spec}' is ambiguous: {[path_of(c) for c in hits]}")


def citekey_of(item: dict) -> str | None:
    """OUR key. The Extra field is authoritative — it is where the migrated key
    is preserved on import. Zotero's native `citationKey` holds whatever BBX
    generated, which is exactly what we must not trust."""
    m = re.search(r"^\s*Citation Key\s*:\s*(\S+)", item.get("extra", ""), re.I | re.M)
    return m.group(1) if m else None


def brace(value: str) -> str:
    """BibTeX-escape. Keeps existing {…} groups (they protect capitalisation)."""
    v = str(value).strip()
    for ch, esc in (("&", r"\&"), ("%", r"\%"), ("$", r"\$"), ("#", r"\#"), ("_", r"\_")):
        v = re.sub(rf"(?<!\\){re.escape(ch)}", esc, v)
    return v


def names(item: dict, kind: str) -> str:
    out = []
    for c in item.get("creators", []):
        if c.get("creatorType") != kind:
            continue
        if c.get("name"):                       # single-field name
            out.append(c["name"])
        else:
            out.append(f'{c.get("lastName", "")}, {c.get("firstName", "")}'.strip().strip(","))
    return " and ".join(out)


def year_of(item: dict) -> str:
    m = re.search(r"(1[0-9]{3}|20[0-9]{2})", str(item.get("date", "")))
    return m.group(1) if m else ""


def to_entry(item: dict, key: str) -> str:
    etype, zfield, bfield = TYPE_MAP.get(item["itemType"], ("misc", None, None))
    f: dict[str, str] = {}

    author, editor = names(item, "author"), names(item, "editor")
    if author:
        f["author"] = author
    if editor and not author:
        f["editor"] = editor
    elif editor and etype in ("incollection", "inproceedings", "book"):
        f["editor"] = editor

    f["title"] = item.get("title", "")
    if zfield and item.get(zfield):
        f[bfield] = item[zfield]
    for z, b in (("series", "series"), ("publisher", "publisher"), ("place", "address"),
                 ("volume", "volume"), ("issue", "number"), ("university", "school"),
                 ("institution", "institution"), ("ISBN", "isbn"), ("ISSN", "issn"),
                 ("url", "url"), ("DOI", "doi")):
        if item.get(z):
            f[b] = item[z]
    if item.get("pages"):
        f["pages"] = re.sub(r"\s*[-–—]\s*", "--", str(item["pages"]))
    if year_of(item):
        f["year"] = year_of(item)

    width = max((len(k) for k in f), default=6)
    lines = [f"@{etype}{{{key},"]
    for name in FIELD_ORDER:
        if name in f and str(f[name]).strip():
            lines.append(f"  {name.ljust(width)} = {{{brace(f[name])}}},")
    lines.append("}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--collection", required=True,
                    help="collection key, name, or 'Parent/Child' path")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--check", action="store_true",
                    help="report differences against --out, write nothing (CI-friendly)")
    args = ap.parse_args()

    try:
        ckey = resolve_collection(args.collection)
    except OSError:
        print("  ✗ Zotero's local API is not answering — is Zotero running?", file=sys.stderr)
        return 1

    items = [d for d in all_items()
             if d.get("itemType") not in ("attachment", "note", "annotation")
             and ckey in d.get("collections", [])]
    if not items:
        print(f"  ✗ collection '{args.collection}' has no items", file=sys.stderr)
        return 1

    entries, unkeyed = {}, []
    for it in items:
        key = citekey_of(it)
        if not key:
            unkeyed.append(it.get("title", "?")[:60])
            continue
        if key in entries:
            print(f"  ✗ two items claim the key '{key}' — refusing", file=sys.stderr)
            return 1
        entries[key] = to_entry(it, key)

    if unkeyed:
        # A silent drop here would leave the manuscript citing a key that no
        # longer exists in the bib, and Quarto renders that as ??? while exiting 0.
        print(f"  ✗ {len(unkeyed)} item(s) carry no 'Citation Key:' in Extra:", file=sys.stderr)
        for t in unkeyed[:8]:
            print(f"      {t}", file=sys.stderr)
        print("    Import them with zotero_add_by_bibtex (it preserves the key), "
              "or add the line by hand.", file=sys.stderr)
        return 1

    body = "\n\n".join(entries[k] for k in sorted(entries)) + "\n"

    if args.check:
        old = args.out.read_text(encoding="utf-8") if args.out.exists() else ""
        if old == body:
            print(f"  ✓ {args.out} is up to date ({len(entries)} entries)")
            return 0
        old_keys = set(re.findall(r"@[a-zA-Z]+\{([^,]+),", old))
        print(f"  ✗ {args.out} differs from Zotero")
        print(f"      only in Zotero : {sorted(set(entries) - old_keys)[:6]}")
        print(f"      only in file   : {sorted(old_keys - set(entries))[:6]}")
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(body, encoding="utf-8")
    print(f"  ✓ wrote {args.out} — {len(entries)} entries from '{args.collection}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
