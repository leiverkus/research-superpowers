#!/usr/bin/env python3
"""
Wiki lint: structural checks on the research wiki.

Three deterministic, CI-friendly checks:
  1. Frontmatter against schema/knowledge-frontmatter.schema.json
  2. Wikilinks (broken targets, orphan pages)
  3. Status distribution

Content checks (contradictions between pages, stale claims) do NOT belong
here — use the semantic-wiki-review skill for those.

Usage:
    python scripts/lint-wiki.py
    python scripts/lint-wiki.py --verbose
"""

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

import yaml

# Force UTF-8 stdout/stderr regardless of platform locale: Windows defaults to
# cp1252, which cannot encode the arrow (←/→) and dash glyphs we emit.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except AttributeError:  # pragma: no cover - non-reconfigurable stream
        pass


class _NoDatesLoader(yaml.SafeLoader):
    """SafeLoader that does NOT auto-convert ISO dates to datetime objects.

    Keeps `created: 2026-04-15` a string (so format validation is possible) and
    stops invalid dates like `2026-99-99` from raising ValueError mid-parse.
    """


_NoDatesLoader.yaml_implicit_resolvers = {
    ch: [(tag, rx) for (tag, rx) in res if tag != "tag:yaml.org,2002:timestamp"]
    for ch, res in yaml.SafeLoader.yaml_implicit_resolvers.items()
}

WIKI_DIR = Path("knowledge")
SCHEMA_PATH = Path("schema/knowledge-frontmatter.schema.json")
OVERRIDES_LOG = Path("knowledge/_meta/gate-overrides.log")
OVERRIDE_RECENT_DAYS = 30
OVERRIDE_WARN_COUNT = 5

RELATION_CONFIDENCE = ("extracted", "inferred", "ambiguous")
RELATION_KEYS = {"target", "type", "confidence", "because"}
INFERENCE_WARN_THRESHOLD = 0.50


def load_schema() -> dict:
    """Load the frontmatter JSON schema. Fails loudly if missing."""
    if not SCHEMA_PATH.exists():
        print(f"Error: schema file '{SCHEMA_PATH}' not found.")
        print("Expected at the project root; scaffolded automatically from the template.")
        sys.exit(2)
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


_PY_TYPE = {"string": str, "array": list, "integer": int, "object": dict, "number": (int, float)}


def validate_frontmatter(fm: dict, schema: dict, path: Path) -> list[str]:
    """Draft-07 validator covering the subset our schema uses: required, type,
    enum, format=date, pattern, array item type, and conditional if/then from
    allOf. (Dates are kept as strings by _NoDatesLoader so format can be checked.)"""
    issues: list[str] = []
    props = schema.get("properties", {})

    for field in schema.get("required", []):
        if field not in fm or fm[field] in (None, ""):
            issues.append(f"  MISSING: {path} — required field '{field}' is missing")

    for field, value in fm.items():
        if field not in props or value is None:
            continue
        spec = props[field]
        expected = spec.get("type")
        if expected in _PY_TYPE and not isinstance(value, _PY_TYPE[expected]):
            issues.append(f"  TYPE: {path} — '{field}' must be {expected} (got {type(value).__name__})")
            continue
        if "enum" in spec and value not in spec["enum"]:
            issues.append(f"  INVALID: {path} — {field}='{value}' (allowed: {', '.join(spec['enum'])})")
        if spec.get("format") == "date" and isinstance(value, str):
            # Require strict YYYY-MM-DD; date.fromisoformat() alone also accepts
            # basic (20260415) and week dates (2026-W15-3), which the schema forbids.
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                issues.append(f"  DATE: {path} — {field}='{value}' must be YYYY-MM-DD")
            else:
                try:
                    datetime.date.fromisoformat(value)
                except ValueError:
                    issues.append(f"  DATE: {path} — {field}='{value}' is not a real calendar date")
        if spec.get("pattern") and isinstance(value, str) and not re.match(spec["pattern"], value):
            issues.append(f"  PATTERN: {path} — {field}='{value}' violates {spec['pattern']}")
        if expected == "array":
            item_type = spec.get("items", {}).get("type")
            if item_type in _PY_TYPE and not all(isinstance(x, _PY_TYPE[item_type]) for x in value):
                issues.append(f"  TYPE: {path} — every item of '{field}' must be {item_type}")

    for clause in schema.get("allOf", []):
        cond = clause.get("if", {}).get("properties", {})
        if not cond:
            continue
        cond_matched = all(
            field in fm and fm[field] == spec.get("const")
            for field, spec in cond.items()
        )
        if cond_matched:
            for field in clause.get("then", {}).get("required", []):
                if field not in fm or fm[field] in (None, ""):
                    issues.append(
                        f"  MISSING: {path} — required field '{field}' is missing (conditional on {cond})"
                    )

    return issues


