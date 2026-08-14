#!/usr/bin/env python3
"""
Merge every project's ``references.bib`` into ONE master bibliography.

WHY
---
17 projects keep 17 bibliographies, and 145 bibkeys appear in more than one. That
is 145 chances for the same work to be recorded differently — and it happens: an
audit of the live projects found a wrong DOI, a wrong title, an off-by-one page
range, LaTeX-escaped umlauts next to Unicode ones, and initials next to full names.

You cannot fix that 17 times. One record, fixed once.

HOW A CONFLICT IS SETTLED
-------------------------
For each field where the projects disagree:

    same after normalising  → keep the RICHER rendering: Unicode over LaTeX escapes
                              (``Çatalhöyük`` beats ``{\\c{C}}atalh{\\"o}y{\\"u}k``),
                              full names over initials, the longer title over the
                              truncated one.
    genuinely different     → REPORT it. Never silently pick a winner on a field
                              like ``doi`` or ``year``, where one value is simply
                              wrong and only a human (or Crossref) can say which.

Verified corrections are applied from an override file rather than guessed — the
same discipline the citekey migration uses. Two are known:

    danielson-2024-edom  doi   10.1017/9781009311700 does not resolve;
                               10.1017/9781009424325 is the real one
    berlejung-2025-yhwh  title the PDF's title page reads "YHWH's Diversity:
                               A Lot of Names and No Iconography?"

USAGE
-----
    python scripts/merge-bibs.py --from-registry --out ~/UOLcloud/Bibliothek/references.bib
    python scripts/merge-bibs.py --roots <p1> <p2> … --out …
    python scripts/merge-bibs.py --from-registry --out … --overrides overrides.json
    python scripts/merge-bibs.py --from-registry --out … --report-only

``--from-registry`` reads ~/.config/research-superpowers/projects itself. Prefer it:
handing the registry to ``--roots`` through the shell needs quoting that is correct
in bash AND zsh, and every way of getting it wrong FAILS SILENTLY — a project drops
out of the merge and only the project count betrays it. See read_registry().
"""

import argparse
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except AttributeError:  # pragma: no cover
        pass

BUILD_DIRS = ("_output", "_files", ".quarto")

# Fields where a difference is a real disagreement about the world, not a rendering
# choice. Never auto-resolve these — one of them is simply wrong.
FACTUAL = ("doi", "year", "pages", "volume", "number", "isbn")

FIELD_ORDER = ["author", "editor", "title", "shorttitle", "journal", "booktitle",
               "series", "school", "institution", "publisher", "address", "volume",
               "number", "pages", "year", "isbn", "issn", "url", "doi", "keywords", "note"]

# Dropped on merge: project-local bookkeeping that has no place in a shared library.
# NOT "keywords" — a project's curated keywords belong in the shared master too,
# just not through this DROP-and-pick-a-winner path (see the union block in main()):
# two projects' keyword sets for the same source are both correct facts, not a
# disagreement, and the generic "longer string wins" merge would silently drop
# whichever project's terms lose that comparison.
DROP = {"file", "abstract", "timestamp", "owner", "groups"}


def iter_entries(text: str):
    for m in re.finditer(r"@([a-zA-Z]+)\s*\{\s*([^,\s{}]+)\s*,", text):
        opened = text.find("{", m.start())
        depth = 0
        for j in range(opened, len(text)):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    yield m.group(1).lower(), m.group(2), text[m.end():j]
                    break


