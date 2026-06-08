#!/usr/bin/env python3
"""Release helper for research-superpowers (stdlib only).

Single source of truth for the three things a release must get right:
the two manifest versions, the git tag, and the matching CHANGELOG section.

Sub-commands
------------
    python scripts/release.py check --tag v0.12.0
        Verify plugin.json == marketplace.json == tag (sans leading 'v') and
        that CHANGELOG.md has a `## [x.y.z]` section. Exit non-zero otherwise.
        (Run by .github/workflows/release.yml on tag push, and locally.)

    python scripts/release.py notes --version 0.12.0
        Print the body of that CHANGELOG section to stdout (release notes).

    python scripts/release.py bump --version 0.12.0
        Bump both manifests + the README version badge and, if missing, insert
        a dated CHANGELOG skeleton heading. You then write the notes by hand.

This is plugin-internal tooling; it is NOT mirrored into the template/example.
"""
import argparse
import datetime
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGIN = ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"
README = ROOT / "README.md"
CHANGELOG = ROOT / "CHANGELOG.md"

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def _plugin_version() -> str:
    return json.loads(PLUGIN.read_text(encoding="utf-8"))["version"]


def _marketplace_version() -> str:
    return json.loads(MARKETPLACE.read_text(encoding="utf-8"))["plugins"][0]["version"]


def strip_v(ref: str) -> str:
    """v0.12.0 / refs/tags/v0.12.0 → 0.12.0."""
    return ref.rsplit("/", 1)[-1].lstrip("v")


def extract_changelog_section(version: str, text: str | None = None) -> str | None:
    """Return the body under `## [version]` up to the next `## [` heading, or
    None if there is no such section."""
    if text is None:
        text = CHANGELOG.read_text(encoding="utf-8")
    # Heading like:  ## [0.12.0] — 2026-06-08   (em dash optional / any tail)
    pattern = re.compile(
        r"^##\s*\[" + re.escape(version) + r"\].*?$(.*?)(?=^##\s*\[|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(text)
    return m.group(1).strip() if m else None


def cmd_check(args) -> int:
    pv, mv, tag_v = _plugin_version(), _marketplace_version(), strip_v(args.tag)
    problems = []
    if not SEMVER.match(tag_v):
        problems.append(f"tag '{args.tag}' is not vMAJOR.MINOR.PATCH")
    if pv != mv:
        problems.append(f"plugin.json ({pv}) != marketplace.json ({mv})")
    if pv != tag_v:
        problems.append(f"plugin.json ({pv}) != tag ({tag_v})")
    if extract_changelog_section(tag_v) is None:
        problems.append(f"CHANGELOG.md has no '## [{tag_v}]' section")
    if problems:
        for p in problems:
            print(f"::error::release check: {p}")
        return 1
    print(f"release check OK — v{tag_v} (manifests + tag + changelog all agree)")
    return 0


def cmd_notes(args) -> int:
    section = extract_changelog_section(args.version)
    if section is None:
        print(f"::error::no CHANGELOG section for {args.version}", file=sys.stderr)
        return 1
    print(section)
    return 0


def cmd_bump(args) -> int:
    version = args.version
    if not SEMVER.match(version):
        print(f"::error::'{version}' is not MAJOR.MINOR.PATCH", file=sys.stderr)
        return 1

    p = json.loads(PLUGIN.read_text(encoding="utf-8"))
    p["version"] = version
    PLUGIN.write_text(json.dumps(p, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    m = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
    m["plugins"][0]["version"] = version
    MARKETPLACE.write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    readme = README.read_text(encoding="utf-8")
    README.write_text(re.sub(r"badge/version-[0-9][^-]*-", f"badge/version-{version}-", readme),
                      encoding="utf-8")

    if extract_changelog_section(version) is None:
        today = args.date or datetime.date.today().isoformat()
        cl = CHANGELOG.read_text(encoding="utf-8")
        skeleton = (f"## [{version}] — {today}\n\n"
                    "_Describe the release here._\n\n### Added\n\n### Changed\n\n### Fixed\n\n")
        # insert before the first existing version heading
        m2 = re.search(r"^##\s*\[", cl, re.MULTILINE)
        cl = (cl[:m2.start()] + skeleton + cl[m2.start():]) if m2 else cl + "\n" + skeleton
        CHANGELOG.write_text(cl, encoding="utf-8")
        print(f"bumped to {version}; inserted CHANGELOG skeleton — write the notes, then tag v{version}")
    else:
        print(f"bumped to {version}; CHANGELOG section already present")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Release helper")
    sub = parser.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="verify manifests + tag + changelog agree")
    c.add_argument("--tag", required=True)
    c.set_defaults(func=cmd_check)
    n = sub.add_parser("notes", help="print the CHANGELOG section for a version")
    n.add_argument("--version", required=True)
    n.set_defaults(func=cmd_notes)
    b = sub.add_parser("bump", help="bump manifests + badge + changelog skeleton")
    b.add_argument("--version", required=True)
    b.add_argument("--date", help="override date for the changelog skeleton (YYYY-MM-DD)")
    b.set_defaults(func=cmd_bump)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
