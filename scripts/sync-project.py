#!/usr/bin/env python3
"""
Bring a scaffolded project's mirrored files back in step with the plugin.

WHY
---
`lint-wiki.py`, the frontmatter schema and nine sibling scripts are **copied**
into a project at scaffold time. After that there is no return channel. CI
guards the copies *inside this repo* — template vs. `schema/` vs.
`examples/example-project/` — but nothing guards the real projects on disk, and
they are the ones that run.

That is harmless exactly as long as the plugin never changes those files. The
moment it does — a new `confidence` value, a new gate exemption — every existing
project keeps silently validating against the old rules, and the failure looks
like a wiki problem rather than a version problem: the linter rejects frontmatter
that the current schema explicitly allows.

This script is the return channel. It reports first and writes only when asked.

WHAT IT WILL NOT DO
-------------------
Overwrite a file a project has edited. `--apply` refuses those and names them;
`--force` is the deliberate second step. A project that patched its own
`lint-wiki.py` did so for a reason, and finding out by losing the patch is the
worst way to learn about this script.

OUTDATED vs. LOCALLY MODIFIED
-----------------------------
A hash comparison alone cannot tell "old copy" from "edited copy" — both are
just *different*. The `plugin_version` recorded in the project's CLAUDE.md
frontmatter settles it:

    version older than the plugin + file differs  → OUTDATED (sync it)
    version equal to the plugin   + file differs  → LOCAL EDIT (needs a human)
    no version recorded at all                    → UNKNOWN, treated as outdated,
                                                    because projects scaffolded
                                                    before this field existed are
                                                    by definition behind

The heuristic is named in the output rather than hidden, because the middle case
is the one where being wrong costs something.

USAGE
-----
    python scripts/sync-project.py --from-registry
    python scripts/sync-project.py --roots <p1> <p2> …
    python scripts/sync-project.py --from-registry --apply
    python scripts/sync-project.py --roots <p> --apply --force

``--from-registry`` reads ~/.config/research-superpowers/projects itself. Prefer
it: handing the registry to ``--roots`` through the shell needs quoting that is
correct in bash AND zsh, and every way of getting it wrong fails silently.
"""

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except AttributeError:  # pragma: no cover
        pass

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = PLUGIN_ROOT / "templates" / "research-project-template"
CONFIG_DIR = Path.home() / ".config" / "research-superpowers"

# The files a project receives from the plugin and must keep in step with it.
#
# The scripts half MUST match the loop in .github/workflows/lint.yml ("Script
# mirrors are in sync") — that loop is what gates the build, and it is an
# allowlist, so anything missing from it fails open. `tests/test_sync_project.py`
# asserts the two agree, which is the check CONTRIBUTING.md asks for in prose.
SYNCED_PATHS = (
    "schema/knowledge-frontmatter.schema.json",
    "scripts/lint-wiki.py",
    "scripts/wiki-to-graph.py",
    "scripts/graph_mcp.py",
    "scripts/wiki-global-graph.py",
    "scripts/library.py",
    "scripts/bib-subset.py",
    "scripts/bib-search.py",
    "scripts/check-pdf-version.py",
    "scripts/add-to-library.py",
    "scripts/optimize-pdf.py",
    "scripts/vendor/cytoscape.min.js",
)

FRONTMATTER_KEY = "plugin_version"


def plugin_version() -> str:
    manifest = json.loads((PLUGIN_ROOT / ".claude-plugin" / "plugin.json")
                          .read_text(encoding="utf-8"))
    return str(manifest["version"])


def version_tuple(v: str) -> tuple[int, ...]:
    """Compare versions numerically, not as strings: '0.9.0' > '0.10.0' is the
    bug this avoids. Unparseable parts sort as 0 rather than raising — a project
    with a hand-edited version string should still get a report."""
    out = []
    for part in str(v).split("."):
        m = re.match(r"\d+", part)
        out.append(int(m.group(0)) if m else 0)
    return tuple(out)


def sha1(p: Path) -> str | None:
    try:
        return hashlib.sha1(p.read_bytes()).hexdigest()
    except OSError:
        return None


def registry_path() -> Path:
    return CONFIG_DIR / "projects"


def read_registry() -> list[Path]:
    try:
        lines = registry_path().read_text(encoding="utf-8").splitlines()
    except OSError as e:
        sys.exit(f"  ✗ cannot read the project registry {registry_path()}: {e}")
    return [Path(ln.strip()).expanduser() for ln in lines
            if ln.strip() and not ln.strip().startswith("#")]


def resolve_roots(roots: list[Path], source: str) -> list[Path]:
    """Every root must exist. A missing one means a typo in the registry or a
    path mangled by the shell, and a silently shrunken project set turns "all in
    sync" into a statement about a set that never contained the broken one."""
    if not roots:
        sys.exit(f"  ✗ no project roots {source}")
    missing = [r for r in roots if not r.is_dir()]
    if missing:
        print(f"  ✗ {len(missing)} of {len(roots)} project root(s) {source} "
              f"do not exist:", file=sys.stderr)
        for m in missing:
            print(f"      {m}", file=sys.stderr)
        print("    Fix the path, or — if this came from the shell — pass "
              "--from-registry instead of expanding the registry yourself.",
              file=sys.stderr)
        return []
    return roots


def read_project_version(root: Path) -> str | None:
    """Read `plugin_version` from the project's CLAUDE.md frontmatter.

    Deliberately regex over the frontmatter block rather than a YAML parse: this
    is a maintainer tool that must run with the standard library alone, on a
    project whose CLAUDE.md may carry anything below the frontmatter.
    """
    try:
        text = (root / "CLAUDE.md").read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end < 0:
        return None
    m = re.search(rf'(?m)^{FRONTMATTER_KEY}:\s*"?([^"\n#]+?)"?\s*(?:#.*)?$',
                  text[:end])
    return m.group(1).strip() if m else None


