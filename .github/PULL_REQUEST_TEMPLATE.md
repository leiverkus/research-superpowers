<!--
Thanks for the PR. A few quick checks before opening it:

1. Read CONTRIBUTING.md if you haven't — especially the "Verification before a PR" section.
2. For new skills: have an approved skill-proposal issue first (see .github/ISSUE_TEMPLATE/new_skill.yml).
3. Keep diffs scoped — one logical change per PR.
-->

## What this PR changes

<!-- One paragraph. The WHY matters more than the WHAT — the diff shows the what. -->

## Why

<!-- Link to the related issue if any: "Closes #N" or "Refs #N". -->

## Type of change

- [ ] Bug fix (skill, agent, template, lint, docs)
- [ ] New skill (with prior approved proposal)
- [ ] MCP integration (follows soft-preference pattern, plugin remains standalone)
- [ ] Documentation
- [ ] Refactor / chore (no behaviour change)
- [ ] Release / versioning

## Verification

<!--
Paste the output of the relevant commands. Empty / "all good" / exit-0 outputs are also useful — they prove you ran them.
-->

```bash
# Plugin manifests valid
claude plugin validate . --strict

# Schema valid + template mirror in sync
python3 -c "import json; json.load(open('schema/knowledge-frontmatter.schema.json'))"
diff -q schema/knowledge-frontmatter.schema.json \
        templates/research-project-template/schema/knowledge-frontmatter.schema.json

# Example project lints clean
cd examples/example-project && python3 scripts/lint-wiki.py && cd -

# Every agent references an existing skill
for f in agents/*.md; do
  impl=$(grep '^implements:' "$f" | awk '{print $2}')
  [ -d "skills/$impl" ] || echo "MISSING SKILL: $f → $impl"
done
```

## Checklist

- [ ] Diff is scoped to one logical change
- [ ] Language convention respected: English skill prose; domain terms italicised (*Quellenkritik*, *Forschungsstand*, …); field names / paths in English
- [ ] If a skill changed: `agents/` and `docs/` references still resolve, the SOFT-GATE pattern is preserved
- [ ] If a new file: it appears in `docs/README.md` or the relevant index where users would look
- [ ] CHANGELOG entry added under a new section (or under `## [Unreleased]`)
- [ ] If breaking: a migration note is included or a follow-up `docs/migration-vX-to-vY.md` is planned
- [ ] `claude plugin validate . --strict` passes

## Screenshots / sample output

<!-- Optional — useful for skill behaviour changes, template visual changes, lint output changes. -->
