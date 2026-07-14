#!/usr/bin/env python3
"""
One-time citekey migration: `autor-jahr` (and whatever else drifted in) →
`surname-year-shorttitle`.

WHY THIS EXISTS
---------------
`bibkey` is not merely a citation key in this setup — it is the **cross-project
join key**. ``wiki-global-graph.py`` matches sources across projects on it. An
audit of 17 wikis found the documented ``autor-jahr`` convention was a *minority*
(208 of 511 keys); the rest had drifted into Better-BibTeX-ish shapes
(``Hensel2024ReconsideringYahwism``, ``smith2016``). The damage:

  * **17 missed joins**  — the same work under different keys in different
    projects (``Smith2016`` vs ``smith2016``), so the graph never links them.
  * **2 false positives** — ``hensel-2024`` and ``tebes-2023`` each denote TWO
    DIFFERENT papers, so the graph asserts a shared source where none exists.

The fix is a key that is a *deterministic function of the work's own metadata*,
so the same work yields the same key in every project. ``surname-year-shorttitle``
is also exactly the PDF filename schema the template already mandates
(``autor-jahr-kurztitel.pdf``) — after this migration ``bibkey == PDF filename
stem`` is a real, checkable invariant. We are restoring a broken rule, not
inventing a new one.

WHAT IT TOUCHES
---------------
Per project, in lockstep (a partial rename breaks what currently works):

  * ``output/**/*.bib``        — entry keys, in EVERY bib (incl. ``archive/``, ``_FINAL``)
  * ``knowledge/**/*.md``      — frontmatter ``bibkey:`` AND body ``[@key]`` citations
  * ``output/**/*.qmd|.md``    — ``[@key]`` citations (incl. ``nocite:``)

It does NOT touch:

  * ``[[wikilinks]]``  — source-page *slugs* are a separate namespace and are
    deliberately left alone (only 158 of 515 pages even have slug == bibkey).
    Because we only ever match ``@``-prefixed tokens, ``[[hensel-2024]]`` cannot
    be confused with ``[@hensel-2024]``. Asserted, not assumed.
  * Quarto cross-references (``@sec-``, ``@fig-``, ``@tbl-``, ``@eq-`` …) — they
    share the ``@`` syntax with citations but are not citations.
  * ``input/**`` — literature guides, plans and acquisition logs are provenance;
    rewriting them would rewrite history. They are reported, not edited.
  * git — the tool never runs git. It prints the exact pathspec so you commit
    only what it touched, never your WIP.

USAGE
-----
    # 1. propose a mapping (writes NOTHING into the project)
    python scripts/migrate-citekeys.py plan <project-root> --map-out map.json

    # 2. *** review map.json by hand — resolve every "needs-decision" ***

    # 3. dry run (prints a diff; still writes nothing)
    python scripts/migrate-citekeys.py apply <project-root> --map map.json

    # 4. for real
    python scripts/migrate-citekeys.py apply <project-root> --map map.json \
        --write --backup-dir /tmp/citekey-backup

Pure standard library + PyYAML. Deterministic: same input → byte-identical map.
Idempotent: applying a second time is a no-op (the old keys are gone, so the
substitution matches nothing).
"""

import argparse
import difflib
import json
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

import yaml

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except AttributeError:  # pragma: no cover - non-reconfigurable stream
        pass

# --------------------------------------------------------------------------
# Conventions
# --------------------------------------------------------------------------

BUILD_DIRS = ("_output", "_files", ".quarto", "node_modules")
EXAMPLE_PREFIXES = ("_example-", "_beispiel-")

# The target shape. Mirrors schema/knowledge-frontmatter.schema.json's `bibkey`
# pattern — keep the two in sync.
CITEKEY_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*-[0-9]{4}[a-z]?-[a-z0-9]+(?:-[a-z0-9]+)*$")

# Quarto cross-references share the `@name` syntax with pandoc citations but are
# NOT citations. Rewriting or flagging them is a bug.
QUARTO_XREF_RE = re.compile(
    r"^(?:sec|fig|tbl|lst|eq|thm|lem|cor|prp|cnj|def|exm|exr|sol|rem|tip|nte|wrn|imp|cau)-"
)

