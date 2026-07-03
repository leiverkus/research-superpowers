# Installation — click-only path (Cowork & non-technical users)

This guide is for users who don't have (or don't want) a terminal, Python, or git. Everything below happens inside Claude — no commands typed at the shell.

Audience: [Anthropic Cowork](https://claude.com/plugins) users, and Claude Code users who prefer a guided setup over the manual `cp -r` flow in [`installation.md`](installation.md).

Total time: **3–5 minutes**.

## What you need

Just Claude. Specifically: either Anthropic Cowork or Claude Code (any recent version). That's the only prerequisite.

- **No Python** — required for the optional fast wiki linter; the plugin falls back to an inline (in-chat) check when Python isn't there. Slower for large wikis but functionally equivalent for projects under ~20 pages.
- **No Git** — recommended eventually for version history, but the plugin works fine without. You can add git later.
- **No Quarto** — required only at the very end when you want to render a PDF or HTML of your finished manuscript. Until then, every file is plain Markdown and readable in any editor or right inside Claude.
- **No terminal at all** — everything is `/plugin install …` or natural-language conversation.

## Step 1 — Install the plugin

In your Claude session (Cowork or Claude Code), type:

```
/plugin marketplace add leiverkus/research-superpowers
```

You'll see a confirmation that the marketplace is registered.

Then:

```
/plugin install research-superpowers@leiverkus-research
```

The plugin downloads and activates. Restart your Claude session (close and reopen the conversation) and you'll see a short "Research Superpowers" notice at the start — that confirms the plugin is active.

## Step 2 — Create your first research project (no `cp` needed)

Don't open a terminal. Don't copy folders. Just say:

> Start a new research project on **Iron Age chronology in the Negev**.

(Replace the topic with your own.)

The `scaffold-research-project` skill triggers. The conversation looks roughly like this:

> **Claude:** "Project name? (kebab-case, e.g. `iron-age-chronology`)"
>
> **You:** "iron-age-chronology"
>
> **Claude:** "Parent directory? Default is `~/Documents`. Or paste an absolute path."
>
> **You:** "~/Documents"
>
> **Claude:** "Methodology? Three options: **hermeneutic** (default — theology, exegesis, source criticism, interpretive archaeology; no frozen hypothesis), **quantitative** (geostatistics, 14C Bayesian, full pre-registration), or **mixed** (per-sub-study)."
>
> **You:** "hermeneutic"
>
> **Claude:** "Discipline? Examples: 'Biblical Archaeology', 'Theology / Old Testament', 'Digital Humanities'."
>
> **You:** "Biblical Archaeology"
>
> **Claude:** "Languages for sources and wiki prose? Default `[en]`. Add others like `[de, en]` if you work bilingually."
>
> **You:** "en, de"
>
> **Claude:** "I'll create `~/Documents/iron-age-chronology/` with methodology `hermeneutic`, discipline `Biblical Archaeology`, languages `[en, de]`. Proceed?"
>
> **You:** "yes"

Claude creates the project directory, copies the full template, fills in your answers in `CLAUDE.md` frontmatter, and offers to initialise git (skip if you don't want it).

You now have a working research project.

## Step 3 — Add your first source

Open the new project in Claude (point your session at `~/Documents/iron-age-chronology/`).

Find any scholarly PDF you want to read. Save it into `input/bibliography/` of your project. (Cowork users: drag-and-drop into the project folder via Finder / Files; no shell needed.)

Back in Claude, say:

> Ingest this PDF: input/bibliography/finkelstein-2003-low-chronology.pdf

The `ingest-source` skill reads the full PDF, extracts the key claims, identifies the people, places, and concepts mentioned, and writes structured wiki pages to `knowledge/sources/` and `knowledge/entities/`. Plus a BibTeX entry and a log line.

You review the new files (in Claude or any text editor), accept or revise, and you're done with your first ingest.

## Step 4 — Check the wiki (still no Python)

Once you have a few sources ingested, say:

> Check the wiki for issues.

The `wiki-lint` skill runs. Because you don't have Python installed, it takes the **fallback path**: it validates the frontmatter of every page inline (in chat) and reports any missing fields. It tells you upfront that it's running in fallback mode and that wikilink-resolution and orphan-detection require Python — for now, you can skip those.

If your wiki stays under ~20 pages, that's fine. If it grows past that, the fallback gets slow (it costs tokens for every page read). At that point, ask Claude:

> How do I install Python and PyYAML?

It'll walk you through it. Or just keep using the inline check — your call.

## What about drafting and PDF rendering?

You can draft chapters and articles without any of this:

> Draft a chapter titled "The Chronology Debate" from the synthesis page chronology-debate.

The `drafting-manuscript` skill writes a `.qmd` file (Quarto Markdown — readable as plain Markdown in any editor) into `output/`. You can read and edit it in Claude or any text editor.

**PDF or HTML output requires Quarto.** This is the one thing you'll eventually need a CLI for. When you're ready to publish:

- Quarto runs locally (one-click installer at [quarto.org/docs/get-started](https://quarto.org/docs/get-started/))
- Or have a colleague with Quarto installed do the render (the `.qmd` file is what you hand them)
- Or use an online Quarto renderer (several exist)

For everything **before** publication — research, ingest, synthesis, drafting, peer review — you don't need Quarto.

## Recap: what each "give up" actually costs

| Without … | What's lost | Workaround |
|---|---|---|
| Python + PyYAML | Fast wiki linter, full wikilink + orphan check | Inline fallback covers frontmatter; install Python later if the wiki grows |
| Git | Version history, undo, branches | Save manual copies of important states; add git later |
| Quarto | PDF / HTML rendering | Quarto only at the publication step; `.qmd` files are Markdown until then |
| Terminal in general | None for ingest, synthesis, drafting, peer review | The whole research lifecycle works in chat |

## When to upgrade to the full setup

If you find yourself doing any of these regularly, switching to the full setup in [`installation.md`](installation.md) will be more comfortable:

- Wikis above ~50 pages (fallback lint gets noticeably slow)
- Multiple collaborators (git makes co-authoring much easier)
- Heavy drafting cycles (local Quarto preview is faster than copy-pasting around)
- Working with the optional MCPs (`dao-paper-search-mcp` for verified citations; needs Python via uvx — see [`recommended-mcps.md`](recommended-mcps.md))

Nothing in your project changes when you upgrade — the same `CLAUDE.md`, same wiki, same template. The CLI just becomes available.

## Troubleshooting

### Plugin install fails

Make sure you're on a recent enough version of Cowork or Claude Code (2.x or newer). The `/plugin` slash-command is required.

### "I told it to start a project but nothing happened"

Be explicit. "Start a new research project on X" reliably triggers the scaffold skill. "I want to research X" sometimes triggers `brainstorming-research` instead, which is *also* useful but does a different thing. If you're not sure, say: "Use the `scaffold-research-project` skill to set me up."

### "The fallback lint says 'schema not found'"

The scaffold should have copied the schema into your project. If it didn't (e.g. you copied the template manually instead of using the scaffold skill), say: "Copy the frontmatter schema from the plugin into my project's `schema/` folder." Claude does it.

### "I want to add Python later"

Say: "Walk me through installing Python and PyYAML." Or follow [`installation.md` § Before you start](installation.md#before-you-start) for the manual steps.

## See also

- [`installation.md`](installation.md) — the full setup with terminal, Python, git, Quarto
- [`quickstart.md`](quickstart.md) — five-minute hands-on for users with the full setup
- [`tutorial.md`](tutorial.md) — end-to-end walkthrough on a realistic mini-project
- [`concepts.md`](concepts.md) — what SOFT-GATE, methodology, and the SOT pattern mean
- [`recommended-mcps.md`](recommended-mcps.md) — optional MCPs for verified citations (requires Python / Docker)
