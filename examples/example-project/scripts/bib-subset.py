#!/usr/bin/env python3
"""
Write ``output/bibtex/references.bib`` as the subset of the shared library that THIS
project actually cites.

WHY A SUBSET AND NOT JUST POINTING AT THE MASTER
------------------------------------------------
Quarto would happily render against the master bibliography — it only emits entries
that are cited. But the template promises that an ``output/article/`` folder can be
zipped and shipped, and CI renders without the library (which is machine-local and
not in git). A committed per-project subset keeps both promises: the repo stays
self-contained, and the render is reproducible on a machine that has never heard of
the library.

The subset is *derived*, never hand-edited. Re-run it after every ingest.

By default it KEEPS what the project already carried — a research bibliography is
what you have collected, not merely what you have cited so far. Every entry is
re-drawn from the master bib, so the library's verified metadata propagates into
the project. ``--prune`` opts into the strict cited-only subset.

WHAT COUNTS AS A CITATION
-------------------------
The same scanner ``lint-wiki.py`` uses, and for the same reason — it already knows
what is NOT a citation, each case having been a real false positive on the live
projects:

    @sec-methods, @fig-map     Quarto cross-references
    AP\\@IoU0.5                 an escaped at-sign: the backslash means "literal"
    `@key` and fenced code     a citation shown as an example is not a citation
    foo@bar.com                 an e-mail address
    knowledge/_meta/           bookkeeping ("durchgehend mit @citekeys belegt")
    _example-*.md              template fixtures

Frontmatter ``bibkey:`` counts too: a source page always belongs in the bibliography,
even before anything cites it.

FAILURE IS LOUD
---------------
A cited key that the library does not know is a **hard error**. Silently dropping it
would leave the manuscript citing a key that is in no ``.bib`` — and Quarto renders
that as ``???`` while exiting 0.

USAGE
-----
    python scripts/bib-subset.py                       # writes output/bibtex/references.bib
    python scripts/bib-subset.py --out <path>
    python scripts/bib-subset.py --check               # CI: differs? exit 1, write nothing
"""

import argparse
import importlib.util
import re
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except AttributeError:  # pragma: no cover
        pass

HERE = Path(__file__).resolve().parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def cited_keys(root: Path) -> set[str]:
    """Every bibkey this project references — from frontmatter and from prose."""
    lw = _load("_rs_lint", HERE / "lint-wiki.py")
    keys: set[str] = set()

    for page in sorted((root / "knowledge").rglob("*.md")):
        if page.name.startswith(("_beispiel-", "_example-")):
            continue
        if "_meta" in page.parts or not lw._not_build(page):
            continue
        fm = lw.parse_frontmatter(page)
        if isinstance(fm, dict) and fm.get("bibkey"):
            keys.add(str(fm["bibkey"]))
        body = lw._strip_code(page.read_text(encoding="utf-8", errors="replace"))
        body = re.sub(r"^---\n.*?\n---", "", body, count=1, flags=re.S)
        for m in lw.CITE_RE.finditer(body):
            if not lw.QUARTO_XREF.match(m.group(1)):
                keys.add(m.group(1))

    out = root / "output"
    if out.is_dir():
        for f in sorted(out.rglob("*.qmd")):
            if not lw._not_build(f):
                continue
            body = lw._strip_code(f.read_text(encoding="utf-8", errors="replace"))
            for m in lw.CITE_RE.finditer(body):
                if not lw.QUARTO_XREF.match(m.group(1)):
                    keys.add(m.group(1))
    return keys


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--out", type=Path, default=Path("output/bibtex/references.bib"))
    ap.add_argument("--prune", action="store_true",
                    help="strict: keep ONLY what is cited. Default keeps what the "
                         "project already carried (re-drawn from the library, so the "
                         "library's verified metadata propagates).")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    root = args.root.resolve()

    lib = _load("_rs_library", HERE / "library.py")
    try:
        master = lib.master_bib(root)
    except lib.LibraryNotConfigured as e:
        print(f"  ✗ {e}", file=sys.stderr)
        return 1
    if master is None:
        print("  ✗ the library has no references.bib", file=sys.stderr)
        return 1

    zb = _load("_rs_zbib", HERE / "lint-wiki.py")
    text = master.read_text(encoding="utf-8")
    entries: dict[str, str] = {}
    for m in re.finditer(r"@([a-zA-Z]+)\s*\{\s*([^,\s{}]+)\s*,", text):
        opened = text.find("{", m.start())
        depth = 0
        for j in range(opened, len(text)):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    entries[m.group(2)] = text[m.start():j + 1]
                    break

    wanted = cited_keys(root)

    # By default, KEEP what the project already carried. A research bibliography is
    # what you have collected, not merely what you have cited so far — most of these
    # are acquired-but-not-yet-ingested sources, and `literaturguide.md` still lists
    # them.
    #
    # The stronger reason: every entry is re-drawn from the MASTER bib, so the
    # library's verified metadata propagates into the project. Dropping an entry and
    # letting a later `ingest-source` re-derive it from the PDF would throw away that
    # verification — and this migration alone fixed four real errors (a DOI that does
    # not resolve, a wrong title, two wrong page ranges).
    #
    # --prune opts into the strict cited-only subset.
    if out_existing := (root / args.out if not args.out.is_absolute() else args.out):
        if not args.prune and out_existing.is_file():
            had = set(re.findall(r"@[a-zA-Z]+\s*\{\s*([^,\s{}]+)\s*,",
                                 out_existing.read_text(encoding="utf-8", errors="replace")))
            kept = had & set(entries)
            orphans = sorted(had - set(entries))
            if orphans:
                # In the project's bib but in NO library entry. Not droppable in
                # silence: if anything cites one, the manuscript renders ??? .
                print(f"  ⚠ {len(orphans)} entry(ies) are in this project's bib but in NO "
                      f"library entry — they are NOT carried over:")
                for k in orphans[:8]:
                    print(f"      {k}")
                print("    Add them to the library, or drop them from the project.")
            wanted |= kept

    unknown = sorted(wanted - set(entries))
    if unknown:
        # Loud on purpose: a dropped entry becomes ??? in the rendered manuscript,
        # and Quarto exits 0 while doing it.
        print(f"  ✗ {len(unknown)} cited key(s) are in NO library entry:", file=sys.stderr)
        for k in unknown[:10]:
            print(f"      @{k}", file=sys.stderr)
        print(f"\n    Add them to {master}, or fix the citation.", file=sys.stderr)
        return 1

    out = (root / args.out) if not args.out.is_absolute() else args.out
    body = "\n\n".join(entries[k] for k in sorted(wanted)) + "\n"

    if args.check:
        old = out.read_text(encoding="utf-8") if out.is_file() else ""
        if old == body:
            print(f"  ✓ {out} is up to date ({len(wanted)} entries)")
            return 0
        print(f"  ✗ {out} differs from the library — re-run bib-subset.py")
        return 1

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body, encoding="utf-8")
    print(f"  ✓ wrote {out} — {len(wanted)} of {len(entries)} library entries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