# Right boundary. It must reject exactly what could extend the match into a
# DIFFERENT key — alphanumerics, underscore, hyphen (the alphabet our keys are
# built from), so `@smith2016` never eats `@smith2016b`, a different work.
#
# It must NOT reject sentence punctuation. Pandoc allows `.` *inside* a citekey,
# but a TRAILING period ends the sentence and is not part of the key. An earlier
# cut used pandoc's full continuation set here and therefore skipped every
# citation that happened to end a sentence — `[@dereu2013dh.` stayed behind while
# the .bib entry was renamed. A partial migration is worse than none: the key
# resolves nowhere and Quarto renders ??? while exiting 0.
CITEKEY_CONT = r"[A-Za-z0-9_-]"

STOPWORDS = {
    "the", "a", "an", "of", "and", "in", "on", "for", "to", "from", "with", "at",
    "der", "die", "das", "und", "von", "im", "zur", "zum", "des", "ein", "eine",
    "la", "le", "les", "el", "del", "al", "il", "un", "une", "y", "e",
}

BIB_ENTRY_RE = re.compile(r"(@[a-zA-Z]+\s*\{\s*)([^,\s]+)(\s*,)")
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


# --------------------------------------------------------------------------
# Key generation
# --------------------------------------------------------------------------

def deascii(s: str) -> str:
    """Fold to ASCII the way the PDF-filename rule does (ä→ae, ß→ss, é→e)."""
    s = (s.replace("ß", "ss").replace("Ä", "Ae").replace("Ö", "Oe")
          .replace("Ü", "Ue").replace("ä", "ae").replace("ö", "oe")
          .replace("ü", "ue").replace("æ", "ae").replace("ø", "o")
          .replace("Ø", "O").replace("ð", "d").replace("þ", "th"))
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def _brace_value(text: str, i: int) -> str | None:
    """Read the value starting at text[i]: {braced}, "quoted", or bare."""
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


def _field(body: str, name: str) -> str | None:
    """Pull one BibTeX field value, brace-balanced and format-agnostic.

    Must cope with BOTH shapes found in the wild — a regex anchored to line
    starts silently misses the second, which would migrate only part of a bib
    and leave the rest of the manuscript citing keys that no longer exist:

        author = {Ravi, Nikhila},                        # one field per line
        @inproceedings{k-2023, title={Segment Anything}, year={2023} }   # all inline

    Field names are matched case-insensitively (`DOI=`, `ISSN=`, `Title=` all occur).
    """
    for m in re.finditer(rf"(?:^|[,{{\s]){re.escape(name)}\s*=\s*", body, re.I):
        val = _brace_value(body, m.end())
        if val is not None:
            return val.strip()
    return None


def surname_of(body: str) -> str | None:
    """First author's family name; falls back to first editor. None if neither."""
    raw = _field(body, "author") or _field(body, "editor")
    if not raw:
        return None
    first = re.split(r"\s+and\s+", raw.strip())[0].strip()
    family = first.split(",")[0] if "," in first else first.split()[-1] if first.split() else ""
    family = re.sub(r"[^a-z]", "", deascii(family).lower())
    return family or None


def year_of(body: str) -> str | None:
    """First 4-digit year. Tolerates ranges ('1998–2007' → '1998')."""
    raw = _field(body, "year") or _field(body, "date") or ""
    m = re.search(r"(1[0-9]{3}|20[0-9]{2})", raw)
    return m.group(1) if m else None


def shorttitle_of(body: str, words: int = 1) -> str | None:
    """First significant title word(s): stopwords dropped, deascii'd, lowercased."""
    raw = _field(body, "title")
    if not raw:
        return None
    text = deascii(re.sub(r"[{}\\$]", "", raw)).lower()
    parts = [w for w in re.findall(r"[a-z0-9]+", text) if w not in STOPWORDS and len(w) > 2]
    return "-".join(parts[:words]) if parts else None


