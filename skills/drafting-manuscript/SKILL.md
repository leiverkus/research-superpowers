---
name: drafting-manuscript
description: Use to draft a book chapter, article section, or grant exposé from synthesized wiki content. Settles the argument architecture with the user first, then drafts section by section — each section's argument agreed before its prose is written. Pulls from stable synthesis pages and source pages, writes to `output/**/*.qmd` with proper citations. Never drafts from memory — always from the wiki.
argument-hint: "<section, e.g. 3.2 Core arguments>"
inputs:
  - name: plan_task_id
    description: Reference to the explicit Draft task in input/ideas/<slug>-plan.md
    required: true
  - name: target_section
    description: Section title and chapter position (e.g. "3.2 The Low Chronology — Core Arguments")
    required: true
  - name: output_path
    description: Target QMD file path (e.g. output/book/text/03-methods.qmd)
    required: true
  - name: synthesis_pages
    description: Paths to knowledge/synthesis/*.md to draw from (must include at least one status=stable)
    required: true
  - name: source_pages
    description: Paths to knowledge/sources/*.md whose bibkeys are allowed for citation
    required: true
  - name: source_pdfs
    description: Paths to the original PDFs for the cited sources — resolve them with scripts/library.py (they live at <library>/pdf/<bibkey>.pdf) — for reaching back to examples/context when a page is too thin. Optional but strongly recommended; acquire-sources places these in the library.
    required: false
  - name: target_language
    description: de or en
    required: false
  - name: target_word_count
    description: Target prose length (±15%), distributed over the sections as per-section budgets in the outline
    required: false
outputs:
  - path: output/<book|article>/outline/<basename>.md
    kind: created_or_modified
  - path: output/**/*.qmd
    kind: created_or_modified
  - path: knowledge/_meta/log.md
    kind: appended
agents:
  - drafter
---

# Drafting a Manuscript

Turn stable synthesis pages into publishable prose. Every claim gets a citation. Every citation resolves in `output/bibtex/references.bib`. No inventing, no paraphrasing from memory — the wiki is the single source of truth for *what is claimed*.

