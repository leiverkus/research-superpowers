#!/usr/bin/env python3
"""
Add ONE document directly to the shared master library.

WHY THIS EXISTS
---------------
`ingest-source` is the project route: a full read that produces wiki pages, a
project-local BibTeX entry, and — only later, via a maintainer `merge-bibs.py`
run — a master entry. There was no way to say "I have this PDF, just put it in
the library" so it surfaces in `bib-search.py` for every future project, without
that whole machinery and a full read.

This is the deterministic half of that capability. The `add-to-library` SKILL
does the judgement — discover and VERIFY the metadata against Crossref/OpenAlex
(never guessing), and curate keywords from the PDF's docinfo + first-page
abstract. Then it hands the verified fields to this script, which does the
mechanics: compute the canonical bibkey, place the PDF at `<library>/pdf/`, and
append the entry to `<library>/references.bib`.

Two subcommands, dry-run by default (nothing is written without `--write`):

    inspect   read-only: docinfo + first-page text + detected DOIs + whether the
              PDF has a text layer. The skill reads this to decide what to verify.

    commit    compute the bibkey from VERIFIED fields, resolve any collision,
              sha-guard the PDF copy, append the entry. `--write` to act.

SAFETY
------
  * The bibkey comes from `library.make_bibkey`, which RAISES on a missing slot —
    so a half-key is never minted; the skill stops and asks instead.
  * A PDF already at `<library>/pdf/<bibkey>.pdf` with a DIFFERENT sha is NOT
    overwritten without `--force`.
  * Re-adding a work already in the library (matched by DOI) unions its keywords
    into the existing entry rather than duplicating the key.

USAGE
-----
    python scripts/add-to-library.py inspect path/to/paper.pdf --json
    python scripts/add-to-library.py commit --pdf path/to/paper.pdf \
        --author "Finkelstein, Israel" --year 2003 --title "The Low Chronology…" \
        --kurztitel "low chronology" --journal Levant --pages 65-77 \
        --doi 10.1179/lev.2003.35.1.65 --keywords "low chronology; iron age" --write
"""

import argparse
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except AttributeError:  # pragma: no cover
        pass

HERE = Path(__file__).resolve().parent

# A DOI is 10.<registrant>/<suffix>. Kept local (one line) rather than cross-importing
# from the maintainer rename-source-pdfs.py, which is not shipped into a project.
DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", re.I)

# The fields the skill can pass through to the entry, in no particular order —
# library.emit_entry imposes the canonical order. Bookkeeping fields (file,
# abstract, …) are deliberately absent: they have no place in the shared library.
ENTRY_FIELDS = ("author", "editor", "title", "shorttitle", "journal", "booktitle",
                "series", "school", "institution", "publisher", "address", "volume",
                "number", "pages", "year", "isbn", "issn", "url", "doi", "keywords", "note")

_ENTRY_RE = re.compile(r"@([a-zA-Z]+)\s*\{\s*([^,\s{}]+)\s*,")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── PDF signals (cheap — first page only, never a full read) ────────────────

def pdf_meta(pdf: Path) -> dict:
    out = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
    d = {}
    for line in out.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            d[k.strip()] = v.strip()
    return d


def page_text(pdf: Path, first: int, last: int) -> str:
    return subprocess.run(["pdftotext", "-q", "-f", str(first), "-l", str(last), str(pdf), "-"],
                          capture_output=True, text=True).stdout