def make_key(body: str) -> tuple[str | None, str]:
    """Return (new_key, reason). new_key is None when a slot cannot be filled.

    Deliberately does NOT invent a surname for author-less reference-work entries
    (RGG, DNP, TRE, LThK …). Their conventional siglum is an initialism a machine
    cannot derive reliably ("Der Neue Pauly" → `dnp`, not `np`), so those become
    `needs-decision` and a human fills them in. Do not automate what you cannot
    verify.
    """
    s, y, t = surname_of(body), year_of(body), shorttitle_of(body)
    missing = [n for n, v in (("author/editor", s), ("year", y), ("title", t)) if not v]
    if missing:
        return None, "missing " + ", ".join(missing)
    return f"{s}-{y}-{t}", "ok"


# --------------------------------------------------------------------------
# Project scanning
# --------------------------------------------------------------------------

def _usable(p: Path) -> bool:
    return not any(d in p.parts for d in BUILD_DIRS)


def bib_files(root: Path) -> list[Path]:
    return sorted(p for p in root.glob("output/**/*.bib") if _usable(p))


def prose_files(root: Path) -> list[Path]:
    """Files whose BODY may carry `[@key]` citations."""
    out = [p for p in root.glob("knowledge/**/*.md") if _usable(p)]
    out += [p for p in root.glob("output/**/*.qmd") if _usable(p)]
    out += [p for p in root.glob("output/**/*.md") if _usable(p)]
    out += [p for p in root.glob("output/**/_quarto.yml") if _usable(p)]
    return sorted(set(out))


def iter_bib_entries(text: str):
    """Yield (type, key, body) per entry, walking braces to find the real end.

    Anchoring the end on '\\n}' (the obvious regex) silently drops every
    single-line entry — and real bibs mix both shapes freely. Missing entries
    here is the worst possible failure: the migration would rewrite some keys
    and not others, leaving the manuscript citing keys that no longer exist.
    """
    for m in re.finditer(r"@([a-zA-Z]+)\s*\{\s*([^,\s{}]+)\s*,", text):
        open_brace = text.find("{", m.start())
        depth, end = 0, None
        for j in range(open_brace, len(text)):
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
                if depth == 0:
                    end = j
                    break
        if end is None:                      # unbalanced tail — skip, never guess
            continue
        yield m.group(1), m.group(2), text[m.end():end]


def parse_bib(path: Path) -> dict[str, dict]:
    """{key: {type, title, year, doi, body}} for one .bib. Never raises."""
    text = path.read_text(encoding="utf-8", errors="replace")
    entries: dict[str, dict] = {}
    for etype, key, body in iter_bib_entries(text):
        entries[key] = {
            "type": etype,
            "title": (_field(body, "title") or "").strip(),
            "year": year_of(body) or "",
            "doi": (_field(body, "doi") or "").strip().lower(),
            "body": body,
        }
    return entries


def frontmatter_bibkeys(root: Path) -> dict[str, list[str]]:
    """{bibkey: [page names]} from knowledge/ source pages."""
    found: dict[str, list[str]] = {}
    for p in root.glob("knowledge/**/*.md"):
        if not _usable(p) or p.name.startswith(EXAMPLE_PREFIXES):
            continue
        m = FRONTMATTER_RE.match(p.read_text(encoding="utf-8-sig", errors="replace"))
        if not m:
            continue
        try:
            fm = yaml.safe_load(m.group(1))
        except yaml.YAMLError:
            continue
        if isinstance(fm, dict) and fm.get("bibkey"):
            found.setdefault(str(fm["bibkey"]), []).append(p.name)
    return found


# --------------------------------------------------------------------------
# plan
# --------------------------------------------------------------------------

