#!/usr/bin/env python3
"""
Full-text search across the shared source library — one hit per *page*.

WHY PAGES AND NOT DOCUMENTS
---------------------------
A document-level hit ("this paper mentions copper smelting") is nearly useless: you
still have to find the passage in a 40-page PDF. A page-level hit composes with the
rest of the workflow — `drafting-manuscript` reaches back into the source at the
cited pages, and this tells it *which* page to open:

    bib-search "kupferverhüttung arabah"
      → ben-yosef-2019-architecture · p. 12 · …die …Verhüttung… im …Arabah-Tal…

    then: read <library>/pdf/ben-yosef-2019-architecture.pdf at page 12

**The page number is the PHYSICAL page of the PDF** (1-based, as `pdftotext -f`
counts), not the printed page number of the journal. That is exactly what you want
for *reading* the PDF — and exactly what you must NOT cite. Take the printed page
from the page itself; never guess it from this number.

WHERE THE INDEX LIVES — AND WHY NOT IN THE CLOUD
------------------------------------------------
    ~/.cache/research-superpowers/index-<hash>.sqlite

**Local, never in the synced folder.** SQLite and file-sync corrupt each other: the
sync client copies the database file while a write is in flight and has no idea about
transactions or the -wal sidecar. It is the same failure class as a git repo inside
Nextcloud — and this project has already been bitten by that one. The index is a
derived artefact: if it is lost, rebuild it.

`<hash>` is derived from the library path, so two libraries never share an index.

INCREMENTAL
-----------
A PDF is re-extracted only when its size or mtime changed. PDFs that vanished from
the library have their pages purged. Measured on the real library: a first build over
505 documents / 20 422 pages took **11 seconds** and produced a 116 MB index; the next
run, with nothing changed, took 0 s. `pdftotext` is fast and the work parallelises, so
there is no reason to make indexing a rare, ceremonial event — run it after every
acquisition.

SCANS WITHOUT A TEXT LAYER ARE REPORTED, NOT SWALLOWED
------------------------------------------------------
A PDF that yields no text is invisible to search. Silently indexing it as "empty"
would make the library look complete when it is not, so `index` counts them and
`status` lists them. Run OCR on those (`ocrmypdf`) and re-index.

CURATED KEYWORDS — A THIRD MECHANISM, NOT DERIVED FROM THE TEXT
-----------------------------------------------------------------
Full-text search over the PDF (above) and a prototyped semantic/vector index were
both measured against the same failure: a paper that describes a method in prose
without ever naming it is invisible to a lexical query, however many synonyms you
add, and no better reached by an embedding — see
docs/measurements/2026-07-17-semantic-search/README.md for the numbers. Neither
mechanism can close that gap, because both derive their signal from the text.

A `keywords` field on the entry in <library>/references.bib (semicolon-separated,
the Zotero / Better-BibTeX export convention) is a third mechanism: it is not
derived from anything — it records what a human or LLM understood the source to
be about, at ingest time (`ingest-source` writes it). Every search checks it,
always, no separate flag — a keyword hit is microseconds and, being curated, can
only ADD a result, never rank an exact lookup worse. Keyword hits carry
`page: None` (they describe the whole document, not a passage) and print first.

USAGE
-----
    python scripts/bib-search.py index            # build / update (incremental)
    python scripts/bib-search.py index --rebuild  # from scratch
    python scripts/bib-search.py status           # what is indexed, what has no text
    python scripts/bib-search.py "copper smelting"
    python scripts/bib-search.py "edom NEAR/5 yhwh" --limit 30
    python scripts/bib-search.py "shasu" --key tebes-2021-archaeology
    python scripts/bib-search.py "shasu" --json

The query is FTS5 syntax: bare words are AND-ed, `"..."` is a phrase, `OR`/`NOT`/
`NEAR(a b, 5)` work, a trailing `*` is a prefix search. Punctuation that FTS5 would
choke on is quoted automatically.
"""

import argparse
import concurrent.futures
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except AttributeError:  # pragma: no cover
        pass

HERE = Path(__file__).resolve().parent
SCHEMA_VERSION = 2
WORKERS = 8
PDFTOTEXT_TIMEOUT = 180
KEYWORD_HIT_CAP = 200  # safety valve only — curated sets are normally a handful


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── where the index lives ────────────────────────────────────────────────────

