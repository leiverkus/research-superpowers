# Installation

This guide walks you through installing `research-superpowers` step by step. No prior experience with Claude Code plugins is assumed. If you've used Claude Code plugins before, the [Quickstart in the README](../README.md#installation) covers the same ground in 30 seconds.

**No terminal, no Python, no git?** Skip this page and read [`installation-cowork.md`](installation-cowork.md) instead — the click-only path takes 3–5 minutes and works fully in Cowork.

Total time: **5–10 minutes** for the recommended path.

## Before you start

You need three things on your computer. If any are missing, install them first — links below.

### 1. Claude Code

[Claude Code](https://docs.claude.com/en/docs/claude-code) is Anthropic's terminal-based AI coding assistant. Without it, this plugin cannot run.

- **macOS / Linux**: open a terminal and run
  ```bash
  curl -fsSL https://claude.com/install.sh | bash
  ```
- **Windows**: install via the [installer page](https://docs.claude.com/en/docs/claude-code/setup).

Verify it works:
```bash
claude --version
```
You should see a version number (something like `2.x.y`). If you get "command not found", restart your terminal and try again. If still nothing, see the [Claude Code setup docs](https://docs.claude.com/en/docs/claude-code/setup).

### 2. Python 3.10 or newer

The plugin's lint script needs Python. Check what you have:

```bash
python3 --version
```

If you see `Python 3.10.x` or higher, you're good. If not:
- **macOS**: `brew install python` (install [Homebrew](https://brew.sh) first if needed).
- **Linux**: `sudo apt install python3 python3-pip` (Ubuntu/Debian).
- **Windows**: download from [python.org/downloads](https://www.python.org/downloads/).

Then install the one Python library the lint script needs:
```bash
python3 -m pip install --user pyyaml
```

### 3. Git

You probably have it. Check:
```bash
git --version
```

If not: macOS gets it with Xcode Command Line Tools (`xcode-select --install`); Linux via the package manager; Windows from [git-scm.com](https://git-scm.com/download/win).

## Recommended path: install from the marketplace

This is the cleanest way to install and get updates.

### Step 1 — Tell Claude Code where to find the marketplace

Open Claude Code in any directory:

```bash
claude
```

Inside the Claude Code session, type:

```
/plugin marketplace add leiverkus/research-superpowers
```

(The slash-command UI auto-completes once you type `/plugin`.) Press Enter. Claude Code fetches the marketplace catalog from GitHub and confirms it added one marketplace named `leiverkus-research`.

### Step 2 — Install the plugin

Still in Claude Code:

```
/plugin install research-superpowers@leiverkus-research
```

This downloads the plugin into `~/.claude/plugins/cache/` and activates it. You'll see a confirmation.

### Step 3 — Verify

Restart Claude Code (`exit` the current session, then `claude` again). On the new session-start you should see a short "Research Superpowers" notice listing available skills — that means the SessionStart hook ran and the plugin is active.

If you don't see the notice, run:
```
/plugin list
```
to confirm `research-superpowers` shows up as installed.

### Step 4 — Updates

When a new version ships:
```
/plugin update research-superpowers@leiverkus-research
```

## Alternative path: install from a GitHub URL

If you'd rather not add the marketplace, you can install the plugin directly from its GitHub URL:

```
/plugin install https://github.com/leiverkus/research-superpowers
```

This works but doesn't get auto-updates. You'd re-run the command to pull the latest version.

## Alternative path: install from a local clone

For development, or if you want to modify the plugin:

```bash
# Clone the repo somewhere on disk
git clone https://github.com/leiverkus/research-superpowers ~/code/research-superpowers
cd ~/code/research-superpowers
```

Then in Claude Code:
```
/plugin install ~/code/research-superpowers
```

Edits you make to the cloned files take effect on the next Claude Code session.

## Recommended path for OpenCode users

[OpenCode](https://opencode.ai/) reads `SKILL.md` files natively from `.claude/skills/<name>/SKILL.md`. So even though OpenCode has no `/plugin install` command, you can use the same plugin:

```bash
# Clone the repo
git clone https://github.com/leiverkus/research-superpowers ~/code/research-superpowers

# In your research project root, symlink the skills directory:
cd /path/to/your-research-project
ln -s ~/code/research-superpowers/skills .claude/skills
```

OpenCode now discovers all 15 skills and the 7 agents. The SessionStart hook is Claude-Code-specific, so OpenCode users don't get the index injection — instead, mention "Research Superpowers" in your project's `AGENTS.md` and OpenCode will load skills on demand.

## Create your first research project

The plugin is installed, but it works on a *research project* — a directory with a specific layout. Scaffold one from the template:

```bash
# Copy the template anywhere on disk
cp -r ~/code/research-superpowers/templates/research-project-template ~/Documents/my-first-research-project
cd ~/Documents/my-first-research-project
```

(If you installed via the marketplace, the template lives at `~/.claude/plugins/cache/leiverkus-research/research-superpowers/templates/research-project-template`. Adjust the path.)

Open `CLAUDE.md` and edit the top three frontmatter lines:

```yaml
---
methodology: hermeneutic   # hermeneutic | quantitative | mixed
discipline: "Biblical Archaeology"
languages: [en, de]
---
```

That's it. The project is ready. Open Claude Code in this directory:

```bash
cd ~/Documents/my-first-research-project
claude
```

And try a first ingest — see [`quickstart.md`](quickstart.md) for the 5-minute walkthrough, or [`tutorial.md`](tutorial.md) for the full hour-long tour.

## Optional: install the recommended MCPs

The plugin works without them. They add structurally verified citations and web-source-class detection. See [`recommended-mcps.md`](recommended-mcps.md).

## Troubleshooting

### "command not found: claude"

Claude Code isn't on your `PATH`. Restart your terminal; if still not found, re-run the install script from [§1 above](#1-claude-code) or follow [the official setup docs](https://docs.claude.com/en/docs/claude-code/setup).

### "Plugin not found"

You may have typed the wrong marketplace name. List marketplaces:
```
/plugin marketplace list
```
Then install with the exact name shown.

### Lint script fails with "No module named yaml"

Re-run the PyYAML install:
```bash
python3 -m pip install --user pyyaml
```

### Lint script fails with "schema file not found"

You're running the lint from outside a research project. Make sure you're in the project root (where `schema/` and `knowledge/` live), not in the plugin directory.

### SessionStart hook didn't fire

Check `~/.claude/plugins/cache/` for `research-superpowers/` and that `hooks/hooks.json` is present. If it's there but doesn't run, your Claude Code version may pre-date hook support — upgrade via `claude --update`.

### Symlink approach (OpenCode) — Windows note

`ln -s` doesn't exist on Windows; use `mklink` in an admin Command Prompt:
```cmd
mklink /D .claude\skills C:\path\to\research-superpowers\skills
```

## How to uninstall

```
/plugin uninstall research-superpowers@leiverkus-research
```

This removes the plugin and its hooks; your research projects on disk are untouched.

To remove the marketplace itself:
```
/plugin marketplace remove leiverkus-research
```

## What landed on disk

For curiosity / debugging — the plugin lives at:

- **Marketplace install**: `~/.claude/plugins/cache/leiverkus-research/research-superpowers/`
- **GitHub URL install**: `~/.claude/plugins/cache/<hash>/research-superpowers/`
- **Local install**: wherever you cloned it; Claude Code keeps a reference.

The plugin reads from these files; it doesn't modify them. Your research projects live wherever you scaffolded them (`~/Documents/...` or similar). The plugin never writes outside the project you're working in.

## Where to go next

- [`quickstart.md`](quickstart.md) — 5 minutes to your first ingest
- [`tutorial.md`](tutorial.md) — full walkthrough on a realistic mini-project
- [`concepts.md`](concepts.md) — the *why* behind SOFT-GATE, methodology branching, SOT pattern
- [`recommended-mcps.md`](recommended-mcps.md) — set up the optional MCPs for verified citations