def cmd_plan(root: Path, map_out: Path) -> int:
    bibs = bib_files(root)
    if not bibs:
        print(f"  ✗ no .bib under {root}/output/ — nothing to migrate", file=sys.stderr)
        return 1

    all_entries: dict[str, dict] = {}
    dupes: dict[str, list[str]] = {}           # key -> the differing titles seen
    for b in bibs:
        rel = str(b.relative_to(root))
        text = b.read_text(encoding="utf-8", errors="replace")
        seen_here: set[str] = set()
        for etype, k, body in iter_bib_entries(text):
            e = {"type": etype, "title": (_field(body, "title") or "").strip(),
                 "year": year_of(body) or "", "doi": (_field(body, "doi") or "").strip().lower(),
                 "body": body, "bib": rel}
            # A key defined twice is a silent last-wins in pandoc, and the two
            # entries may generate DIFFERENT target keys. Never swallow it.
            if k in seen_here or (k in all_entries and all_entries[k]["title"] != e["title"]):
                dupes.setdefault(k, []).append(e["title"][:60] or "(no title)")
                prev = all_entries.get(k, {}).get("title", "")
                if prev and prev[:60] not in dupes[k]:
                    dupes[k].insert(0, prev[:60])
            seen_here.add(k)
            all_entries[k] = e

    fm_keys = frontmatter_bibkeys(root)
    orphan_fm = sorted(set(fm_keys) - set(all_entries))

    rows, new_seen = [], {}
    for old in sorted(all_entries):
        e = all_entries[old]
        new, reason = make_key(e["body"])
        if new is None:
            status = "needs-decision"
        elif new == old:
            status = "identity"
        else:
            status = "ok"
        if new:
            new_seen.setdefault(new, []).append(old)
        rows.append({
            "old": old, "new": new, "status": status, "reason": reason,
            "title": e["title"][:90], "year": e["year"], "doi": e["doi"],
            "bib": e["bib"], "pages": fm_keys.get(old, []),
        })

    # collision: two DIFFERENT old keys generating the SAME new key
    for r in rows:
        if r["new"] and len(new_seen.get(r["new"], [])) > 1:
            r["status"] = "collision"
            r["reason"] = "shares generated key with: " + ", ".join(
                k for k in new_seen[r["new"]] if k != r["old"])

    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1

    map_out.parent.mkdir(parents=True, exist_ok=True)
    map_out.write_text(json.dumps(
        {"project": str(root), "bibs": [str(b.relative_to(root)) for b in bibs],
         "entries": rows}, indent=2, ensure_ascii=False, sort_keys=False) + "\n",
        encoding="utf-8")

    print(f"  project      : {root}")
    print(f"  .bib files   : {len(bibs)}  ({', '.join(b.name for b in bibs)})")
    print(f"  entries      : {len(rows)}")
    for s in ("ok", "identity", "needs-decision", "collision"):
        if counts.get(s):
            print(f"    {s:<15} {counts[s]}")
    if dupes:
        print(f"  ⚠ key defined more than once ({len(dupes)}) — pandoc silently takes the"
              " last; dedupe the .bib by hand:")
        for k, titles in sorted(dupes.items()):
            print(f"      {k}")
            for t in titles:
                print(f"        · {t}")
    if orphan_fm:
        print(f"  ⚠ frontmatter bibkey with no .bib entry ({len(orphan_fm)}): "
              + ", ".join(orphan_fm[:6]) + (" …" if len(orphan_fm) > 6 else ""))
    for r in rows:
        if r["status"] in ("needs-decision", "collision"):
            print(f"    ⚠ {r['status']:<15} {r['old']:<34} {r['reason']}")
    print(f"\n  map written  : {map_out}")
    if counts.get("needs-decision") or counts.get("collision"):
        print("  → resolve every needs-decision / collision in the map, then run `apply`.")
    return 0


# --------------------------------------------------------------------------
# apply
# --------------------------------------------------------------------------