But the wiki is deliberately terse — bullets, one-sentence claims, page numbers in parentheses. It is a **pointer to the depth, not the depth itself.** Drafting straight from it produces dense, compressed prose that reads like reflowed bullet points, without the examples and explanations a reader needs. The fix is *not* to write more from memory (that reintroduces hallucination) but to **reach back to the sources for depth**: the illustrative examples, the explanation of *why* a claim holds, and the surrounding argument live in the source pages' quote/example sections and — when those are too thin — in the original PDFs in the shared library (`<library>/pdf/<bibkey>.pdf`, put there by `acquire-sources`). Elaboration must be **grounded and cited**; only connective/expository framing (transitions, restating an argument's logic) is uncited. See [Writing with depth](#writing-with-depth-not-bullet-reflow).

And the wiki tells you *what is claimed* — never *what this chapter argues*. The claim chain is the author's contribution, not the wiki's — which is why the thesis comes **from the author first** (STOP 0), and you sharpen it rather than propose it. A thesis the user merely approves looks like agreement but skips the thinking: a polished machine formulation reads as better than one's own and is accepted unchecked (automation bias). Formulating the thesis *is* the author's work; checking it against the wiki, naming its gaps and its strongest counter-position is yours. And the claim chain is the thing that drifts: drafted in one pass, a chapter wanders into whatever the sources happen to be rich about, and the drift only becomes visible once thousands of words exist and are expensive to throw away. So the argument is **settled on paper and discussed before any prose exists**, then carried out one section at a time, each section's argument agreed before it is written. See [The three stages](#the-three-stages).

**Announce at start:** "Using drafting-manuscript to draft <chapter/section> into `<path>`. Three stages: you state the thesis in your own words, we settle the argument architecture on it, then go section by section — argument, then prose, with a check-in at each."

<SOFT-GATE>
Before drafting, check:
(1) At least one `knowledge/synthesis/*.md` with `status: stable` exists AND is referenced by the draft task — *`lint-wiki.py`'s `UNSTABLE-DRAFT` gate checks the first half of this mechanically (a drafted manuscript with no stable synthesis anywhere). Only the user promotes a page to `stable`; an agent that edits that field to clear the gate has forged an attestation, not satisfied it.*
(2) Every source cited in the target section exists as `knowledge/sources/*.md` AND has a BibTeX entry
(3) `wiki-lint` is green on the knowledge tree
(4) The research plan `<slug>-plan.md` contains an explicit Draft task for this output file
(5) None of the synthesis / source pages this draft pulls from carries an open `review_flags` entry (`state: open`)

If a condition is unmet: tell the user which (e.g. "no stable synthesis yet"),
ask for a short reason to draft anyway, write it into
`knowledge/_meta/gate-overrides.log`, and start the draft. Repeated overrides
on (3) are a maintenance signal.

On (5): an open flag means a content review found an unresolved concern
(overstatement, weak support, stale claim) on a page you are about to turn into
prose — drafting from it would bake the problem into the manuscript. Prefer
resolving it first (fix the page, set the flag `state: resolved`) over
overriding. Note which page and flag `kind` in the override reason.
</SOFT-GATE>

## The three stages

| Stage | Produces | Ends at |
|-------|----------|---------|
| **A — Architecture** | The author's thesis, then the sharpened thesis + claim chain + per-section claims, in the outline file | **STOP 0**: author states thesis · **STOP 1**: user approves the architecture |
| **B — Section loop** | Per section: an argument sketch, then its prose | **STOP 2** and **STOP 3**, per section |
| **C — Finishing** | Citation check, render, log | Done |

Stage B repeats per section. A chapter is finished when every section in the outline has `Status: approved`.

<STAGE-GATE>
Four stops. At each one you **present (or ask) and wait** — the message that
presents a stop ends there. Do not present a stop and continue past it in the same message;
that is not a check-in, it is an announcement.

**STOP 0 — The author's thesis (start of Stage A, after reading).** Before you
write any outline, ask the user: *what does this chapter establish, in one or
two sentences — and roughly how does it get there?* Rough is fine: a sentence,
a list of steps, a voice-note transcript, a paragraph of free writing. Do not
offer a candidate thesis in the same message; a suggestion on the table becomes
the answer. Wait. Record their words verbatim in the outline's
`Author's formulation` field. Then build the thesis and claim chain **on that
formulation**: sharpen it, check each step against the synthesis and source
pages, and say plainly where the wiki does not carry it, where it is a topic
rather than a claim, and what the strongest counter-position is. If you propose
a substantially different thesis, present it as an alternative *next to* theirs,
with the reason — not as a silent replacement. On resume (outline exists), STOP 0
is already done.

If the user explicitly asks you to propose the thesis ("schlag du vor", "you
suggest one"), do so — that is an override of STOP 0: note it in
`knowledge/_meta/gate-overrides.log`, mark the outline's `Author's formulation`
as `agent-proposed — not yet in the author's words`, and at STOP 1 ask them to
restate the thesis in their own words before the chain is approved.

**STOP 1 — Architecture (end of Stage A).** The outline file is written; present
the thesis and the claim chain (not the whole file — the user can read it) and
ask whether the chain holds. Wait. No prose exists yet and none is written until
this is approved.

**STOP 2 — Section argument (per section, Stage B).** The section's
Argumentationsgang is sketched into the outline. Present it. Ask whether the
argument is right *before* it costs a thousand words. Wait. This is the cheap
place to redirect — that is the entire point of the stage.

**STOP 3 — Section prose (per section, Stage B).** The prose for THIS section
only, plus an explicit line on where it deviates from the approved sketch (or
"no deviations"), plus its **reverse outline** — one line per paragraph: its
function and its main statement (see [Reverse outline](#reverse-outline)). The
reverse outline is what lets the user check in thirty seconds whether the prose
says what they mean; reading a thousand words for that is what gets skipped.
Present. Wait. On approval, append to the target file, set the
section's `Status: approved`, and move to the next section — one section per
turn, never two.

**Overriding.** The user may want a straight run ("zieh durch", "just draft the
whole thing"). That is legitimate. Name which stops you are skipping, write the
reason to `knowledge/_meta/gate-overrides.log`, and proceed. An override is
per-request, not permanent: it covers this draft, not the next one. Repeated
overrides on STOP 2 mean the section loop is not earning its cost — worth saying
so out loud.
</STAGE-GATE>

## When to use

- A plan Draft task is current (`executing-research-plan` routes here)
- Synthesis page(s) are stable and user asks for chapter/article draft
- Rewriting a chapter after peer-review revisions (iterate via same skill — the outline is the thing you revise against)

**NOT for:** first-draft brainstorming (use `brainstorming-research`), unsynthesized material (go back and synthesize first), grant research narratives from scratch (use `grant-finder`).

## Checklist

### Stage A — Architecture

1. **Confirm plan task** — find the exact entry in `<slug>-plan.md`; confirm output file path
2. **Pre-flight checks (SOFT-GATE)** — stable synthesis pages? BibTeX complete? wiki-lint green? No open `review_flags` on the pages you pull from?
3. **Read all referenced synthesis pages** fully
4. **Read all cited source pages** — the full page, especially the `### Direct quotes` and `### Examples & illustrations` sections (the raw material for depth), not just the one-line claims
5. **Resume check** — if an outline already exists at the derived path, read it and continue from the first section whose `Status` is not `approved`. Do not restart the chapter.
6. **STOP 0 — ask for the author's thesis** — one or two sentences plus a rough path, in their own words; no candidate of yours in that message. Wait. Skip on resume
7. **Write the outline** — the author's formulation verbatim, then the sharpened thesis, claim chain, per-section claims, to `output/<book|article>/outline/<basename>.md` (see [Outline file](#outline-file)). Distribute `target_word_count` into per-section budgets
8. **STOP 1** — present thesis + claim chain, wait for approval, revise until the chain holds

### Stage B — Section loop (repeat per section)

9. **Sketch the section's argument** — claim, steps with their evidence, the concrete material, the counter-position and how it is handled, the handoff to the next section (see [Section argument sketch](#section-argument-sketch)). Write it into the outline under that section. Bullets, not prose
10. **STOP 2** — present the sketch, wait for approval, revise until the argument is right
11. **Draft prose for this section only** — against the approved sketch; develop each substantive point (assertion → grounding → example → significance, see [Writing with depth](#writing-with-depth-not-bullet-reflow)); citations inline as `[@bibkey]` or `[@bibkey, p. 152]`. For long sections, dispatch the `drafter` subagent (see [Subagent dispatch](#subagent-dispatch-per-section-not-per-chapter))
12. **Reach back to sources where the wiki is thin** — when a page cannot support the needed elaboration, open its `### Direct quotes` / `### Examples & illustrations`; if still insufficient, open the original PDF at `<library>/pdf/<bibkey>.pdf` at the page anchors the source page cites, draw out the example/explanation, and cite it. Never fill the gap from memory
13. **Check the prose against the sketch** — every approved step present? anything in the prose that is not in the sketch? Name deviations explicitly rather than hoping they pass. Then **write the reverse outline** (see [Reverse outline](#reverse-outline)) and read it against the sketch: a paragraph whose function you cannot name, two paragraphs with the same main statement, or a paragraph that only lines up facts (*knowledge telling*) is fixed now, before STOP 3. Check the [precision rules](#precision-rules) on the same pass
14. **STOP 3** — present the prose + the deviation line + the reverse outline, wait for approval, revise
15. **Append and mark** — append to the target `.qmd`, set the section's `Status: approved` in the outline, then go to step 9 for the next section
16. **If the chain changed** — a STOP 2 or STOP 3 discussion may invalidate the architecture (a section's claim moves, a step migrates to a neighbour). Update the outline's claim chain and say so. Do not let the outline and the manuscript drift apart — a stale outline is worse than none

### Stage C — Finishing

17. **Chapter coherence check** — once every section is approved, read the chapter as a whole, because each section passing on its own does not make the chapter cohere (LLM prose is typically coherent locally and breaks globally). (a) Join the section reverse outlines and read them against the outline's thesis and claim chain: does each section hand on what the next one starts from, does any step of the chain have no section carrying it? (b) **Introduction ↔ conclusion**: is every question, aim or promise the introduction announces answered or explicitly bracketed in the conclusion, and does the conclusion claim nothing the chapter did not argue? (c) Terminology: is each key term used in one sense throughout? Present the findings as a short list with locations; fix only what the user approves — this is a check, not a rewrite pass
18. **Verify every citation** — each `[@bibkey]` has a matching entry in `output/bibtex/references.bib`
19. **Render check** — run `make render` (or `quarto render`) in the target `output/<book|article>/` directory; fix any errors
20. **Log** — entry in `knowledge/_meta/log.md`: date, draft, target file, word count, source count

## Process Flow

```dot
digraph drafting {
    "Confirm plan task" [shape=box];
    "Pre-flight (SOFT-GATE)" [shape=box];
    "Gate passes?" [shape=diamond];
    "Back to synthesis / ingest / lint" [shape=box];
    "Read synthesis + source pages" [shape=box];
    "Outline exists?" [shape=diamond];
    "STOP 0: author states thesis" [shape=box];
    "Write outline: thesis + claim chain" [shape=box];
    "Resume at first unapproved section" [shape=box];
    "STOP 1: architecture approved?" [shape=diamond];
    "Revise outline" [shape=box];

    "Next unapproved section" [shape=box];
    "Sketch section argument" [shape=box];
    "STOP 2: argument approved?" [shape=diamond];
    "Revise sketch" [shape=box];
    "Draft prose for THIS section" [shape=box];
    "Page too thin for depth?" [shape=diamond];
    "Reach back to source quotes / PDF" [shape=box];
    "Check prose against sketch" [shape=box];
    "STOP 3: section approved?" [shape=diamond];
    "Revise prose" [shape=box];
    "Append to .qmd; Status=approved" [shape=box];
    "Sections left?" [shape=diamond];

    "Chapter coherence check" [shape=box];
    "Verify citations" [shape=box];
    "Citations complete?" [shape=diamond];
    "Fix citations" [shape=box];
    "Render check" [shape=box];
    "Render OK?" [shape=diamond];
    "Fix render errors" [shape=box];
    "Log entry" [shape=box];
    "Done" [shape=doublecircle];

    "Confirm plan task" -> "Pre-flight (SOFT-GATE)";
    "Pre-flight (SOFT-GATE)" -> "Gate passes?";
    "Gate passes?" -> "Back to synthesis / ingest / lint" [label="no"];
    "Gate passes?" -> "Read synthesis + source pages" [label="yes"];
    "Read synthesis + source pages" -> "Outline exists?";
    "Outline exists?" -> "Resume at first unapproved section" [label="yes"];
    "Outline exists?" -> "STOP 0: author states thesis" [label="no"];
    "STOP 0: author states thesis" -> "Write outline: thesis + claim chain";
    "Write outline: thesis + claim chain" -> "STOP 1: architecture approved?";
    "STOP 1: architecture approved?" -> "Revise outline" [label="no"];
    "Revise outline" -> "STOP 1: architecture approved?";
    "STOP 1: architecture approved?" -> "Next unapproved section" [label="yes"];
    "Resume at first unapproved section" -> "Next unapproved section";

    "Next unapproved section" -> "Sketch section argument";
    "Sketch section argument" -> "STOP 2: argument approved?";
    "STOP 2: argument approved?" -> "Revise sketch" [label="no"];
    "Revise sketch" -> "STOP 2: argument approved?";
    "STOP 2: argument approved?" -> "Draft prose for THIS section" [label="yes"];

    "Draft prose for THIS section" -> "Page too thin for depth?";
    "Page too thin for depth?" -> "Reach back to source quotes / PDF" [label="yes"];
    "Reach back to source quotes / PDF" -> "Draft prose for THIS section";
    "Page too thin for depth?" -> "Check prose against sketch" [label="no"];
    "Check prose against sketch" -> "STOP 3: section approved?";
    "STOP 3: section approved?" -> "Revise prose" [label="no"];
    "Revise prose" -> "STOP 3: section approved?";
    "STOP 3: section approved?" -> "Append to .qmd; Status=approved" [label="yes"];
    "Append to .qmd; Status=approved" -> "Sections left?";
    "Sections left?" -> "Next unapproved section" [label="yes"];
    "Sections left?" -> "Chapter coherence check" [label="no"];
    "Chapter coherence check" -> "Verify citations";

    "Verify citations" -> "Citations complete?";
    "Citations complete?" -> "Fix citations" [label="no"];
    "Fix citations" -> "Verify citations";
    "Citations complete?" -> "Render check" [label="yes"];
    "Render check" -> "Render OK?";
    "Render OK?" -> "Fix render errors" [label="no"];
    "Fix render errors" -> "Render check";
    "Render OK?" -> "Log entry" [label="yes"];
    "Log entry" -> "Done";
}
```

## Outline file

One outline per draft target. The path is **derived mechanically** from `output_path`: same directory root, `outline/`, same basename, `.md`.

| Target | Outline |
|--------|---------|
| `output/book/text/03-methods.qmd` | `output/book/outline/03-methods.md` |
| `output/article/article.qmd` | `output/article/outline/article.md` |

It sits outside Quarto's render tree (`_quarto.yml` lists chapters explicitly), so it never renders. It is a **living document**: the architecture, plus each section's approved argument sketch, plus the per-section status. That is what makes a long chapter survive a context compaction or a break of several days — the agreements are on disk, not in the chat history. It is also what you revise against after peer review.

```markdown
---
title: "<Chapter / section title>"
type: outline
target: output/book/text/03-methods.qmd
plan_task: "<Draft task id from <slug>-plan.md>"
created: YYYY-MM-DD
updated: YYYY-MM-DD
target_words: 4500
status: draft | approved
---

# Outline: <Chapter title>

## Author's formulation

<The user's own words at STOP 0, verbatim — rough is fine. Or
`agent-proposed — not yet in the author's words` if STOP 0 was overridden.
Kept as written; the sharpened version goes below.>

## Thesis

<ONE sentence, sharpened from the author's formulation: what this chapter establishes that the reader did not have
before. Not a topic ("this chapter discusses the Low Chronology") — a claim
("the Low Chronology's stratigraphic case rests on three sites whose sequences
are themselves dated by the pottery they are meant to date"). If you cannot
write it as one sentence, the chapter has no thesis yet — go back to the
synthesis pages before proposing an outline.>

## Claim chain

<2–5 sentences of prose: how the sections build from the thesis to the
conclusion, each one earning the next. Readable aloud as a chain. THIS is what
the user approves at STOP 1 — if it only makes sense as a list of topics, it is
a table of contents, not an argument.>

## Sections

### S1 — <Section title>

- **Claim:** <what this section establishes — one sentence>
- **Evidence:** `[@bibkey1]`, `[@bibkey2]`
- **Synthesis basis:** `[[synthesis-page-slug]]`
- **Function:** <what it hands to the next section>
- **Not here:** <the adjacent point that belongs elsewhere — the anti-drift line>
- **Budget:** ~<n> words
- **Status:** outlined | sketched | drafted | approved

### S2 — <Section title>
…
```

## Section argument sketch

At STOP 2, this block goes into the outline **under the section it belongs to**, then gets approved. Bullets — writing prose here defeats the purpose.

```markdown
#### Argument (approved YYYY-MM-DD)

- **Claim:** <the section's claim, sharpened by the discussion>
- **Steps:**
  1. <step> — carried by `[@bibkey, p. XX]`
  2. <step> — carried by `[@bibkey, p. XX]`
  3. <step> — carried by `[@bibkey, p. XX]`
- **Concrete material:** <the specific artefact / site / passage / dataset that
  illustrates the argument, named, with its source-page anchor. If you cannot
  name one, this section will be assertion-stacking — find one or narrow the
  claim.>
- **Counter-position:** <the strongest objection in the literature, cited> —
  handled by <conceding / refuting on evidence X / bracketing as out of scope>
- **Hands to next:** <the sentence the next section can start from>
```

The counter-position line is not decoration. A section that cannot name what argues against it has not engaged the debate, and a reviewer will say so — cheaper to hear it here.

## Reverse outline

Written after the prose, from the prose — not copied from the sketch. One line
per paragraph:

```markdown
#### Reverse outline — S3
| ¶ | Function | Main statement |
|---|----------|----------------|
| 1 | claim | The Negev argument rests on three sites anchored by the horizon they date |
| 2 | grounding | Tel Masos II is dated only by its pottery [@finkelstein-1999-hazor, p. 61] |
| 3 | example | … |
| 4 | counter-position | Mazar reads Arad independently [@mazar-2011-iron] |
| 5 | rebuttal | … |
| 6 | handoff | The circularity is methodological, not evidential → S4 |
```

**Functions** (use these words, so a gap is visible): `claim`, `grounding`,
`example`, `counter-position`, `rebuttal` / `concession`, `definition`,
`method`, `significance`, `transition`, `handoff`. A paragraph that can only be
labelled `facts` is *knowledge telling* — information lined up without being
turned towards the section's claim. Rewrite it so it states what the facts show
for the argument, or cut it.

**What the user reads it for:** does each line say what *they* mean? does the
sequence follow the approved steps? is any step missing, doubled, or in a
paragraph that does two jobs? The reverse outline is stored in the outline file
under the section, below its approved sketch, and is updated if the prose is
revised.

## Citation Rules

- Inline citations: `[@finkelstein-2003]` or `[@finkelstein-2003, p. 152]`
- Multiple: `[@finkelstein-2003; @mazar-2011]`
- Every citation key MUST exist in `output/bibtex/references.bib`
- Direct quotes: inline with `>` or an em-dash, always with page number
- No uncited claims in argumentative sections (exception: common knowledge, clearly marked)
- **Positions carry their date.** Before sketching a section, run `python scripts/wiki-to-graph.py timeline <slug>` for each concept or synthesis page the section argues about (MCP: `graph_timeline`), and read the `Research chronology` section of `lint-wiki.py`. The timeline lists the sources in publication order with what each says about the page and about the earlier sources; put the relevant lines into the sketch, so the order of the argument is agreed at STOP 2 and not improvised in prose. Then:
  - A researcher's view is what they hold in their **latest** source in the wiki. An earlier view they gave up (`revises`) appears as history, in the past tense, with what changed their mind: "Finkelstein first dated … [@finkelstein-1996-…]; after the Tel Rehov dates he moved to … [@finkelstein-2003-…]".
  - A source with an incoming `supersedes` is not cited as the state of the question. Cite it together with what superseded it, and say on what `basis` — new evidence dates the older position, a reinterpretation only disputes it.
  - Positions from different decades are not listed as parallel options unless the wiki shows the earlier one is still held (`contradicts`, or a `responds-to` that leaves it open). Order them in time and name the finds or arguments that moved the discussion.
  - Later is not the same as right. Where a later source merely ignores an earlier objection, say so; do not present it as settled.
- **Same author, same year, several works** — citeproc disambiguates the rendered citation on its own (*2026a*, *2026b*), so the manuscript needs nothing. What a human and the next agent need is a way to look up which is which, and that goes in a `shortlabel` field on the BibTeX entry, never in `note`:
  ```bibtex
  @incollection{hensel-2026-obadja,
    ...
    shortlabel = {Hensel 2026e},
    note       = {Open Access (CC BY-NC-ND 4.0)}
  }
  ```
  The label is a fact about **this** manuscript's reference list, not about the work — the same title is 2026b in a project whose author wrote a different set of chapters. `merge-bibs.py` drops `shortlabel` on merge for exactly that reason, while `note` keeps merging because the rest of what lives there is shared fact. Putting the label in `note` sends one book's numbering into every other project.
- **Web citations** (online databases, digital editions, research blogs without a BibTeX entry): use the `(domain — title)` form as an inline link, e.g. `[(idai.gazetteer.de — Tel Megiddo)](https://gazetteer.dainst.org/place/2048473)`. Use sparingly; group separately as "Web resources" in the references list.

## Writing with depth (not bullet-reflow)

The single most common failure of wiki-driven drafting is **bullet-reflow**: each terse wiki claim becomes one flat sentence, so the prose is dense, assertion-stacked, and unreadable. Avoid it by developing every substantive point instead of merely restating it.

**Three kinds of expansion — know which you are doing:**

| Expansion | Allowed? | Rule |
|-----------|----------|------|
| **Grounded elaboration** — examples, the explanation of *why* a claim holds, the argument around it | **Yes, do this** | Must come from the source (its page/quotes/examples or the PDF), and must be cited |
| **Expository framing** — transitions, restating an argument's logic, signposting | Yes | Rhetoric, not a new claim; uncited |
| **New factual claim from memory** | **No** | This is invention — the thing the wiki-only rule forbids |

**Develop each substantive point** — a useful pattern per paragraph (not a rigid template):

1. **Assertion** — the claim, in your own prose (from the wiki).
2. **Grounding** — the evidence or reasoning the source gives for it, cited `[@bibkey, p. XX]`.
3. **Example / illustration** — a concrete case the source uses (a specific artefact, site, dataset, passage). This is what the wiki bullet omits and what the reader needs — reach into the source for it.
4. **Significance** — why it matters for the section's argument (expository, uncited).

A single terse wiki bullet typically becomes a **developed passage**, not a single sentence. If a paragraph has assertions but no example and no explanation, it is not finished.

**Reach-back procedure** (checklist step 12) — escalate only as far as needed:

1. The source page's `### Direct quotes` and `### Examples & illustrations` sections — the cheapest, already-extracted depth.
2. If still too thin: open the **original PDF** at `<library>/pdf/<bibkey>.pdf` at the page numbers the source page cites (the anchors point you straight to the passage — no full re-read), and draw out the example/explanation.
3. If the source page gives **no usable page anchor**, do not read the PDF end to end — find the passage:

   ```bash
   python scripts/bib-search.py "copper smelting" --key benyosef-2019-copper
   ```

   It returns the **physical** PDF page — right for opening the file, wrong for citing. Take the printed page number from the page itself.

   **Search for the concept, not the string.** `bib-search` is lexical: it matches the characters you typed and nothing else. A method is written differently by every discipline that borrowed it, so a single-string query measures your vocabulary, not the library. Name the method, list its aliases, run them as rank-fused `--q` variants, and **say which alias hit** (the `via:` line reports it) — see [Searching for a concept](#searching-for-a-concept-not-a-string).
4. Cite whatever you use. If the source genuinely lacks the needed depth, say so plainly or narrow the claim — do **not** fill the gap from memory.

### Searching for a concept, not a string

Before a concept search, run `python scripts/bib-search.py index` — it is incremental and costs about a second. A stale index answers about the library you had, not the one you have.

Then run the method's aliases as **several narrow queries, rank-fused** — one alias per `--q`:

```bash
python scripts/bib-search.py '"random labelling"' \
    --q '"random labeling"' --q 'relabel* OR shuffl*' \
    --q '"mark permutation" OR "permutation of marks"' \
    --q '"toroidal shift"' --q '"random thinning"' --limit 40
```

Every query runs separately and the page lists are merged by **reciprocal rank fusion** (RRF): a page's score is Σ 1/(60 + rank-in-list) over the lists it appears in. Two consequences, both deliberate: a page that several aliases agree on rises above any single list's top hit, and an alias's best hit can never be flooded out of its own list by a noisy sibling — the failure mode of the old single-OR-query form, where every alias competed inside one BM25 ranking. BM25 scores are never compared across queries (they are not on one scale); only ranks cross the boundary. Each hit's `via:` line reports which queries matched it — the "say which alias hit" discipline below, mechanised.

What belongs in the alias list, in order of how often it is the one that pays:

- **Spelling variants first.** `labelling` / `labeling`, `modelling` / `modeling`, `analyse` / `analyze`. Measured on the real library: `"random labelling"` found one paper, `"random labeling"` found a different one — a 311-page dissertation that makes the technique its explicit default. **One letter, and it was invisible.** This is the cheapest alias and the most neglected.
- **Word stems, not exact forms — `relabel*`, not `relabelling`.** A paper writes *relabeled*, *permuted*, *shuffling*; an exact-form alias list matches none of those. This is not hypothetical: adding `relabel*` and `shuffl*` to the query above takes it from **two of five** hand-checked papers to **three**, because one of them names the procedure four times over — "randomly relabeled", "randomly permuted", "shuffling only the labels" — in inflections no exact form catches.
- **Keep the stem rare.** Check selectivity before adding one; a stem that matches half the library buys nothing and costs a paper you already had. On this library `relabel*` matches 5 pages, `shuffl*` 21 — both precise. `permut*` matches 116 and `random*` matches 2,126: adding `permut*` surfaced a new paper and **dropped one the narrower query had found**, because FTS5 ranks by BM25 and a broad stem floods the ranking with pages that merely use the word. Inside one query that trade is real; as its own `--q` variant a broad stem is harmless to its siblings (each query keeps its own top-`limit`) — though it still buys little if it matches half the library.
- **The other disciplines' names for it.** Ecology, statistics and archaeology rename each other's methods. In the same measurement `"mark permutation"` surfaced three papers that a purely archaeological vocabulary never reaches.
- **The other language — always, when the library is mixed.** The index matches characters, so a query in the language you are *writing* in does not reach a source written in another: `Besiedlungslücke` finds no page that says "occupation gap", and the reverse. Run every concept in each language the library holds (German and English at least; French, Spanish, Italian where the field publishes in them), one `--q` per language. Measured on a 3,131-document library with 20 wiki claims of known source: queries in the source's language found 17, queries in the other language found 3 — and those three only through a proper name both languages share (`Teman`, `Apollonia`). Place names and transliterations need the same care: `Nitzana` / `Nessana`, `Garizim` / `Gerizim`, `Qos` / `Qaus`.
- **Search with the source's words, not your paraphrase of them.** A wiki claim is already a rewording; its distinctive words may appear nowhere in the source. In the same measurement a paraphrase ("nomads … monumental architecture … invisible") missed a paper that its own term ("architectural bias") puts at rank 1. `bib-search` helps with the first half: a plain query of 3–6 terms that leaves room under `--limit` is filled from its two-term pairs, and those hits are marked `~` with the pair that found them. **A `~` hit matched part of your query, not all of it** — read the page before treating it as an answer, and use `--no-relax` when "no page has all of these" is itself the finding. Swapping the paraphrased term for the source's own is still yours to do.

**Report which alias hit which source.** That line is the point of the exercise: it is a finding about the field's vocabulary, not search bookkeeping — and it is what makes the next item visible.

> **Know the ceiling — and don't overstate it.** On a hand-checked set of five papers that the wiki says use random labelling, the stem query above finds **three**. The two it misses fail for different reasons, and telling them apart is the whole lesson:
>
> - **One is outranked, not unnamed.** It writes "permutation" on two pages and "shuffl" on a third. A lexical query *can* reach it — but only a stem broad enough to cost another paper its place. That is a **ranking** limit, and the rank-fused `--q` form above is exactly the fix: one alias per query, so the broad stem competes only inside its own list.
> - **One is genuinely unnamed.** It calls the procedure "random type assignment to the points in the pattern" and carries no alias on any page. **No lexical query reaches it**, and adding synonyms cannot change that.
>
> When a concept search comes back thin, that is evidence about *naming*, not about absence — go to the source pages and the wiki's concept page, which record what the paper *does* rather than what it calls it. Do not report "not found in the library" from a lexical miss.
>
> **Reaching for embeddings here is a trap.** The obvious fix — index the library semantically and search by meaning — was prototyped and measured against exactly this question (BGE-M3 and Qwen3-Embedding-0.6B, chunked from 450 down to 40 tokens), and it does not pay. Scored on a 3,000-page sample — a tenth of the library, so a tenth of the difficulty — BGE-M3 put all five gold pages between rank 334 and 621 (`recall@20 = 0 of 5`); Qwen3, the better of the two by a factor of four, reached `recall@10 = 1 of 5`. That merely **ties** the naive one-string FTS query, which scores its 1 of 5 against the *whole* library — and it costs a 2.3-hour index build. A page of dense academic prose carries one method sentence among hundreds, and the average drowns it at every chunk size whose vectors still fit in memory. The vocabulary gap above is real; a vector index is not what closes it.

> **A third avenue: curated keywords, once they exist.** Both the alias-query technique above and the rejected vector index are *derived-from-text* mechanisms — they infer intent from what a paper's prose happens to say. A curated `keywords` field on the BibTeX entry (see `ingest-source`'s BibTeX Entry Convention) is neither: it records what a human or LLM understood the source to be about, at ingest time. `bib-search.py` checks it automatically and lists a keyword hit first, ahead of any page hit — cheaper and higher-precision than building an alias query, when it exists. It does not replace the alias-query technique above: most of the library predates this field and carries none yet. Check keywords first, fall back to the alias recipe when a source has none.

### Precision rules

Fluent prose is not yet precise prose. The typical failures of model-written
academic text are not grammatical; they are these:

- **Terms of art are fixed.** Once a term is introduced — *Low Chronology*,
  *Stratum VA–IVB*, *Formgeschichte*, *random labelling* — it is repeated
  exactly, not varied for elegance. A synonym tells the reader a second concept
  has appeared. Use the wording of the outline and the wiki's concept pages; if
  two sources name the same thing differently, say so once and pick one.
- **Connectives carry logic.** *because*, *therefore*, *although*, *whereas*,
  *by contrast*, *thus*, *indem*, *wenngleich*, *während* each assert a specific
  relation (cause, consequence, concession, contrast, means, time). Use the one
  the sketch's step actually asserts; if the relation is only sequence, do not
  dress it as consequence. Check every connective against the sketch on the
  step-13 pass.
- **No simplification at the cost of precision.** Do not drop the qualifiers the
  source gives — *probably*, *in the excavated area*, *for the 10th-century
  levels*, the sample size. A hedged claim in the source stays hedged in the prose.
- **Reader guidance follows the discipline's conventions.** Announcements, back
  references, and short summaries are welcome where the genre uses them;
  rhetorical questions, dramatic openers ("But what if…?") and promotional
  adjectives (*groundbreaking*, *crucial*, *fascinating*) are not.
- **No filler moves.** No paragraph opens by restating the previous one; no
  section closes with a generic "this shows the importance of …" sentence. The
  handoff says what the next section starts from.

### Style anchor (optional)

A project can anchor the prose to a voice instead of to the model's default
register — the counterweight to every manuscript sounding the same. Ask the
user for 2–3 pages of **their own published prose** (or, failing that, one
article from the target venue they consider well written). Analyse it for:
sentence length and rhythm, person (*I* / *we* / impersonal), how claims are
hedged, how sources are introduced (author-prominent or claim-prominent),
paragraph length, and the reader-guidance moves it uses. Write the result as
5–10 concrete bullets into the project's root `CLAUDE.md` under
`Manuscript style` → `Style profile`, **show them to the user, and keep only
what they confirm**. The style profile then travels into every drafter dispatch.
A profile describes the user's voice; it never licenses imitating another
author's wording.

> **Per-project house style.** Density, example-richness, and target register are tunable per project in the root `CLAUDE.md` ("Manuscript style"). Read it before drafting; it overrides the defaults here.

## MCP Optimisation (recommended)

> If `dao-paper-search-mcp` (see [`docs/recommended-mcps.md`](../../docs/recommended-mcps.md)) is available, verify citations through it instead of reconstructing them from memory. Otherwise, copy strictly from the source page's "Direct quotes" sections.

- **Book / article citations**: `dao-paper-search-mcp.search_crossref(query=<doi>)` — check that the hit's `identifiers.doi` is the DOI you asked for — returns `inline_citation.markdown` (a ready Author-Year link) and `authoritative_bibliography_line` (the full references-list line). Paste both verbatim instead of formatting Author-Year yourself.
- **Web citations**: fetch the page and classify it per [`docs/source-classes.md`](../../docs/source-classes.md). If `aggregator` or `suspect`, either find the primary source or name the aggregator status transparently in the text.

## Subagent dispatch (per section, not per chapter)

For sections over ~1200 words, dispatch the `drafter` subagent (see `agents/drafter.md`) at checklist step 11 — **one section, after its sketch has passed STOP 2**. Never fan out across sections: a chapter drafted in parallel cannot be steered, which is the failure this skill's staging exists to prevent.

The subagent receives:
- **The approved argument sketch** for this section — its contract; the prose must carry out *this* argument, not a reasonable-looking alternative
- **The timeline** of each contested concept the section treats (`wiki-to-graph.py timeline <slug>` output, pasted) — which source came first, who answered whom, what has been superseded
- List of synthesis pages (paths) to pull from
- List of source pages (paths) with allowed citation keys
- **List of the corresponding source PDF paths** (`<library>/pdf/<bibkey>.pdf` — resolve with `scripts/library.py`) — so the subagent can reach back for examples/context when a page is thin (checklist step 11). Without these, the subagent can only bullet-reflow
- The section's word budget from the outline (a floor for development, not a ceiling to pad toward)
- The project's **`Manuscript style` block** from the root `CLAUDE.md`, including the `Style profile` if one exists

Its report includes a **deviations-from-sketch** line. Carry that into STOP 3 verbatim — do not quietly absorb it. A deviation the user never sees is exactly the drift the stages are meant to surface.

## Quarto Template Hooks

The template's `output/book/` uses a Quarto book structure (see `templates/research-project-template/output/book/`):

- `_quarto.yml` defines the chapter list — update when adding a new chapter file
- `text/<nn-slug>.qmd` is the chapter-file naming convention (`01-introduction.qmd`, `02-state-of-the-field.qmd`, …)
- `outline/<nn-slug>.md` holds the chapter's argument architecture — not listed in `_quarto.yml`, never rendered
- `template/_preamble.tex` holds LaTeX preamble for PDF output
- `Makefile` targets: `make render`, `make preview`, `make clean`

For articles, use `output/article/article.qmd` with single-file layout and `output/article/outline/article.md`.

## Red Flags

| Thought | Reality |
|---------|----------|
| "I'll show the outline and get started on section 1 — saves a round-trip" | A stop you walk past is not a stop. The message that presents a stop ends there. |
| "The user approved the outline, so the sections are approved" | STOP 1 approves the *chain*. Each section's argument is its own agreement — that is where the focus is actually held. |
| "I'll draft all the sections and we can discuss at the end" | Discussion after the fact is editing, not steering. By then the drift is expensive to undo — which is why it never gets undone. |
| "Section 3 needs a point from section 5, I'll pull it forward" | That is drift. Either change the outline and say so, or respect the section's "Not here" line. |
| "The source is rich here, so I'll go deeper than the sketch said" | Source richness is not an argument. The sketch is the contract; if it is wrong, renegotiate it — don't silently exceed it. |
| "Both positions are in the wiki, so I'll present both" | One may be thirty years older, and its author may have left it since. Check the years and the `supersedes` / `revises` edges before giving them equal weight. |
| "The subagent's deviations line is minor, I won't mention it" | Then the stages bought nothing. Deviations go to the user verbatim. |
| "I'll propose a strong thesis, the user can just approve it" | Approving is not formulating. Ask first (STOP 0); sharpen what they say. A thesis the author never put into words is one they cannot defend. |
| "The user's thesis is weak, I'll quietly use my better one" | Put yours next to theirs, with the reason. A silent replacement is the same drift as in prose, one level up. |
| "Thesis: 'this chapter examines the Low Chronology'" | That is a topic, not a thesis. A thesis can be wrong; a topic cannot. Rewrite it as a claim. |
| "The source roughly says …" | Either a verbatim quote with page, or a paraphrase with a citation. No hearsay. |
| "I'll vary the term so the prose reads less repetitively" | In a scholarly text a new word is a new concept. Terms of art are repeated exactly. |
| "Each section was approved, so the chapter is coherent" | Sections pass locally; chapters break globally. Run the chapter coherence check — reverse outlines against the claim chain, introduction against conclusion. |
| "The reverse outline is just the sketch again" | It is written from the prose. If it matches the sketch line by line without you rereading the paragraphs, you copied it. |
| "I've turned every wiki bullet into a sentence — done" | That is bullet-reflow, not prose. Each substantive point needs development: grounding, an example from the source, and why it matters. |
| "The wiki page is thin, so the paragraph is thin" | The wiki points to the depth; the source holds it. Reach back to the quotes/examples or the PDF and cite — don't ship a thin paragraph. |
| "It needs more depth, I'll just add explanation I know" | Grounded elaboration comes from the source and is cited. Explanation from memory is invention. |
| "I'll cite this passage properly later" | Later citations get forgotten. Get it right now, or not at all. |
| "Wiki-lint isn't needed, I know everything is fine" | Mandatory before every draft — broken wikilinks are invisible when rendered. |
| "This page is `stable`, so it's safe to draft" | Stable is maturity, not health. An open `review_flag` on it is an unresolved content concern — resolve or override, don't ignore. |
| "The chapter is so good, I'll ignore the render errors" | A chapter that won't render is not a chapter. |

## Key Principles

- **The thesis is the author's** — asked for before anything is proposed; you sharpen, check and challenge it
- **Architecture before prose** — the thesis and claim chain are settled and approved before a single paragraph exists
- **The argument is agreed before it is written** — per section: sketch, discuss, then draft. Redirecting twenty lines is free; redirecting a thousand words is not
- **A stop is a stop** — present and wait; never present and continue in the same message
- **The outline is the memory** — status per section on disk, so a long chapter survives compaction, breaks, and revision rounds
- **The wiki is truth** — every claim traceable to a synthesis or source page
- **Elaborate from the source, not from memory** — the wiki says *what* is claimed; the source holds the examples and explanations. Reach back and cite; a thin wiki page is a pointer, not a limit
- **Develop, don't reflow** — a wiki bullet becomes a developed passage (assertion → grounding → example → significance), not one flat sentence
- **Deviations are surfaced, not absorbed** — prose that leaves the sketch says so
- **Every section comes with its reverse outline** — function and main statement per paragraph, so intent can be checked without rereading
- **Precise before fluent** — fixed terms, connectives that mean what they assert, qualifiers kept
- **Every citation verified** — bibkey existence before commit
- **Render check is part of drafting** — not "later"
- **One draft per run, one log entry** — keep changes traceable