def inspect(pdf: Path) -> dict:
    """Cheap, read-only signals for the skill to verify against — docinfo, the
    first page's text (where the abstract lives), and any DOI printed on it.
    First two pages only: a full read is exactly what this capability avoids."""
    meta = pdf_meta(pdf)
    pages = int(meta.get("Pages", 0) or 0)
    front = page_text(pdf, 1, min(2, pages)) if pages else ""
    first_page = page_text(pdf, 1, 1) if pages else ""
    dois = []
    for m in DOI_RE.finditer(front):
        d = norm_doi(m.group(0))
        if d and d not in dois:
            dois.append(d)
    return {
        "pdf": str(pdf),
        "page_count": pages,
        # A scanned PDF (image-only) yields almost no extractable text on its
        # front matter: below this floor, treat it as having no text layer, so
        # the skill stops rather than "verifying" against nothing.
        "has_text_layer": len(front.strip()) >= 20,
        "docinfo": {k: meta.get(k, "") for k in ("Title", "Author", "Keywords", "Subject")},
        "producer": f"{meta.get('Producer', '')} {meta.get('Creator', '')}".strip(),
        "dois": dois,
        "first_page_text": first_page.strip(),
    }


# ── BibTeX helpers (local, self-contained — this script is shipped) ─────────

def norm_doi(s: str) -> str:
    if not s:
        return ""
    s = s.strip().lower()
    s = re.sub(r"^https?://(dx\.)?doi\.org/", "", s)
    s = re.sub(r"^doi:\s*", "", s)
    return s.rstrip(".,;)")


def iter_entries(text: str):
    """(key, full_block, etype) for every entry — full_block includes the closing brace."""
    for m in _ENTRY_RE.finditer(text):
        opened = text.find("{", m.start())
        depth = 0
        for j in range(opened, len(text)):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    yield m.group(2), text[m.start():j + 1], m.group(1).lower()
                    break


def field(block: str, name: str) -> str | None:
    """One field's value from an entry block, brace/quote/bare aware."""
    m = re.search(rf"(?:^|[,{{\s]){re.escape(name)}\s*=\s*", block, re.I)
    if not m:
        return None
    i = m.end()
    if i >= len(block):
        return None
    if block[i] == "{":
        depth = 0
        for j in range(i, len(block)):
            if block[j] == "{":
                depth += 1
            elif block[j] == "}":
                depth -= 1
                if depth == 0:
                    return block[i + 1:j].strip()
        return None
    if block[i] == '"':
        j = block.find('"', i + 1)
        return block[i + 1:j].strip() if j > 0 else None
    mm = re.match(r"[^,\n}]+", block[i:])
    return mm.group(0).strip() if mm else None


def surname_of(author: str) -> str:
    """First author's family name from a BibTeX author string."""
    first = re.split(r"\s+and\s+", (author or "").strip())[0].strip()
    if "," in first:
        return first.split(",")[0].strip()
    parts = first.split()
    return parts[-1] if parts else ""


def union_terms(*raws: str) -> list[str]:
    """Case-insensitive union of semicolon-separated keyword strings, first-seen casing."""
    seen: dict[str, str] = {}
    for raw in raws:
        for t in (raw or "").split(";"):
            t = t.strip()
            if t and t.casefold() not in seen:
                seen[t.casefold()] = t
    return list(seen.values())


def set_keywords(block: str, terms: list[str]) -> str:
    """Return the entry block with its `keywords` field set to `terms` — replacing
    an existing keywords field in place, or inserting one before the closing brace.
    Touches only keywords, so no unrelated field is reformatted."""
    value = "; ".join(terms)
    m = re.search(r"(\bkeywords\s*=\s*)(\{[^{}]*\}|\"[^\"]*\"|[^,\n}]+)", block, re.I)
    if m:
        return block[:m.start()] + f"{m.group(1)}{{{value}}}" + block[m.end():]
    idx = block.rfind("}")
    head = block[:idx].rstrip()
    if not head.endswith(","):
        head += ","
    return f"{head}\n  keywords = {{{value}}},\n{block[idx:]}"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


# ── commit ──────────────────────────────────────────────────────────────────