def load_map(map_path: Path) -> dict[str, str]:
    data = json.loads(map_path.read_text(encoding="utf-8"))
    mapping, bad = {}, []
    for r in data["entries"]:
        old, new = r["old"], r.get("new")
        if not new:
            bad.append(f"{old}: still needs-decision (new is null)")
            continue
        if r.get("status") == "collision":
            bad.append(f"{old}: still marked collision → {new}")
        if not CITEKEY_RE.match(new):
            bad.append(f"{old} → {new}: does not match the citekey pattern")
        mapping[old] = new
    if bad:
        raise SystemExit("  ✗ map is not ready:\n" + "\n".join("      " + b for b in bad))
    return mapping


def assert_invariants(mapping: dict[str, str]) -> None:
    """The three asserts that make a rename safe. Abort loudly, never guess."""
    olds, news = list(mapping), list(mapping.values())

    # 1. Bijection — two works must never collapse onto one key.
    if len(set(news)) != len(set(olds)):
        dupes = {n for n in news if news.count(n) > 1}
        raise SystemExit("  ✗ NOT A BIJECTION — these generated keys are shared by "
                         f"several works: {sorted(dupes)}")

    # 2. No chaining — if A's new key equals B's old key, a sequential rewrite
    #    would silently merge two works. (We substitute in one pass, so this
    #    cannot actually bite, but a map that needs it is a map with a bug.)
    identity = {k for k, v in mapping.items() if k == v}
    overlap = (set(news) & set(olds)) - identity
    if overlap:
        raise SystemExit("  ✗ CHAINING — a new key equals another entry's old key: "
                         f"{sorted(overlap)}")


def build_substituter(mapping: dict[str, str]):
    """One single-pass alternation. Longest key first so `smith2016b` wins over
    `smith2016`; a right-boundary lookahead so `@smith2016` never eats
    `@smith2016b`; a left guard so emails and `[[wikilinks]]` are untouchable.
    """
    active = {o: n for o, n in mapping.items() if o != n}
    if not active:
        return None
    alt = "|".join(re.escape(k) for k in sorted(active, key=len, reverse=True))
    pat = re.compile(rf"(?<![A-Za-z0-9_`@.])@({alt})(?!{CITEKEY_CONT})")
    return lambda text: pat.sub(lambda m: "@" + active[m.group(1)], text)


def rewrite_bib(text: str, mapping: dict[str, str]) -> str:
    def repl(m):
        head, key, tail = m.group(1), m.group(2), m.group(3)
        return head + mapping.get(key, key) + tail
    return BIB_ENTRY_RE.sub(repl, text)


def rewrite_frontmatter_bibkey(text: str, mapping: dict[str, str]) -> str:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return text
    block = m.group(1)

    def repl(mm):
        val = mm.group(2).strip().strip('"\'')
        new = mapping.get(val)
        return f"{mm.group(1)}{new}" if new else mm.group(0)

    new_block = re.sub(r'^(bibkey:\s*)(.+)$', repl, block, flags=re.M)
    return text[:m.start(1)] + new_block + text[m.end(1):]


def _mask_code(text: str) -> tuple[str, list[str]]:
    """Hide fenced + inline code so citations inside them are never rewritten."""
    stash: list[str] = []

    def keep(m):
        stash.append(m.group(0))
        return f"\x00{len(stash) - 1}\x00"

    text = re.sub(r"```.*?```", keep, text, flags=re.S)
    text = re.sub(r"`[^`\n]*`", keep, text)
    return text, stash


def _unmask_code(text: str, stash: list[str]) -> str:
    return re.sub(r"\x00(\d+)\x00", lambda m: stash[int(m.group(1))], text)


WIKILINK_RE = re.compile(r"\[\[[^\]]+\]\]")
XREF_TOKEN_RE = re.compile(
    r"@(?:sec|fig|tbl|lst|eq|thm|lem|cor|prp|cnj|def|exm|exr|sol|rem|tip|nte|wrn|imp|cau)-")


