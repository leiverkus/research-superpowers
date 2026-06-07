# Vendored libraries

These files are bundled so the wiki tooling works **offline, with no install
and no network access** (matching the project's data-handling constraints).

| File | Version | Source | License |
|------|---------|--------|---------|
| `cytoscape.min.js` | 3.30.4 | https://cdn.jsdelivr.net/npm/cytoscape@3.30.4/dist/cytoscape.min.js | MIT |

`scripts/wiki-to-graph.py` inlines `cytoscape.min.js` into the generated
`graph.html`, producing a single self-contained, offline interactive graph.
To update, replace the file with a newer release and bump the version above.