def cmd_commit(args, lib) -> int:
    pdf = args.pdf
    if not pdf.is_file():
        print(f"  ✗ no such PDF: {pdf}", file=sys.stderr)
        return 1

    try:
        library = lib.find_library(args.root.resolve())
    except lib.LibraryNotConfigured as e:
        print(f"  ✗ {e}", file=sys.stderr)
        return 1

    master = library / "references.bib"
    text = master.read_text(encoding="utf-8") if master.is_file() else ""
    entries = {key: (block, etype) for key, block, etype in iter_entries(text)}
    incoming_doi = norm_doi(args.doi)

    # 1. Same work already in the library? DOI is the reliable dedupe key. If it
    #    is already present (possibly under a different kurztitel), union keywords
    #    into that entry rather than mint a second key for the same work.
    doi_match = None
    if incoming_doi:
        for key, (block, _etype) in entries.items():
            if norm_doi(field(block, "doi") or "") == incoming_doi:
                doi_match = key
                break

    # 2. Compute the bibkey from VERIFIED fields (raises on a missing slot).
    if args.bibkey:
        bibkey = args.bibkey
    else:
        try:
            bibkey = lib.make_bibkey(surname_of(args.author), args.year, args.kurztitel)
        except ValueError as e:
            print(f"  ✗ {e}\n    Supply --bibkey explicitly, or fix the metadata and retry.",
                  file=sys.stderr)
            return 1

    new_terms = union_terms(args.keywords)

    # ── keywords-union path: the work is already here ───────────────────────
    union_key = doi_match or (bibkey if bibkey in entries and _same_work(entries[bibkey][0],
                                                                         incoming_doi, args.title)
                              else None)
    if union_key:
        block, _etype = entries[union_key]
        existing_terms = field(block, "keywords") or ""
        merged = union_terms(existing_terms, args.keywords)
        changed = [t for t in merged if t not in union_terms(existing_terms)]
        pdf_target = library / "pdf" / f"{union_key}.pdf"
        print(f"  ↺ already in the library as '{union_key}'"
              + (f" (matched DOI {incoming_doi})" if doi_match else " (same key)"))
        if changed:
            print(f"    keywords += {'; '.join(changed)}")
        else:
            print("    keywords: nothing new to add")
        if not pdf_target.is_file():
            print(f"    ⚠ its PDF is missing at {pdf_target} — placing this file there")
        if not args.write:
            _dry(args, {"action": "keywords-union", "bibkey": union_key,
                        "keywords_added": changed})
            return 0
        if changed:
            new_block = set_keywords(block, merged)
            master.write_text(text.replace(block, new_block, 1), encoding="utf-8")
        if not pdf_target.is_file():
            _place_pdf(pdf, pdf_target, force=args.force)
        _emit_result(args, {"action": "keywords-union", "bibkey": union_key,
                            "keywords_added": changed})
        return 0

    # ── disambiguation: exact key taken by a DIFFERENT work ─────────────────
    if bibkey in entries:
        letter = lib.next_free_letter(entries.keys(), surname_of(args.author), args.year)
        disambiguated = lib.make_bibkey(surname_of(args.author), args.year, args.kurztitel,
                                        letter=letter)
        print(f"  ⚠ '{bibkey}' already denotes a different work in the library.")
        print(f"    Proposing the disambiguated key '{disambiguated}' (letter '{letter}').")
        print("    Confirm this is a genuinely different work before --write.")
        bibkey = disambiguated

    # ── new entry ───────────────────────────────────────────────────────────
    pdf_target = library / "pdf" / f"{bibkey}.pdf"
    fields = {f: getattr(args, f, None) for f in ENTRY_FIELDS if getattr(args, f, None)}
    fields["keywords"] = "; ".join(new_terms) if new_terms else ""
    entry = lib.emit_entry(args.etype, bibkey, fields)

    print(f"  + new entry '{bibkey}'  ({args.etype})")
    print(f"    PDF  → {pdf_target}")
    if pdf_target.is_file() and sha(pdf_target) != sha(pdf):
        print(f"    ⚠ a DIFFERENT file already sits at that path — needs --force")
    print("    entry:")
    for line in entry.splitlines():
        print(f"      {line}")

    if not args.write:
        _dry(args, {"action": "new-entry", "bibkey": bibkey, "pdf_target": str(pdf_target)})
        return 0

    if not _place_pdf(pdf, pdf_target, force=args.force):
        return 1
    new_text = (text.rstrip() + "\n\n" + entry + "\n") if text.strip() else (entry + "\n")
    master.write_text(new_text, encoding="utf-8")
    _emit_result(args, {"action": "new-entry", "bibkey": bibkey, "pdf_target": str(pdf_target)})
    return 0