def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME")
    return (Path(base) if base else Path.home() / ".cache") / "research-superpowers"


def index_path(library: Path) -> Path:
    h = hashlib.sha1(str(library.resolve()).encode("utf-8")).hexdigest()[:8]
    return cache_dir() / f"index-{h}.sqlite"


# ── extraction ───────────────────────────────────────────────────────────────

def extract_pages(pdf: Path) -> list[str]:
    """The PDF's pages as text, one string per physical page.

    Separate function on purpose: it is the only part that shells out, so the tests
    replace it rather than having to synthesise real PDFs.

    A page that pdftotext cannot read comes back as "" — an empty *page*, not an
    error. A PDF it cannot open at all raises.
    """
    out = subprocess.run(
        ["pdftotext", "-q", "-enc", "UTF-8", str(pdf), "-"],
        capture_output=True, timeout=PDFTOTEXT_TIMEOUT,
    )
    if out.returncode != 0:
        raise RuntimeError((out.stderr or b"").decode("utf-8", "replace").strip()
                           or f"pdftotext exited {out.returncode}")
    text = out.stdout.decode("utf-8", "replace")
    # pdftotext separates pages with a form feed. A trailing one produces a phantom
    # empty page — drop it, or every document gains a page it does not have.
    pages = text.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    return pages


# ── the index ────────────────────────────────────────────────────────────────

class IndexSchemaMismatch(RuntimeError):
    """The index on disk was built by a different SCHEMA_VERSION.

    Raised, never migrated. The index is a *derived* artefact — rebuilding it takes
    seconds and is always correct, whereas a migration is code that runs once, on
    data nobody has any more, and is therefore never tested against the version it
    claims to migrate from. `build()` rebuilds automatically; the read-only entry
    points refuse rather than answer from a schema they do not understand.
    """


def _remove_index(db: Path) -> None:
    """The index and its WAL sidecars. Removing the .sqlite alone leaves the -wal
    behind, and SQLite will happily replay it into the fresh file."""
    db.unlink(missing_ok=True)
    for side in (db.with_suffix(".sqlite-wal"), db.with_suffix(".sqlite-shm")):
        side.unlink(missing_ok=True)


def connect(db: Path) -> sqlite3.Connection:
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db)
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(f"""
        CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
        CREATE TABLE IF NOT EXISTS docs(
            bibkey     TEXT PRIMARY KEY,
            mtime      REAL    NOT NULL,
            size       INTEGER NOT NULL,
            -- pages WITH TEXT, not physical pages. A scan has physical pages and no
            -- text; counting those would hide it from the no-text-layer report, which
            -- is the one thing that must not be quiet.
            pages      INTEGER NOT NULL,   -- 0 = no text layer (a scan) or unreadable
            error      TEXT,
            indexed_at TEXT    NOT NULL
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS pages USING fts5(
            bibkey UNINDEXED, page UNINDEXED, text,
            tokenize='unicode61 remove_diacritics 2'
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS keywords USING fts5(
            bibkey UNINDEXED, keyword,
            tokenize='unicode61 remove_diacritics 2'
        );
        INSERT OR IGNORE INTO meta(k, v) VALUES('schema', '{SCHEMA_VERSION}');
    """)
    # Read it back. The INSERT above is OR IGNORE, so on an existing index it is a
    # no-op and the row still holds the version that BUILT the file — which is the
    # whole point: the CREATE ... IF NOT EXISTS statements above are no-ops too, so
    # an old file keeps its old table shapes while this code assumes the new ones.
    # Without this check a schema bump is invisible and the mismatch surfaces later
    # as a wrong answer instead of an error.
    found = con.execute("SELECT v FROM meta WHERE k = 'schema'").fetchone()
    on_disk = int(found[0]) if found else 0        # 0 = predates versioning
    if on_disk != SCHEMA_VERSION:
        con.close()
        raise IndexSchemaMismatch(
            f"The index was built with schema v{on_disk}, this is v{SCHEMA_VERSION}.\n"
            f"    {db}\n"
            f"    It is derived data — rebuild it:  python scripts/bib-search.py index --rebuild")
    return con


