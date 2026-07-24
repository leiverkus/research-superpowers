#!/usr/bin/env python3
"""
Shrink oversized library PDFs — for reading, not for the archive.

WHY THIS EXISTS
---------------
Every PDF reaches the shared library the same way — `add-to-library`, `acquire-sources`,
or a manual VPN download — and every one of those writes `<library>/pdf/<bibkey>.pdf`
byte-for-byte as it arrived. Nothing ever looked at the *size*. Publishers ship wildly
inconsistent files: a 25-page remote-sensing article whose figures are stored at 1877 ppi
(118 MB), a print-production chapter in CMYK at 1200 ppi, a colour textbook whose plates
are stored uncompressed. On one live corpus the master library carried ~1.4 GB of pure
byte-bloat this way — the same works, at the same visible quality, in a fraction of the space.

That matters for a *shared* library specifically:

  * the whole thing syncs to every teammate (Nextcloud today, Git LFS tomorrow);
  * under LFS every replaced version is kept forever, so a churny 300-MB file is 300 MB
    of history each time it changes.

THE RECIPE (and why Ghostscript, not ocrmypdf)
----------------------------------------------
The bloat is almost always *resolution*: images stored far above what a screen or a printer
can show (300 ppi is already past both). Ghostscript re-distills the PDF, downsampling images
over ~450 ppi to 300 and re-encoding at JPEG quality 90; it converts print CMYK to sRGB.
Crucially it operates on image objects, so the **text layer and the page count survive** —
page numbers, and therefore every printed-page citation, are unchanged. `ocrmypdf --optimize`
was measured on the same files and only recompresses at the *original* resolution: on the
1877-ppi article it reached 27 MB where Ghostscript reached 3 (identical on screen).

This is not lossless, and does not pretend to be. It is *reading-lossless*: the pristine
publisher file remains re-fetchable by DOI via `acquire-sources`. Treat the library as a
reading-and-citation corpus, not an archival master — that is the deliberate trade.

GUARDRAILS (measured the hard way)
----------------------------------
  * MEASURE FIRST. `scan` only reports; it never changes a file. Estimates are a floor —
    the real number comes from `optimize`.
  * ONLY WHEN BLOATED. A clean 300-ppi grayscale scan gains nothing and is left alone.
    `optimize` refuses a file that is not flagged unless `--force`.
  * SELF-VERIFY, KEEP THE ORIGINAL ON DOUBT. After Ghostscript, the page count must match
    and the extractable text must stay above THRESHOLD. If either fails, the optimised copy
    is discarded and the original is kept — a shrunk file whose text layer broke is worse
    than a big one. (A large *benign* text drop happens too — e.g. a duplicated
    "FOR PEER REVIEW" draft layer being cleaned up — so a failed check means *ask a human*,
    not *the file is ruined*.)
  * A HUMAN STILL LOOKS AT A FIGURE. Bytes and page counts do not see JPEG mush. For the
    aggressive shrinks, render a figure page and compare before trusting a batch.

USAGE
-----
    python scripts/optimize-pdf.py scan <library>            # report bloated candidates only
    python scripts/optimize-pdf.py scan <library> --json
    python scripts/optimize-pdf.py check <pdf>               # diagnose one file
    python scripts/optimize-pdf.py optimize <pdf>            # write <pdf>.optimized.pdf + verify
    python scripts/optimize-pdf.py optimize <pdf> --replace  # swap in place iff verified (.orig kept)
    python scripts/optimize-pdf.py optimize <pdf> --force    # optimise even if not flagged

Needs Ghostscript (`gs`) plus poppler (`pdfinfo`/`pdftotext`/`pdfimages`). Without them the
tool reports what is missing and does nothing.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# ── thresholds, all justified in the docstring ──────────────────────────────
TARGET_PPI = 300          # screen/print need; images above ~1.5× this get downsampled
OVERRES_PPI = 400         # median image ppi above this ⇒ over-resolution candidate
RAW_MB_PER_PAGE = 1.2     # this dense at ≤ OVERRES_PPI ⇒ raw-stored images (recodec win)
CMYK_MIN = 5              # this many CMYK images ⇒ print-production file
MIN_FLAG_MB = 15.0        # ignore small files; the win is not worth the churn
MIN_SAVE_MB = 8.0         # a candidate must plausibly save at least this much
TEXT_KEEP = 0.90          # optimised text length must stay ≥ this fraction of the original
JPEG_Q = 90               # Ghostscript JPEG quality for downsampled colour/gray images


# ── PDF readers (shelled out; stubbed wholesale in the tests) ───────────────
def pdf_pages(path: str) -> int:
    """Physical page count via pdfinfo, or 0 if unreadable."""
    try:
        out = subprocess.run(["pdfinfo", path], capture_output=True, text=True, timeout=60).stdout
        m = re.search(r"^Pages:\s*(\d+)", out, re.M)
        return int(m.group(1)) if m else 0
    except Exception:
        return 0


def pdf_text_len(path: str) -> int:
    """Length of the extractable text layer via pdftotext, or 0."""
    try:
        return len(subprocess.run(["pdftotext", path, "-"], capture_output=True, timeout=300).stdout)
    except Exception:
        return 0


def pdf_image_stats(path: str) -> dict:
    """Median/max image ppi and CMYK count via `pdfimages -list`.

    Returns {median_ppi, max_ppi, cmyk, n_images}. Empty on any failure.
    """
    try:
        out = subprocess.run(["pdfimages", "-list", path],
                             capture_output=True, text=True, timeout=300).stdout
    except Exception:
        return {"median_ppi": 0, "max_ppi": 0, "cmyk": 0, "n_images": 0}
    ppis, cmyk, n = [], 0, 0
    for line in out.splitlines()[2:]:            # skip the two header rows
        c = line.split()
        if len(c) < 14:
            continue
        n += 1
        if c[5] == "cmyk":
            cmyk += 1
        if c[12].isdigit() and int(c[12]) > 0:
            ppis.append(int(c[12]))
    ppis.sort()
    return {"median_ppi": ppis[len(ppis) // 2] if ppis else 0,
            "max_ppi": ppis[-1] if ppis else 0, "cmyk": cmyk, "n_images": n}


# ── classification: PURE, so the tests can pin it without a real PDF ────────
def classify(mb: float, pages: int, median_ppi: int, cmyk: int) -> dict:
    """Decide whether a file is bloated and estimate the recoverable megabytes.

    The three bloat shapes seen on real corpora, in priority order:
      over-resolution — images far above 300 ppi; downsampling scales bytes ~ (300/ppi)²
      raw-storage     — dense MB/page at normal ppi ⇒ images stored uncompressed; recodec
      cmyk            — print-production colour; convert to sRGB (and usually downsample)
    Returns {flagged, reason, est_saved_mb}.
    """
    mbpp = mb / pages if pages else mb
    reason, est = "", 0.0
    if median_ppi > OVERRES_PPI:                       # downsampling scales bytes ~ (300/ppi)²
        keep = max((TARGET_PPI / median_ppi) ** 2, 0.05)
        reason, est = "over-resolution", mb * (1 - keep) * 0.9
    elif mbpp > RAW_MB_PER_PAGE and mb >= MIN_FLAG_MB:  # dense at normal ppi ⇒ raw-stored
        reason, est = "raw-storage", mb * 0.5
    elif cmyk >= CMYK_MIN and mb >= MIN_FLAG_MB:        # print-production colour
        reason, est = "cmyk", mb * 0.4
    # The gate is the *recoverable* size, not the file size: a small over-resolution
    # PDF can still be worth it, a big clean one is not.
    if est >= MIN_SAVE_MB:
        return {"flagged": True, "reason": reason, "est_saved_mb": round(est, 1)}
    return {"flagged": False, "reason": "", "est_saved_mb": 0.0}


def diagnose(path: str) -> dict:
    """Full per-file diagnosis: size + geometry + classification."""
    mb = os.path.getsize(path) / 1e6
    pages = pdf_pages(path)
    img = pdf_image_stats(path)
    d = {"file": os.path.basename(path), "mb": round(mb, 1), "pages": pages,
         "mb_per_page": round(mb / pages, 2) if pages else 0.0,
         "median_ppi": img["median_ppi"], "max_ppi": img["max_ppi"],
         "cmyk": img["cmyk"], "n_images": img["n_images"]}
    d.update(classify(mb, pages, img["median_ppi"], img["cmyk"]))
    return d


# ── Ghostscript + verification ──────────────────────────────────────────────
def gs_args(src: str, dst: str, cmyk: bool) -> list:
    """The re-distill command. CMYK files also get converted to sRGB."""
    a = ["gs", "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.6",
         "-dDownsampleColorImages=true", f"-dColorImageResolution={TARGET_PPI}",
         "-dColorImageDownsampleType=/Bicubic", "-dColorImageDownsampleThreshold=1.5",
         "-dDownsampleGrayImages=true", f"-dGrayImageResolution={TARGET_PPI}",
         "-dGrayImageDownsampleType=/Bicubic", "-dGrayImageDownsampleThreshold=1.5",
         "-dDownsampleMonoImages=true", f"-dMonoImageResolution={TARGET_PPI}",
         f"-dJPEGQ={JPEG_Q}", "-dAutoRotatePages=/None",
         "-dNOPAUSE", "-dBATCH", "-dQUIET"]
    if cmyk:
        a.append("-sColorConversionStrategy=RGB")
    a += [f"-sOutputFile={dst}", src]
    return a


def verify(src_pages: int, src_text: int, dst_pages: int, dst_text: int) -> dict:
    """The optimised file is trustworthy iff the page count is identical and the text
    layer survived. Returns {ok, reason, text_ratio}."""
    ratio = dst_text / src_text if src_text else 1.0
    if dst_pages != src_pages:
        return {"ok": False, "reason": f"page count changed {src_pages}→{dst_pages}",
                "text_ratio": round(ratio, 3)}
    if ratio < TEXT_KEEP:
        return {"ok": False, "reason": f"text layer dropped to {ratio:.0%} — inspect manually",
                "text_ratio": round(ratio, 3)}
    return {"ok": True, "reason": "", "text_ratio": round(ratio, 3)}


def optimize_file(src: str, dst: str) -> dict:
    """Run Ghostscript src→dst and verify. Never touches src. Returns a result dict;
    on a failed verification `dst` is removed so nothing broken is left behind."""
    d = diagnose(src)
    cmyk = d["cmyk"] >= CMYK_MIN
    sp, st = pdf_pages(src), pdf_text_len(src)
    try:
        subprocess.run(gs_args(src, dst, cmyk), capture_output=True, timeout=1800)
    except Exception as e:
        return {"ok": False, "reason": f"ghostscript failed: {e}", "old_mb": d["mb"], "new_mb": 0.0}
    if not os.path.exists(dst) or os.path.getsize(dst) == 0:
        return {"ok": False, "reason": "ghostscript produced no output", "old_mb": d["mb"], "new_mb": 0.0}
    v = verify(sp, st, pdf_pages(dst), pdf_text_len(dst))
    new_mb = os.path.getsize(dst) / 1e6
    if not v["ok"]:
        os.remove(dst)
        return {"ok": False, "reason": v["reason"], "old_mb": d["mb"], "new_mb": round(new_mb, 1),
                "text_ratio": v["text_ratio"]}
    return {"ok": True, "reason": "", "old_mb": d["mb"], "new_mb": round(new_mb, 1),
            "text_ratio": v["text_ratio"], "cmyk": cmyk}


# ── commands ────────────────────────────────────────────────────────────────
def cmd_scan(library: Path, as_json: bool) -> int:
    pdfs = sorted((library / "pdf").glob("*.pdf"))
    if not pdfs:
        print(f"  no PDFs under {library}/pdf", file=sys.stderr)
        return 1
    rows = [diagnose(str(p)) for p in pdfs]
    cands = sorted((r for r in rows if r["flagged"] and r["est_saved_mb"] >= MIN_SAVE_MB),
                   key=lambda r: -r["est_saved_mb"])
    total = sum(r["mb"] for r in rows)
    pot = sum(r["est_saved_mb"] for r in cands)
    if as_json:
        print(json.dumps({"total_mb": round(total, 1), "n_pdfs": len(rows),
                          "candidates": cands, "est_saved_mb": round(pot, 1)}, ensure_ascii=False))
        return 0
    print(f"  library : {library}  ({len(rows)} PDFs, {total/1024:.2f} GB)")
    print(f"  candidates (est. ≥ {MIN_SAVE_MB:.0f} MB each): {len(cands)}")
    print(f"  estimated recoverable: ~{pot/1024:.2f} GB (a floor — measure with `optimize`)\n")
    if cands:
        print(f"  {'file':44}{'MB':>6}{'pg':>5}{'ppi':>6}{'~save':>7}  reason")
        for r in cands[:40]:
            print(f"  {r['file'][:42]:44}{r['mb']:>6.0f}{r['pages']:>5}"
                  f"{r['median_ppi']:>6}{r['est_saved_mb']:>7.0f}  {r['reason']}")
        if len(cands) > 40:
            print(f"  … and {len(cands) - 40} more (--json for all)")
    return 0


def cmd_check(pdf: str) -> int:
    d = diagnose(pdf)
    print(json.dumps(d, ensure_ascii=False, indent=2))
    return 0


def cmd_optimize(pdf: str, replace: bool, force: bool) -> int:
    d = diagnose(pdf)
    if not d["flagged"] and not force:
        print(f"  {d['file']}: not flagged as bloated "
              f"({d['mb']:.0f} MB, {d['median_ppi']} ppi) — nothing to do (use --force to override).")
        return 0
    dst = pdf[:-4] + ".optimized.pdf" if pdf.lower().endswith(".pdf") else pdf + ".optimized.pdf"
    res = optimize_file(pdf, dst)
    if not res["ok"]:
        print(f"  ✗ {os.path.basename(pdf)}: {res['reason']} — original kept, no change.")
        return 1
    saved = res["old_mb"] - res["new_mb"]
    print(f"  ✓ {os.path.basename(pdf)}: {res['old_mb']:.0f} → {res['new_mb']:.0f} MB "
          f"(−{saved:.0f} MB), text {res['text_ratio']:.0%}, pages preserved.")
    if replace:
        bak = pdf + ".orig"
        if not os.path.exists(bak):
            shutil.copy2(pdf, bak)
        shutil.move(dst, pdf)
        print(f"    replaced in place; original saved as {os.path.basename(bak)}.")
        print("    re-index so the change is picked up:  python scripts/bib-search.py index")
    else:
        print(f"    wrote {os.path.basename(dst)} (original untouched). "
              f"Eyeball a figure, then --replace or move it into place.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Shrink oversized library PDFs (reading-lossless).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan", help="report bloated candidates in a library (no changes)")
    s.add_argument("library", type=Path)
    s.add_argument("--json", action="store_true")
    c = sub.add_parser("check", help="diagnose a single PDF")
    c.add_argument("pdf")
    o = sub.add_parser("optimize", help="optimise a single PDF, self-verifying")
    o.add_argument("pdf")
    o.add_argument("--replace", action="store_true", help="swap in place iff verified (.orig kept)")
    o.add_argument("--force", action="store_true", help="optimise even if not flagged")
    args = ap.parse_args(argv)

    missing = [t for t in ("gs", "pdfinfo", "pdftotext", "pdfimages") if not shutil.which(t)]
    if missing and args.cmd in ("scan", "check", "optimize"):
        need = "ghostscript" if "gs" in missing else "poppler"
        print(f"  ✗ missing: {', '.join(missing)} (install {need}). Nothing done.", file=sys.stderr)
        return 1

    if args.cmd == "scan":
        return cmd_scan(args.library, args.json)
    if args.cmd == "check":
        return cmd_check(args.pdf)
    if args.cmd == "optimize":
        return cmd_optimize(args.pdf, args.replace, args.force)
    return 2


if __name__ == "__main__":
    sys.exit(main())
