# Source classes for web citations

Three skills (`drafting-manuscript`, `requesting-peer-review`,
`semantic-wiki-review`) check every cited URL for what kind of source stands
behind it. Until v0.45 the optional `dao-searxng-mcp` returned this as a
`source_class` field. That MCP is discontinued; the classification is now done
by the agent itself, with the same six labels, so existing wiki flags and review
reports stay valid.

## Procedure

1. Fetch the page with the host's web-fetch tool (`WebFetch` in Claude Code,
   `webfetch` in OpenCode). A dead or redirecting URL is itself a finding.
2. Classify from the **hostname and the page itself**: imprint, publisher name,
   DOI on the page, editorial or peer-review statement, author and date.
3. When the evidence is thin, use `grey_lit_or_unknown`. **Never upgrade a
   class on a guess** — the purpose is to catch weak sources, not to excuse them.
4. For an article with a DOI, the DOI landing page (`doi.org/…` → publisher) is
   the primary source, whatever URL the text cited.

## The six classes

| `source_class` | What it is | Typical hosts |
|---|---|---|
| `primary_publisher` | The publisher, journal, society or institution that issues the text itself; a DOI landing page | `doi.org` targets, `brill.com`, `tandfonline.com`, `publications.dainst.org`, `publications.iaa.org.il`, `publication.doa.gov.jo` |
| `academic_repository` | An institutional or disciplinary repository holding the published or author version | `epub.ub.uni-muenchen.de`, `publikationen.uni-tuebingen.de`, `zenodo.org`, `hal.science`, `archiv.ub.uni-heidelberg.de/propylaeumdok` |
| `preprint_server` | Not yet peer-reviewed versions | `arxiv.org`, `biorxiv.org`, `osf.io/preprints`, `hcommons.org` |
| `aggregator` | Re-posts or summaries without editorial responsibility | `wikipedia.org`, `researchgate.net`, `academia.edu`, `scribd.com`, Google Books snippets, `bible.ca`, `biblewalks.com` |
| `suspect` | No identifiable author or publisher, content farms, machine-generated pages, mirrors of paywalled texts, contradictory metadata | — |
| `grey_lit_or_unknown` | Legitimate but not peer-reviewed (project sites, excavation reports, press releases, institutional news) — or not decidable | excavation-project sites, museum news, conference programmes |

## What follows from the class

- `aggregator` or `suspect` → find the primary source (usually via DOI), or name
  the status openly in the text. In a review, an unexplained aggregator or
  suspect citation is at least a Minor Issue; in `semantic-wiki-review` it goes
  into the "Suspect / aggregator citations" category.
- `grey_lit_or_unknown` is not a defect on its own; it matters when such a source
  carries a central claim.
