#!/usr/bin/env python3
"""
Restore the ``bibkey == PDF filename stem`` invariant in ``input/bibliography/``.

WHY THIS EXISTS
---------------
The template has always mandated ``autor-jahr-kurztitel.pdf`` for source PDFs, and
``ingest-source`` HARD-STOPS when it cannot find the original under that name. It
is also how ``drafting-manuscript`` reaches back into the PDF at the cited pages
when a wiki page is too thin — the whole defence against bullet-reflow.

An audit of 17 wikis found **2 of 733 PDFs** conform. The convention was honoured
in the breach, exactly like the citekey convention before it (which is now
enforced by ``lint-wiki.py``). After the citekey migration the two conventions are
the same string, so this is a rename, not a redesign:

    bibkey  finkelstein-2003-low-chronology
    PDF     input/bibliography/finkelstein-2003-low-chronology.pdf

WHY IT IS CAREFUL
-----------------
A PDF renamed onto the WRONG bibkey is worse than one left alone: ``ingest-source``
would then silently read the wrong source, and ``drafting-manuscript`` would quote
the wrong paper at the wrong pages. And ``input/bibliography/*.pdf`` is gitignored,
so **there is no git undo**.

So the tool never guesses. It resolves each PDF through ranked signals and reports
its confidence; anything it cannot settle goes on a worklist for the human instead
of being renamed on a hunch:

    file-field    the bib entry's own ``file = {…}`` points at this PDF   (certain)
    old-bibkey    the stem IS a pre-migration bibkey                      (certain)
    doi           a DOI in the PDF text matches exactly one bib entry     (certain)
    author-year   surname + year in the filename match exactly one key    (high)
    title         the PDF/filename title matches exactly one bib title    (medium)
    —             nothing resolves it                                     (worklist)

The written map IS the undo: every rename is recorded old → new.

Nested PDFs (the older ``<slug>/<slug>.pdf`` layout) are flattened into
``input/bibliography/`` as the template requires.

USAGE
-----
    python scripts/rename-source-pdfs.py plan <project-root> --map-out map.json
    #   *** review map.json — resolve or drop every "unresolved" ***
    python scripts/rename-source-pdfs.py apply <project-root> --map map.json
    python scripts/rename-source-pdfs.py apply <project-root> --map map.json --write

Requires ``pdftotext``/``pdfinfo`` (poppler) for the DOI and title signals; without
them those two signals are skipped and the rest still work.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except AttributeError:  # pragma: no cover
        pass

BUILD_DIRS = ("_output", "_files", ".quarto")
DOI_RE = re.compile(r"10\.\d{4,9}/[^\s,;)>\]}\"']+", re.I)
STOP = {"the", "a", "an", "of", "and", "in", "on", "for", "to", "from", "with", "at",
        "der", "die", "das", "und", "von", "im", "zur", "zum", "des", "ein", "eine"}


# Letters NFKD does NOT decompose — they are distinct letters, not base+diacritic.
# Without an explicit mapping the [^a-z] filter drops them, so the filename
# "Sırmaçek …" (Turkish dotless ı) never matches the key `sirmacek-…`. Must stay in
# step with migrate-citekeys.py: the two tools have to fold names identically or the
# PDF and the bibkey they are supposed to unify can never meet.
_UNDECOMPOSABLE = {
    "ı": "i", "İ": "I", "ł": "l", "Ł": "L", "đ": "d", "Đ": "D",
    "ħ": "h", "Ħ": "H", "ŧ": "t", "ø": "o", "Ø": "O",
    "æ": "ae", "Æ": "Ae", "œ": "oe", "Œ": "Oe",
    "ß": "ss", "þ": "th", "Þ": "Th", "ð": "d", "Ð": "D",
    "ä": "ae", "Ä": "Ae", "ö": "oe", "Ö": "Oe", "ü": "ue", "Ü": "Ue",
}


def deascii(s: str) -> str:
    for src, dst in _UNDECOMPOSABLE.items():
        s = s.replace(src, dst)
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def _brace_value(text: str, i: int):
    if i >= len(text):
        return None
    if text[i] == "{":
        depth = 0
        for j in range(i, len(text)):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    return text[i + 1:j]
        return None
    if text[i] == '"':
        j = text.find('"', i + 1)
        return text[i + 1:j] if j > 0 else None
    m = re.match(r"[^,\s}]+", text[i:])
    return m.group(0) if m else None


def bib_field(body: str, name: str) -> str:
    for m in re.finditer(rf"(?:^|[,{{\s]){name}\s*=\s*", body, re.I):
        v = _brace_value(body, m.end())
        if v is not None:
            return v.strip()
    return ""


def iter_entries(text: str):
    """Brace-balanced — real bibs mix multi-line and single-line entries."""
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


def read_bib(root: Path) -> dict[str, dict]:
    out = {}
    for b in sorted((root / "output").glob("**/*.bib")):
        if any(d in b.parts for d in BUILD_DIRS):
            continue
        for key, body in iter_entries(b.read_text(encoding="utf-8", errors="replace")):
            out[key] = {
                "title": bib_field(body, "title"),
                "doi": bib_field(body, "doi").lower().rstrip("."),
                "file": bib_field(body, "file"),
            }
    return out


def title_words(text: str) -> list[str]:
    t = re.sub(r"\\[a-zA-Z]+", " ", text)
    t = re.sub(r"[{}$\\\"'`^~]", "", t)
    t = deascii(t).lower()
    return [w for w in re.findall(r"[a-z0-9]+", t) if w not in STOP and len(w) > 2]


def pdf_text(path: Path) -> str:
    try:
        r = subprocess.run(["pdftotext", "-f", "1", "-l", "3", str(path), "-"],
                           capture_output=True, text=True, timeout=30)
        return r.stdout if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def pdf_title(path: Path) -> str:
    try:
        r = subprocess.run(["pdfinfo", str(path)], capture_output=True, text=True, timeout=20)
        for line in r.stdout.splitlines():
            if line.lower().startswith("title:"):
                return line.split(":", 1)[1].strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return ""


# --------------------------------------------------------------------------

def resolve(pdf: Path, root: Path, bib: dict, old2new: dict, by_ay: dict,
            by_doi: dict, use_pdf: bool) -> tuple[str | None, str, str]:
    """Return (bibkey|None, signal, note). Never guesses — see the module docstring."""
    stem = pdf.stem

    if stem in bib:
        return stem, "already-ok", ""

    # 1. the bib entry itself points at this file
    for key, e in bib.items():
        if e["file"] and Path(e["file"]).name == pdf.name:
            return key, "file-field", "bib file = field"

    # 2. the stem IS a pre-migration bibkey
    if stem.lower() in old2new:
        return old2new[stem.lower()], "old-bibkey", f"was {stem}"

    # 3. a DOI inside the PDF matching exactly one entry
    if use_pdf and by_doi:
        for doi in {d.lower().rstrip(".") for d in DOI_RE.findall(pdf_text(pdf))}:
            if doi in by_doi:
                return by_doi[doi], "doi", doi

    # 4. surname + year in the filename matching exactly one key
    s = deascii(stem).lower()
    years = re.findall(r"(?:19|20)\d\d", s)
    words = [w for w in re.findall(r"[a-z]+", s) if len(w) > 2]
    hits = {k for y in years for w in words for k in by_ay.get((w, y), [])}
    if len(hits) == 1:
        return hits.pop(), "author-year", ""
    if len(hits) > 1:
        return None, "ambiguous", "matches " + ", ".join(sorted(hits))

    # 5. title overlap — the PDF's own title, else the filename
    if use_pdf:
        cand = pdf_title(pdf) or stem
        pw = set(title_words(cand))
        if len(pw) >= 3:
            scored = []
            for key, e in bib.items():
                bw = set(title_words(e["title"]))
                if not bw:
                    continue
                overlap = len(pw & bw) / max(len(bw), 1)
                if overlap >= 0.6:
                    scored.append((overlap, key))
            scored.sort(reverse=True)
            if len(scored) == 1 or (len(scored) > 1 and scored[0][0] - scored[1][0] >= 0.2):
                return scored[0][1], "title", f"overlap {scored[0][0]:.2f}"
            if len(scored) > 1:
                return None, "ambiguous", "title matches " + ", ".join(k for _, k in scored[:3])

    return None, "unresolved", ""


def cmd_plan(root: Path, map_out: Path, old_map: Path | None, use_pdf: bool) -> int:
    bib = read_bib(root)
    if not bib:
        print("  ✗ no .bib entries found", file=sys.stderr)
        return 1

    old2new = {}
    if old_map and old_map.exists():
        for r in json.loads(old_map.read_text(encoding="utf-8"))["entries"]:
            if r.get("new"):
                old2new[r["old"].lower()] = r["new"]

    by_ay: dict[tuple[str, str], list[str]] = {}
    for k in bib:
        m = re.match(r"^([a-z0-9-]+?)-((?:19|20)\d\d)[a-z]?-", k)
        if m:
            by_ay.setdefault((m.group(1), m.group(2)), []).append(k)
    by_doi = {e["doi"]: k for k, e in bib.items() if e["doi"]}

    pdfs = sorted((root / "input" / "bibliography").rglob("*.pdf"))
    rows, taken = [], {}
    for p in pdfs:
        key, signal, note = resolve(p, root, bib, old2new, by_ay, by_doi, use_pdf)
        rows.append({"pdf": str(p.relative_to(root)), "bibkey": key,
                     "signal": signal, "note": note,
                     "target": f"input/bibliography/{key}.pdf" if key else None})
        if key:
            taken.setdefault(key, []).append(str(p.relative_to(root)))

    # two PDFs claiming the same bibkey is a conflict a human must settle
    for r in rows:
        if r["bibkey"] and len(taken[r["bibkey"]]) > 1:
            r["signal"] = "conflict"
            r["note"] = f"{len(taken[r['bibkey']])} PDFs claim this key"

    counts: dict[str, int] = {}
    for r in rows:
        counts[r["signal"]] = counts.get(r["signal"], 0) + 1

    map_out.parent.mkdir(parents=True, exist_ok=True)
    map_out.write_text(json.dumps({"project": str(root), "renames": rows},
                                  indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"  project : {root}")
    print(f"  PDFs    : {len(pdfs)}   bib entries: {len(bib)}")
    for s in ("already-ok", "file-field", "old-bibkey", "doi", "author-year", "title",
              "ambiguous", "conflict", "unresolved"):
        if counts.get(s):
            print(f"    {s:<14}{counts[s]}")
    todo = counts.get("ambiguous", 0) + counts.get("conflict", 0) + counts.get("unresolved", 0)
    print(f"\n  map written: {map_out}")
    if todo:
        print(f"  → {todo} PDF(s) need a human: set \"bibkey\" by hand, or null to skip.")
    return 0


def cmd_apply(root: Path, map_path: Path, write: bool) -> int:
    data = json.loads(map_path.read_text(encoding="utf-8"))
    bib = read_bib(root)
    moves, skipped = [], 0
    for r in data["renames"]:
        key = r.get("bibkey")
        if not key or r["signal"] == "already-ok":
            skipped += 1
            continue
        if key not in bib:
            raise SystemExit(f"  ✗ {r['pdf']} → '{key}' is in no .bib — refusing")
        src = root / r["pdf"]
        dst = root / "input" / "bibliography" / f"{key}.pdf"
        if not src.exists():
            print(f"  ⚠ missing on disk, skipped: {r['pdf']}")
            continue
        if dst.exists() and dst != src:
            raise SystemExit(f"  ✗ target exists: {dst.relative_to(root)} — refusing to overwrite")
        moves.append((src, dst))

    targets = [d for _, d in moves]
    if len(set(targets)) != len(targets):
        raise SystemExit("  ✗ two PDFs would land on the same filename — fix the map")

    print(f"  {len(moves)} rename(s), {skipped} skipped")
    for src, dst in moves[:10]:
        print(f"    {src.name}\n      → {dst.name}")
    if len(moves) > 10:
        print(f"    … +{len(moves) - 10} more")

    if not write:
        print("\n  DRY RUN — nothing moved. Re-run with --write.")
        return 0

    for src, dst in moves:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
    # drop the now-empty per-source subfolders of the older nested layout
    for d in sorted((root / "input" / "bibliography").rglob("*"), reverse=True):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()
    print(f"  ✓ moved {len(moves)} file(s); the map records every old → new for undo")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("root", type=Path)
    p.add_argument("--map-out", type=Path, required=True)
    p.add_argument("--citekey-map", type=Path, default=None,
                   help="the migrate-citekeys map, so a pre-migration bibkey stem resolves")
    p.add_argument("--no-pdf", action="store_true", help="skip the DOI/title signals")
    a = sub.add_parser("apply")
    a.add_argument("root", type=Path)
    a.add_argument("--map", type=Path, required=True)
    a.add_argument("--write", action="store_true")

    args = ap.parse_args()
    root = args.root.resolve()
    if not (root / "input" / "bibliography").is_dir():
        print(f"  ✗ {root} has no input/bibliography/", file=sys.stderr)
        return 1
    if args.cmd == "plan":
        return cmd_plan(root, args.map_out, args.citekey_map, not args.no_pdf)
    return cmd_apply(root, args.map, args.write)


if __name__ == "__main__":
    sys.exit(main())
