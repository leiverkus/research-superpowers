# Migration v0.3 → v0.4

**TL;DR — nothing to do.** v0.4 is purely additive. Existing users with the full CLI setup (Python, Git, Quarto) see no behaviour change.

## What changed

- New skill: `scaffold-research-project`. Creates new projects via conversation; useful as a friendlier alternative to `cp -r templates/...`. The old `cp -r` approach still works.
- New fallback in `wiki-lint`: when Python or PyYAML is not available, the skill validates frontmatter inline. Existing users with Python see no difference — the script path is taken as before.
- New doc: `docs/installation-cowork.md` — installation path for Cowork users / non-technical users without a terminal.
- Version: `.claude-plugin/plugin.json` and `marketplace.json` both at 0.4.0. Description and marketplace tags mention Cowork compatibility.

## What you can optionally do

### 1. Try the scaffolding skill on your next project

Instead of `cp -r ~/.claude/plugins/cache/leiverkus-research/research-superpowers/templates/research-project-template ~/Documents/my-project`, just ask Claude:

> Start a new research project on **<topic>**.

The skill walks through the questions and writes the files. Output is the same project tree you'd get from `cp -r`, but you don't have to remember the path.

### 2. Tell colleagues without dev setup that they can now use the plugin

If you've been hesitant to recommend the plugin to colleagues who don't have Python, Git, or a terminal: that hesitation is gone. Point them at [`installation-cowork.md`](installation-cowork.md).

## What you don't have to do

- No manifest changes.
- No frontmatter changes.
- No template re-copy — your existing projects continue to work.
- No need to switch to the scaffold skill if `cp -r` works for you.

## If you want the Cowork-style workflow

```bash
# Update the plugin
/plugin update research-superpowers@leiverkus-research

# In Claude (any new conversation):
> Start a new research project on X.
```

The scaffold skill takes over.

## See also

- [`installation-cowork.md`](installation-cowork.md) — full Cowork install path
- [`installation.md`](installation.md) — full CLI install (unchanged from v0.3)
- [`../CHANGELOG.md`](../CHANGELOG.md) — full change list
- [`migration-v0.2-to-v0.3.md`](migration-v0.2-to-v0.3.md) — previous release migration
