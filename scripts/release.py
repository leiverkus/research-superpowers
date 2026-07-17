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

    python scripts/release.py audit
        Verify every version CHANGELOG documents was actually tagged — the
        newest section excepted, since during a release PR the manifest is
        bumped and the notes are written before the tag is pushed.
        (Run by .github/workflows/lint.yml on every push/PR.)

        `check` cannot catch a *missing* release: it only runs when a tag is
        pushed, so forgetting to tag means it never runs at all. That is not
        hypothetical — 0.27.0 through 0.30.0 were bumped, changelogged and
        merged, and sat untagged behind a green CI until someone noticed
        GitHub still showed 0.26.1 as latest. This sub-command is the check
        that would have said so, one release later instead of six.

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
import subprocess
import sys

# Force UTF-8 stdout/stderr: `notes` prints the CHANGELOG section (em dashes),
# which a Windows cp1252 console cannot encode.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except AttributeError:  # pragma: no cover
        pass

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLUGIN = ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"
README = ROOT / "README.md"
CHANGELOG = ROOT / "CHANGELOG.md"

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")

# `audit` floor. Everything below this predates the release discipline and is
# immutable history, not a finding:
#   * the first tag is v0.3.0, so 0.1.0 and 0.2.0 were never taggable at all;
#   * 0.3.1 is a CHANGELOG section for a release that never happened — NO commit
#     ever carried 0.3.1 in its manifests (git rev-list v0.3.0..v0.4.0 has four
#     commits; none of them). There is nothing to tag, so it can never be fixed.
# Auditing that stretch is archaeology. From 0.4.0 on the history is clean, so
# that is where enforcement starts.
AUDIT_FLOOR = (0, 4, 0)


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


def git_tags() -> set[str]:
    """Every tag visible in this checkout. Empty set if git cannot answer."""
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "tag", "--list"],
                             capture_output=True, text=True, check=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return set()
    return {ln.strip() for ln in out.splitlines() if ln.strip()}


def version_tuple(v: str) -> tuple[int, int, int]:
    """'0.4.0' → (0, 4, 0), so versions compare numerically ('0.10.0' > '0.9.0')."""
    major, minor, patch = v.split(".")
    return int(major), int(minor), int(patch)


def released_versions(text: str | None = None) -> list[str]:
    """Versions documented in CHANGELOG.md, in file order (newest first).

    The semver capture group also does the filtering: `## [Unreleased]` has no
    x.y.z, so it never matches and needs no special case."""
    if text is None:
        text = CHANGELOG.read_text(encoding="utf-8")
    return re.findall(r"^##\s*\[(\d+\.\d+\.\d+)\]", text, re.MULTILINE)


def cmd_audit(args) -> int:
    versions = released_versions()
    if not versions:
        print("::error::release audit: CHANGELOG.md documents no '## [x.y.z]' version")
        return 1

    tags = git_tags()
    if not tags:
        # Fail loudly rather than pass vacuously: with no tags visible EVERY
        # version looks untagged, so a silent pass here would be the same class
        # of bug this command exists to catch.
        print("::error::release audit: no git tags visible — a shallow checkout cannot "
              "answer this. Use actions/checkout with fetch-depth: 0 (or fetch-tags: true).")
        return 1

    # The newest section is exempt: a release PR bumps the manifests and writes
    # the notes BEFORE the tag is pushed, so requiring it would fail every
    # release PR — the false positive that gets a check switched off.
    newest, older = versions[0], versions[1:]
    missing = [v for v in older
               if version_tuple(v) >= AUDIT_FLOOR and f"v{v}" not in tags]

    if missing:
        for v in missing:
            print(f"::error::release audit: CHANGELOG documents {v}, but v{v} is not tagged — "
                  f"that version was never released")
        print(f"::error::release audit: {len(missing)} documented version(s) never tagged. "
              f"Tag the commit whose manifests carry the version, then push the tags "
              f"ONE AT A TIME — GitHub creates no push event at all when more than three "
              f"tags arrive in a single push, so the release workflow would never fire.")
        return 1

    if f"v{newest}" in tags:
        print(f"release audit OK — every documented version is tagged (newest: v{newest})")
    else:
        print(f"release audit OK — v{newest} is not tagged yet (expected while its release "
              f"is in flight); every older version is tagged")
    return 0


