#!/usr/bin/env bash
# Install research-superpowers into OpenCode (macOS / Linux) by symlinking:
#
#   skills  ~/.config/opencode/skills/research-superpowers  → <repo>/skills
#           one grouping link; OpenCode finds every <name>/SKILL.md below it
#           and keeps the plain skill names (ingest-source, wiki-lint, …).
#   agents  ~/.config/opencode/agents/<name>.md             → <repo>/opencode/agents/<name>.md
#           one link per agent: OpenCode names an agent in a sub-directory
#           "<dir>/<name>", and the skills dispatch them by bare name.
#   plugin  ~/.config/opencode/plugin/research-superpowers.ts → <repo>/opencode/plugin/…
#           skill index + drift check at session start, plugin root for shell.
#
# Safe to re-run (e.g. after a new agent was added). It never replaces a real
# file or a link that points somewhere else — it reports those and stops.
# Override the target with OPENCODE_CONFIG_DIR. `--uninstall` removes exactly
# the links this script would create.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
CONF="${OPENCODE_CONFIG_DIR:-$HOME/.config/opencode}"
MODE="${1:-install}"
conflicts=0

link() { # link <target> <link-path>
  local target="$1" path="$2"
  if [ -L "$path" ]; then
    if [ "$(readlink "$path")" = "$target" ]; then
      echo "ok       $path"
      return
    fi
    echo "CONFLICT $path is a symlink to $(readlink "$path"), not $target" >&2
    conflicts=1
    return
  fi
  if [ -e "$path" ]; then
    echo "CONFLICT $path exists and is not a symlink — left untouched" >&2
    conflicts=1
    return
  fi
  mkdir -p "$(dirname "$path")"
  ln -s "$target" "$path"
  echo "linked   $path → $target"
}

unlink_ours() { # unlink_ours <target> <link-path>
  if [ -L "$2" ] && [ "$(readlink "$2")" = "$1" ]; then
    rm "$2"
    echo "removed  $2"
  fi
}

op=link
[ "$MODE" = "--uninstall" ] && op=unlink_ours

$op "$REPO/skills" "$CONF/skills/research-superpowers"
for agent in "$REPO"/opencode/agents/*.md; do
  $op "$agent" "$CONF/agents/$(basename "$agent")"
done
$op "$REPO/opencode/plugin/research-superpowers.ts" "$CONF/plugin/research-superpowers.ts"

if [ "$conflicts" -ne 0 ]; then
  echo "Some links were not created — see CONFLICT lines above." >&2
  exit 1
fi
[ "$op" = link ] && echo "Done. Restart OpenCode (opencode service restart, or quit the app)."
exit 0
