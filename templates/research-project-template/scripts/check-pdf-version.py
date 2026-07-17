#!/usr/bin/env python3
"""
Is this PDF the published article, or the author's manuscript?

WHY THIS EXISTS
---------------
`acquire-sources` downloads Open-Access PDFs. Green OA — the copy an author deposits in
a repository — is very often **not** the typeset article but the *accepted manuscript*:
double-spaced, single-column, figures appended as bare "Figure 1." placeholders, and
crucially **no printed page numbers**.

Nothing checked which version landed on disk. That is a quiet, load-bearing failure:

  * `ingest-source` requires a printed page anchor on every quote. From a manuscript
    there is none — so the anchor gets invented, and an invented page number is *worse*
    than none: it is checkable, it is wrong, and it looks like grounding.
  * `drafting-manuscript` reaches back into the PDF at the cited page. On a manuscript
    that page holds different text.

Found on the live corpus: of four sources dispatched for ingest in one project, **two**
were accepted manuscripts. Both agents refused to write rather than fabricate anchors —
but only because they were told to look. This script is what makes them look.

THE SIGNALS
-----------
No single one is decisive. A typeset article can be text-only; a manuscript can carry
page numbers. The script scores them and reports the evidence, so a human decides:

  cover-sheet      "Accepted Manuscript", "peer reviewed version of the following
                   article", "postprint" … in the first two pages          — decisive
  repository       an arXiv / eScholarship / institutional-repository stamp on the
                   first pages — a deposited copy with no printed journal pages — decisive
  no-figures       the body says "Figure N" but the PDF embeds NO images   — very strong
  word-producer    Producer/Creator is Microsoft Word                      — strong
                   (publishers typeset with 3B2, Arbortext, SPi, TeX …)
  page-count       physical pages ≥ 1.5 × the printed page range in the .bib — strong
  no-running-head  the journal name never appears after page 1             — weak
  line-numbers     many bare numerals per page (submission line numbering) — weak

USAGE
-----
    python scripts/check-pdf-version.py                    # every PDF in the library
    python scripts/check-pdf-version.py --key riris-2017-towards
    python scripts/check-pdf-version.py --suspect-only     # just the ones to look at
    python scripts/check-pdf-version.py --json

Exit code is 0 even when suspects are found: this is a worklist, not a broken build.
"""

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except AttributeError:  # pragma: no cover
        pass

HERE = Path(__file__).resolve().parent

COVER = re.compile(
    r"accepted manuscript|author'?s? (accepted|final|original) (manuscript|version)|"
    r"post-?print|this is the peer[- ]reviewed version|"
    r"this is a pdf file of an unedited manuscript|"
    r"submitted (manuscript|version)|author accepted manuscript", re.I)

TYPESETTERS = re.compile(r"3b2|arbortext|spi\b|springer|elsevier|atypon|tex|latex|"
                         r"pdftex|xetex|indesign|quark|apex|newgen|integra|thomson digital",
                         re.I)
WORDLIKE = re.compile(r"microsoft.{0,3}word|word 20\d\d|libreoffice|openoffice|pages", re.I)

# A repository / preprint stamp on the first pages is decisive on its own: the file is
# a deposited copy, NOT the typeset article, so it carries no printed journal page
# numbers — the exact failure that makes a page anchor invented. arXiv stamps every
# page "arXiv:NNNN.NNNNN"; eScholarship and White-Rose-style IRs announce themselves on
# a cover sheet; bio/medRxiv stamp a preprint banner. (Found live: forte-2012 was an
# eScholarship manuscript and vanetten-2020 an arXiv preprint — both slipped through as
# "ok", and their source pages cited physical PDF positions as if they were printed pages.)
REPO_STAMP = re.compile(
    r"arxiv:\s*\d{4}\.\d{4,5}"           # arXiv preprint stamp (left margin of every page)
    r"|escholarship(?:\.org)?"           # UC eScholarship institutional-repository cover
    r"|this is a repository copy of"     # White Rose and the many IRs that clone its cover
    r"|(?:bio|med)rxiv preprint",        # bioRxiv / medRxiv preprint banner
    re.I)


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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


def image_count(pdf: Path) -> int:
    out = subprocess.run(["pdfimages", "-list", str(pdf)], capture_output=True, text=True).stdout
    # header is 2 lines; anything after is one image per line
    return max(0, len(out.strip().splitlines()) - 2)


def bib_pages(bib_text: str, key: str) -> tuple[int, int] | None:
    m = re.search(r"@\w+\{\s*" + re.escape(key) + r"\s*,", bib_text)
    if not m:
        return None
    start = bib_text.find("{", m.start())
    depth = 0
    for j in range(start, len(bib_text)):
        if bib_text[j] == "{":
            depth += 1
        elif bib_text[j] == "}":
            depth -= 1
            if depth == 0:
                body = bib_text[m.start():j + 1]
                break
    else:
        return None
    pm = re.search(r"\bpages\s*=\s*[{\"]\s*(\d+)\s*-+\s*(\d+)", body)
    return (int(pm.group(1)), int(pm.group(2))) if pm else None