# `[ \t]*$`, not `\s*$`: \s matches newlines, so `\s*$` would eat the blank line
# after the heading and glue the promoted notes straight onto it.
UNRELEASED_RE = re.compile(r"^##[ \t]*\[Unreleased\][ \t]*$", re.MULTILINE | re.IGNORECASE)
VERSION_HEADING_RE = re.compile(r"^##\s*\[\d+\.\d+\.\d+\]", re.MULTILINE)

SKELETON_BODY = "\n\n_Describe the release here._\n\n### Added\n\n### Changed\n\n### Fixed\n\n"


def plan_changelog(cl: str, version: str, today: str) -> tuple[str, str]:
    """Return (new CHANGELOG text, what happened) for releasing `version`.

    Keep a Changelog puts `## [Unreleased]` on top and the newest release under
    it. Naively inserting before the first `## [` heading therefore files the new
    version ABOVE [Unreleased] — and strands the notes written during
    development under [Unreleased], where `notes` will never find them. The
    release then ships "_Describe the release here._" as its body while the real
    notes sit orphaned. So: promote those notes rather than skirt them.
    """
    if extract_changelog_section(version, cl) is not None:
        return cl, "CHANGELOG section already present"

    m_unrel = UNRELEASED_RE.search(cl)
    m_ver = VERSION_HEADING_RE.search(cl)
    heading = f"## [{version}] — {today}"

    if m_unrel:
        body_start = m_unrel.end()
        body_end = m_ver.start() if m_ver else len(cl)
        body = cl[body_start:body_end]
        if body.strip():
            # The notes are already written — they ARE this release. Move them
            # down under the version heading and leave [Unreleased] empty.
            return (cl[:m_unrel.start()] + "## [Unreleased]\n\n" + heading + body
                    + cl[body_end:]), "promoted the [Unreleased] notes into it"
        # [Unreleased] exists but is empty: skeleton goes directly below it.
        return (cl[:body_end] + heading + SKELETON_BODY + cl[body_end:]), "inserted a skeleton"

    if m_ver:
        return (cl[:m_ver.start()] + heading + SKELETON_BODY
                + cl[m_ver.start():]), "inserted a skeleton"
    return cl + "\n" + heading + SKELETON_BODY, "inserted a skeleton"


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

    # --- Phase 1: compute & validate every change in memory (write nothing yet)
    # so a failure (e.g. missing README badge) can't leave a half-bumped repo. ---
    p = json.loads(PLUGIN.read_text(encoding="utf-8"))
    p["version"] = version
    plugin_text = json.dumps(p, indent=2, ensure_ascii=False) + "\n"

    m = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
    m["plugins"][0]["version"] = version
    market_text = json.dumps(m, indent=2, ensure_ascii=False) + "\n"

    readme_text, n_badge = re.subn(r"badge/version-[0-9][^-]*-",
                                   f"badge/version-{version}-",
                                   README.read_text(encoding="utf-8"))
    if n_badge == 0:
        print("::error::README version badge not found — nothing written", file=sys.stderr)
        return 1   # fail before any file is touched

    today = args.date or datetime.date.today().isoformat()
    cl, what = plan_changelog(CHANGELOG.read_text(encoding="utf-8"), version, today)

    # --- Phase 2: everything validated — now commit all writes together. ---
    PLUGIN.write_text(plugin_text, encoding="utf-8")
    MARKETPLACE.write_text(market_text, encoding="utf-8")
    README.write_text(readme_text, encoding="utf-8")
    CHANGELOG.write_text(cl, encoding="utf-8")

    print(f"bumped to {version}; {what}")
    if what.startswith("inserted"):
        print(f"  write the notes, then tag v{version}")
    elif what.startswith("promoted"):
        print(f"  read them over, then tag v{version}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Release helper")
    sub = parser.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="verify manifests + tag + changelog agree")
    c.add_argument("--tag", required=True)
    c.set_defaults(func=cmd_check)
    a = sub.add_parser("audit", help="verify every documented version was tagged")
    a.set_defaults(func=cmd_audit)
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