def fields_of(body: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in re.finditer(r"(?:^|,)\s*([a-zA-Z][a-zA-Z0-9_-]*)\s*=\s*", body):
        name = m.group(1).lower()
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
                        out[name] = body[i + 1:j].strip()
                        break
        elif body[i] == '"':
            j = body.find('"', i + 1)
            if j > 0:
                out[name] = body[i + 1:j].strip()
        else:
            mm = re.match(r"[^,\s}]+", body[i:])
            if mm:
                out[name] = mm.group(0).strip()
    return out


def norm(s: str) -> str:
    """Strip rendering so two spellings of the same fact compare equal."""
    s = re.sub(r"\\[a-zA-Z]+\s*", "", s or "")          # \c, \"o, \& …
    s = re.sub(r"[{}$\\\"'`^~]", "", s)
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def richer(a: str, b: str) -> str:
    """Same fact, two renderings — keep the better one.

    Fewer backslashes (Unicode beat LaTeX escapes), then longer (full names and
    untruncated titles beat initials and truncations).
    """
    for cand in (a, b):
        if cand is None:
            return b if cand is a else a
    ka, kb = a.count("\\"), b.count("\\")
    if ka != kb:
        return a if ka < kb else b
    return a if len(a) >= len(b) else b


def registry_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    return (Path(base) if base else Path.home() / ".config") / "research-superpowers" / "projects"


def read_registry() -> list[Path]:
    """Every non-comment line of the registry, one path per line.

    UNFILTERED on purpose: a line that is not a directory is an error to report
    (see resolve_roots), not an entry to quietly skip. The hook's own
    read_registry() does skip them — it runs at every session start and must not
    die on one stale line — which is why this is 8 lines here rather than an
    import: same file, opposite duty.

    Reading the registry HERE rather than expanding it in the shell is the point.
    `--roots $(grep -v "^#" REG)` word-splits inside a path, so an iCloud project
    with spaces in its name arrives as five nonexistent fragments; `--roots $REG`
    does not split at all in zsh and arrives as one nonexistent path. Both drop
    projects silently.
    """
    try:
        lines = registry_path().read_text(encoding="utf-8").splitlines()
    except OSError as e:
        sys.exit(f"  ✗ cannot read the project registry {registry_path()}: {e}")
    return [Path(ln.strip()).expanduser() for ln in lines
            if ln.strip() and not ln.strip().startswith("#")]


def resolve_roots(roots: list[Path], source: str) -> list[Path]:
    """Every root must exist. A missing one means a typo in the registry or a
    path mangled by the shell — both silently shrink the merge, and the merge is
    the release gate for the master bib: reporting "0 conflicts" over a set that
    is missing a project is worse than not reporting at all."""
    if not roots:
        sys.exit(f"  ✗ no project roots {source}")
    missing = [r for r in roots if not r.is_dir()]
    if missing:
        print(f"  ✗ {len(missing)} of {len(roots)} project root(s) {source} "
              f"do not exist:", file=sys.stderr)
        for m in missing:
            print(f"      {m}", file=sys.stderr)
        print("    Fix the path, or — if this came from the shell — pass "
              "--from-registry instead of expanding the registry yourself.",
              file=sys.stderr)
        return []
    return roots


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--roots", nargs="+", type=Path)
    src.add_argument("--from-registry", action="store_true",
                     help="read the project roots from ~/.config/research-superpowers/projects "
                          "(preferred — no shell quoting to get wrong)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--overrides", type=Path, default=None,
                    help='JSON: {"<bibkey>": {"<field>": "<verified value>"}} — verified, not guessed')
    ap.add_argument("--report-only", action="store_true")
    args = ap.parse_args()

    if args.from_registry:
        roots = resolve_roots(read_registry(), f"in {registry_path()}")
    else:
        roots = resolve_roots(args.roots, "given to --roots")
    if not roots:
        return 2

    overrides = json.loads(args.overrides.read_text(encoding="utf-8")) if args.overrides else {}

    # key -> field -> {normalised: (rendering, [projects])}
    seen: dict[str, dict[str, dict[str, tuple[str, list[str]]]]] = defaultdict(lambda: defaultdict(dict))
    etypes: dict[str, list[str]] = defaultdict(list)
    # key -> {casefolded term: (rendering, [projects])} — kept OUTSIDE `seen` on
    # purpose: two projects' keyword sets are both correct facts to UNION, not a
    # disagreement for the generic one-value-wins loop below to adjudicate.
    keyword_terms: dict[str, dict[str, tuple[str, list[str]]]] = defaultdict(dict)
    def absorb(key: str, etype: str, body: str, proj: str) -> None:
        etypes[key].append(etype)
        for f, v in fields_of(body).items():
            if f in DROP or not v.strip():
                continue
            if f == "keywords":
                for term in v.split(";"):
                    term = term.strip()
                    if not term:
                        continue
                    tn = term.casefold()
                    if tn in keyword_terms[key]:
                        best = richer(keyword_terms[key][tn][0], term)
                        keyword_terms[key][tn] = (best, keyword_terms[key][tn][1] + [proj])
                    else:
                        keyword_terms[key][tn] = (term, [proj])
                continue
            n = norm(v)
            if n in seen[key][f]:
                best = richer(seen[key][f][n][0], v)
                seen[key][f][n] = (best, seen[key][f][n][1] + [proj])
            else:
                seen[key][f][n] = (v, [proj])

    bibless = []
    for root in roots:
        proj = root.name if root.name != "paper" else root.parent.name
        found = 0
        for bib in sorted((root / "output").glob("**/*.bib")):
            if any(d in bib.parts for d in BUILD_DIRS):
                continue
            found += 1
            for etype, key, body in iter_entries(bib.read_text(encoding="utf-8", errors="replace")):
                absorb(key, etype, body, proj)
        if not found:
            # Legitimate for a freshly scaffolded project — a warning, not a stop.
            bibless.append(root)

    # Fold in entries that live ONLY in the existing master — added there directly
    # (e.g. by the add-to-library skill), cited by no project. Without this they are
    # dropped on the next merge, because the merge is otherwise built purely from the
    # project roots. MASTER-ONLY keys only: a key a project also defines keeps the
    # project's value, so a stale master rendering a project has since corrected can
    # never resurface here.
    master_only = 0
    if args.out.is_file():
        from_projects = set(seen) | set(keyword_terms)
        for etype, key, body in iter_entries(args.out.read_text(encoding="utf-8", errors="replace")):
            if key in from_projects:
                continue
            absorb(key, etype, body, "(master)")
            master_only += 1

    conflicts = []
    entries: dict[str, tuple[str, dict[str, str]]] = {}
    # union with keyword_terms: an entry could in principle carry ONLY a keywords
    # field (nothing else disagreed on or agreed on), which would never touch `seen`.
    for key in sorted(set(seen) | set(keyword_terms)):
        etype = max(set(etypes[key]), key=etypes[key].count)
        merged: dict[str, str] = {}
        for f, variants in seen[key].items():
            if len(variants) == 1:
                merged[f] = next(iter(variants.values()))[0]
                continue
            picks = sorted(variants.values(), key=lambda x: (-len(x[0]), x[0]))
            merged[f] = picks[0][0]
            conflicts.append({"key": key, "field": f, "factual": f in FACTUAL,
                              "variants": [{"value": v, "projects": p} for v, p in variants.values()],
                              "chosen": picks[0][0]})
        if keyword_terms.get(key):
            # A union, never a conflict — must not appear in the report above.
            terms = sorted((v for v, _ in keyword_terms[key].values()), key=str.casefold)
            merged["keywords"] = "; ".join(terms)
        for f, v in overrides.get(key, {}).items():
            merged[f] = v
        entries[key] = (etype, merged)

    hard = [c for c in conflicts if c["factual"]]
    soft = [c for c in conflicts if not c["factual"]]
    # "root(s) read" rather than a bare project count: this number is what the
    # user checks against the registry, and the whole failure it now guards was
    # a count that had silently become wrong.
    print(f"  {len(entries)} distinct bibkeys from {len(roots)} project root(s) read"
          f" ({len(bibless)} without a .bib)")
    for root in bibless:
        print(f"    ⚠ no .bib under {root}/output — nothing merged from it")
    if master_only:
        print(f"  {master_only} master-only entr(ies) carried through "
              f"(added directly, cited by no project)")
    print(f"  {len(soft)} rendering difference(s) — resolved automatically (Unicode / longest)")
    print(f"  {len(hard)} FACTUAL conflict(s) — one value is simply wrong:\n")
    for c in hard:
        ov = " ← OVERRIDE APPLIED" if c["field"] in overrides.get(c["key"], {}) else "  ⚠ VERIFY"
        print(f"    {c['key']} · {c['field']}{ov}")
        for v in c["variants"]:
            print(f"       [{', '.join(v['projects'])[:30]:<32}] {v['value'][:44]}")

    if args.report_only:
        return 0

    out = []
    for key, (etype, f) in entries.items():
        width = max((len(k) for k in f), default=6)
        lines = [f"@{etype}{{{key},"]
        for name in FIELD_ORDER:
            if name in f:
                lines.append(f"  {name.ljust(width)} = {{{f[name]}}},")
        for name in sorted(set(f) - set(FIELD_ORDER)):
            lines.append(f"  {name.ljust(width)} = {{{f[name]}}},")
        lines.append("}")
        out.append("\n".join(lines))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n\n".join(out) + "\n", encoding="utf-8")
    print(f"\n  ✓ wrote {args.out} — {len(entries)} entries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
