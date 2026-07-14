#!/usr/bin/env python3
"""
Wiki lint: structural checks on the research wiki.

Deterministic, CI-friendly checks:
  1. Frontmatter against schema/knowledge-frontmatter.schema.json
  2. Wikilinks (broken targets, orphan pages)
  3. Citekey / bibliography integrity (see below)
  4. Status distribution

The citekey checks exist because `bibkey` is not merely a citation key: it is the
cross-project JOIN KEY that scripts/wiki-global-graph.py matches sources on. An
audit of 17 wikis found the documented convention honoured by only 40% of 511
keys — costing 17 missed joins and producing 2 false positives (one key denoting
two different papers). Nothing checked it. Now something does:

  * every .bib entry key matches the schema's bibkey pattern
  * no key defined twice in one .bib (pandoc silently takes the last)
  * every frontmatter `bibkey:` resolves to a real entry
  * every `[@key]` — in the wiki AND the manuscript — resolves
  * every `bibliography:` path a manuscript declares exists on disk. Quarto
    resolves a missing bibliography SILENTLY, renders every citation as ???, and
    exits 0. Nothing else catches this.
  * the same key never means different works in two .bib files

Content checks (contradictions between pages, stale claims) do NOT belong
here — use the semantic-wiki-review skill for those. This script only
*surfaces* the review findings that skill records as `review_flags:`
frontmatter (open flags are reported, not computed, and do not fail the
exit code); it never judges page content itself.

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

REVIEW_FLAG_KINDS = ("overstatement", "weak-support", "stale", "missing-citation", "open-question")

# Authority-ID fields on type=entity. These are the join key that makes an
# entity matchable ACROSS projects (scripts/wiki-global-graph.py); coverage is
# reported as an advisory signal, never a hard error. orcid covers living
# researchers (where gnd_id / wikidata_qid often do not).
AUTHORITY_FIELDS = ("orcid", "gnd_id", "idai_gazetteer_id", "wikidata_qid")
# Concepts have no gazetteer/ORCID identity; their controlled-vocabulary join
# key is Getty AAT (or Wikidata / GND where AAT has no matching term).
CONCEPT_AUTHORITY_FIELDS = ("getty_aat_id", "wikidata_qid", "gnd_id")


def load_schema() -> dict:
    """Load the frontmatter JSON schema. Fails loudly if missing."""
    if not SCHEMA_PATH.exists():
        print(f"Error: schema file '{SCHEMA_PATH}' not found.")
        print("Expected at the project root; scaffolded automatically from the template.")
        sys.exit(2)
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


_PY_TYPE = {"string": str, "array": list, "integer": int, "object": dict, "number": (int, float)}


def _validate_value(value, spec: dict, path: Path, label: str, issues: list[str]) -> None:
    """Recursively validate one value against a (sub)schema. Covers type, enum,
    format=date, pattern, array items, and nested objects (required, properties,
    additionalProperties=false) — so the relations[] item rules are enforced too,
    not just 'is a dict'. Keeps the TYPE/INVALID/DATE/PATTERN/MISSING/UNKNOWN tags."""
    expected = spec.get("type")
    if expected in _PY_TYPE and not isinstance(value, _PY_TYPE[expected]):
        issues.append(f"  TYPE: {path} — '{label}' must be {expected} (got {type(value).__name__})")
        return  # type is wrong; deeper checks would be noise
    if "enum" in spec and value not in spec["enum"]:
        allowed = ", ".join(map(str, spec["enum"]))
        issues.append(f"  INVALID: {path} — {label}='{value}' (allowed: {allowed})")
    if spec.get("format") == "date" and isinstance(value, str):
        # Require strict YYYY-MM-DD; date.fromisoformat() alone also accepts
        # basic (20260415) and week dates (2026-W15-3), which the schema forbids.
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            issues.append(f"  DATE: {path} — {label}='{value}' must be YYYY-MM-DD")
        else:
            try:
                datetime.date.fromisoformat(value)
            except ValueError:
                issues.append(f"  DATE: {path} — {label}='{value}' is not a real calendar date")
    if spec.get("pattern") and isinstance(value, str) and not re.match(spec["pattern"], value):
        issues.append(f"  PATTERN: {path} — {label}='{value}' violates {spec['pattern']}")
    if expected == "array" and isinstance(value, list):
        item_spec = spec.get("items")
        if isinstance(item_spec, dict):
            for i, item in enumerate(value):
                _validate_value(item, item_spec, path, f"{label}[{i}]", issues)
    if isinstance(value, dict) and (expected == "object" or "properties" in spec):
        sub_props = spec.get("properties", {})
        for req in spec.get("required", []):
            if req not in value or value[req] in (None, ""):
                issues.append(f"  MISSING: {path} — '{label}.{req}' is required")
        if spec.get("additionalProperties") is False:
            for key in value:
                if key not in sub_props:
                    issues.append(f"  UNKNOWN: {path} — '{label}.{key}' is not an allowed property")
        for key, sub_value in value.items():
            if key in sub_props and sub_value is not None:
                _validate_value(sub_value, sub_props[key], path, f"{label}.{key}", issues)


def validate_frontmatter(fm: dict, schema: dict, path: Path) -> list[str]:
    """Draft-07 validator covering the subset our schema uses: required, type,
    enum, format=date, pattern, array items, nested objects (required /
    properties / additionalProperties), and conditional if/then from allOf.
    (Dates are kept as strings by _NoDatesLoader so format can be checked.)"""
    issues: list[str] = []
    props = schema.get("properties", {})

    for field in schema.get("required", []):
        if field not in fm or fm[field] in (None, ""):
            issues.append(f"  MISSING: {path} — required field '{field}' is missing")

    for field, value in fm.items():
        if field not in props or value is None:
            continue
        _validate_value(value, props[field], path, field, issues)

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


def _is_generated_export(page: Path) -> bool:
    """True for files under the generated ``knowledge/_meta/graph/`` export dir
    (``GRAPH_REPORT.md`` and friends, written by ``wiki-to-graph.py``). These are
    build artefacts, not wiki pages, so lint must not treat them as content — a
    stray ``GRAPH_REPORT.md`` would otherwise be flagged as a page with no
    frontmatter and as an orphan."""
    return page.parent.name == "graph" and page.parent.parent.name == "_meta"


def collect_pages(wiki_dir: Path) -> dict[str, Path]:
    pages = {}
    for page in wiki_dir.rglob("*.md"):
        if page.name.startswith(("_beispiel-", "_example-")) or _is_generated_export(page):
            continue
        pages[page.stem] = page
    return pages


def find_duplicate_slugs(wiki_dir: Path) -> dict[str, list[str]]:
    """Page slugs (filenames) must be unique — wikilinks resolve by slug, so two
    `foo.md` in different folders silently collide. Return {slug: [paths]} for any
    slug used more than once."""
    seen: dict[str, list[str]] = {}
    for page in wiki_dir.rglob("*.md"):
        if page.name.startswith(("_beispiel-", "_example-")) or _is_generated_export(page):
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
        for raw in find_wikilinks(path):
            # Normalise `[[b|alias]]` / `[[b#heading]]` to the bare slug before
            # resolving — otherwise a valid aliased/anchored link is falsely
            # flagged BROKEN and its target falsely reported as an orphan (the
            # graph builder normalises the same way). Self-links don't count as
            # an incoming link — else a page linking only to itself hides as
            # non-orphan.
            target = _relation_target(raw)
            if not target or target == name:
                continue
            if target in incoming:
                incoming[target].add(name)
            else:
                broken.append(f"  BROKEN: {path} → [[{raw}]] (target does not exist)")

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


def report_review_flags(pages: dict[str, Path]) -> tuple[list[str], int]:
    """Surface single-page content-review findings (`review_flags`) raised by
    semantic-wiki-review.

    Open flags are a *content* signal, not a structural defect — they are
    reported here (and gate drafting via the drafting-manuscript SOFT-GATE),
    but they deliberately do NOT count toward the lint exit code. A wiki with
    open, known review findings is not malformed. Malformed flags (bad enum,
    missing key, unknown property) are already caught by the frontmatter schema
    check above, which does fail the build.
    """
    lines: list[str] = []
    open_total = 0
    resolved_total = 0
    for name, path in sorted(pages.items()):
        fm = parse_frontmatter(path)
        if not fm:
            continue
        flags = fm.get("review_flags")
        if not isinstance(flags, list):
            continue
        for flag in flags:
            if not isinstance(flag, dict):
                continue
            if flag.get("state") == "resolved":
                resolved_total += 1
                continue
            open_total += 1
            kind = flag.get("kind", "?")
            detail = str(flag.get("detail", "")).strip()
            suffix = f" — {detail}" if detail else ""
            lines.append(f"  OPEN [{kind}]: {path}{suffix}")

    if open_total == 0:
        tail = f" ({resolved_total} resolved, kept for audit)" if resolved_total else ""
        return ([f"  No open review flags.{tail}"], 0)

    header = [
        f"  {open_total} open review flag(s) — advisory content findings. These "
        f"gate drafting (drafting-manuscript SOFT-GATE), not the lint exit code."
    ]
    return (header + lines, open_total)


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


def report_authority_coverage(pages: dict[str, Path], verbose: bool = False) -> list[str]:
    """Advisory: how many `type=entity` pages carry an authority ID
    (gnd_id / idai_gazetteer_id / wikidata_qid).

    Authority IDs are the join key that makes an entity matchable *across*
    projects (`scripts/wiki-global-graph.py overlap`) — an untagged entity is
    invisible to cross-project linkage and to a future merged graph. This is
    **not** an error (a dataset / method / software entity may have no
    applicable ID) and does not affect the exit code; it is surfaced so the gap
    is visible and the untagged list doubles as a tagging worklist.
    """
    entities = []
    for slug, path in pages.items():
        if "_meta" in path.parts:          # index/log are meta, not content pages
            continue
        fm = parse_frontmatter(path)
        if fm and fm.get("type") == "entity":
            has_id = any(str(fm.get(f, "")).strip() for f in AUTHORITY_FIELDS)
            entities.append((slug, has_id))
    if not entities:
        return ["  No entity pages."]

    untagged = sorted(slug for slug, has_id in entities if not has_id)
    tagged = len(entities) - len(untagged)
    pct = tagged / len(entities) * 100
    report = [f"  {tagged} of {len(entities)} entity page(s) carry an authority ID ({pct:.0f}%)."]
    if untagged:
        report.append(
            "  Untagged entities are invisible to cross-project linkage. Sites should "
            "carry idai_gazetteer_id; living researchers orcid (the key that covers "
            "working scientists — prefer it over gnd_id / wikidata_qid); resolve via "
            "dao-paper-search resolve_site / resolve_author. Datasets / methods / "
            "software may legitimately have none — review the list.")
        if verbose:
            report.append("  Untagged entities:")
            report.extend(f"    - {slug}" for slug in untagged)
        else:
            preview = ", ".join(untagged[:8]) + (" …" if len(untagged) > 8 else "")
            report.append(f"  Untagged ({len(untagged)}): {preview}   [--verbose for the full worklist]")
    return report


def report_concept_coverage(pages: dict[str, Path], verbose: bool = False) -> list[str]:
    """Advisory: how many `type=concept` pages carry a controlled-vocabulary
    join key (getty_aat_id / wikidata_qid / gnd_id).

    Concepts have no authority ID by default, so cross-project *concept* overlap
    — the deepest tissue of a methods portfolio (a method recurring across
    modules) — is invisible until they are tagged. This is **not** an error (a
    project-specific concept may have no external term) and does not affect the
    exit code; it is surfaced so the gap is visible and doubles as a worklist.
    """
    concepts = []
    for slug, path in pages.items():
        if "_meta" in path.parts:          # index/log are meta, not content pages
            continue
        fm = parse_frontmatter(path)
        if fm and fm.get("type") == "concept":
            has_id = any(str(fm.get(f, "")).strip() for f in CONCEPT_AUTHORITY_FIELDS)
            concepts.append((slug, has_id))
    if not concepts:
        return ["  No concept pages."]

    untagged = sorted(slug for slug, has_id in concepts if not has_id)
    tagged = len(concepts) - len(untagged)
    pct = tagged / len(concepts) * 100
    report = [f"  {tagged} of {len(concepts)} concept page(s) carry a vocabulary ID ({pct:.0f}%)."]
    if untagged:
        report.append(
            "  Untagged concepts are invisible to cross-project concept linkage. Tag "
            "shared methods/concepts with getty_aat_id (vocab.getty.edu/aat), or "
            "wikidata_qid / gnd_id where AAT has no term; a project-specific concept "
            "may legitimately have none — review the list.")
        if verbose:
            report.append("  Untagged concepts:")
            report.extend(f"    - {slug}" for slug in untagged)
        else:
            preview = ", ".join(untagged[:8]) + (" …" if len(untagged) > 8 else "")
            report.append(f"  Untagged ({len(untagged)}): {preview}   [--verbose for the full worklist]")
    return report


# ---------------------------------------------------------------------------
# Citekey / bibliography integrity
# ---------------------------------------------------------------------------

BUILD_DIRS = ("_output", "_files", ".quarto", "node_modules")
BIBLIOGRAPHY_RE = re.compile(r"^\s*bibliography:\s*(.+?)\s*$", re.M)

# Quarto cross-references share the `@name` syntax with pandoc citations but are
# NOT citations. Flagging them produces ~150 false errors portfolio-wide, which
# is exactly how a linter gets switched off.
QUARTO_XREF = re.compile(
    r"^(?:sec|fig|tbl|lst|eq|thm|lem|cor|prp|cnj|def|exm|exr|sol|rem|tip|nte|wrn|imp|cau)-")
# A citation: `@key`, `[@key]`, `-@key`. NOT an email (`foo@bar`), NOT a word-
# internal @, and NOT an escaped `\@` — the backslash is precisely how an author
# says "this at-sign is literal", as in the metric notation `AP\@IoU0.5`.
CITE_RE = re.compile(r"(?<![A-Za-z0-9_`@.\\])@([A-Za-z][A-Za-z0-9_:.+/-]*[A-Za-z0-9])")


def _library_pdf_dir() -> Path | None:
    """<library>/pdf, or None if this machine has no library configured.

    Imported from the sibling library.py by path, not by package name: these scripts
    ship into projects as loose files and are also loaded by the test suite via
    importlib, so there is no package to import from.
    """
    import importlib.util
    mod_path = Path(__file__).resolve().parent / "library.py"
    if not mod_path.is_file():
        return None
    try:
        spec = importlib.util.spec_from_file_location("_rs_library", mod_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.pdf_dir(required=False)
    except Exception:                                  # pragma: no cover
        return None


def _not_build(path: Path) -> bool:
    return not any(d in path.parts for d in BUILD_DIRS)


def _strip_code(text: str) -> str:
    """Blank out fenced and inline code — a citation shown as an example is not
    a citation. (Blank, not delete, so nothing shifts.)"""
    text = re.sub(r"```.*?```", lambda m: " " * len(m.group(0)), text, flags=re.S)
    return re.sub(r"`[^`\n]*`", lambda m: " " * len(m.group(0)), text)


def _bib_field(body: str, name: str) -> str:
    """One BibTeX field, brace-balanced, case-insensitive."""
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


def iter_bib_entries(text: str):
    """Yield (key, body) per entry, walking braces to find the real end.

    Anchoring on '\\n}' (the obvious regex) silently drops every single-line
    entry — and real bibs mix both shapes freely. In one project that would have
    hidden 98 of 122 entries.
    """
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


def lint_citekeys(pages: dict[str, Path], schema: dict) -> tuple[list[str], list[str]]:
    """Citekey + bibliography integrity. Returns (hard_issues, advisory_lines).

    `bibkey` is the cross-project JOIN KEY (scripts/wiki-global-graph.py matches
    sources across projects on it). An audit of 17 wikis found the convention was
    honoured by only 40% of 511 keys, which cost 17 missed joins and produced 2
    false positives (one key denoting two different papers). Nothing checked it —
    hence this.
    """
    hard: list[str] = []
    advisory: list[str] = []

    pattern = schema.get("properties", {}).get("bibkey", {}).get("pattern")
    key_re = re.compile(pattern) if pattern else None

    bibs = sorted(p for p in Path("output").glob("**/*.bib") if _not_build(p)) \
        if Path("output").is_dir() else []
    if not bibs:
        advisory.append("  No .bib under output/ — citekey checks skipped.")
        return hard, advisory

    # ---- 1 + 2: every entry key well-shaped; no key defined twice in one file
    defined: dict[str, tuple[Path, str, str, str]] = {}   # key -> (bib, title, doi, pages)
    for bib in bibs:
        text = bib.read_text(encoding="utf-8", errors="replace")
        seen: set[str] = set()
        for key, body in iter_bib_entries(text):
            if key_re and not key_re.match(key):
                hard.append(f"  CITEKEY: {bib} → '{key}' does not match the "
                            f"surname-year-shorttitle convention")
            if key in seen:
                # pandoc silently takes the last one
                hard.append(f"  DUPLICATE-KEY: {bib} defines '{key}' more than once")
            seen.add(key)
            title = _bib_field(body, "title").lower()
            doi = _bib_field(body, "doi").lower()
            # ---- 6: same key in two bibs, but a DIFFERENT work behind it
            if key in defined:
                prev_bib, prev_title, prev_doi, _ = defined[key]
                if doi and prev_doi:
                    differs = doi != prev_doi           # two DOIs — decisive
                else:
                    # A DOI on only ONE side proves nothing about difference, so fall
                    # back to the title. But the SAME work gets transcribed at
                    # different lengths — an archived bib carries "Yahwistic Diversity
                    # and the Hebrew Bible" where the current one carries the full
                    # "…: State of the Field, Desiderata and Research Perspectives…".
                    # Treat a prefix relation as the same work, or every truncated
                    # title reads as a divergence and the real signal drowns.
                    differs = bool(title and prev_title) and not (
                        title.startswith(prev_title) or prev_title.startswith(title))
                if differs:
                    hard.append(f"  KEY-DIVERGENCE: '{key}' means different works in "
                                f"{prev_bib} and {bib}")
            defined[key] = (bib, title, doi, _bib_field(body, "pages"))

    # ---- 5: every bibliography: path a manuscript declares must exist
    for f in sorted(list(Path("output").glob("**/*.qmd"))
                    + list(Path("output").glob("**/_quarto.yml"))):
        if not _not_build(f):
            continue
        for m in BIBLIOGRAPHY_RE.finditer(f.read_text(encoding="utf-8", errors="replace")):
            raw = m.group(1).strip().strip("\"'")
            for cand in [c.strip().strip("\"'") for c in raw.strip("[]").split(",")]:
                if cand and not (f.parent / cand).exists():
                    # Quarto resolves a missing bibliography silently and renders
                    # EVERY citation as ???, exiting 0. Nothing else catches this.
                    hard.append(f"  DEAD-BIBLIOGRAPHY: {f} → '{cand}' does not exist")

    # ---- 3: every frontmatter bibkey resolves to a real entry
    for slug, path in sorted(pages.items()):
        fm = parse_frontmatter(path)
        key = fm.get("bibkey") if isinstance(fm, dict) else None
        if key and str(key) not in defined:
            hard.append(f"  UNRESOLVED-BIBKEY: {path} → '{key}' is in no .bib")

    # ---- 4: every citation in the wiki AND the manuscript resolves.
    # knowledge/_meta/ is excluded: log.md, index.md and literaturguide.md are
    # bookkeeping and provenance, not manuscript-bound prose. They contain German
    # sentences like "durchgehend mit @citekeys belegt" — flagging those is the
    # kind of noise that gets a linter switched off.
    cited: set[str] = set()
    sources = [p for p in Path(".").glob("knowledge/**/*.md")
               if _not_build(p) and "_meta" not in p.parts
               and not p.name.startswith(("_beispiel-", "_example-"))]
    sources += [p for p in Path("output").glob("**/*.qmd") if _not_build(p)] \
        if Path("output").is_dir() else []
    for f in sorted(sources):
        body = _strip_code(f.read_text(encoding="utf-8", errors="replace"))
        body = re.sub(r"^---\n.*?\n---", "", body, count=1, flags=re.S)   # drop frontmatter
        for m in CITE_RE.finditer(body):
            key = m.group(1)
            if QUARTO_XREF.match(key):
                continue
            cited.add(key)
            if key not in defined:
                hard.append(f"  BROKEN-CITATION: {f} → '@{key}' is in no .bib")

    # ---- 7 (advisory): entries nobody cites and no source page describes
    with_page = {str(parse_frontmatter(p).get("bibkey"))
                 for p in pages.values() if isinstance(parse_frontmatter(p), dict)}
    unused = sorted(set(defined) - cited - with_page)
    if unused:
        advisory.append(f"  Uncited, no source page ({len(unused)}): "
                        + ", ".join(unused[:8]) + (" …" if len(unused) > 8 else ""))

    # ---- 8 (advisory): every source page's bibkey should have a PDF in the shared
    # library (<library>/pdf/<bibkey>.pdf — the filename IS the citekey).
    #
    # ADVISORY, AND required=False, ON PURPOSE. The library is machine-local and does
    # not exist in CI; a hard gate — or a raised LibraryNotConfigured — would fail
    # every build and every contributor who has not configured it yet. A missing PDF
    # is a worklist, not a broken repo.
    lib_pdfs = _library_pdf_dir()
    if lib_pdfs is None:
        if with_page:
            advisory.append("  No source library configured on this machine "
                            "(RESEARCH_LIBRARY / .research-library) — PDF check skipped.")
    else:
        stems = {p.stem for p in lib_pdfs.glob("*.pdf")}
        missing = sorted(k for k in with_page if k and k != "None" and k not in stems)
        if missing:
            advisory.append(
                f"  bibkey with no PDF in the library ({len(missing)} of {len(with_page)}): "
                + ", ".join(missing[:6]) + (" …" if len(missing) > 6 else ""))
        elif with_page:
            advisory.append(f"  All {len(with_page)} bibkeys have a PDF in the library.")

        # ---- 9 (advisory): the OTHER direction — a source that was acquired but never
        # ingested. Check 8 asks "does every source page have a PDF?"; nothing asked
        # "does every PDF have a source page?", so a source could sit in the library,
        # paid for and downloaded, and simply be forgotten. Across 17 live wikis that
        # was true of 146 sources — one project had 48 of its 55 PDFs un-ingested.
        #
        # NOT the same as check 7. Check 7 reports entries nobody CITES and no page
        # describes; an entry cited in the manuscript but never ingested slips past it.
        # This one is about the wiki's own coverage of what is on disk.
        acquired = {k for k in defined if k in stems}
        not_ingested = sorted(acquired - {k for k in with_page if k and k != "None"})
        if not_ingested:
            advisory.append(
                f"  Acquired but NOT ingested ({len(not_ingested)} of {len(acquired)}): "
                + ", ".join(not_ingested[:6]) + (" …" if len(not_ingested) > 6 else ""))
            advisory.append("    → run ingest-source on these; the PDFs are already in "
                            "the library.")
        elif acquired:
            advisory.append(f"  All {len(acquired)} acquired sources are ingested.")

    # ---- 10 (HARD): every page anchor must fall inside the work's printed page range.
    #
    # This is the check that catches a fabricated citation. `acquire-sources` downloads
    # Open-Access PDFs, and a green-OA deposit is very often the author's ACCEPTED
    # MANUSCRIPT, not the typeset article: no printed page numbers exist in it. An
    # ingester reading it has nothing to anchor to — so it anchors to the physical PDF
    # page and writes "(p. 3)". The result is a citation that is checkable and wrong,
    # which is strictly worse than no citation at all: it survives review because it
    # looks like evidence, and `drafting-manuscript` reaches back into the wrong page.
    #
    # Found on the live corpus: `crema-2010-probabilistic` cited at "(p. 2)", "(p. 9)"
    # in two projects — the article is printed on pages 1118–1130. `lake-2003-visibility`
    # cited at "(pp. 1–7)" — printed 689–707.
    #
    # HARD, not advisory. A page outside the printed range is not a worklist item, a
    # rough edge, or a machine-specific gap. It is a false statement about a source.
    #
    # Only checked where the .bib gives a real page RANGE. Article-number journals
    # (PLOS, Entangled Religions) print no range, and a book chapter may legitimately
    # omit one — those are skipped, not guessed at.
    for slug, path in sorted(pages.items()):
        fm = parse_frontmatter(path)
        key = str(fm.get("bibkey")) if isinstance(fm, dict) and fm.get("bibkey") else None
        if not key or key not in defined:
            continue
        spans = _printed_spans(defined[key][3])
        if not spans:
            continue
        text = _own_sections(_strip_code(path.read_text(encoding="utf-8", errors="replace")))
        bad = sorted({n for n in _cited_pages(text)
                      if not any(a <= n <= b for a, b in spans)})
        if bad:
            shown = ", ".join(str(n) for n in bad[:8]) + (" …" if len(bad) > 8 else "")
            printed = ", ".join(f"{a}–{b}" for a, b in spans)
            hard.append(
                f"  PAGE-OUT-OF-RANGE: {path} → cites p. {shown}, but '{key}' is printed "
                f"on {printed}. The PDF may be an author's manuscript, not the published "
                f"article — check scripts/check-pdf-version.py.")

    if not hard and not advisory:
        advisory.append(f"  {len(defined)} citekeys, all resolving.")
    return hard, advisory


# A page anchor as the ingest skill writes it: "(p. 12)", "(pp. 12–14)", "(pp. 12, 15)".
# Deliberately narrow — a bare "12" in prose is not a citation, and "(fig. 3)" is not a page.
PAGE_ANCHOR = re.compile(r"\(\s*pp?\.\s*([0-9][0-9,\s–—-]*)\)")

# Sections where a page anchor refers to a DIFFERENT work, not the ingested one.
# `## Connections` is the offender: "Cited by [[gillings-2009-affordance]] (p. 344)" is
# Gillings' page 344, not Ogburn's — and Ogburn is printed on 405–413. Checking those
# would fire on correct pages, and a hard check with false positives gets switched off.
FOREIGN_SECTIONS = re.compile(
    r"^##\s+(connections|mentioned entities|related|references|see also|"
    r"verbindungen|erwähnte entitäten)\b", re.I | re.M)


def _own_sections(text: str) -> str:
    """Drop the sections that talk about OTHER works, keep the ones about this source.

    The ingest template puts claims, quotes, examples and boundary — everything that
    describes *this* source — before `## Connections`. Everything a page says about
    other works lives at the end, and its page anchors belong to those works.
    """
    out, skipping = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            skipping = bool(FOREIGN_SECTIONS.match(line))
        if not skipping:
            out.append(line)
    return "\n".join(out)


def _cited_pages(text: str) -> set[int]:
    out: set[int] = set()
    for m in PAGE_ANCHOR.finditer(text):
        for part in re.split(r",", m.group(1)):
            part = part.strip()
            r = re.match(r"^(\d+)\s*[–—-]\s*(\d+)$", part)
            if r:
                a, b = int(r.group(1)), int(r.group(2))
                if a <= b:
                    out.update({a, b})       # endpoints suffice; the span between is implied
            elif part.isdigit():
                out.add(int(part))
    return out


def _printed_spans(pages_field: str) -> list[tuple[int, int]]:
    """The printed page range(s) from a .bib `pages` field.

    Multi-segment ranges are real and must not be flagged: a magazine article continues
    at the back of the issue, and our own `burnett-2016-ammon` is printed on
    `26--40, 66--67`. Treating that as a single 26–67 span would hide a real error;
    treating it as one range 26–40 would invent one.
    """
    spans: list[tuple[int, int]] = []
    for seg in re.split(r"[;,]", pages_field or ""):
        m = re.search(r"(\d+)\s*-{1,3}\s*(\d+)", seg)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a <= b:
                spans.append((a, b))
    return spans


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

    print("\n=== Citekey / bibliography integrity ===")
    cite_issues, cite_advisory = lint_citekeys(pages, schema)
    print("\n".join(cite_issues) if cite_issues else "  All citekeys well-formed and resolving.")
    if cite_advisory:
        print("\n".join(cite_advisory))

    print("\n=== Relations check ===")
    rel_issues = lint_relations(pages)
    print("\n".join(rel_issues) if rel_issues else "  No relation issues.")

    print("\n=== Status distribution ===")
    print("\n".join(lint_status_distribution(pages)))

    print("\n=== Inference rate ===")
    print("\n".join(report_inference_rate(pages)))

    print("\n=== Review flags ===")
    review_lines, _open_flags = report_review_flags(pages)
    print("\n".join(review_lines))

    print("\n=== Authority-ID coverage (entities) ===")
    print("\n".join(report_authority_coverage(pages, args.verbose)))

    print("\n=== Vocabulary coverage (concepts) ===")
    print("\n".join(report_concept_coverage(pages, args.verbose)))

    print("\n=== Gate overrides ===")
    print("\n".join(report_gate_overrides()))

    total_issues = (len(fm_issues) + len(broken) + len(orphans) + len(rel_issues)
                    + len(dups) + len(cite_issues))
    print(f"\n{'=' * 40}")
    print(f"Total: {total_issues} issue(s) found")

    sys.exit(1 if total_issues > 0 else 0)


if __name__ == "__main__":
    main()
