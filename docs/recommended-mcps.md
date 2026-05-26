# Recommended MCPs

Two MCP servers (by the same author as this plugin) cover gaps that `research-superpowers` alone can only declare:

| MCP | Closes the gap of … | Used by |
|---|---|---|
| [`dao-paper-search-mcp`](https://github.com/leiverkus/dao-paper-search-mcp) | Structurally verified citations (no "Author-Year hallucination"), DAO-specific search (Zenon DAI, IAA, ADAJ, IxTheo, Propylaeum) plus cross-platform search (OpenAlex, Crossref, Semantic Scholar, arXiv, CORE, Zenodo, bioRxiv), Wikidata / iDAI.gazetteer entity resolution | `literature-review`, `literature-scout`, `ingest-source` |
| [`dao-searxng-mcp`](https://github.com/leiverkus/dao-searxng-mcp) | Web search with `source_class` detection (primary / aggregator / suspect) — makes the "don't cite academia.edu" discipline enforceable rather than aspirational | `semantic-wiki-review`, `requesting-peer-review`, `drafting-manuscript` |

Both are **optional**. If they aren't set up, the affected skills fall back to manual API calls / the documented bucket lists. The plugin is fully standalone-functional.

## `dao-paper-search-mcp`

### Install — Claude Code

```bash
claude mcp add dao-paper-search -- uvx --from "git+https://github.com/leiverkus/dao-paper-search-mcp@main" python -m dao_paper_search_mcp.server
```

For reproducibility, pin a concrete tag instead of `@main` once a release is available (e.g. `@v0.7.1`).

### Install — OpenCode

In `~/.config/opencode/opencode.json` under `mcp`:

```jsonc
"dao-paper-search": {
  "type": "local",
  "command": [
    "uvx", "--from",
    "git+https://github.com/leiverkus/dao-paper-search-mcp@main",
    "python", "-m", "dao_paper_search_mcp.server"
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

## `dao-searxng-mcp`

### Install — Docker stack (recommended — ships SearXNG too)

```bash
git clone https://github.com/leiverkus/dao-searxng-mcp.git
cd dao-searxng-mcp
cp .env.example .env
echo "SEARXNG_SECRET_KEY=$(openssl rand -hex 32)" >> .env
cp searxng-config/settings.yml.example searxng-config/settings.yml
sed -i.bak "s/REPLACE_WITH_RANDOM_HEX_STRING/$(openssl rand -hex 32)/" \
  searxng-config/settings.yml && rm searxng-config/settings.yml.bak
docker compose up -d
```

After startup: SearXNG UI at <http://localhost:8888>, MCP server (HTTP transport) at <http://127.0.0.1:3333/mcp>.

### Connect — Claude Code / OpenCode

HTTP transport:

```json
{
  "mcpServers": {
    "dao-searxng": { "url": "http://127.0.0.1:3333/mcp" }
  }
}
```

stdio transport (alternative): see the repo README.

### What skills use

- **Search tools**: `web_search`, `news_search`, `science_search`, `fetch_url`
- **Per-hit annotation** (skills route on these):
  - `source_class`: `primary_publisher` | `academic_repository` | `preprint_server` | `aggregator` | `suspect` | `grey_lit_or_unknown`
  - `doi_detected`: DOI string when found in title/snippet/text (hand to `dao-paper-search-mcp` for verification)
  - `oa_url_heuristic`: `likely` | `maybe` | `no`
  - `content_type`, `content_extraction`: HTTP headers and Readability status
- **Output**: pre-formatted Markdown with `(domain)` labels and an automatic "Sources:" section

## Fallback — what happens without the MCPs

Skills that mention these MCPs consistently use a **soft-preference pattern**:

> If `dao-paper-search-mcp` is available in the project, use the MCP tools instead of the manual API calls below — they return structurally verified citation blocks. Otherwise stay on the manual path.

The manual path (the documented database bucket list, manual BibTeX entry, manual source classification) remains fully documented. No skill fails without an MCP.

## Version pinning

Recommended: before serious research use, pin concrete version tags instead of `@main`. Both MCPs evolve; a pinned tag makes research runs reproducible. Tags are published under each repo's "Releases".
