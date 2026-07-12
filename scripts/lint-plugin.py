#!/usr/bin/env python3
"""
Skill ↔ Agent drift checker — verifies the contracts defined in docs/skill-contract.md.

Checks:
  1. Every agent's `implements:` points to an existing skill.
  2. Every skill's `agents:` list entry points to an existing agent file.
  3. Symmetry: if an agent implements skill X, skill X should list that agent
     in its `agents:` field (and vice-versa).
  4. Agent files must not contain a numbered checklist longer than 3 items
     (heuristic: procedural content belongs in SKILL.md, not the agent).

Usage:
  python scripts/lint-plugin.py [--root <repo-root>]

Exit codes:
  0  no issues
  1  one or more ERRORs found
"""

import argparse
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Frontmatter parsing (no external deps)
# ---------------------------------------------------------------------------

def _parse_frontmatter(text: str) -> dict:
    """Return a dict of the YAML frontmatter fields we care about.

    Handles only the subset used in this plugin:
      - scalar strings  (name, implements, description)
      - simple flat lists under a key  (agents:, inputs:, outputs:)
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    end = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = i
            break
    if end is None:
        return {}

    fm: dict = {}
    current_list_key = None

    for line in lines[1:end]:
        # list item under a known key
        list_item = re.match(r"^\s{2,}- (.+)$", line)
        if list_item and current_list_key:
            raw = list_item.group(1).strip()
            # handle `- name: foo` sub-maps (inputs/outputs) — extract name
            name_match = re.match(r"name:\s*(.+)", raw)
            fm[current_list_key].append(name_match.group(1).strip() if name_match else raw)
            continue

        # top-level key: value
        kv = re.match(r"^(\w[\w-]*):\s*(.*)", line)
        if kv:
            key, value = kv.group(1), kv.group(2).strip()
            current_list_key = None
            if value == "":
                # block list follows
                fm[key] = []
                current_list_key = key
            else:
                fm[key] = value

    return fm


def _body(text: str) -> str:
    """Return the content after the closing --- of the frontmatter."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[i + 1:])
    return text


# ---------------------------------------------------------------------------
# Checklist-depth heuristic
# ---------------------------------------------------------------------------

def _max_numbered_run(body: str) -> int:
    """Return the length of the longest run of consecutive 1-based numbered
    list items found in `body`  (e.g. '1. … 2. … 3. … 4. …' → 4)."""
    numbers = [
        int(m.group(1))
        for m in re.finditer(r"^\s*(\d+)\. ", body, re.MULTILINE)
    ]
    if not numbers:
        return 0
    max_run = 0
    run = 0
    expected = 1
    for n in numbers:
        if n == expected:
            run += 1
            expected += 1
        elif n == 1:
            run = 1
            expected = 2
        else:
            run = 0
            expected = n + 1
        max_run = max(max_run, run)
    return max_run


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repo root (default: cwd)")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    skills_dir = root / "skills"
    agents_dir = root / "agents"

    errors: list[str] = []
    warnings: list[str] = []

    # --- collect skills ---
    skills: dict[str, dict] = {}
    for skill_file in sorted(skills_dir.glob("*/SKILL.md")):
        text = skill_file.read_text(encoding="utf-8")
        fm = _parse_frontmatter(text)
        skill_name = fm.get("name") or skill_file.parent.name
        skills[skill_name] = {"fm": fm, "path": skill_file}

    # --- collect agents ---
    agents: dict[str, dict] = {}
    for agent_file in sorted(agents_dir.glob("*.md")):
        text = agent_file.read_text(encoding="utf-8")
        fm = _parse_frontmatter(text)
        agent_name = fm.get("name") or agent_file.stem
        agents[agent_name] = {"fm": fm, "path": agent_file, "body": _body(text)}

    if not skills:
        print(f"WARN  no skills found under {skills_dir}")
    if not agents:
        print(f"WARN  no agents found under {agents_dir}")

    # --- Check 1: agent implements → skill exists ---
    for agent_name, agent in agents.items():
        implements = agent["fm"].get("implements")
        if not implements:
            errors.append(
                f"[ERR]   agents/{agent_name}.md  missing `implements:` field"
            )
            continue
        if implements not in skills:
            errors.append(
                f"[ERR]   agents/{agent_name}.md  implements: '{implements}' "
                f"— no matching skills/{implements}/SKILL.md"
            )

    # --- Check 2: skill agents: → agent file exists ---
    for skill_name, skill in skills.items():
        declared_agents = skill["fm"].get("agents") or []
        if isinstance(declared_agents, str):
            declared_agents = [declared_agents]
        for a in declared_agents:
            if a not in agents:
                errors.append(
                    f"[ERR]   skills/{skill_name}/SKILL.md  agents: '{a}' "
                    f"— no matching agents/{a}.md"
                )

    # --- Check 3: symmetry ---
    # 3a. agent implements skill X → skill X should list this agent
    for agent_name, agent in agents.items():
        implements = agent["fm"].get("implements")
        if not implements or implements not in skills:
            continue
        skill_agents = skills[implements]["fm"].get("agents") or []
        if isinstance(skill_agents, str):
            skill_agents = [skill_agents]
        if agent_name not in skill_agents:
            errors.append(
                f"[ERR]   agents/{agent_name}.md  implements: '{implements}', "
                f"but skills/{implements}/SKILL.md does not list '{agent_name}' in agents:"
            )

    # 3b. skill lists agent A → agent A's implements: should be this skill
    #     (or at least the agent exists — covered by check 2; here we check
    #      the back-pointer when the agent does exist)
    for skill_name, skill in skills.items():
        declared_agents = skill["fm"].get("agents") or []
        if isinstance(declared_agents, str):
            declared_agents = [declared_agents]
        for a in declared_agents:
            if a not in agents:
                continue  # already flagged by check 2
            back = agents[a]["fm"].get("implements")
            if back and back != skill_name:
                # agent is reused (e.g. source-ingester in executing-research-plan)
                # only warn if the agent's primary skill doesn't exist at all
                if back not in skills:
                    errors.append(
                        f"[ERR]   skills/{skill_name}/SKILL.md  lists agent '{a}', "
                        f"but {a}.implements = '{back}' (skill not found)"
                    )

    # --- Check 4: agent checklist depth ---
    for agent_name, agent in agents.items():
        depth = _max_numbered_run(agent["body"])
        if depth > 3:
            warnings.append(
                f"[WARN]  agents/{agent_name}.md  numbered checklist reaches "
                f"item {depth} — procedural content belongs in SKILL.md "
                f"(skill-contract.md §Lint check)"
            )

    # --- Report ---
    all_issues = errors + warnings
    if not all_issues:
        print(f"OK    {len(skills)} skills, {len(agents)} agents — no drift detected.")
        return 0

    for line in errors:
        print(line)
    for line in warnings:
        print(line)

    if errors:
        print(f"\n{len(errors)} error(s), {len(warnings)} warning(s).")
        return 1

    print(f"\n0 errors, {len(warnings)} warning(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
