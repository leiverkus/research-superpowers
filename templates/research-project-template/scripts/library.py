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
