# schema/

Single source of truth for structured artefacts in research projects.

## Files

- `knowledge-frontmatter.schema.json` — JSON Schema Draft-07 for the YAML frontmatter of every `knowledge/**/*.md` page.

## Consumers

| Consumer | How it uses the schema |
|----------|-----------------------|
| `scripts/lint-wiki.py` (template) | Loaded at runtime to validate frontmatter; failures become CI errors. |
| VS Code `yaml.schemas` (template `.vscode/settings.json`) | Live in-editor validation while authoring `.md` wiki pages. |
| Skills (`skills/*/SKILL.md`) | Reference the schema by path rather than inlining field lists. |
| `docs/frontmatter-schema.md` | Narrative explanation; defers to this file as the normative definition. |

## Changing the schema

The schema is the contract between skills, the linter, and the IDE. When you change it:

1. Bump the schema version in `$id` only if the change is breaking (field removal, enum narrowing, new required field).
2. Update `docs/frontmatter-schema.md` if the narrative explanation needs to change.
3. Run `python scripts/lint-wiki.py` on `examples/example-project/` to make sure the example still validates — or update the example.
4. Note the change in `CHANGELOG.md` under the next release.

Skill files should never inline the full schema — only minimal usage examples. The schema lives here.

## Template sync

`templates/research-project-template/schema/knowledge-frontmatter.schema.json` is a verbatim copy of this schema, shipped into every scaffolded project so that `scripts/lint-wiki.py` can resolve the schema at a project-relative path. When the plugin schema changes, mirror the change into the template copy in the same commit.

