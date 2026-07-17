#!/usr/bin/env python3
"""
Resolve the path to the shared source library.

WHY A CONFIG FILE AND NOT A SYMLINK
-----------------------------------
The obvious move is ``ln -s ~/UOLcloud/Bibliothek input/bibliography`` — and it is
wrong twice over:

1. **Symlinks need administrator rights on Windows.** This plugin's CI tests on
   Windows, and a workflow that only works for admins is not a workflow.
2. ``input/bibliography/`` is **mixed-ownership**: the PDFs are shared and gitignored,
   but ``literaturguide.md``, ``acquisition-todo.md`` and the audit logs are
   per-project and **tracked**. Symlinking the folder would drag tracked artefacts
   into the shared library.

So the PDFs move out to the library and the folder keeps its text artefacts. The
library path is machine-local — it differs between your laptop and the institute
machine — and therefore must never be committed.

RESOLUTION ORDER
----------------
1. ``RESEARCH_LIBRARY``           — environment variable (this is what CI sets)
2. ``<project>/.research-library`` — one line, gitignored
3. ``~/.config/research-superpowers/library``

The library itself:

    <library>/references.bib      the master bibliography
    <library>/pdf/<bibkey>.pdf    one PDF per source; the filename IS the citekey

USAGE (from any script in this folder)
--------------------------------------
    from library import find_library, pdf_for

    lib = find_library()                    # raises LibraryNotConfigured with a
                                            # message telling the user what to do
    pdf = pdf_for("finkelstein-2003-low-chronology")   # None if absent
"""

import os
import re
import string
import unicodedata
from pathlib import Path

CONFIG_NAME = ".research-library"
GLOBAL_CONFIG = Path.home() / ".config" / "research-superpowers" / "library"
ENV_VAR = "RESEARCH_LIBRARY"


class LibraryNotConfigured(RuntimeError):
    """Raised when no library path can be resolved.

    Carries an actionable message on purpose: the failure a user actually hits is
    `ingest-source` hard-stopping, and "PDF not found" would send them hunting for a
    file when the real problem is that this machine has never been told where the
    library lives.
    """


def _read(path: Path) -> str | None:
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                return line
    except OSError:
        pass
    return None


def find_library(project_root: Path | None = None, *, required: bool = True) -> Path | None:
    """Resolve the library root. `required=False` returns None instead of raising —
    for advisory checks (lint) that must not fail a build on an unconfigured machine."""
    root = Path(project_root or Path.cwd())

    candidates: list[str] = []
    env = os.environ.get(ENV_VAR)
    if env:
        candidates.append(env)
    local = _read(root / CONFIG_NAME)
    if local:
        candidates.append(local)
    glob = _read(GLOBAL_CONFIG)
    if glob:
        candidates.append(glob)

    for c in candidates:
        p = Path(c).expanduser()
        if p.is_dir():
            return p.resolve()

    if not required:
        return None

    tried = "\n".join(f"      {c}" for c in candidates) or "      (nothing configured)"
    raise LibraryNotConfigured(
        "The shared source library is not configured on this machine.\n\n"
        f"    Tried:\n{tried}\n\n"
        "    Point this project at it — one line, no trailing slash:\n\n"
        f"      echo '/path/to/Bibliothek' > {root / CONFIG_NAME}\n\n"
        f"    or set {ENV_VAR}, or write the path to {GLOBAL_CONFIG}.\n"
        f"    ({CONFIG_NAME} is gitignored: the path is machine-local and must not be committed.)"
    )


def pdf_dir(project_root: Path | None = None, *, required: bool = True) -> Path | None:
    lib = find_library(project_root, required=required)
    return (lib / "pdf") if lib else None


def pdf_for(bibkey: str, project_root: Path | None = None) -> Path | None:
    """The PDF for a bibkey, or None. The whole point of `bibkey == filename stem`:
    no globbing, no fuzzy matching, no guessing."""
    d = pdf_dir(project_root, required=False)
    if not d:
        return None
    p = d / f"{bibkey}.pdf"
    return p if p.is_file() else None


def master_bib(project_root: Path | None = None, *, required: bool = True) -> Path | None:
    lib = find_library(project_root, required=required)
    if not lib:
        return None
    p = lib / "references.bib"
    return p if p.is_file() else None


_ENTRY_RE = re.compile(r"@[a-zA-Z]+\s*\{\s*([^,\s{}]+)\s*,")
_KEYWORDS_FIELD_RE = re.compile(r"(?:^|[,{\s])keywords\s*=\s*", re.I)


def _field_value(text: str, i: int) -> str | None:
    """Read a BibTeX field value at text[i]: {braced}, "quoted", or a bare token."""
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