def write_project_version(root: Path, version: str) -> bool:
    """Set `plugin_version` in the frontmatter, adding the key if it is absent.

    Returns False when there is no frontmatter to patch — a project whose
    CLAUDE.md was replaced wholesale is not one to guess at.
    """
    path = root / "CLAUDE.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    if not text.startswith("---"):
        return False
    end = text.find("\n---", 3)
    if end < 0:
        return False
    head, rest = text[:end], text[end:]
    line = f'{FRONTMATTER_KEY}: "{version}"'
    if re.search(rf"(?m)^{FRONTMATTER_KEY}:", head):
        head = re.sub(rf"(?m)^{FRONTMATTER_KEY}:.*$", line, head, count=1)
    else:
        head = head.rstrip("\n") + "\n" + line
    path.write_text(head + rest, encoding="utf-8")
    return True


def classify(root: Path, current: str) -> tuple[str | None, list[tuple[str, str]]]:
    """Return the project's recorded version and one (path, state) per file.

    States: "same", "outdated", "local-edit", "missing".
    """
    recorded = read_project_version(root)
    behind = recorded is None or version_tuple(recorded) < version_tuple(current)
    rows: list[tuple[str, str]] = []
    for rel in SYNCED_PATHS:
        src, dst = TEMPLATE / rel, root / rel
        if not dst.exists():
            rows.append((rel, "missing"))
            continue
        if sha1(src) == sha1(dst):
            rows.append((rel, "same"))
            continue
        rows.append((rel, "outdated" if behind else "local-edit"))
    return recorded, rows


def labels_for(roots: list[Path]) -> dict[Path, str]:
    """A short but UNAMBIGUOUS name per project.

    Nine of the registered projects are directories called `paper`. Reporting
    them by basename produces nine identical lines, and the one that needs
    attention is indistinguishable from the eight that do not — so fall back to
    `<parent>/<name>` for any name that is not unique, and to the full path if
    even that collides.
    """
    out: dict[Path, str] = {}
    for candidate in (lambda r: r.name,
                      lambda r: f"{r.parent.name}/{r.name}",
                      lambda r: str(r)):
        names = [candidate(r) for r in roots]
        remaining = [r for r in roots if r not in out]
        for r in remaining:
            if names.count(candidate(r)) == 1:
                out[r] = candidate(r)
        if len(out) == len(roots):
            break
    for r in roots:
        out.setdefault(r, str(r))
    return out


def sync_file(root: Path, rel: str) -> None:
    src, dst = TEMPLATE / rel, root / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--roots", nargs="+", type=Path)
    src.add_argument("--from-registry", action="store_true",
                     help="read the project roots from ~/.config/research-superpowers/projects "
                          "(preferred — no shell quoting to get wrong)")
    ap.add_argument("--apply", action="store_true",
                    help="copy the outdated files (default: report only)")
    ap.add_argument("--force", action="store_true",
                    help="with --apply: overwrite locally modified files too")
    args = ap.parse_args()

    if args.from_registry:
        roots = resolve_roots(read_registry(), "in the registry")
    else:
        roots = resolve_roots([p.expanduser() for p in args.roots], "given on the command line")
    if not roots:
        return 1

    current = plugin_version()
    labels = labels_for(roots)
    print(f"# Project sync — plugin {current}\n")

    total_out = total_local = total_missing = written = refused = 0
    for root in roots:
        recorded, rows = classify(root, current)
        out = [r for r, s in rows if s == "outdated"]
        loc = [r for r, s in rows if s == "local-edit"]
        gone = [r for r, s in rows if s == "missing"]
        total_out += len(out)
        total_local += len(loc)
        total_missing += len(gone)

        shown = recorded or "not recorded"
        if not out and not loc and not gone:
            print(f"  ✓ {labels[root]} ({shown}) — in sync")
            continue

        print(f"  • {labels[root]} ({shown})")
        for rel in gone:
            print(f"      MISSING    {rel}")
        for rel in out:
            print(f"      OUTDATED   {rel}")
        for rel in loc:
            print(f"      LOCAL EDIT {rel}  ⚠ differs while claiming the current version")

        if args.apply:
            to_write = out + gone + (loc if args.force else [])
            for rel in to_write:
                sync_file(root, rel)
                written += 1
            if loc and not args.force:
                refused += len(loc)
            # The version is only truthful once every file actually matches.
            if not (loc and not args.force):
                if write_project_version(root, current):
                    print(f"      → synced {len(to_write)} file(s), "
                          f"{FRONTMATTER_KEY} set to {current}")
                else:
                    print(f"      → synced {len(to_write)} file(s); "
                          f"⚠ no frontmatter in CLAUDE.md, {FRONTMATTER_KEY} not recorded")
            else:
                print(f"      → synced {len(to_write)} file(s); "
                      f"{FRONTMATTER_KEY} left at {shown} because "
                      f"{len(loc)} local edit(s) remain")
        print()

    print(f"\n  {len(roots)} project(s) · {total_out} outdated · "
          f"{total_local} locally modified · {total_missing} missing")
    if not args.apply and (total_out or total_missing or total_local):
        print("  → re-run with --apply to copy the outdated ones "
              "(add --force to overwrite local edits)")
    if args.apply:
        print(f"  → wrote {written} file(s)"
              + (f", refused {refused} local edit(s) — pass --force to overwrite"
                 if refused else ""))
    # Local edits are a finding a human must settle; outdated files are not an
    # error once --apply has dealt with them.
    return 1 if (total_local and not args.force) else 0


if __name__ == "__main__":
    raise SystemExit(main())
