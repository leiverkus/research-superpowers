# Concepts

A narrative walk through the ideas this plugin is built on. Read this once; you won't need most skill files until you actually invoke them.

## The lifecycle

Research is a long process with phases that produce stable artefacts: an idea becomes a design doc; a design doc becomes a plan; a plan organises literature work, ingest, analysis, drafting, peer review, and finally a published artefact. The plugin gives each phase one **skill** — a checklist with discipline baked in.

```
brainstorming-research → writing-research-plan → literature-review ⇄ ingest-source
   → executing-research-plan → drafting-manuscript → requesting-peer-review → finishing-a-research-project
```

Plus three cross-cutting skills (`wiki-lint`, `semantic-wiki-review`, `grant-finder`) that fire when context demands them rather than at a fixed phase. See [`phase-flow.md`](phase-flow.md) for the full graph including back-edges.

## SOFT-GATE: discipline without authoritarianism

Earlier versions of this plugin used HARD-GATES: a skill would simply refuse to proceed unless a precondition held. That collapsed in practice — researchers ignored the gate (the model is supposed to obey the user, not block them), and once one gate was bypassed, the *principle* of gating eroded across the whole workflow.

v0.2 introduced SOFT-GATES instead. A SOFT-GATE has three parts:

1. **Check** — verify a named precondition (e.g. "at least one synthesis page has `status: stable`").
2. **If unmet, prompt** — the skill tells the user *exactly* which condition is missing and asks for a one-line reason to proceed anyway.
3. **Log and continue** — the reason is appended to `knowledge/_meta/gate-overrides.log` (date, skill name, missed condition, reason). Work proceeds.

The audit trail does the disciplining. Override rate above 30% over the last 10 entries triggers a `wiki-lint` warning — overrides are meant to be the exception, not the routine.

This pattern preserves the researcher's authority while making slippage visible.

## Pre-registration is methodology-aware

Pre-registered hypotheses come from quantitative psychology and medicine: state the hypothesis and the falsification criteria *before* looking at data, so the test is genuine. Adopted naively into humanities research, this becomes epistemically broken — hermeneutic disciplines (theology, exegesis, interpretive archaeology) are constituted by the iterative revision of understanding through engagement with sources. The *hermeneutic circle* is not a methodological failure.

v0.2 made pre-registration *methodology-aware*. Each project declares its `methodology` in the root `CLAUDE.md` frontmatter:

- **`hermeneutic`** (default) — the plan documents research question, method sketch, expected sources. No frozen hypothesis. Hypothesis revision through new reading is legitimate and logged.
- **`quantitative`** — full pre-registration applies (hypothesis, operationalisation, stop criterion). Deviations are logged; downstream results get marked exploratory rather than retconned.
- **`mixed`** — pre-registration applies per sub-study. Quantitative tasks in the plan are marked `pre-registered: true`; hermeneutic tasks are not.

Skills like `writing-research-plan` and `executing-research-plan` read the methodology and adapt their behaviour: the plan template differs, the review mode differs (two-stage spec+quality for quantitative; single-stage synthesis review for hermeneutic).

## SOT pattern: Skill is the only source of truth

A workflow has exactly **one** skill — the SOT. If the workflow also needs a subagent (for context isolation on a heavy task), an agent file is added; the agent **never duplicates** the skill checklist. Its only job is to declare:

- which skill it implements (`implements: <skill-name>` in its frontmatter)
- subagent-specific dispatch rules (no parent memory, one message, strict output format)
- the output report template

When the parent skill dispatches a subagent, it embeds the full SKILL.md content into the agent's prompt at dispatch time. The agent file stays small; the checklist lives in one place.

This was a v0.2 change. Earlier versions had three artefact types (skill, agent, command) and the same workflow logic lived in all three — which divergence made literally inevitable. See [`skill-contract.md`](skill-contract.md) for the formal contract, including the `inputs:` / `outputs:` frontmatter.

There used to be a third artefact type — OpenCode slash-command shims (`/ingest`, `/draft`, …). v0.3 removed them: OpenCode now reads skills natively from `.claude/skills/<name>/SKILL.md`, and the slash shortcuts added no UX value over natural-language triggering or the `skill` tool.

## Structural vs semantic review

Two skills audit the wiki, and they do *different* things:

- **`wiki-lint`** runs `scripts/lint-wiki.py` — a deterministic, CI-tauglich Python script. It checks frontmatter completeness, wikilink resolution, status distribution, and (since Phase 3) the rate of SOFT-GATE overrides. Fast, mechanical, repeatable.
- **`semantic-wiki-review`** is an LLM-driven content audit. It reads pages, builds a claim ledger, and flags contradictions, stale syntheses, unsupported claims, missing cross-references, and (with `dao-searxng-mcp`) aggregator/suspect citations. Slow, judgement-based, not a CI gate.

Earlier versions promised semantic checks in `wiki-lint`. They were never implemented. v0.2 split the work so the lint script only claims what it actually does, and the LLM work lives in its own skill that's invoked manually.

## Wiki is purpose-built, not a generic archive

This is the principle behind the focus-driven `ingest-source` skill (introduced in v0.5).

A generic RAG system indexes the full text of every document so anything can be retrieved. The result is faithful to the source but agnostic about what *you* need from it — and in practice, retrieval surfaces a lot of irrelevant material that the LLM then has to filter on every query.

This plugin takes the opposite stance. A source page documents **what your project takes from a source under a specific focus**, not a generic summary. Each ingest answers a per-source question: *for the project's research question, and for the specific aspect you're working on right now, what does this source actually contribute?* The skill asks for that focus (proposing the project's research question as the default) and extracts only the claims, quotes, and entities that bear on it. The raw PDF stays in `input/bibliography/` as the canonical "everything"; the wiki is the curated interpretation.

When a new focus emerges — say you're working on a different chapter that draws on the same source from a different angle — you re-ingest. The skill detects the existing source page and **appends** a new `## Focus: …` block rather than overwriting the previous one. One wiki page accretes multiple lenses over the project's life. The bibkey stays the same; later focuses just add new bullets, new quotes, new entities.

Two structural honesty conventions support this:

- **`## Boundary: what this source does NOT address (within this focus)`** — every focus block explicitly names what's *not* there. Researchers reading the page later (or downstream skills like `drafting-manuscript`) know exactly where the source's reach ends.
- **`## Other content in this source`** — one paragraph noting major topics not extracted under any current focus. A signpost to the PDF in case a future re-ingest needs them. Replaced (not appended to) on each re-ingest.

The trade-off: source pages are thinner than a full summary, and a colleague who later wants a "what does Finkelstein 2003 say overall?" view has to read the PDF or trigger a re-ingest with a broader focus. We think that's the right trade — it keeps the wiki aligned with the project rather than pretending to be a personal library.

This is also why the skill never silently overwrites an existing source page. The wiki is treated as accumulated interpretation, not a regenerable summary.

## MCPs are soft-preference, not required

The plugin ships standalone. Two recommended MCPs ([`dao-paper-search-mcp`](https://github.com/leiverkus/dao-paper-search-mcp) and [`dao-searxng-mcp`](https://github.com/leiverkus/dao-searxng-mcp)) add structurally verified citations and source-class detection — exactly the discipline problems the plugin's red flags talk about. Each skill that benefits from these MCPs has an "MCP Optimisation (recommended)" section that names the soft-preference: *if* the MCP is available, use it; otherwise stay on the documented manual path.

The plugin must never *require* an MCP to function. See [`recommended-mcps.md`](recommended-mcps.md) for setup.

## What this plugin doesn't do

- It doesn't write your manuscript for you. Drafting is collaborative; the skill enforces "every claim cites a source page, every citation resolves in BibTeX, render-check is part of drafting."
- It doesn't replace your editor. Skills produce artefacts (wiki pages, plans, drafts); you read and revise them in your IDE.
- It doesn't promote `status: draft` → `status: stable`. Only the user does. Agents are explicit about not self-promoting their own output.
- It doesn't decide your methodology for you. The `methodology` field has a default (`hermeneutic`) but you set it; the plugin reads and respects what you wrote.

## Where to go next

- Hands-on: [`quickstart.md`](quickstart.md) (5 minutes to first ingest).
- Full walkthrough: [`tutorial.md`](tutorial.md) (end-to-end on a realistic mini-project).
- Reference: [`frontmatter-schema.md`](frontmatter-schema.md), [`skill-contract.md`](skill-contract.md), [`skill-authoring.md`](skill-authoring.md).
- Phase graph: [`phase-flow.md`](phase-flow.md).
- Optional MCPs: [`recommended-mcps.md`](recommended-mcps.md).