def _index_one(pdf: Path) -> tuple[str, list[str], str | None]:
    try:
        return pdf.stem, extract_pages(pdf), None
    except Exception as e:  # a corrupt PDF must not abort the whole run
        return pdf.stem, [], str(e)[:200]


def build(library: Path, *, rebuild: bool = False, quiet: bool = False) -> dict:
    db = index_path(library)
    if rebuild:
        _remove_index(db)

    try:
        con = connect(db)
    except IndexSchemaMismatch as e:
        # `build` is the one entry point that can *fix* this, so it does. Refusing
        # here would hand the user an unusable index and a flag to guess at, for a
        # change they did not make — and the file is derived, so there is nothing
        # to lose. Say it out loud, though: a silent 11-second rebuild that the
        # user did not ask for should still be visible in the output.
        if not quiet:
            print(f"  – {str(e).splitlines()[0]} Rebuilding from scratch.")
        _remove_index(db)
        con = connect(db)
    con.execute("INSERT OR REPLACE INTO meta(k, v) VALUES('library', ?)", (str(library),))

    pdf_dir = library / "pdf"
    on_disk = {p.stem: p for p in sorted(pdf_dir.glob("*.pdf"))}
    known = {k: (m, s) for k, m, s in con.execute("SELECT bibkey, mtime, size FROM docs")}

    stale = [p for k, p in on_disk.items()
             if k not in known
             or known[k] != (p.stat().st_mtime, p.stat().st_size)]
    gone = sorted(set(known) - set(on_disk))

    for k in gone:
        con.execute("DELETE FROM pages WHERE bibkey = ?", (k,))
        con.execute("DELETE FROM docs  WHERE bibkey = ?", (k,))
    if gone and not quiet:
        print(f"  – {len(gone)} PDF(s) gone from the library — pages purged")

    stats = {"indexed": 0, "pages": 0, "no_text": [], "failed": [],
             "skipped": len(on_disk) - len(stale), "removed": len(gone)}

    if stale:
        if not quiet:
            print(f"  extracting {len(stale)} PDF(s) with pdftotext "
                  f"({stats['skipped']} unchanged, skipped) …")
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        done = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
            for bibkey, pages, err in pool.map(_index_one, stale):
                pdf = on_disk[bibkey]
                st = pdf.stat()
                with_text = [(bibkey, i, t) for i, t in enumerate(pages, 1) if t.strip()]
                con.execute("DELETE FROM pages WHERE bibkey = ?", (bibkey,))
                con.executemany(
                    "INSERT INTO pages(bibkey, page, text) VALUES(?, ?, ?)", with_text)
                con.execute(
                    "INSERT OR REPLACE INTO docs(bibkey, mtime, size, pages, error, indexed_at)"
                    " VALUES(?, ?, ?, ?, ?, ?)",
                    (bibkey, st.st_mtime, st.st_size, len(with_text), err, now))
                if err:
                    stats["failed"].append(bibkey)
                elif not with_text:
                    stats["no_text"].append(bibkey)
                stats["indexed"] += 1
                stats["pages"] += len(with_text)
                done += 1
                if not quiet and done % 25 == 0:
                    print(f"    {done}/{len(stale)}")
                    con.commit()

    # ── curated keywords ────────────────────────────────────────────────────
    # Re-parsed whole on every run, no incremental tracking: ~900 entries costs
    # nothing next to pdftotext extraction, the actual bottleneck. DELETE +
    # reinsert is always correct and simple.
    kw_path = library / "references.bib"
    con.execute("DELETE FROM keywords")
    kw_docs = kw_terms = 0
    if kw_path.is_file():
        lib = _load("_rs_library", HERE / "library.py")
        try:
            by_key = lib.read_keywords(kw_path)
        except Exception as e:  # a malformed master bib must not abort PDF indexing
            by_key = {}
            if not quiet:
                print(f"  – could not read keywords from {kw_path}: {e}")
        rows = [(k, t) for k, terms in by_key.items() for t in terms]
        con.executemany("INSERT INTO keywords(bibkey, keyword) VALUES(?, ?)", rows)
        kw_docs, kw_terms = len(by_key), len(rows)
    stats["keyword_docs"] = kw_docs
    stats["keyword_terms"] = kw_terms

    con.commit()
    con.close()
    return stats