def _same_work(block: str, incoming_doi: str, incoming_title: str) -> bool:
    """Is this existing entry the SAME work as what we're adding? DOI is decisive;
    with no DOI on either side we cannot be sure, so we say No — and the caller
    then disambiguates rather than risk overwriting a different work under one key."""
    existing_doi = norm_doi(field(block, "doi") or "")
    if existing_doi and incoming_doi:
        return existing_doi == incoming_doi
    return False


def _place_pdf(src: Path, target: Path, *, force: bool) -> bool:
    if target.is_file():
        if sha(target) == sha(src):
            return True                                    # idempotent: already there
        if not force:
            print(f"  ✗ {target.name} already exists with different content — "
                  f"pass --force to overwrite", file=sys.stderr)
            return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, target)
    return True


def _dry(args, result: dict):
    result["wrote"] = False
    print("\n  (dry run — nothing written. Re-run with --write to apply.)")
    if args.json:
        print(json.dumps(result, ensure_ascii=False))


def _emit_result(args, result: dict):
    result["wrote"] = True
    print(f"\n  ✓ done — bibkey '{result['bibkey']}'")
    if args.json:
        print(json.dumps(result, ensure_ascii=False))


# ── inspect ─────────────────────────────────────────────────────────────────

def cmd_inspect(args, _lib) -> int:
    if not args.pdf.is_file():
        print(f"  ✗ no such PDF: {args.pdf}", file=sys.stderr)
        return 1
    result = inspect(args.pdf)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    print(f"  {args.pdf.name}")
    print(f"    pages       : {result['page_count']}")
    print(f"    text layer  : {'yes' if result['has_text_layer'] else 'NO (scanned?)'}")
    for k, v in result["docinfo"].items():
        if v:
            print(f"    {k:<11} : {v[:70]}")
    print(f"    producer    : {result['producer'][:70]}")
    print(f"    DOIs        : {', '.join(result['dois']) or '— none on the first pages —'}")
    if not result["has_text_layer"] and not result["dois"]:
        print("\n  ⚠ No text layer and no DOI: metadata cannot be verified cheaply. "
              "OCR it or add it via ingest-source instead.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=Path("."),
                    help="project root used to resolve the library (default: .)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("inspect", help="cheap read-only PDF signals for verification")
    pi.add_argument("pdf", type=Path)
    pi.add_argument("--json", action="store_true")

    pc = sub.add_parser("commit", help="place the PDF + append the entry (dry-run by default)")
    pc.add_argument("--pdf", type=Path, required=True)
    for f in ENTRY_FIELDS:
        pc.add_argument(f"--{f}", default=None)
    pc.add_argument("--etype", default="article", help="BibTeX entry type (default: article)")
    pc.add_argument("--kurztitel", default=None,
                    help="the chosen short-title word(s) for the bibkey (judgement, not the full title)")
    pc.add_argument("--bibkey", default=None, help="override the computed bibkey")
    pc.add_argument("--write", action="store_true", help="actually write (default: dry run)")
    pc.add_argument("--force", action="store_true", help="overwrite a different PDF at the target path")
    pc.add_argument("--json", action="store_true")

    args = ap.parse_args()
    lib = _load("_rs_library", HERE / "library.py")
    if args.cmd == "inspect":
        return cmd_inspect(args, lib)
    return cmd_commit(args, lib)


if __name__ == "__main__":
    sys.exit(main())