def cmd_apply(root: Path, map_path: Path, write: bool, backup_dir: Path | None) -> int:
    mapping = load_map(map_path)
    assert_invariants(mapping)
    subst = build_substituter(mapping)
    if subst is None:
        print("  nothing to do — every key already has its target shape.")
        return 0

    changes: list[tuple[Path, str, str]] = []

    for b in bib_files(root):
        old = b.read_text(encoding="utf-8", errors="replace")
        new = rewrite_bib(old, mapping)
        if new != old:
            changes.append((b, old, new))

    for f in prose_files(root):
        old = f.read_text(encoding="utf-8", errors="replace")
        masked, stash = _mask_code(old)
        new = subst(masked)
        if f.suffix == ".md" and "knowledge" in f.parts:
            new = rewrite_frontmatter_bibkey(new, mapping)
        new = _unmask_code(new, stash)

        # Invariants 5 + 6: wikilinks and Quarto cross-refs are untouchable.
        if len(WIKILINK_RE.findall(new)) != len(WIKILINK_RE.findall(old)):
            raise SystemExit(f"  ✗ WIKILINK COUNT CHANGED in {f} — refusing to write")
        if len(XREF_TOKEN_RE.findall(new)) != len(XREF_TOKEN_RE.findall(old)):
            raise SystemExit(f"  ✗ QUARTO XREF COUNT CHANGED in {f} — refusing to write")

        if new != old:
            changes.append((f, old, new))

    if not changes:
        print("  no occurrences found — already migrated (idempotent no-op).")
        return 0

    print(f"  files to change: {len(changes)}\n")
    for path, old, new in changes:
        rel = path.relative_to(root)
        diff = list(difflib.unified_diff(
            old.splitlines(), new.splitlines(),
            fromfile=f"a/{rel}", tofile=f"b/{rel}", lineterm="", n=0))
        shown = [d for d in diff if d.startswith(("+", "-")) and not d.startswith(("+++", "---"))]
        print(f"  ── {rel}  ({len(shown)} line(s))")
        for d in shown[:6]:
            print(f"       {d}")
        if len(shown) > 6:
            print(f"       … +{len(shown) - 6} more")

    if not write:
        print("\n  DRY RUN — nothing written. Re-run with --write --backup-dir <path>.")
        return 0

    # No-undo guard: refuse to touch untracked/ignored files without a backup.
    risky = []
    for path, _, _ in changes:
        rel = str(path.relative_to(root))
        tracked = subprocess.run(["git", "-C", str(root), "ls-files", "--error-unmatch", rel],
                                 capture_output=True).returncode == 0
        if not tracked:
            risky.append(rel)
    if risky and backup_dir is None:
        print(f"\n  ✗ {len(risky)} file(s) are untracked/ignored — they have NO git undo:")
        for r in risky[:10]:
            print(f"      {r}")
        print("  Refusing to --write without --backup-dir.")
        return 1

    if backup_dir:
        for path, old, _ in changes:
            dest = backup_dir / path.relative_to(root)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
        print(f"\n  backup written to {backup_dir}")

    for path, _, new in changes:
        path.write_text(new, encoding="utf-8")
    print(f"  ✓ rewrote {len(changes)} file(s)")

    paths = " ".join(str(p.relative_to(root)) for p, _, _ in changes)
    print("\n  Commit ONLY what this tool touched (your WIP stays untouched):")
    print(f"    git -C {root} commit -m 'meta: migrate citekeys' -- {paths}")
    return 0


# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("plan", help="propose a mapping; writes nothing into the project")
    p.add_argument("root", type=Path)
    p.add_argument("--map-out", type=Path, required=True)

    a = sub.add_parser("apply", help="rewrite keys (dry-run unless --write)")
    a.add_argument("root", type=Path)
    a.add_argument("--map", type=Path, required=True)
    a.add_argument("--write", action="store_true")
    a.add_argument("--backup-dir", type=Path, default=None)

    args = ap.parse_args()
    root = args.root.resolve()
    if not (root / "knowledge").is_dir():
        print(f"  ✗ {root} has no knowledge/ — not a research project", file=sys.stderr)
        return 1

    if args.cmd == "plan":
        return cmd_plan(root, args.map_out)
    return cmd_apply(root, args.map, args.write, args.backup_dir)


if __name__ == "__main__":
    sys.exit(main())