# ── search ───────────────────────────────────────────────────────────────────

_FTS_SAFE = re.compile(r'^[\w\s"*^]+$', re.UNICODE)


def _fallback_query(q: str) -> str:
    """Quote every token so FTS5 treats punctuation as literal.

    A user typing `ben-yosef` or `14C-dating` means a word, not the NOT operator and
    not a syntax error. Rather than second-guess FTS5's grammar, we let it fail and
    retry with everything quoted.
    """
    toks = [t for t in re.split(r"\s+", q.strip()) if t]
    return " ".join('"' + t.replace('"', '""') + '"' for t in toks)


def search(library: Path, query: str, *, limit: int = 20, key: str | None = None) -> list[dict]:
    """`limit` bounds page hits only. Keyword hits (capped separately by
    KEYWORD_HIT_CAP, a safety valve — curated sets are normally a handful) are
    always returned in full and listed first.

    The two are never rank-fused: a keyword table and a page table are two
    different FTS5 corpora, and their BM25 scores are not on a comparable scale
    — the same reason a prototyped semantic index was never merged into this
    search by score (see docs/measurements/2026-07-17-semantic-search/README.md).
    Two independent queries, each sorted by its own rank, concatenated instead.
    """
    db = index_path(library)
    if not db.exists():
        raise FileNotFoundError(
            f"No index yet for {library}.\n"
            f"    Build it:  python scripts/bib-search.py index")
    con = connect(db)

    kw_sql = "SELECT bibkey, keyword, rank FROM keywords WHERE keywords MATCH ?"
    kw_params: list = [query]
    if key:
        kw_sql += " AND bibkey = ?"
        kw_params.append(key)
    kw_sql += " ORDER BY rank LIMIT ?"
    kw_params.append(KEYWORD_HIT_CAP)
    try:
        kw_rows = con.execute(kw_sql, kw_params).fetchall()
    except sqlite3.OperationalError:
        kw_params[0] = _fallback_query(query)
        kw_rows = con.execute(kw_sql, kw_params).fetchall()
    keyword_hits = [{"bibkey": b, "page": None, "snippet": kw, "matched": "keyword"}
                     for b, kw, _ in kw_rows]

    sql = ("SELECT bibkey, page, snippet(pages, 2, '«', '»', ' … ', 14) AS s, rank"
           " FROM pages WHERE pages MATCH ?")
    params: list = [query]
    if key:
        sql += " AND bibkey = ?"
        params.append(key)
    sql += " ORDER BY rank LIMIT ?"
    params.append(limit)
    try:
        rows = con.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        params[0] = _fallback_query(query)
        rows = con.execute(sql, params).fetchall()
    con.close()
    page_hits = [{"bibkey": b, "page": p, "snippet": " ".join(s.split()), "matched": "text"}
                 for b, p, s, _ in rows]

    return keyword_hits + page_hits