def inspect(pdf: Path, printed: tuple[int, int] | None = None) -> dict:
    """Score one PDF. Returns the evidence, never a bare verdict."""
    meta = pdf_meta(pdf)
    pages = int(meta.get("Pages", 0) or 0)
    head = page_text(pdf, 1, min(2, pages)) if pages else ""
    body = page_text(pdf, 2, min(8, pages)) if pages > 1 else ""

    signals: list[str] = []

    if COVER.search(head):
        signals.append("cover-sheet: the PDF says so itself")

    repo = REPO_STAMP.search(head)
    if repo:
        signals.append(f"repository-version: '{repo.group(0).strip()[:32]}' "
                       f"— a deposited copy, no printed journal pagination")

    producer = f"{meta.get('Producer', '')} {meta.get('Creator', '')}"
    if WORDLIKE.search(producer) and not TYPESETTERS.search(producer):
        signals.append(f"word-producer: {producer.strip()[:48]}")

    mentions_figs = len(re.findall(r"\bfig(?:ure)?\.?\s*\d", body, re.I))
    imgs = image_count(pdf)
    if mentions_figs >= 3 and imgs == 0:
        signals.append(f"no-figures: text names {mentions_figs} figures, PDF embeds 0 images")

    if printed and pages:
        span = printed[1] - printed[0] + 1
        if span > 0 and pages / span >= 1.5:
            signals.append(f"page-count: {pages} physical vs {span} printed "
                           f"({printed[0]}–{printed[1]}), factor {pages / span:.1f}")

    # Weak, corroborating only — NEVER enough on its own. Bare numerals on their own
    # line look like submission line-numbering, but a numbered reference list produces
    # exactly the same pattern: this signal alone flagged a genuine typeset article
    # (kempf-2023-point, 45 numbered references) as a manuscript. A false positive here
    # is expensive — it sends the user hunting for a version of record they already have.
    weak: list[str] = []
    if pages >= 5:
        bare = len(re.findall(r"(?m)^\s*\d{1,3}\s*$", page_text(pdf, 5, 5)))
        if bare > 20:
            weak.append(f"line-numbers?: {bare} bare numerals on one page "
                        f"(could equally be a numbered reference list)")

    strong = len(signals)
    return {
        "pdf": pdf.name,
        "pages": pages,
        "images": imgs,
        "producer": producer.strip(),
        "printed": list(printed) if printed else None,
        "signals": signals + (weak if strong else []),   # weak evidence only alongside strong
        # Decisive only when the document announces itself, or when two independent
        # structural tells agree. One strong tell = "look at it", not "it is a manuscript".
        "verdict": ("manuscript" if any(s.startswith(("cover-sheet", "repository-version"))
                                         for s in signals)
                    or strong >= 2
                    else "suspect" if strong == 1
                    else "ok"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--key", help="check one bibkey only")
    ap.add_argument("--suspect-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    lib = _load("_rs_library", HERE / "library.py")
    try:
        library = lib.find_library(args.root.resolve())
    except lib.LibraryNotConfigured as e:
        print(f"  ✗ {e}", file=sys.stderr)
        return 1

    master = library / "references.bib"
    bib_text = master.read_text(encoding="utf-8") if master.is_file() else ""

    pdfs = sorted((library / "pdf").glob("*.pdf"))
    if args.key:
        pdfs = [p for p in pdfs if p.stem == args.key]
        if not pdfs:
            print(f"  ✗ no PDF for '{args.key}' in the library", file=sys.stderr)
            return 1

    results = [inspect(p, bib_pages(bib_text, p.stem)) for p in pdfs]

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 0

    bad = [r for r in results if r["verdict"] != "ok"]
    shown = bad if args.suspect_only else results
    for r in shown:
        mark = {"manuscript": "✗", "suspect": "⚠", "ok": "✓"}[r["verdict"]]
        print(f"  {mark} {r['pdf'][:-4]}")
        for s in r["signals"]:
            print(f"      {s}")

    n_ms = sum(r["verdict"] == "manuscript" for r in results)
    n_su = sum(r["verdict"] == "suspect" for r in results)
    print(f"\n  {len(results)} PDF(s): {len(results) - n_ms - n_su} ok · "
          f"{n_su} suspect · {n_ms} manuscript")
    if n_ms or n_su:
        print("\n  A manuscript carries NO printed page numbers. Any page anchor taken from")
        print("  one is invented — and an invented anchor is worse than none, because it is")
        print("  checkable and wrong. Acquire the version of record, or ingest with")
        print("  `based_on: preprint` and section-number locators.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
