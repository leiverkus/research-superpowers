---
name: revising-manuscript
description: Use when working through an EXISTING manuscript text with the user — paragraph by paragraph or section by section — to revise, tighten, or rework it (the author's own draft, a chapter produced by drafting-manuscript, or a text after peer review). Keeps every decision made in the discussion in a revision ledger on disk, re-reads it before each paragraph, edits minimally, and freezes approved paragraphs, so that arguments agreed earlier are not lost or smoothed away later in a long session. Triggers on "let's go through the text paragraph by paragraph", "revise chapter 3 with me", "Absatz für Absatz durchgehen", "überarbeiten wir den Text". NOT for writing new prose from the wiki (that is drafting-manuscript).
argument-hint: "<path to the text, e.g. output/book/text/03-methods.qmd>"
inputs:
  - name: target_path
    description: The text being revised (.qmd or .md; a .docx is converted to a Markdown working copy first, see "Word files")
    required: true
  - name: scope
    description: Which part is revised in this round (whole chapter, sections 3.2–3.4, paragraphs P05–P12)
    required: false
  - name: revision_goal
    description: What this round is for, in the user's words (e.g. "tighten the argument in 3.2", "work in the reviewer's comments", "make the conclusion specific")
    required: false
outputs:
  - path: <ledger path, see "The revision ledger">
    kind: created_or_modified
  - path: <target_path>
    kind: modified
  - path: knowledge/_meta/log.md
    kind: appended
---

# Revising a Manuscript

Working through a real text with the user, one paragraph at a time, produces a
stream of small agreements: *this argument stays as it is*, *in this chapter
"Redaktion" means the Persian-period layer only*, *don't soften the claim about
Tel Rehov*, *we rejected moving the counter-position to the end, because the
reader needs it before §3*. Each of them is made in the chat, and in the chat is
where they get lost. Three mechanisms do it, and all three are normal model
behaviour rather than accidents:

1. **Attention dilution.** Twenty paragraphs in, an agreement from paragraph 3 is
   one of many thousands of tokens and no longer shapes the next edit.
2. **Compaction.** When a long session is summarised, the agreements are
   condensed or dropped; the summary keeps *that* paragraph 3 was discussed, not
   *what was decided*.
3. **Local re-optimisation.** Asked to improve paragraph 14, the model improves
   it on its own terms — and quietly re-introduces the wording, the hedge, or the
   ordering the user rejected an hour ago, or drops a thread that paragraph 14 was
   supposed to pick up.

The user experiences all three as the same thing: *earlier arguments seem to be
forgotten.* The fix is the one that already works for drafting: **the
agreements live on disk, not in the conversation**, and they are re-read — not
remembered — before every edit.

**Announce at start:** "Using revising-manuscript on `<path>`. I'll keep a
revision ledger at `<ledger path>`: every decision we make goes in there, I
re-read it before each paragraph, change only what we discussed, and don't
touch approved paragraphs again unless you reopen them."

## The revision ledger

One ledger per revised text. Path:

| Text | Ledger |
|------|--------|
| `output/book/text/03-methods.qmd` | `output/book/outline/03-methods-revision.md` |
| `output/article/article.qmd` | `output/article/outline/article-revision.md` |
| anything else (`<dir>/<name>.<ext>`) | `<dir>/<name>-revision.md` |

If an outline from `drafting-manuscript` exists for the same text, read it too:
its thesis, claim chain and approved section sketches are **binding** for the
revision unless the user changes them — and a change goes into both files.

```markdown
---
title: "Revision ledger: <text title>"
type: revision-ledger
target: output/book/text/03-methods.qmd
round: 1
revision_goal: "<the user's words>"
created: YYYY-MM-DD
updated: YYYY-MM-DD
---

## Decisions

| ID | Kind | Decision | Applies to | Reason | Date |
|----|------|----------|------------|--------|------|
| D1 | argument | The circularity objection stays in §3.2 and is answered there, not deferred | P04–P06 | Reader needs it before the Megiddo case | 2026-11-15 |
| D2 | term | "Redaktion" = the Persian-period layer only; earlier layers are "Bearbeitung" | all | Avoids two concepts under one word | 2026-11-15 |
| D3 | rejected | Do NOT hedge "the dates are circular" to "possibly circular" | P05 | The author's claim; the source supports it | 2026-11-15 |
| D4 | wording | Keep "nicht entscheidend" verbatim from Finkelstein | P07 | It is a quotation-like paraphrase | 2026-11-15 |

## Paragraphs

| ID | Anchor (first words) | Status | Decisions |
|----|----------------------|--------|-----------|
| P01 | "Die Chronologiedebatte ist …" | approved | — |
| P02 | "Ausgangspunkt der Neudatierung …" | approved | D2 |
| P03 | "Gegen diese Lesart …" | in-discussion | D1 |
| P04 | "Für Megiddo bedeutet das …" | open | D1 |

## Open threads

- T1 — The term "Fremdgötter" is used before it is introduced; settle when we reach P09 (raised at P03)
- T2 — P11 must pick up the Tel Rehov point from P05 (D3)
```

**Kinds of decision** (use these words so the ledger stays scannable):
`argument` (a point that stays, moves, or goes), `term` (a fixed meaning or
fixed wording of a term of art), `wording` (a formulation that is kept
verbatim), `rejected` (a proposal that was turned down — with the reason, so it
is not proposed again), `scope` (what this text does *not* do), `structure`
(order, cuts, merges), `style` (a register or voice decision).

**Write decisions in the user's words** where they gave them. A decision
recorded as your paraphrase is already a step of drift.

**Paragraph IDs are stable.** Assign P01, P02 … once, at the start, by order.
Numbers in the chat ("the fourth paragraph") shift when paragraphs are split or
merged; IDs do not. A split paragraph becomes P07a / P07b, a merge keeps the
first ID and marks the other `merged into P07`. The anchor (first words) is
how you find the paragraph again in the file.

**Status:** `open` (not yet worked on) · `in-discussion` · `approved` (agreed,
written to the file, frozen) · `reopened` (the user unfroze it, with the reason
as a decision).

## Checklist

### Setup

1. **Read the whole text** once before discussing any paragraph. Revising
   paragraph 3 well requires knowing what paragraph 12 needs from it.
2. **Read the outline** if one exists (see above) and the project's root
   `CLAUDE.md` → `Manuscript style`.
3. **Resume check** — if a ledger exists, read it fully and continue at the
   first paragraph that is not `approved`. Do not reconstruct the agreements
   from a chat summary or from memory: the ledger is the record. If the text on
   disk differs from the ledger (paragraphs the ledger marks approved have
   changed), say so before going on.
4. **Create the ledger** (if new): the `revision_goal` in the user's words, the
   paragraph register with IDs and anchors, and any decisions the user states
   up front ("the thesis stays", "don't touch the introduction").

### Paragraph loop (repeat)

5. **Re-read the ledger** — the file, this turn, not your memory of it. Every
   paragraph, every time. It is short; the cost is trivial next to a lost
   agreement.
6. **Read the paragraph in context** — the paragraph, the two approved
   paragraphs before it, and the one after it. List the decisions whose
   `Applies to` covers it, and the open threads that land here.
7. **Discuss** — what is the paragraph's job in the argument, and what should
   change? Follow the user's lead. When you see a problem, name it; when the
   user disagrees, that is a decision (`rejected`, with their reason).
8. **Propose a minimal edit** — change what was discussed and nothing else (see
   [Minimal edits](#minimal-edits)). Present it as **before / after** for the
   changed sentences only, then the **ledger check**:

   ```
   Ledger check P05: D1 kept (objection answered here) · D3 kept (no hedge
   added) · D4 kept (verbatim) · T2 noted for P11.
   ```

   Name every decision that applies, kept or not. A decision you are proposing
   to break is stated as such — "this would undo D3; reopen it?" — never
   slipped in.
9. **STOP** — present and wait. The message that presents the edit ends there.
10. **Record before moving on** — on approval: write the paragraph to the file,
    set it `approved`, and add every decision made in this discussion to the
    ledger **in the same turn**. Tell the user in one line what went in
    ("Ledger: + D7 term 'Bearbeitung', + T3 for P14") so a misrecorded decision
    is caught now. Then go to step 5 for the next paragraph — one paragraph per
    turn, unless the user asks for a batch.

### Checkpoints

11. **Look-back every ~5 approved paragraphs**, at every resume, and after a
    context compaction: re-read the ledger, then the approved paragraphs, and
    check each `Decisions` entry against the text as it now stands. Report in a
    short list — "D2: P09 uses 'Redaktion' for the Assyrian layer — conflict" —
    and fix only what the user approves. This is the step that catches what the
    paragraph-level check could not: a later paragraph that contradicts an
    earlier one without touching any single decision.
12. **Open threads** — when a thread's paragraph comes up, resolve it there; a
    thread still open at the end is listed in the closing report, not dropped.

### Closing

13. **Whole-text pass** — read the revised text against the ledger and, if one
    exists, against the outline's claim chain. Every decision honoured? Every
    thread closed or listed? Terms used in one sense throughout? Report; fix
    only what the user approves.
14. **Citations and render** — every `[@bibkey]` resolves in
    `output/bibtex/references.bib`; for a `.qmd`, render it.
15. **Log** — entry in `knowledge/_meta/log.md`: date, text, round, paragraphs
    revised, decisions recorded. Increment `round` in the ledger if another
    round follows; decisions carry over between rounds.

## Minimal edits

- **Change what was discussed.** Sentences nobody talked about stay as they
  are, word for word. A "while I was at it" improvement is how a rejected
  wording comes back.
- **No silent style pass.** If you think the untouched sentences need work, say
  so as a separate proposal.
- **Keep the author's voice.** The text is theirs. Prefer their constructions
  over your smoother ones; a style decision in the ledger beats your defaults.
- **Do not re-hedge or de-hedge.** Hedges and scope qualifiers are content. The
  author's strong claim stays strong unless the source does not carry it — then
  say that, citing the page; don't weaken it quietly.
- **New content follows the drafting rules.** A sentence that adds a factual
  claim needs a source (source page, or the PDF at `<library>/pdf/<bibkey>.pdf`
  at the cited page) and a citation — the same rule as `drafting-manuscript`.
  Nothing from memory.
- **Precision rules apply** — terms of art repeated exactly, connectives that
  assert the relation the argument makes, no filler openers or closers (see
  `drafting-manuscript` → Precision rules).

## Frozen paragraphs

An approved paragraph is not edited again in passing. When work on a later
paragraph requires a change to an earlier one — a term is redefined, an
argument moves — **name the affected paragraphs and ask to reopen them**:

> "D2 changes 'Redaktion' to the Persian-period layer only. P02 and P06 use it
> for the Assyrian layer — reopen both?"

On yes: status `reopened`, the reason goes into the ledger as a decision, edit,
re-approve. On no: the new decision is narrowed, or the conflict is recorded as
an open thread. Never adjust an approved paragraph as a side effect.

## Word files

The ledger and the minimal-edit discipline need a text you can diff. For a
`.docx`, convert once to a Markdown working copy next to it
(`pandoc -t markdown <file>.docx -o <file>.md`), revise that, and tell the user
the changes will need to be carried back into Word (or converted back with
`pandoc`) — formatting, comments and tracked changes do not survive the round
trip. For tracked changes in the Word file itself, use the host's Word tooling;
the ledger and the loop stay the same.

## Red Flags

| Thought | Reality |
|---------|---------|
| "I remember what we agreed on paragraph 3" | Memory is exactly what fails here. Re-read the ledger, every paragraph. |
| "The summary after compaction says we discussed P03" | Discussed is not decided. The ledger has the decision; the summary does not. |
| "I'll tidy the sentences around the change too" | That is how rejected wordings return. Change what was discussed. |
| "This is better phrasing than what the author had" | The text is theirs. Propose it separately, or leave it. |
| "The user rejected this earlier, but it really is better" | It is in the ledger as `rejected`, with a reason. Don't propose it again unless something new speaks for it — and then say what. |
| "P14 needs P04 adjusted; I'll fix P04 quickly" | P04 is approved. Ask to reopen it. |
| "I'll record the decisions at the end" | By the end they are half-remembered. Record in the same turn. |
| "The ledger check is a formality — nothing applies here" | Then write "no decisions apply" — after checking `Applies to` and the open threads. |
| "I'll soften this claim to be safe" | A hedge the author didn't write changes the argument. Raise it; don't apply it. |
| "Let's just do the next three paragraphs at once" | Fine if the user asks — then one ledger check per paragraph, and still one STOP. |

## Key Principles

- **The ledger is the memory** — decisions on disk, re-read every time, never reconstructed from the chat
- **Decisions in the user's words** — including what was rejected, and why
- **Minimal edits** — change what was discussed, nothing else
- **Approved means frozen** — reopening is explicit and recorded
- **Every edit shows its ledger check** — which decisions apply, kept or deliberately reopened
- **Look back regularly** — local checks miss global contradictions
- **New facts need sources** — revising is no licence to add from memory