def read_keywords(bib_path: Path) -> dict[str, list[str]]:
    """{bibkey: [keyword phrase, ...]} for every entry carrying a `keywords` field.

    Semicolon-separated (the Zotero / Better-BibTeX export convention), each
    phrase trimmed and deduplicated case-insensitively within an entry (first-seen
    casing wins). Entries with no `keywords` field are absent from the result, not
    present with an empty list.

    Never raises on malformed content: an entry whose braces never balance is
    skipped, not guessed at — the same discipline the sibling brace-depth
    scanners in this repo (merge-bibs.py, migrate-citekeys.py, bib-subset.py) all
    follow. This is a fourth copy of that idiom, not an oversight: the other
    three live in maintainer-only scripts/, never shipped into a project, so
    nothing there is importable from here.

    A bibkey defined twice in the master bib is already a hard error caught
    separately by lint-wiki.py's DUPLICATE-KEY-IN-LIBRARY check — this reader
    does not duplicate that detection; a second definition simply overwrites the
    first, BibTeX's own last-wins behaviour.
    """
    text = bib_path.read_text(encoding="utf-8", errors="replace")
    out: dict[str, list[str]] = {}
    for m in _ENTRY_RE.finditer(text):
        bibkey = m.group(1)
        opened = text.find("{", m.start())
        depth, end = 0, None
        for j in range(opened, len(text)):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    end = j
                    break
        if end is None:
            continue                                  # unbalanced tail — skip, never guess
        body = text[m.end():end]
        km = _KEYWORDS_FIELD_RE.search(body)
        if not km:
            continue
        raw = _field_value(body, km.end())
        if not raw:
            continue
        seen: dict[str, str] = {}                      # casefolded -> first-seen rendering
        for term in raw.split(";"):
            term = term.strip()
            if term and term.casefold() not in seen:
                seen[term.casefold()] = term
        if seen:
            out[bibkey] = list(seen.values())
    return out


# --------------------------------------------------------------------------
# Canonical bibkey generation  (autor-jahr-kurztitel)
# --------------------------------------------------------------------------
# The bibkey IS the PDF filename stem and the cross-project join key, so the
# same work must yield the same key in every project and every tool. The
# folding table and stopword list below are copied VERBATIM from the maintainer
# scripts/migrate-citekeys.py: that script is not importable from here (it lives
# in maintainer-only scripts/, never shipped into a project), so this is a
# deliberate second copy that must stay byte-identical, not an oversight — the
# same reasoning read_keywords() gives for the brace scanner. If you change one,
# change both, or a migrated key and a directly-added key for the same work stop
# matching and the join breaks silently.

STOPWORDS = {
    "the", "a", "an", "of", "and", "in", "on", "for", "to", "from", "with", "at",
    "der", "die", "das", "und", "von", "im", "zur", "zum", "des", "ein", "eine",
    "la", "le", "les", "el", "del", "al", "il", "un", "une", "y", "e",
}

# Letters NFKD does NOT decompose, because they are distinct letters and not
# "base + combining diacritic". Without an explicit mapping the [^a-z] filter
# drops them silently, mangling the surname: Turkish "Sırmaçek" → "srmacek",
# Polish "Trybała" → "trybaa". Both happened.
_UNDECOMPOSABLE = {
    "ı": "i", "İ": "I",          # Turkish dotless / dotted i
    "ł": "l", "Ł": "L",          # Polish stroked l
    "đ": "d", "Đ": "D",          # Croatian / Vietnamese stroked d
    "ħ": "h", "Ħ": "H",          # Maltese
    "ŧ": "t", "ø": "o", "Ø": "O",
    "æ": "ae", "Æ": "Ae", "œ": "oe", "Œ": "Oe",
    "ß": "ss", "þ": "th", "Þ": "Th", "ð": "d", "Ð": "D",
    "ä": "ae", "Ä": "Ae", "ö": "oe", "Ö": "Oe", "ü": "ue", "Ü": "Ue",
}


def deascii(s: str) -> str:
    """Fold to ASCII the way the PDF-filename rule does (ä→ae, ß→ss, é→e).

    The explicit table comes FIRST: NFKD only splits base+diacritic, so a letter
    like ı or ł survives it untouched and is then dropped by the [^a-z] filter —
    silently shortening the surname and minting a key nobody can guess.
    """
    for src, dst in _UNDECOMPOSABLE.items():
        s = s.replace(src, dst)
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def propose_shorttitle(title: str, words: int = 3) -> str | None:
    """A *suggestion* for the kurztitel: the first significant title words,
    stopwords dropped, deascii'd, lowercased, hyphen-joined. None if the title
    yields nothing usable.

    Only a starting point — the kurztitel is a human/LLM judgement, NOT a
    deterministic function of the title. "The Low Chronology and the Problem of
    the Archaeology of Iron Age Palestine" has the short title `low-chronology`,
    but the first three significant words give `low-chronology-problem`. So this
    proposes; the caller chooses. (This is why the default is multi-word, unlike
    migrate-citekeys.py's words=1 — a single word is almost never the right key.)
    """
    if not title:
        return None
    text = deascii(re.sub(r"[{}\\$]", "", title)).lower()
    parts = [w for w in re.findall(r"[a-z0-9]+", text) if w not in STOPWORDS and len(w) > 2]
    return "-".join(parts[:words]) if parts else None


