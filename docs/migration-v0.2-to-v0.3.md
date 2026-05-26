# Migration v0.2 → v0.3

**TL;DR — nothing mandatory.** v0.3 is largely additive. There is one breaking change (the `opencode-commands/` directory was removed; OpenCode now reads skills natively), but it only affects users who scripted against those slash shortcuts. Everything else is opt-in.

## What changed

- **`opencode-commands/` removed.** OpenCode reads `SKILL.md` files natively from `.claude/skills/<name>/SKILL.md`. Trigger skills via natural language or the `skill` tool. The 5 shortcut commands (`/ingest`, `/draft`, `/peer-review`, `/lit-review`, `/research-brainstorm`) are gone.
- **All skill prose, templates, and example content translated to English.** Domain-specific German terms (*Quellenkritik*, *Formgeschichte*, *Forschungsstand*) kept italicised. Frontmatter field names, JSON keys, BibTeX keys, and slugs stay English.
- **New manual.** Root `README.md`, `docs/quickstart.md`, `docs/tutorial.md`, `docs/concepts.md`, `LICENSE`, `.gitignore`, `CONTRIBUTING.md` are all new — see [`../CHANGELOG.md`](../CHANGELOG.md).
- **Skills that benefit from external structured data** (`literature-review`, `literature-scout`, `ingest-source`, `semantic-wiki-review`, `requesting-peer-review`, `drafting-manuscript`) gained a new **"MCP Optimisation (recommended)"** section.
- **Schema** has three new optional entity fields: `wikidata_qid`, `idai_gazetteer_id`, `gnd_id`.
- **Example entity template** shows the new fields in use.

## What you can optionally do

### 1. Set up the MCPs (recommended for the DAO workflow)

Read [`recommended-mcps.md`](recommended-mcps.md). In short:

- `dao-paper-search-mcp` via `claude mcp add ...` (Python, uvx)
- `dao-searxng-mcp` via Docker stack (Node + SearXNG container)

After setup, skills use the MCPs automatically when available — soft preference, no plugin configuration change needed.

### 2. Backfill authority IDs in existing entity pages

If you want to add `wikidata_qid` / `idai_gazetteer_id` / `gnd_id` to your existing `knowledge/entities/*.qmd`:

```yaml
---
title: "Tel Megiddo"
type: entity
# … existing fields …
wikidata_qid: Q173799
idai_gazetteer_id: "2048473"
---
```

None of this is mandatory. The lint script only validates the regex pattern when a field is present, never demands existence. Useful for later deduplication and cross-references.

With `dao-paper-search-mcp` set up, you can let `resolve_author` / `resolve_site` backfill these IDs automatically.

### 3. Update your schema mirror

If your project has its own copy of `schema/knowledge-frontmatter.schema.json` (it should, from the v0.2 migration), copy the new version from the plugin:

```bash
cp ~/.claude/plugins/research-superpowers/templates/research-project-template/schema/knowledge-frontmatter.schema.json schema/
```

## What you don't have to do

- No mandatory migration of skills or frontmatter.
- No update to plan or source files.
- No MCP installation required for the plugin to work.

## If you scripted against `opencode-commands/`

Replace any `cp opencode-commands/*.md ~/.config/opencode/commands/` line in your setup scripts with the symlink approach:

```bash
ln -s /path/to/research-superpowers/skills .claude/skills
```

Replace `/ingest`-style triggers with natural-language requests ("ingest this PDF") or the OpenCode `skill` tool: `skill({ name: "ingest-source" })`.

## Verification after an optional update

```bash
python scripts/lint-wiki.py
```

Should still exit 0 (or report pre-existing issues unrelated to the migration). New optional fields are validated against their patterns but not required.

## If you set up the MCPs

Test that routing fires: invoke `literature-review` on a topic and watch for MCP-tool calls (`search_zenon`, `search_openalex`, …) instead of shell requests; source pages should copy `inline_citation.authoritative_bibliography_line` verbatim from the MCP response.

## See also

- [`recommended-mcps.md`](recommended-mcps.md) — setup details for both MCPs
- [`../CHANGELOG.md`](../CHANGELOG.md) — full change list
- [`migration-v0.1-to-v0.2.md`](migration-v0.1-to-v0.2.md) — migration for the previous release (if not done yet)
