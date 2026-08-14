#!/usr/bin/env python3
"""
Merge every project's ``input/bibliography/*.pdf`` into ONE central library.

WHY
---
Today the same paper sits in up to four projects. That is not just wasted disk: a
metadata error, a corrupt scan, or a truncated extract has to be found and fixed
four times, and in practice never is. One library, one copy, one fix.

The move is only possible because ``bibkey == PDF filename stem`` now holds (see
``rename-source-pdfs.py``): the filename IS the identity, so merging is a rename
into a shared folder, not a guessing game.

    ~/UOLcloud/Bibliothek/pdf/<bibkey>.pdf

WHEN TWO PROJECTS DISAGREE
--------------------------
770 files collapse to 728 keys, so 42 are duplicates — and they are NOT all the
same file:

    identical bytes                    → deduplicate, either copy will do
    same page count, different bytes   → same document, keep the LARGER (better scan)
    different page count               → DIFFERENT FILES. Keep the one with the most
                                         pages, and REPORT it — a human has to look.

That last class is real and it is dangerous. Measured on the live projects:

    james-2019-guidelines        15 pages  vs   4 pages   ← one is an extract
    james-2017-uncertainty       68 pages  vs  20 pages
    marwick-2017-computational   43 / 43   vs  27 pages   ← one is truncated
    zissu-2023-underground       36 pages  vs   0 pages   ← one is CORRUPT

Silently picking the wrong one means every ingest and every page-anchored reach-back
in that project reads the wrong document. So: most pages wins (the most complete
copy), every case is logged, and **nothing is deleted** — the losers go to the
backup directory, which is the undo.

USAGE
-----
    python scripts/build-library.py plan  --roots <p1> <p2> … --map-out map.json
    #   *** read the report — especially the page-count conflicts ***
    python scripts/build-library.py apply --map map.json --library ~/UOLcloud/Bibliothek
    python scripts/build-library.py apply --map map.json --library … --write --backup-dir <path>

``--write`` requires ``--backup-dir``. The map records every source path, so it is
also the undo.

Requires ``pdfinfo`` (poppler) for the page count. Without it, the page-count rule
degrades to "keep the larger file" and every conflict is reported instead.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except AttributeError:  # pragma: no cover
        pass


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pages(path: Path) -> int:
    """Page count via poppler. 0 means 'could not read' — which is itself a finding:
    a 0-page PDF is corrupt, and one such file is live in the projects today."""
    try:
        r = subprocess.run(["pdfinfo", str(path)], capture_output=True, text=True, timeout=30)
        for line in r.stdout.splitlines():
            if line.startswith("Pages:"):
                return int(line.split(":", 1)[1].strip())
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return 0


def collect(roots: list[Path]) -> dict[str, list[Path]]:
    by_key: dict[str, list[Path]] = defaultdict(list)
    for root in roots:
        bib = root / "input" / "bibliography"
        if not bib.is_dir():
            continue
        for pdf in sorted(bib.rglob("*.pdf")):
            by_key[pdf.stem].append(pdf)
    return by_key


def choose(cands: list[Path]) -> tuple[Path, str, list[dict]]:
    """Return (winner, verdict, per-file facts). Never deletes; the caller backs up."""
    facts = [{"path": str(p), "bytes": p.stat().st_size, "pages": pages(p), "sha": sha(p)}
             for p in cands]
    if len(cands) == 1:
        return cands[0], "single", facts

    if len({f["sha"] for f in facts}) == 1:
        return cands[0], "identical", facts

    pg = {f["pages"] for f in facts}
    if len(pg) == 1:
        # Same document, different encoding/producer. The larger file is the better
        # scan often enough, and is never worse.
        best = max(facts, key=lambda f: f["bytes"])
        return Path(best["path"]), "same-pages-larger-wins", facts

    # Genuinely different files. Most pages = most complete. ALWAYS reported.
    best = max(facts, key=lambda f: (f["pages"], f["bytes"]))
    return Path(best["path"]), "CONFLICT-most-pages-wins", facts


def cmd_plan(roots: list[Path], map_out: Path) -> int:
    # A root that does not exist globs to nothing WITHOUT an error, so a path the
    # shell mangled (word-splitting inside a directory name with spaces) would
    # just shrink the plan invisibly. Same failure the merge had; same hard stop.
    missing = [r for r in roots if not r.is_dir()]
    if missing:
        print(f"  ✗ {len(missing)} of {len(roots)} project root(s) do not exist:",
              file=sys.stderr)
        for m in missing:
            print(f"      {m}", file=sys.stderr)
        print("    Quote paths that contain spaces.", file=sys.stderr)
        return 2

    by_key = collect(roots)
    if not by_key:
        print("  ✗ no PDFs found under any <root>/input/bibliography/", file=sys.stderr)
        return 1

    rows, counts = [], defaultdict(int)
    conflicts = []
    for key in sorted(by_key):
        winner, verdict, facts = choose(by_key[key])
        counts[verdict] += 1
        rows.append({"bibkey": key, "verdict": verdict, "winner": str(winner),
                     "candidates": facts})
        if verdict == "CONFLICT-most-pages-wins":
            conflicts.append((key, facts, winner))

    total = sum(len(v) for v in by_key.values())
    print(f"  source PDFs : {total}")
    print(f"  distinct keys: {len(by_key)}")
    for v in ("single", "identical", "same-pages-larger-wins", "CONFLICT-most-pages-wins"):
        if counts[v]:
            print(f"    {v:<28}{counts[v]}")

    if conflicts:
        print(f"\n  ⚠ {len(conflicts)} key(s) where the files genuinely DIFFER — "
              f"most pages wins, losers go to the backup:\n")
        for key, facts, winner in conflicts:
            print(f"    {key}")
            for f in sorted(facts, key=lambda x: -x["pages"]):
                mark = "→ KEEP" if f["path"] == str(winner) else "  drop"
                proj = "/".join(Path(f["path"]).parts[-5:-3])
                warn = "  ⚠ CORRUPT (0 pages)" if f["pages"] == 0 else ""
                print(f"      {mark}  {f['pages']:>3} pages  {f['bytes']//1024:>6} KB  {proj}{warn}")

    map_out.parent.mkdir(parents=True, exist_ok=True)
    map_out.write_text(json.dumps({"entries": rows}, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    print(f"\n  map written: {map_out}")
    return 0


def cmd_apply(map_path: Path, library: Path, write: bool, backup: Path | None) -> int:
    data = json.loads(map_path.read_text(encoding="utf-8"))
    rows = data["entries"]
    if write and not backup:
        raise SystemExit("  ✗ --write requires --backup-dir (the losers must land somewhere)")

    pdf_dir = library / "pdf"
    copies, backups = [], []
    for r in rows:
        src = Path(r["winner"])
        if not src.is_file():
            print(f"  ⚠ missing on disk, skipped: {src}")
            continue
        copies.append((src, pdf_dir / f"{r['bibkey']}.pdf"))
        for c in r["candidates"]:
            p = Path(c["path"])
            if str(p) != str(src):
                backups.append(p)

    print(f"  {len(copies)} file(s) → {pdf_dir}")
    print(f"  {len(backups)} loser(s) → backup")
    for src, dst in copies[:6]:
        print(f"    {src.name}")
    if len(copies) > 6:
        print(f"    … +{len(copies) - 6} more")

    if not write:
        print("\n  DRY RUN — nothing copied. Re-run with --write --backup-dir <path>.")
        return 0

    pdf_dir.mkdir(parents=True, exist_ok=True)
    backup.mkdir(parents=True, exist_ok=True)
    for src, dst in copies:
        # COPY, not move: the projects keep working until Phase 3 removes their PDFs.
        # A half-migrated state must never leave a project without its sources.
        if not dst.exists() or sha(src) != sha(dst):
            shutil.copy2(src, dst)
    for p in backups:
        # Flatten with the project in the name, so two 'james-2019-guidelines.pdf'
        # do not collide in the backup either.
        proj = "-".join(p.parts[-5:-3]) or "unknown"
        shutil.copy2(p, backup / f"{proj}--{p.name}")

    print(f"\n  ✓ {len(copies)} PDF(s) in {pdf_dir}")
    print(f"  ✓ {len(backups)} loser(s) in {backup} — nothing was deleted")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--roots", nargs="+", type=Path, required=True)
    p.add_argument("--map-out", type=Path, required=True)
    a = sub.add_parser("apply")
    a.add_argument("--map", type=Path, required=True)
    a.add_argument("--library", type=Path, required=True)
    a.add_argument("--write", action="store_true")
    a.add_argument("--backup-dir", type=Path, default=None)

    args = ap.parse_args()
    if args.cmd == "plan":
        return cmd_plan([r.resolve() for r in args.roots], args.map_out)
    return cmd_apply(args.map, args.library.expanduser().resolve(),
                     args.write, args.backup_dir.expanduser() if args.backup_dir else None)


if __name__ == "__main__":
    sys.exit(main())