def make_bibkey(surname: str, year: str, shorttitle: str, letter: str = "") -> str:
    """Assemble the canonical `autor-jahr[letter]-kurztitel` key.

    `surname` is folded to ASCII and stripped to [a-z] (particles and spaces
    collapse: "van der Toorn" → `vandertoorn`); `year` is the first 4-digit year
    found; `shorttitle` is the CHOSEN kurztitel (see propose_shorttitle) folded
    and slugified. `letter` is an optional disambiguation letter that goes AFTER
    the year (see next_free_letter).

    Raises ValueError when a slot cannot be filled — deliberately, so the skill
    stops and asks rather than minting a key from missing data.
    """
    sur = re.sub(r"[^a-z]", "", deascii(str(surname)).lower())
    ym = re.search(r"(1[0-9]{3}|20[0-9]{2})", str(year))
    slug = "-".join(re.findall(r"[a-z0-9]+", deascii(str(shorttitle)).lower()))
    missing = [n for n, v in (("surname", sur), ("year", ym), ("shorttitle", slug)) if not v]
    if missing:
        raise ValueError("cannot build a bibkey — missing " + ", ".join(missing))
    if letter and not re.fullmatch(r"[a-z]", letter):
        raise ValueError(f"disambiguation letter must be a single a–z character, got {letter!r}")
    return f"{sur}-{ym.group(1)}{letter}-{slug}"


def next_free_letter(existing_keys, surname: str, year: str) -> str:
    """Lowest disambiguation letter free for a NEW `surname-year-*` work.

    Scans the existing keys for `surname-year([a-z]?)-…`, treating the bare-year
    incumbent as occupying the no-letter slot, and returns the lowest a–z letter
    not yet used. The incumbent is never re-lettered — its key is a live PDF
    filename and may already be cited — so the newcomer always takes a letter.
    """
    sur = re.sub(r"[^a-z]", "", deascii(str(surname)).lower())
    ym = re.search(r"(1[0-9]{3}|20[0-9]{2})", str(year))
    if not (sur and ym):
        raise ValueError("cannot disambiguate — missing surname or year")
    pat = re.compile(rf"^{re.escape(sur)}-{ym.group(1)}([a-z]?)-")
    used = {m.group(1) for k in existing_keys if (m := pat.match(k))}
    for c in string.ascii_lowercase:
        if c not in used:
            return c
    raise ValueError(f"ran out of disambiguation letters for {sur}-{ym.group(1)}")


# --------------------------------------------------------------------------
# BibTeX entry emission  (byte-format identical to scripts/merge-bibs.py)
# --------------------------------------------------------------------------
# Kept in step with merge-bibs.py FIELD_ORDER + entry-writing loop, so an entry
# appended directly to the master by add-to-library.py and the same entry
# re-rendered by a later merge-bibs run are byte-for-byte identical — no spurious
# diff on the shared references.bib.
BIB_FIELD_ORDER = ["author", "editor", "title", "shorttitle", "journal", "booktitle",
                   "series", "school", "institution", "publisher", "address", "volume",
                   "number", "pages", "year", "isbn", "issn", "url", "doi", "keywords", "note"]


def emit_entry(etype: str, key: str, fields: dict) -> str:
    """One BibTeX entry as text — FIELD_ORDER first, then leftovers alphabetical,
    field name left-padded to the widest key. Empty/blank fields are dropped."""
    f = {k: str(v).strip() for k, v in fields.items() if str(v).strip()}
    width = max((len(k) for k in f), default=6)
    lines = [f"@{etype}{{{key},"]
    for name in BIB_FIELD_ORDER:
        if name in f:
            lines.append(f"  {name.ljust(width)} = {{{f[name]}}},")
    for name in sorted(set(f) - set(BIB_FIELD_ORDER)):
        lines.append(f"  {name.ljust(width)} = {{{f[name]}}},")
    lines.append("}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    try:
        lib = find_library()
    except LibraryNotConfigured as e:
        print(f"  ✗ {e}", file=sys.stderr)
        sys.exit(1)
    pdfs = list((lib / "pdf").glob("*.pdf")) if (lib / "pdf").is_dir() else []
    bib = lib / "references.bib"
    print(f"  library : {lib}")
    print(f"  bib     : {bib if bib.is_file() else '— missing —'}")
    print(f"  PDFs    : {len(pdfs)}")