def status(library: Path) -> dict:
    db = index_path(library)
    if not db.exists():
        return {"index": str(db), "exists": False}
    con = connect(db)
    docs, pages = con.execute(
        "SELECT COUNT(*), COALESCE(SUM(pages), 0) FROM docs").fetchone()
    no_text = [r[0] for r in con.execute(
        "SELECT bibkey FROM docs WHERE pages = 0 AND error IS NULL ORDER BY bibkey")]
    failed = [(r[0], r[1]) for r in con.execute(
        "SELECT bibkey, error FROM docs WHERE error IS NOT NULL ORDER BY bibkey")]
    keyword_docs, keyword_terms = con.execute(
        "SELECT COUNT(DISTINCT bibkey), COUNT(*) FROM keywords").fetchone()
    con.close()
    return {"index": str(db), "exists": True, "size_mb": round(db.stat().st_size / 1048576, 1),
            "docs": docs, "pages": pages, "no_text": no_text, "failed": failed,
            "keyword_docs": keyword_docs, "keyword_terms": keyword_terms}


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Page-level full-text search across the shared source library.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Page numbers are PHYSICAL PDF pages — right for reading, wrong for citing.")
    ap.add_argument("query", nargs="?", help="FTS5 query, or the sub-command 'index' / 'status'")
    ap.add_argument("--root", type=Path, default=Path("."), help="project root (for .research-library)")
    ap.add_argument("--rebuild", action="store_true", help="index: from scratch")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--key", help="restrict the search to one bibkey")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    lib = _load("_rs_library", HERE / "library.py")
    try:
        library = lib.find_library(args.root.resolve())
    except lib.LibraryNotConfigured as e:
        print(f"  ✗ {e}", file=sys.stderr)
        return 1

    if args.query == "status":
        try:
            st = status(library)
        except IndexSchemaMismatch as e:
            print(f"  ✗ {e}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(st, indent=2, ensure_ascii=False))
            return 0
        if not st["exists"]:
            print(f"  no index yet ({st['index']})")
            print("  build it:  python scripts/bib-search.py index")
            return 0
        print(f"  index   : {st['index']}  ({st['size_mb']} MB)")
        print(f"  library : {library}")
        print(f"  indexed : {st['docs']} document(s), {st['pages']} page(s) with text")
        kw_pct = (st["keyword_docs"] / st["docs"] * 100) if st["docs"] else 0
        print(f"  keywords: {st['keyword_docs']} of {st['docs']} document(s) carry curated "
              f"keywords ({kw_pct:.0f}%), {st['keyword_terms']} term(s) total")
        if st["no_text"]:
            print(f"\n  ⚠ {len(st['no_text'])} PDF(s) have NO text layer — invisible to search.")
            print("    These are scans. OCR them (ocrmypdf) and re-index:")
            for k in st["no_text"][:15]:
                print(f"      {k}")
            if len(st["no_text"]) > 15:
                print(f"      … and {len(st['no_text']) - 15} more (--json for the full list)")
        big = sorted(p.name for p in (library / "pdf").glob("*.pdf")
                     if p.stat().st_size >= 40 * 1024 * 1024)
        if big:
            print(f"\n  ℹ {len(big)} PDF(s) exceed 40 MB — some are bloated "
                  "(over-resolution / uncompressed images), not genuinely large.")
            print("    Check, and shrink reading-lossless, with optimize-pdf.py:")
            print("      python scripts/optimize-pdf.py scan .")
        if st["failed"]:
            print(f"\n  ✗ {len(st['failed'])} PDF(s) could not be read at all:")
            for k, e in st["failed"][:10]:
                print(f"      {k}: {e}")
        return 0

    if args.query == "index":
        if not shutil.which("pdftotext"):
            print("  ✗ pdftotext not found. It ships with poppler:\n"
                  "      macOS:  brew install poppler\n"
                  "      Debian: sudo apt install poppler-utils", file=sys.stderr)
            return 1
        print(f"  library : {library}")
        print(f"  index   : {index_path(library)}  (local cache — never in the synced folder)")
        t0 = time.time()
        st = build(library, rebuild=args.rebuild)
        print(f"\n  ✓ {st['indexed']} document(s) indexed, {st['pages']} page(s) with text "
              f"({st['skipped']} unchanged) in {time.time() - t0:.0f}s")
        if st.get("keyword_docs"):
            print(f"  ✓ {st['keyword_docs']} document(s) carry curated keywords "
                  f"({st['keyword_terms']} term(s) total)")
        if st["no_text"]:
            print(f"  ⚠ {len(st['no_text'])} PDF(s) yielded NO text — scans, invisible to search. "
                  f"See: bib-search.py status")
        if st["failed"]:
            print(f"  ✗ {len(st['failed'])} PDF(s) unreadable. See: bib-search.py status")
        return 0

    if not args.query:
        ap.print_help()
        return 1

    try:
        hits = search(library, args.query, limit=args.limit, key=args.key)
    except (FileNotFoundError, IndexSchemaMismatch) as e:
        print(f"  ✗ {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(hits, indent=2, ensure_ascii=False))
        return 0
    if not hits:
        print(f"  no hits for: {args.query}")
        return 1
    print(f"  {len(hits)} hit(s) — page numbers are PHYSICAL PDF pages, not printed ones\n")
    for h in hits:
        if h["matched"] == "keyword":
            print(f"  {h['bibkey']} · keyword: \"{h['snippet']}\"")
        else:
            print(f"  {h['bibkey']} · p. {h['page']}")
            print(f"      {h['snippet']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
