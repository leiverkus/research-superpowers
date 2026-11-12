#!/usr/bin/env python3
"""Build OpenCode subagents from the Claude Code agents in agents/.

OpenCode does not read Claude Code agent files: it looks only in
`.opencode/agents/` and `~/.config/opencode/agents/` (no `.claude/agents`
compatibility), and the Claude frontmatter does not carry over —

  * no `mode:` → OpenCode registers the agent as a PRIMARY agent, which the
    `subagent` tool cannot launch, so every "dispatch the source-ingester
    subagent" in the skills would go nowhere;
  * `disallowedTools:` is not an OpenCode field → it is silently ignored, so a
    read-only agent such as peer-reviewer could write and edit;
  * `model: sonnet` / `inherit` are Claude aliases, not `provider/model` IDs;
  * unknown keys (`implements`, `skills`, `effort`, …) end up in the provider
    request body.

This script writes one OpenCode agent per Claude agent to opencode/agents/:
same name, description and instructions, plus `mode: subagent` and a
`permission:` block translated from `disallowedTools`. The model is left out,
so the subagent runs on the model of the session that launches it (the
equivalent of `inherit`); pin one per agent in opencode.jsonc if you want.

agents/*.md stays the single source of truth. CI runs `--check` and fails when
opencode/agents/ is out of sync.

Usage:
  python scripts/build-opencode-agents.py           # (re)write opencode/agents/
  python scripts/build-opencode-agents.py --check   # exit 1 if out of sync
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "agents"
DST = ROOT / "opencode" / "agents"

# Claude Code tool → OpenCode permission action (agents.mdx, "Permissions").
TOOL_TO_PERMISSION = {
    "Agent": "subagent",
    "Task": "subagent",
    "Write": "edit",
    "Edit": "edit",
    "MultiEdit": "edit",
    "NotebookEdit": "edit",
    "Bash": "shell",
    "WebFetch": "webfetch",
    "WebSearch": "websearch",
}


def split(text: str) -> tuple[dict[str, str], str]:
    """Return (top-level scalar frontmatter fields, body)."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ValueError("no frontmatter")
    end = next(i for i, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    fm: dict[str, str] = {}
    for line in lines[1:end]:
        m = re.match(r"^(\w[\w-]*):\s*(.*?)\s*$", line)
        if m and m.group(2):
            value = m.group(2)
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            fm[m.group(1)] = value
    return fm, "".join(lines[end + 1:])


def render(src: Path) -> str:
    fm, body = split(src.read_text(encoding="utf-8"))
    for key in ("name", "description"):
        if key not in fm:
            raise ValueError(f"{src.name}: frontmatter lacks `{key}`")

    denied: list[str] = []
    for tool in (t.strip() for t in fm.get("disallowedTools", "").split(",")):
        if not tool:
            continue
        if tool not in TOOL_TO_PERMISSION:
            raise ValueError(f"{src.name}: no OpenCode permission known for "
                             f"disallowed tool `{tool}` — extend TOOL_TO_PERMISSION")
        action = TOOL_TO_PERMISSION[tool]
        if action not in denied:
            denied.append(action)

    out = ["---", f"description: {json.dumps(fm['description'], ensure_ascii=False)}",
           "mode: subagent"]
    if denied:
        out.append("permission:")
        out += [f"  {action}: deny" for action in denied]
    out.append("---")
    out.append(f"<!-- Generated from agents/{src.name} by scripts/build-opencode-agents.py."
               " Edit the source, then re-run the script. -->")
    return "\n".join(out) + "\n" + body


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="verify opencode/agents/ is in sync; write nothing")
    args = ap.parse_args()

    expected = {f"{src.stem}.md": render(src) for src in sorted(SRC.glob("*.md"))}
    actual = {p.name: p.read_text(encoding="utf-8") for p in DST.glob("*.md")} if DST.is_dir() else {}

    stale = sorted(n for n in expected if actual.get(n) != expected[n])
    orphans = sorted(set(actual) - set(expected))
    if args.check:
        if stale or orphans:
            for n in stale:
                print(f"::error file=opencode/agents/{n}::out of sync with agents/{n} "
                      "(run: python scripts/build-opencode-agents.py)")
            for n in orphans:
                print(f"::error file=opencode/agents/{n}::no source in agents/ "
                      "(run: python scripts/build-opencode-agents.py)")
            return 1
        print(f"opencode/agents in sync — {len(expected)} agents")
        return 0

    DST.mkdir(parents=True, exist_ok=True)
    for n in orphans:
        (DST / n).unlink()
    for n, text in expected.items():
        (DST / n).write_text(text, encoding="utf-8")
    print(f"wrote {len(expected)} agents to opencode/agents/"
          + (f", removed {len(orphans)} orphan(s)" if orphans else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
