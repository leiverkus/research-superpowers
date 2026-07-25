#!/usr/bin/env python3
"""State-triggered drift check, run at session start (stdlib only).

WHY STATE, NOT TIME
-------------------
Every kind of drift this plugin knows is caused by an ACTION, not by the passage
of time: an ingest writes keywords the master bib does not have yet, a manual
VPN download drops a PDF the index has not seen, a teammate's Nextcloud sync
moves the shared library under you, an edit in Obsidian breaks a wikilink.
Actions inside a session are handled by the skills that cause them (ingest runs
lint, add-to-library re-indexes). This hook covers the out-of-band rest — and
it triggers on OBSERVED STATE CHANGE, never on a calendar: fingerprints of the
library, the master bib, the registered projects' bibs and the current wiki are
compared against the last run. Nothing changed → nothing runs, nothing is said.
A daily "all quiet" report is ceremony; silence is the correct output.

WHAT IT MAY AND MAY NOT DO
--------------------------
Report-only, with one exception: `bib-search.py index` (an incremental update of
a DERIVED cache) may run if an index already exists. Everything else — merging
bibs, OCR, PDF optimisation, citekey migration — is somebody's decision, so it
is surfaced as a finding with the ready-to-run command, never executed.

FIRST RUN IS A SILENT BASELINE
------------------------------
With no prior state there is nothing to compare against, so the first run only
records fingerprints. Reporting "drift" against nothing would front-load a wall
of findings onto the install experience. To inspect the current state on
demand, run with --force (the `drift-report` skill does).

STATE
-----
    ~/.cache/research-superpowers/drift-state.json    fingerprints of last look
    ~/.cache/research-superpowers/last-drift-report.md  most recent findings
    ~/.config/research-superpowers/projects           registry: one project root
                                                      per line, # comments. The
                                                      hook auto-registers the
                                                      project it starts in.

Kill switch: RESEARCH_SUPERPOWERS_NO_DRIFT_CHECK=1 (exits before anything,
including the state write).

CLI (used by the drift-report skill; the hook passes no flags):
    python3 hooks/drift_check.py --force   # ignore fingerprints, check everything
    python3 hooks/drift_check.py --human   # plain text instead of hook JSON
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

STATE_VERSION = 1
SUBPROC_TIMEOUT = 45          # per check — one slow check must not eat the budget
INDEX_TIMEOUT = 60            # incremental index: 0 s typical, ~11 s worst measured
BLOAT_BYTES = 40 * 1024 * 1024

PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT")
                   or Path(__file__).resolve().parent.parent)


# ── where things live ────────────────────────────────────────────────────────

def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME")
    return (Path(base) if base else Path.home() / ".cache") / "research-superpowers"


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    return (Path(base) if base else Path.home() / ".config") / "research-superpowers"


def state_path() -> Path:
    return cache_dir() / "drift-state.json"


def registry_path() -> Path:
    return config_dir() / "projects"


def find_library(cwd: Path) -> Path | None:
    """Same resolution order as the template's library.py: env → project dotfile
    → global config. Re-implemented (15 lines) rather than imported: the hook
    must work outside any project, where there is no scripts/library.py."""
    for candidate in (
        os.environ.get("RESEARCH_LIBRARY"),
        _read_line(cwd / ".research-library"),
        _read_line(config_dir() / "library"),
    ):
        if candidate:
            p = Path(candidate).expanduser()
            if (p / "pdf").is_dir():
                return p
    return None


def _read_line(p: Path) -> str | None:
    try:
        return p.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def is_research_project(p: Path) -> bool:
    return (p / "knowledge").is_dir() and (p / "scripts" / "lint-wiki.py").is_file()


def plugin_cmd(script: str) -> str:
    """A runnable command for a PLUGIN-ONLY script.

    `merge-bibs.py` and `migrate-citekeys.py` live in the plugin, NOT in the
    template — so a project has no `scripts/merge-bibs.py`, and a finding that
    says to run one gets 'No such file or directory'. Always emit the absolute
    plugin path for these; template-mirrored tools (bib-search, optimize-pdf,
    lint-wiki) keep their project-relative form, which is what the user types.
    """
    return f"python3 {PLUGIN_ROOT / 'scripts' / script}"


def registry_expansion() -> str:
    """A copy-pasteable expansion of the project registry.

    Command substitution word-splits in both bash and zsh (verified), unlike
    an unquoted parameter expansion, which zsh leaves as ONE argument — the
    trap that makes `--roots $ROOTS` silently pass a single path.
    """
    return f'$(grep -v "^#" {registry_path()})'


def scripts_dir_for(cwd: Path) -> Path:
    """The project's own scripts when inside a project, else the plugin's
    template copy — identical files, kept in sync by the release process."""
    if (cwd / "scripts" / "bib-search.py").is_file():
        return cwd / "scripts"
    return PLUGIN_ROOT / "templates" / "research-project-template" / "scripts"


def read_registry() -> list[Path]:
    try:
        lines = registry_path().read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    roots = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#"):
            p = Path(line).expanduser()
            if p.is_dir():
                # resolve() so /var vs /private/var (macOS) or a symlinked
                # checkout can never make one project count as two
                roots.append(p.resolve())
    return roots


def register_project(root: Path) -> None:
    """Plugin-internal bookkeeping (like the state file), so auto-append is not
    a 'silent mutation' of user content. Idempotent."""
    reg = registry_path()
    root = root.resolve()
    known = {str(p) for p in read_registry()}
    if str(root) in known:
        return
    reg.parent.mkdir(parents=True, exist_ok=True)
    header = "" if reg.exists() else (
        "# research-superpowers project registry — one project root per line.\n"
        "# Auto-appended by the session-start drift check; edit freely.\n")
    with reg.open("a", encoding="utf-8") as f:
        f.write(header + str(root) + "\n")


# ── fingerprints ─────────────────────────────────────────────────────────────

def _sha1_file(p: Path) -> str | None:
    try:
        return hashlib.sha1(p.read_bytes()).hexdigest()
    except OSError:
        return None


def fp_library(lib: Path) -> dict:
    pdfs = list((lib / "pdf").glob("*.pdf"))
    stats = [p.stat() for p in pdfs]
    return {
        "pdf_count": len(pdfs),
        "max_mtime": max((int(s.st_mtime) for s in stats), default=0),
        "total_size": sum(s.st_size for s in stats),
        "bib_sha": _sha1_file(lib / "references.bib"),
    }


def fp_project_bib(root: Path) -> str | None:
    return _sha1_file(root / "output" / "bibtex" / "references.bib")


def fp_wiki(root: Path) -> dict:
    mds = list((root / "knowledge").rglob("*.md"))
    return {
        "md_count": len(mds),
        "max_mtime": max((int(p.stat().st_mtime) for p in mds), default=0),
    }


# ── check runners (module-level so tests can replace them) ───────────────────

def _run(cmd: list[str], cwd: Path | None, timeout: int) -> tuple[int, str]:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def run_lint(project: Path) -> tuple[int, str]:
    return _run([sys.executable, str(project / "scripts" / "lint-wiki.py")],
                cwd=project, timeout=SUBPROC_TIMEOUT)


def run_index(scripts: Path, cwd: Path) -> tuple[int, str]:
    return _run([sys.executable, str(scripts / "bib-search.py"), "index"],
                cwd=cwd, timeout=INDEX_TIMEOUT)


def run_status(scripts: Path, cwd: Path) -> tuple[int, str]:
    return _run([sys.executable, str(scripts / "bib-search.py"), "status", "--json"],
                cwd=cwd, timeout=SUBPROC_TIMEOUT)


def run_bibkeys(scripts: Path, roots: list[Path]) -> tuple[int, str]:
    return _run([sys.executable, str(scripts / "wiki-global-graph.py"), "bibkeys",
                 *map(str, roots)], cwd=None, timeout=SUBPROC_TIMEOUT)


def index_exists(lib: Path) -> bool:
    h = hashlib.sha1(str(lib.resolve()).encode("utf-8")).hexdigest()[:8]
    return (cache_dir() / f"index-{h}.sqlite").exists()


# ── merge drift (pure, count-level — merge-bibs.py stays the resolver) ───────

_ENTRY = re.compile(r"@\w+\s*\{\s*([^,\s]+)\s*,(.*?)(?=@\w+\s*\{|\Z)", re.DOTALL)
_KEYWORDS = re.compile(r"keywords\s*=\s*[{\"](.+?)[}\"]\s*,?\s*$",
                       re.MULTILINE | re.DOTALL)


def _bib_map(text: str) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for m in _ENTRY.finditer(text):
        kw = _KEYWORDS.search(m.group(2))
        terms = {t.strip().casefold() for t in kw.group(1).split(";")} if kw else set()
        out[m.group(1)] = {t for t in terms if t}
    return out


def merge_drift(master_bib: Path, roots: list[Path]) -> dict:
    """Keys and keyword terms that exist in project bibs but not (yet) in the
    master. Counting only — resolution belongs to merge-bibs.py, whose parser
    is the authoritative one."""
    try:
        master = _bib_map(master_bib.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return {"missing_keys": [], "keys_with_new_terms": [], "unreadable": True}
    missing_keys: set[str] = set()
    keys_with_new_terms: set[str] = set()
    for root in roots:
        bib = root / "output" / "bibtex" / "references.bib"
        try:
            proj = _bib_map(bib.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        for key, terms in proj.items():
            if key not in master:
                missing_keys.add(key)
            elif terms - master[key]:
                keys_with_new_terms.add(key)
    return {"missing_keys": sorted(missing_keys),
            "keys_with_new_terms": sorted(keys_with_new_terms),
            "unreadable": False}


# ── the check itself ─────────────────────────────────────────────────────────

def collect_findings(cwd: Path, state: dict, *, force: bool) -> tuple[list[str], list[str], dict]:
    """Returns (act_now, good_to_know, new_state)."""
    act: list[str] = []
    info: list[str] = []
    new_state: dict = {"version": STATE_VERSION, "projects": dict(state.get("projects", {})),
                       "wiki": dict(state.get("wiki", {}))}
    baseline = "version" not in state

    lib = find_library(cwd)
    scripts = scripts_dir_for(cwd)
    project = cwd if is_research_project(cwd) else None
    if project:
        register_project(project)
    registry = read_registry()

    # ── current project's wiki: out-of-band edits → lint ────────────────────
    if project:
        wfp = fp_wiki(project)
        new_state["wiki"][str(project)] = wfp
        changed = force or state.get("wiki", {}).get(str(project)) != wfp
        if changed and not (baseline and not force):
            try:
                code, out = run_lint(project)
                if code != 0:
                    tail = "\n".join(out.strip().splitlines()[-12:])
                    act.append(f"Wiki changed outside a session and lint now FAILS "
                               f"({project.name}):\n{tail}\n"
                               f"→ python scripts/lint-wiki.py")
            except Exception as e:  # a broken check must never block session start
                info.append(f"lint check failed to run: {e}")

    # ── shared library: new/changed PDFs, master bib ────────────────────────
    lib_changed = False
    if lib:
        lfp = fp_library(lib)
        new_state["library"] = lfp
        lib_changed = force or state.get("library") != lfp
        if lib_changed and not (baseline and not force):
            try:
                if index_exists(lib):
                    run_index(scripts, cwd)
                    _, status_out = run_status(scripts, cwd)
                    st = json.loads(status_out)
                    if st.get("no_text"):
                        act.append(f"{len(st['no_text'])} PDF(s) in the library have NO "
                                   f"text layer (scans, invisible to search): "
                                   f"{', '.join(st['no_text'][:5])}"
                                   f"{' …' if len(st['no_text']) > 5 else ''}\n"
                                   f"→ ocrmypdf, then: python scripts/bib-search.py index")
                    if st.get("failed"):
                        act.append(f"{len(st['failed'])} PDF(s) unreadable by pdftotext "
                                   f"→ python scripts/bib-search.py status")
                    info.append(f"search index updated ({st.get('docs', '?')} documents, "
                                f"{st.get('pages', '?')} pages)")
                else:
                    info.append("library changed but no search index exists yet "
                                "→ python scripts/bib-search.py index")
                big = [p for p in (lib / "pdf").glob("*.pdf")
                       if p.stat().st_size >= BLOAT_BYTES]
                if big:
                    info.append(f"{len(big)} PDF(s) exceed 40 MB — likely bloat "
                                f"→ python scripts/optimize-pdf.py scan .")
            except Exception as e:
                info.append(f"library check failed to run: {e}")

    # ── registered projects' bibs: merge drift + cross-project bibkeys ──────
    bibs_changed = False
    for root in registry:
        sha = fp_project_bib(root)
        if force or state.get("projects", {}).get(str(root)) != sha:
            bibs_changed = True
        new_state["projects"][str(root)] = sha
    master_changed = lib_changed and lib is not None

    if (bibs_changed or master_changed) and not (baseline and not force):
        if lib:
            try:
                d = merge_drift(lib / "references.bib", registry)
                if d["missing_keys"] or d["keys_with_new_terms"]:
                    ex = ", ".join((d["missing_keys"] + d["keys_with_new_terms"])[:3])
                    info.append(
                        f"merge drift: {len(d['missing_keys'])} bibkey(s) and "
                        f"{len(d['keys_with_new_terms'])} keyword set(s) live in project "
                        f"bibs but not in the master (e.g. {ex})\n"
                        f"→ review first: {plugin_cmd('merge-bibs.py')} "
                        f"--roots {registry_expansion()} "
                        f"--out {lib / 'references.bib'} --report-only")
            except Exception as e:
                info.append(f"merge-drift check failed to run: {e}")
        if len(registry) >= 2:
            try:
                code, out = run_bibkeys(scripts, registry)
                if code != 0:
                    lines = [ln for ln in out.splitlines()
                             if "COLLISION" in ln or "SPLIT" in ln][:6]
                    act.append("cross-project bibkey audit FAILED:\n"
                               + "\n".join(lines)
                               + f"\n→ {plugin_cmd('migrate-citekeys.py')} "
                                 f"(see the audit output for which key, in which projects)")
            except Exception as e:
                info.append(f"bibkey audit failed to run: {e}")

    return act, info, new_state


# ── output ───────────────────────────────────────────────────────────────────

def render_report(act: list[str], info: list[str]) -> str:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    parts = [f"# Drift-Report — {now}"]
    if act:
        parts.append("\n## ⚠ Handeln\n" + "\n".join(f"- {a}" for a in act))
    if info:
        parts.append("\n## ℹ Wissen\n" + "\n".join(f"- {i}" for i in info))
    if not act and not info:
        parts.append("\nNo drift.")
    return "\n".join(parts) + "\n"


def emit_hook_json(report: str) -> None:
    ctx = ("<research-drift-report>\n"
           "Out-of-band changes were detected at session start. Surface these "
           "findings to the user at a natural moment — do not interrupt their "
           "first request with them. Offer the ready-to-run fixes named below; "
           "run none of them without the user's go-ahead.\n\n"
           + report + "</research-drift-report>")
    if os.environ.get("CURSOR_PLUGIN_ROOT"):
        print(json.dumps({"additional_context": ctx}))
    elif os.environ.get("CLAUDE_PLUGIN_ROOT") and not os.environ.get("COPILOT_CLI"):
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "SessionStart", "additionalContext": ctx}}))
    else:
        print(json.dumps({"additionalContext": ctx}))


def main(argv: list[str] | None = None) -> int:
    if os.environ.get("RESEARCH_SUPERPOWERS_NO_DRIFT_CHECK") == "1":
        return 0
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--force", action="store_true",
                    help="ignore fingerprints — check everything now")
    ap.add_argument("--human", action="store_true",
                    help="plain-text report instead of hook JSON; always prints")
    args = ap.parse_args(argv)

    cwd = Path.cwd().resolve()
    try:
        state = json.loads(state_path().read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            state = {}
    except (OSError, ValueError):
        state = {}   # missing or corrupt → silent baseline

    act, info, new_state = collect_findings(cwd, state, force=args.force)

    cache_dir().mkdir(parents=True, exist_ok=True)
    state_path().write_text(json.dumps(new_state, indent=2), encoding="utf-8")

    report = render_report(act, info)
    if act or info:
        (cache_dir() / "last-drift-report.md").write_text(report, encoding="utf-8")

    if args.human:
        print(report, end="")
    elif act or info:
        emit_hook_json(report)
    # no findings, no --human → stay silent: that IS the report
    return 0


if __name__ == "__main__":
    sys.exit(main())