def parse_frontmatter(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return None
    try:
        data = yaml.load(match.group(1), Loader=_NoDatesLoader)
    except (yaml.YAMLError, ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def find_wikilinks(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    return set(re.findall(r"\[\[([^\]]+)\]\]", text))


def collect_pages(wiki_dir: Path) -> dict[str, Path]:
    pages = {}
    for page in wiki_dir.rglob("*.md"):
        if page.name.startswith(("_beispiel-", "_example-")):
            continue
        pages[page.stem] = page
    return pages


def find_duplicate_slugs(wiki_dir: Path) -> dict[str, list[str]]:
    """Page slugs (filenames) must be unique — wikilinks resolve by slug, so two
    `foo.md` in different folders silently collide. Return {slug: [paths]} for any
    slug used more than once."""
    seen: dict[str, list[str]] = {}
    for page in wiki_dir.rglob("*.md"):
        if page.name.startswith(("_beispiel-", "_example-")):
            continue
        seen.setdefault(page.stem, []).append(str(page))
    return {slug: paths for slug, paths in seen.items() if len(paths) > 1}


def lint_frontmatter(
    pages: dict[str, Path], schema: dict, verbose: bool = False
) -> list[str]:
    issues = []
    for name, path in sorted(pages.items()):
        fm = parse_frontmatter(path)
        if fm is None:
            issues.append(f"  ERROR: {path} — no valid YAML frontmatter")
            continue
        page_issues = validate_frontmatter(fm, schema, path)
        issues.extend(page_issues)
        if verbose and not page_issues:
            print(f"  OK: {path}")
    return issues


def lint_wikilinks(pages: dict[str, Path]) -> tuple[list[str], list[str]]:
    incoming = {name: set() for name in pages}
    broken = []

    for name, path in pages.items():
        for target in find_wikilinks(path):
            if target in incoming:
                incoming[target].add(name)
            else:
                broken.append(f"  BROKEN: {path} → [[{target}]] (target does not exist)")

    skip = {"index", "log"}
    orphans = [
        f"  ORPHAN: {pages[name]} (no incoming links)"
        for name in sorted(pages)
        if name not in skip and not incoming[name]
    ]

    return broken, orphans


def _relation_target(raw) -> str:
    """Reduce a relation target to a bare page slug (tolerates [[...]] forms)."""
    target = str(raw).strip()
    if target.startswith("[[") and target.endswith("]]"):
        target = target[2:-2]
    return target.split("|", 1)[0].split("#", 1)[0].strip()


def lint_relations(pages: dict[str, Path]) -> list[str]:
    """Validate structured `relations` blocks against the schema's rules:
    each target resolves to an existing page, confidence is an allowed enum,
    required keys are present, and no unknown keys appear."""
    issues = []
    for name, path in sorted(pages.items()):
        fm = parse_frontmatter(path)
        if not fm:
            continue
        relations = fm.get("relations")
        if relations is None:
            continue
        if not isinstance(relations, list):
            issues.append(f"  RELATION: {path} — 'relations' must be a list")
            continue
        for i, rel in enumerate(relations):
            loc = f"{path} — relations[{i}]"
            if not isinstance(rel, dict):
                issues.append(f"  RELATION: {loc} is not a mapping")
                continue
            for req in ("target", "type", "confidence"):
                if not rel.get(req):
                    issues.append(f"  RELATION: {loc} — missing '{req}'")
            unknown = set(rel) - RELATION_KEYS
            if unknown:
                issues.append(f"  RELATION: {loc} — unknown key(s): {', '.join(sorted(unknown))}")
            target = _relation_target(rel.get("target", ""))
            if target and target not in pages:
                issues.append(f"  RELATION: {loc} — target [[{target}]] does not exist")
            conf = rel.get("confidence")
            if conf and conf not in RELATION_CONFIDENCE:
                issues.append(
                    f"  RELATION: {loc} — confidence '{conf}' "
                    f"(allowed: {', '.join(RELATION_CONFIDENCE)})"
                )
    return issues


def report_inference_rate(pages: dict[str, Path]) -> list[str]:
    """Report the inference-rate: share of structured relations tagged
    `inferred` or `ambiguous`. An audit signal mirroring the override-rate —
    a high share means many edges are model-asserted rather than grounded."""
    total = 0
    uncertain = 0
    grounded = 0
    for path in pages.values():
        fm = parse_frontmatter(path)
        if not fm:
            continue
        for rel in fm.get("relations", []) or []:
            if not isinstance(rel, dict):
                continue
            total += 1
            if str(rel.get("confidence", "")).lower() in ("inferred", "ambiguous"):
                uncertain += 1
            if str(rel.get("because", "")).strip():
                grounded += 1

    if total == 0:
        return ["  No structured relations yet — inference-rate n/a."]

    rate = uncertain / total
    report = [
        f"  Relations: {total} · inferred/ambiguous: {uncertain} ({rate * 100:.0f}%)",
        f"  With a `because` rationale: {grounded} ({100 * grounded // total}%)",
    ]
    if rate > INFERENCE_WARN_THRESHOLD:
        report.append(
            f"  WARNING: inference-rate {rate * 100:.0f}% > "
            f"{INFERENCE_WARN_THRESHOLD * 100:.0f}% — many relations are model-inferred; "
            f"consider grounding them in sources."
        )
    return report


def report_gate_overrides() -> list[str]:
    """Surface SOFT-GATE override activity from the audit log.

    The log records only overrides (not all gate checks), so a pass/fail *rate*
    cannot be computed — we report a **count** and recent **frequency**. Each
    line is expected to start with '- YYYY-MM-DD · <skill> · <condition> · <reason>'.
    """
    if not OVERRIDES_LOG.exists():
        return ["  No gate-overrides.log yet — no SOFT-GATE overrides recorded."]

    lines = [
        line.strip()
        for line in OVERRIDES_LOG.read_text(encoding="utf-8").splitlines()
        if line.lstrip().startswith("- ")
    ]
    total = len(lines)
    if total == 0:
        return ["  gate-overrides.log exists but contains no entries."]

    dates = []
    for line in lines:
        m = re.match(r"-\s*(\d{4}-\d{2}-\d{2})", line)
        if m:
            try:
                dates.append(datetime.date.fromisoformat(m.group(1)))
            except ValueError:
                pass

    report = [f"  Total overrides logged: {total} (a count — overrides are only ever logged when a gate is bypassed)"]
    if dates:
        recent = sum(1 for d in dates if 0 <= (datetime.date.today() - d).days <= OVERRIDE_RECENT_DAYS)
        report.append(f"  In the last {OVERRIDE_RECENT_DAYS} days: {recent}")
        if recent >= OVERRIDE_WARN_COUNT:
            report.append(
                f"  WARNING: {recent} overrides in {OVERRIDE_RECENT_DAYS} days — "
                f"routine bypass? Check skill discipline."
            )
    return report


def lint_status_distribution(pages: dict[str, Path]) -> list[str]:
    counts = {"draft": 0, "review": 0, "stable": 0, "unknown": 0}
    for path in pages.values():
        fm = parse_frontmatter(path)
        status = fm.get("status", "unknown") if fm else "unknown"
        counts[status] = counts.get(status, 0) + 1

    total = sum(counts.values())
    if total == 0:
        return ["  No pages in the wiki."]

    report = []
    for status, count in sorted(counts.items()):
        if count > 0:
            pct = count / total * 100
            report.append(f"  {status}: {count} ({pct:.0f}%)")

    draft_pct = counts["draft"] / total * 100 if total else 0
    if draft_pct > 70:
        report.append(f"  WARNING: {draft_pct:.0f}% of pages are still drafts")

    return report


def main():
    parser = argparse.ArgumentParser(description="Wiki lint for the research wiki")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Also list files that pass"
    )
    args = parser.parse_args()

    if not WIKI_DIR.exists():
        print(f"Error: directory '{WIKI_DIR}' not found.")
        sys.exit(1)

    schema = load_schema()
    pages = collect_pages(WIKI_DIR)
    print(f"Wiki lint: {len(pages)} pages found")
    print(f"Schema:    {SCHEMA_PATH}\n")

    print("=== Frontmatter check ===")
    fm_issues = lint_frontmatter(pages, schema, args.verbose)
    if fm_issues:
        print("\n".join(fm_issues))
    else:
        print("  All good.")

    print("\n=== Wikilink check ===")
    broken, orphans = lint_wikilinks(pages)
    print("\n".join(broken) if broken else "  No broken links.")
    print("\n".join(orphans) if orphans else "  No orphan pages.")

    print("\n=== Duplicate slugs ===")
    dups = find_duplicate_slugs(WIKI_DIR)
    if dups:
        for slug, paths in sorted(dups.items()):
            print(f"  DUPLICATE: '{slug}' used by {len(paths)} files → {', '.join(paths)}")
    else:
        print("  No duplicate slugs.")

    print("\n=== Relations check ===")
    rel_issues = lint_relations(pages)
    print("\n".join(rel_issues) if rel_issues else "  No relation issues.")

    print("\n=== Status distribution ===")
    print("\n".join(lint_status_distribution(pages)))

    print("\n=== Inference rate ===")
    print("\n".join(report_inference_rate(pages)))

    print("\n=== Gate overrides ===")
    print("\n".join(report_gate_overrides()))

    total_issues = len(fm_issues) + len(broken) + len(orphans) + len(rel_issues) + len(dups)
    print(f"\n{'=' * 40}")
    print(f"Total: {total_issues} issue(s) found")

    sys.exit(1 if total_issues > 0 else 0)


if __name__ == "__main__":
    main()
