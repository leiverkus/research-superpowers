#!/usr/bin/env python3
"""Forward search: who answered this work, and what did its author write later?

A literature search by topic finds what was written ABOUT a question. It does
not find what was written IN REPLY to a given work, and it does not find the
same author's later statement on the matter. Both are what decides whether an
older position is still the state of research — and both went missing in a
live project: a wiki held a 2020 article while the chapter that answers that
position cited the author's 2022 restatement, which had never been ingested.

For each work given (a bibkey or a DOI) this script asks three questions:

  1. Which works cite it?            OpenAlex, `filter=cites:<work>`
  2. Which of the works I already own mention it?
                                     the shared library's full-text index
  3. What has its first author published since?   (--author)
                                     OpenAlex, `filter=authorships.author.id`

Neither source is complete, and the script says so in its output. OpenAlex's
citation data is thin for monographs and edited volumes — on one checked case
it listed 39 citing works and missed two chapters that demonstrably cite the
target. The library index knows only what you own. An empty answer therefore
means "nothing found", never "nobody answered".

The script decides nothing. It lists candidates; which of them engage the work
is read off the texts, at ingest (`responds-to` / `supersedes` / `revises`).

Usage:
    python scripts/forward-search.py bartlett-1999-edomites
    python scripts/forward-search.py 10.1179/peq.1999.131.2.102 --author
    python scripts/forward-search.py key1 key2 --since 2015 --json

OpenAlex needs no key for occasional use. Set OPENALEX_API_KEY for a larger
budget; no e-mail address is sent (the `mailto` polite pool ended in 2026).

Stdlib only.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.openalex.org"
USER_AGENT = "research-superpowers-forward-search"
PER_PAGE = 200
MAX_CITING = 600          # a work cited more often than this needs a narrower question
TIMEOUT = 30
HERE = Path(__file__).resolve().parent

DOI_RE = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:)?(10\.\d{4,9}/\S+)$", re.I)
# Publishers register a DOI per book PART — front matter, index, every chapter —
# and each part "cites" whatever the bibliography cites. One monograph then
# shows up seventeen times. The parts share a stem that ends in the ISBN.
BOOK_STEM_RE = re.compile(r"^(10\.\d{4,9}/(?:97[89])?\d{9,10})[./]")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── BibTeX, just enough to turn a bibkey into a DOI / title / author / year ──

def iter_bib_entries(text: str):
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


def bib_field(body: str, name: str) -> str:
    for m in re.finditer(rf"(?:^|[,{{\s]){name}\s*=\s*", body, re.I):
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
                        return body[i + 1:j].strip()
        elif body[i] == '"':
            j = body.find('"', i + 1)
            if j > 0:
                return body[i + 1:j].strip()
        else:
            mm = re.match(r"[^,\s}]+", body[i:])
            if mm:
                return mm.group(0).strip()
    return ""


def norm_doi(raw: str) -> str:
    m = DOI_RE.match((raw or "").strip())
    return m.group(1).rstrip(".,;").lower() if m else ""


def read_bibs(paths: list[Path]) -> dict[str, dict]:
    """bibkey → {doi, title, author, year}. Earlier paths win on a clash."""
    out: dict[str, dict] = {}
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for key, body in iter_bib_entries(text):
            if key in out:
                continue
            clean = lambda s: re.sub(r"[{}]", "", s).strip()
            out[key] = {"doi": norm_doi(bib_field(body, "doi")),
                        "title": clean(bib_field(body, "title")),
                        "author": clean(bib_field(body, "author") or bib_field(body, "editor")),
                        "year": clean(bib_field(body, "year"))[:4]}
    return out


def first_surname(author_field: str) -> str:
    first = re.split(r"\s+and\s+", author_field or "", maxsplit=1)[0].strip()
    if not first:
        return ""
    return first.split(",")[0].strip() if "," in first else first.split()[-1]


# ── OpenAlex ────────────────────────────────────────────────────────────────

def http_get(path: str, params: dict) -> dict:
    """One GET against OpenAlex. Kept as a single seam so tests can replace it."""
    params = {k: v for k, v in params.items() if v not in (None, "")}
    key = os.environ.get("OPENALEX_API_KEY")
    if key:
        params["api_key"] = key
    url = f"{API}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


WORK_FIELDS = "id,doi,display_name,publication_year,type,authorships,cited_by_count"


def slim(work: dict) -> dict:
    authors = [a.get("author", {}).get("display_name") or ""
               for a in work.get("authorships") or []]
    return {"openalex": (work.get("id") or "").rsplit("/", 1)[-1],
            "doi": norm_doi(work.get("doi") or ""),
            "title": work.get("display_name") or "",
            "year": work.get("publication_year"),
            "type": work.get("type") or "",
            "authors": [a for a in authors if a]}


def _norm_title(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def find_work(target: dict, get=http_get) -> tuple[dict | None, str]:
    """Locate the target in OpenAlex. Returns (work, how) — `how` is "doi",
    "title" (matched by title and year, so less certain) or a reason it failed."""
    if target.get("doi"):
        try:
            return get(f"/works/doi:{target['doi']}", {"select": WORK_FIELDS}), "doi"
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
    title, year = target.get("title") or "", target.get("year") or ""
    if not title:
        return None, "no DOI on record and no title to search by"
    flt = f"title.search:{re.sub(r'[,:|]', ' ', title)}"
    if year.isdigit():
        flt += f",publication_year:{year}"
    hits = get("/works", {"filter": flt, "per-page": 5, "select": WORK_FIELDS}).get("results") or []
    want = _norm_title(title)
    for w in hits:
        have = _norm_title(w.get("display_name") or "")
        if have and (have == want or have.startswith(want) or want.startswith(have)):
            return w, "title"
    return None, "not found in OpenAlex"


def citing_works(work_id: str, since: int | None = None, get=http_get) -> tuple[list[dict], int]:
    """All works citing `work_id`, newest first. Returns (works, total reported)."""
    flt = f"cites:{work_id}"
    if since:
        flt += f",from_publication_date:{since}-01-01"
    out, cursor, total = [], "*", 0
    while cursor and len(out) < MAX_CITING:
        page = get("/works", {"filter": flt, "sort": "publication_date:desc",
                              "per-page": PER_PAGE, "cursor": cursor, "select": WORK_FIELDS})
        total = (page.get("meta") or {}).get("count", total)
        results = page.get("results") or []
        out.extend(results)
        cursor = (page.get("meta") or {}).get("next_cursor") if results else None
    return out, total


def later_works(author_id: str, after_year: int, get=http_get, limit: int = 50) -> list[dict]:
    page = get("/works", {"filter": f"authorships.author.id:{author_id},"
                                    f"from_publication_date:{after_year + 1}-01-01",
                          "sort": "publication_date:desc", "per-page": limit,
                          "select": WORK_FIELDS})
    return page.get("results") or []


def collapse_book_parts(works: list[dict]) -> list[dict]:
    """Fold the parts of one book into one row.

    The row kept is the book itself when it is in the list (its DOI is the
    stem), otherwise the part with the most authors named — a chapter with an
    author says more than "Index of Personal Names". `parts` counts what was
    folded, so the reader can see that a row stands for several records."""
    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    for w in works:
        doi = w.get("doi") or ""
        m = BOOK_STEM_RE.match(doi + ".")
        key = m.group(1) if m else (doi or w.get("openalex") or w.get("title") or "")
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(w)
    out = []
    for key in order:
        group = groups[key]
        head = next((w for w in group if (w.get("doi") or "") == key), None) \
            or max(group, key=lambda w: (len(w.get("authors") or []), len(w.get("title") or "")))
        row = dict(head)
        if len(group) > 1:
            row["parts"] = len(group)
            if not row.get("authors"):
                row["authors"] = next((w["authors"] for w in group if w.get("authors")), [])
        out.append(row)
    return out


def mark_owned(works: list[dict], owned_by_doi: dict[str, str]) -> None:
    """Add `bibkey` to every work already in a .bib. A book part counts as owned
    when the book is."""
    for w in works:
        doi = w.get("doi") or ""
        key = owned_by_doi.get(doi)
        if not key:
            m = BOOK_STEM_RE.match(doi + ".")
            key = owned_by_doi.get(m.group(1)) if m else None
        if key:
            w["bibkey"] = key


# ── the library's full-text index ───────────────────────────────────────────

def library_mentions(target: dict, own_key: str | None, root: Path) -> tuple[list[dict], str]:
    """Owned works whose text names the target. Returns (hits, note)."""
    surname = first_surname(target.get("author") or "")
    year = target.get("year") or ""
    if not surname or not year:
        return [], "no author/year on record — library not searched"
    try:
        lib = _load("library", HERE / "library.py")
        bs = _load("bib_search", HERE / "bib-search.py")
        library = lib.find_library(root, required=False)
        if library is None:
            return [], "no shared library configured"
        sur = re.sub(r'["()]', " ", surname)
        queries = [f'"{sur} {year}"']
        words = re.findall(r"\w+", target.get("title") or "")[:3]
        if len(words) == 3:
            queries.append(f'NEAR({sur} "{" ".join(words)}", 20)')
        hits = bs.search(library, queries[0], limit=200, variants=queries[1:])
    except Exception as e:                      # index missing, FTS syntax, …
        return [], f"library search failed: {e}"
    pages: dict[str, set] = {}
    for h in hits:
        if h.get("matched") != "text" or h.get("bibkey") == own_key:
            continue
        pages.setdefault(h["bibkey"], set()).add(h.get("page"))
    out = [{"bibkey": k, "pages": sorted(p for p in v if p is not None)}
           for k, v in sorted(pages.items())]
    return out, f'full-text query {" | ".join(queries)}'


# ── one target, start to finish ─────────────────────────────────────────────

def forward(token: str, bibs: dict[str, dict], root: Path, *, author: bool, since: int | None,
            use_library: bool = True, use_openalex: bool = True, get=http_get) -> dict:
    doi = norm_doi(token)
    key = None if doi else token
    if doi:
        key = next((k for k, v in bibs.items() if v["doi"] == doi), None)
        target = dict(bibs.get(key) or {"doi": doi, "title": "", "author": "", "year": ""})
        target["doi"] = doi
    elif token in bibs:
        target = dict(bibs[token])
    else:
        return {"target": token, "error": f"not a DOI and not a bibkey in the {len(bibs)} "
                                           "entries read from output/**/*.bib and the "
                                           "library's master bib"}

    res: dict = {"target": token, "bibkey": key, "doi": target.get("doi") or "",
                 "title": target.get("title") or "", "year": target.get("year") or "",
                 "notes": []}
    owned = {v["doi"]: k for k, v in bibs.items() if v["doi"]}

    if use_openalex:
        try:
            work, how = find_work(target, get)
            if work is None:
                res["notes"].append(f"OpenAlex: {how}")
            else:
                res["openalex"] = slim(work)["openalex"]
                res["title"] = res["title"] or work.get("display_name") or ""
                res["year"] = res["year"] or str(work.get("publication_year") or "")
                if how == "title":
                    res["notes"].append("OpenAlex: matched by title and year, not by DOI — "
                                        "check that it is the same work")
                raw, total = citing_works(res["openalex"], since, get)
                cited = collapse_book_parts([slim(w) for w in raw])
                mark_owned(cited, owned)
                res["cited_by"] = cited
                res["cited_by_records"] = total
                if total > len(raw):
                    res["notes"].append(f"OpenAlex lists {total} citing records; only the "
                                        f"newest {len(raw)} were read — narrow with --since")
                if author and work.get("authorships"):
                    a = work["authorships"][0].get("author") or {}
                    aid = (a.get("id") or "").rsplit("/", 1)[-1]
                    year = work.get("publication_year")
                    if aid and year:
                        later = collapse_book_parts(
                            [slim(w) for w in later_works(aid, int(year), get)])
                        mark_owned(later, owned)
                        res["author"] = a.get("display_name") or ""
                        res["later_by_author"] = later
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            res["notes"].append(f"OpenAlex request failed: {e}")

    if use_library:
        if not target.get("author"):
            target["author"] = res.get("author") or ""
        target["title"], target["year"] = res["title"], res["year"]
        hits, note = library_mentions(target, key, root)
        res["library_mentions"] = hits
        res["notes"].append(f"Library: {note}")
    return res


def render(res: dict) -> str:
    if res.get("error"):
        return f"✗ {res['target']}: {res['error']}\n"
    lines = [f"=== {res['bibkey'] or res['doi']} — {res['title'] or '(untitled)'} ({res['year'] or 'n.d.'})"]

    def row(w):
        who = (w["authors"][0] if w.get("authors") else "?") + (" et al." if len(w.get("authors") or []) > 1 else "")
        own = f"  ● {w['bibkey']}" if w.get("bibkey") else ""
        parts = f"  [{w['parts']} records]" if w.get("parts") else ""
        ref = w.get("doi") or w.get("openalex") or ""
        return f"  {w.get('year') or 'n.d.'}  {who}: {(w.get('title') or '')[:90]}  {ref}{parts}{own}"

    if "cited_by" in res:
        new = sum(1 for w in res["cited_by"] if not w.get("bibkey"))
        lines.append(f"Cited by — OpenAlex: {len(res['cited_by'])} work(s) "
                     f"from {res['cited_by_records']} record(s); {new} not in your .bib")
        lines += [row(w) for w in res["cited_by"]] or ["  (none listed)"]
    if "library_mentions" in res:
        lines.append(f"Named in works you own — library full text: {len(res['library_mentions'])}")
        for h in res["library_mentions"]:
            pages = ", ".join(str(p) for p in h["pages"][:12]) + (" …" if len(h["pages"]) > 12 else "")
            lines.append(f"  ● {h['bibkey']}  (PDF p. {pages})")
    if "later_by_author" in res:
        lines.append(f"Later works by {res['author']}: {len(res['later_by_author'])} "
                     f"(all topics — pick the ones on this question)")
        lines += [row(w) for w in res["later_by_author"]]
    for n in res["notes"]:
        lines.append(f"  note: {n}")
    lines.append("  Neither list is complete: OpenAlex is thin on monographs and edited volumes, "
                 "and the library\n  index knows only what you own. Nothing found is not the same "
                 "as nobody answered.")
    return "\n".join(lines) + "\n"


BUILD_DIRS = ("_output", "_files", ".quarto", "node_modules")


def bib_paths(root: Path) -> list[Path]:
    """Every .bib under output/ (the same rule lint-wiki.py uses — projects do
    not all keep theirs at output/bibtex/), then the library's master bib."""
    out = root / "output"
    paths = sorted(p for p in out.glob("**/*.bib")
                   if not any(d in p.parts for d in BUILD_DIRS)) if out.is_dir() else []
    try:
        lib = _load("library", HERE / "library.py")
        master = lib.master_bib(root, required=False)
        if master:
            paths.append(master)
    except Exception:
        pass
    return [p for p in paths if p.exists()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("works", nargs="+", help="bibkeys or DOIs")
    ap.add_argument("--root", type=Path, default=Path("."), help="project root")
    ap.add_argument("--author", action="store_true",
                    help="also list what the first author published afterwards")
    ap.add_argument("--since", type=int, help="only citing works from this year on")
    ap.add_argument("--no-library", action="store_true", help="skip the library full-text pass")
    ap.add_argument("--no-openalex", action="store_true", help="skip OpenAlex (offline)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    bibs = read_bibs(bib_paths(args.root))
    results = [forward(t, bibs, args.root, author=args.author, since=args.since,
                       use_library=not args.no_library, use_openalex=not args.no_openalex)
               for t in args.works]
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print("\n".join(render(r) for r in results))
    return 1 if all(r.get("error") for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
