# Recommended MCPs

One MCP server (by the same author as this plugin) covers a gap that `research-superpowers` alone can only declare:

| MCP | Closes the gap of … | Used by |
|---|---|---|
| [`dao-paper-search-mcp`](https://github.com/leiverkus/dao-paper-search-mcp) | Structurally verified citations (no "Author-Year hallucination"), DAO-specific search (Zenon DAI, IAA, ADAJ, IxTheo, Propylaeum) plus cross-platform search (OpenAlex, Crossref, Semantic Scholar, arXiv, CORE, Zenodo, bioRxiv), Wikidata / iDAI.gazetteer entity resolution | `literature-review`, `literature-scout`, `ingest-source` |

It is **optional**. Without it, the affected skills fall back to manual API calls and the documented bucket lists. The plugin is fully standalone-functional.

> **`dao-searxng-mcp` is discontinued (v0.45.1).** It added web search with a `source_class` label per hit. General web search is now the host's own tool (`WebSearch` in Claude Code, `websearch` in OpenCode), and the skills classify cited URLs themselves by the rubric in [`source-classes.md`](source-classes.md) — same six labels, so existing wiki flags and review reports stay valid.

## `dao-paper-search-mcp`

### Install — Claude Code

```bash
claude mcp add dao-paper-search -- uvx --from "dao-paper-search-mcp==1.2.0" dao-paper-search-mcp
```

This installs the release from PyPI, pinned. Keep the pin: `uvx` resolves a fresh environment, so an unpinned or older install picks up whatever its dependencies resolve to today. Releases before 1.0.1 did not bound `mcp`, and since `mcp` 2.0 removed `mcp.server.fastmcp` they crash at start with `ModuleNotFoundError: No module named 'mcp.server.fastmcp'` (Claude Code shows only "Failed to connect"). 1.0.1 pinned `mcp<2`; 1.1.0 runs on `mcp` 2.x and bounds it below 3; 1.2.0 makes `search_crossref(query=<doi>)` a direct DOI lookup, which the skills rely on to verify metadata. To upgrade later, change the version here and in your config together.

### Install — OpenCode

In `~/.config/opencode/opencode.json` under `mcp`:

```jsonc
"dao-paper-search": {
  "type": "local",
  "command": [
    "uvx", "--from",
    "dao-paper-search-mcp==1.2.0",
    "dao-paper-search-mcp"
  ],
  "enabled": true,
  "environment": {
    "CORE_API_KEY": "<your-core-api-key>",
    "DAO_PAPER_SEARCH_CONTACT_EMAIL": "<your-email>",
    "DAO_PAPER_SEARCH_RATE_LIMIT_MS": "1000"
  }
}
```

### Environment variables

| Var | Required | Default | Purpose |
|---|---|---|---|
| `CORE_API_KEY` | **yes** (for `search_core`) | — | Bearer for CORE v3. Free registration: <https://core.ac.uk/services/api>. |
| `DAO_PAPER_SEARCH_CONTACT_EMAIL` | no | `"anonymous"` | Sent as `mailto:` in the User-Agent — better rate-limit priority on OpenAlex / Crossref / CORE / arXiv. |
| `SEMANTIC_SCHOLAR_API_KEY` | no | — | Lifts the limit above the ~100 req/min public bucket. |
| `DAO_PAPER_SEARCH_RATE_LIMIT_MS` | no | `1000` | Minimum milliseconds between outbound requests. |

### What skills use

- **DAO-specific search**: `search_zenon`, `search_iaa`, `search_adaj`, `search_propylaeum`, `search_ixtheo`, `search_openedition`, `search_gnomon`
- **Cross-platform search**: `search_crossref`, `search_openalex`, `search_semantic_scholar`, `search_arxiv`, `search_core`, `search_zenodo`, `search_biorxiv`
- **Entity resolution**: `resolve_author` (Wikidata SPARQL + GND fallback), `resolve_site` (iDAI.gazetteer)
- **Citation fields per hit** (paste verbatim into wiki and manuscript):
  - `inline_citation.markdown` — ready in-text link, e.g. `[(Finkelstein 1999)](https://doi.org/...)`
  - `inline_citation.authoritative_bibliography_line` — ready references-list line
  - `audit.source_class`, `audit.warn_marker` — aggregator/suspect warning with ⚠️ marker

## Fallback — what happens without the MCP

Skills that mention the MCP consistently use a **soft-preference pattern**:

> If `dao-paper-search-mcp` is available in the project, use the MCP tools instead of the manual API calls below — they return structurally verified citation blocks. Otherwise stay on the manual path.

The manual path (the documented database bucket list, manual BibTeX entry, manual source classification) remains fully documented. No skill fails without an MCP.

## Version pinning

Recommended: before serious research use, pin a concrete release instead of `@main`. The MCP evolves; a pinned version makes research runs reproducible. Releases are published on PyPI and under the repo's "Releases".
