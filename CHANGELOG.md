# Changelog

All notable changes to `research-superpowers` are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **`bib-search.py` now also searches curated BibTeX `keywords`.** Full-text search and a
  prototyped vector/embedding index were both measured against a genuinely unnamed case — a
  paper describing a method in prose without ever naming it — and neither could reach it
  (`docs/measurements/2026-07-17-semantic-search/README.md`). A curated `keywords` field on
  the master bibliography (written by `ingest-source` during reading, unioned in on re-ingest
  under a new focus) is a third mechanism: it records human/LLM understanding directly instead
  of deriving it from the text.

  Always-on, no new flag — a keyword hit is microseconds and, being curated, can only add
  results, never rank an exact lookup worse. `merge-bibs.py` now unions keyword sets across
  projects for the same source instead of silently dropping the field.

## [0.32.1] — 2026-07-17

The release helper filed new versions above [Unreleased] and left the notes behind.

### Fixed

- **`release.py bump` put the new version in the wrong place — and stranded the release
  notes.** It inserted the section before the first `## [` heading. In a Keep-a-Changelog
  file that heading is `## [Unreleased]`, so the new version landed *above* it.

  The ordering was the visible half. The damaging half was quieter: notes written under
  `[Unreleased]` during development **stayed there**, while the new section got the
  `_Describe the release here._` skeleton. Since `release.py notes` publishes exactly that
  section, the release would have shipped the placeholder as its body with the real notes
  orphaned one heading up — and nothing would have failed. Both 0.31.0 and 0.32.0 had to be
  hand-written around this.

  `bump` now promotes the `[Unreleased]` notes into the new version section and leaves
  `[Unreleased]` empty above it — what the format means by cutting a release. It still writes
  a skeleton when there is nothing to promote, and it is still idempotent.

## [0.32.0] — 2026-07-17

A release that never happened now fails the build.

### Fixed

- **Six releases were documented but never released — and CI was green throughout.**

  0.27.0, 0.28.0, 0.28.1, 0.29.0, 0.29.1 and 0.30.0 were bumped, changelogged and merged.
  None was tagged. Releases here are cut by pushing a tag, so all six sat unreleased while
  GitHub served **0.26.1** as latest and every check passed.

  `release.py check` could not have caught it. It only ever runs with a tag in hand —
  `release.yml` on tag push, `lint.yml` feeding it the manifest's own version — so forgetting
  to tag means it never runs. The failure was a *missing invocation*, not a wrong answer, and
  no check can fail if no check executes.

  `release.py audit` (new) asks from the other side: every version the CHANGELOG documents must
  have a tag. It runs in `lint.yml` on every push and PR, where nothing was watching.

  - It **exempts the newest section** — a release PR bumps the manifests and writes the notes
    before the tag exists, so requiring one there would redden every release PR. A gap
    therefore surfaces one release later; these six would have been caught at 0.28.0 rather
    than accumulating.
  - It **stops below 0.4.0.** The first tag is `v0.3.0`, so 0.1.0 and 0.2.0 were never
    taggable — and 0.3.1 is a section for a release that never happened: no commit ever carried
    0.3.1 in its manifests, so there is nothing to tag and nothing to fix.
  - With **no tags visible** (a shallow checkout) it fails rather than passes — every version
    would look untagged, and a silent pass there is the same class of bug. Hence
    `fetch-depth: 0` on the lint job.

  The six tags have since been pushed and their releases built. Worth recording for the next
  person: **push tags one at a time.** GitHub creates no push event *at all* when more than
  three tags arrive in a single push, so the workflow never fires and the tags land silently.
## [0.31.0] — 2026-07-17

Drafting stops guessing what the chapter argues.

### Changed

- **`drafting-manuscript` now settles the argument before it writes prose.**

  The skill produced long, well-cited chapters in a single pass — and that was the problem.
  A chapter drafted in one go wanders into whatever the sources happen to be rich about, and
  the drift only becomes visible once thousands of words exist and are too expensive to throw
  away. So they don't get thrown away.

  The skill *said* "confirm with user before prose". Three things made sure that never
  happened:

  - The thing being confirmed was a **heading list** ("introduction, main parts, conclusion").
    Approving it approved nothing about the argument — a table of contents cannot be wrong.
  - The **DOT graph had no user node** between skeleton approval and the render check.
    `"Draft prose section by section"` looped only to `"Page too thin?"`. "Section by section"
    was a model-internal loop, not a dialogue — and the graph is what gets read as the control
    flow.
  - **Subagent dispatch fanned out** across all sections at once, then composed the chapter
    from the results. Maximally unsteerable.

  Drafting now runs in three stages:

  - **Stage A — architecture.** A thesis (one sentence, and it must be falsifiable — a topic
    is not a thesis), a claim chain, and per section: its claim, evidence, function in the
    chain, a `Not here:` scope line, and a word budget. Written to
    `output/<book|article>/outline/<basename>.md`, derived mechanically from the target
    (`book/text/03-methods.qmd` → `book/outline/03-methods.md`). Outside Quarto's render tree.
  - **Stage B — section loop.** Per section: sketch the argument (steps with their evidence,
    the concrete material, the counter-position and how it is handled, the handoff) → **STOP**
    → prose for that section only → **STOP** → append, mark approved, next. Redirecting twenty
    lines is free; redirecting a thousand words is not.
  - **Stage C** — the existing citation check, render, log.

  Supporting changes:

  - The outline carries a per-section `Status` (`outlined → sketched → drafted → approved`)
    and each approved sketch. A long chapter now survives context compaction and a two-week
    break — the agreements are on disk, not in the chat history. It is also what you revise
    against after peer review.
  - The `drafter` subagent takes **the approved sketch as its contract** and reports a
    **deviations-from-sketch** line, which the parent surfaces verbatim. An unreported
    deviation is exactly the drift the stages exist to catch. Dispatch is now sequential —
    one section, after its sketch is approved — never a fan-out.
  - All three stops are `<SOFT-GATE>`-style: a straight run stays available, but it gets named
    and logged to `gate-overrides.log`. Repeated overrides on the section stop are a signal
    that the loop isn't earning its cost.

- **The example project and the tutorial now demonstrate Stage A** —
  `examples/example-project/output/article/outline/main.md` is a real outline: thesis, claim
  chain, six sections with their evidence, scope lines and budgets.

  Every section sits at `Status: outlined` and none is drafted, because that project's
  `chronology-debate.md` is `status: review` with an open `weak-support` flag — the drafting
  SOFT-GATE, unmet and *not* overridden (`lint-wiki` confirms: "no SOFT-GATE overrides
  recorded"). The example now shows the gate working rather than a chapter that skipped it.

  It also shows what Stage A buys: the outline records that **S4, the article's load-bearing
  section, has no citable source at all** — Cohen 1979 was never ingested. That is a finding
  worth ~50 lines of architecture, not 1200 words of prose about an uncitable work.

### Fixed

- **The tutorial taught citation keys that the project's own schema rejects.** Every bibkey in
  `docs/tutorial.md` — `cohen-1979`, `finkelstein-1999`, `finkelstein-2003`, `mazar-2011` —
  was the bare `autor-jahr` shape that `ingest-source` explicitly forbids ("Never the
  `autor-jahr` prefix alone") and that `lint-wiki` hard-fails on. Checked mechanically against
  `schema/knowledge-frontmatter.schema.json`: all four failed the `bibkey` pattern. They are
  now `surname-year-shorttitle`, and the two the example ships (`finkelstein-2003-wrong`,
  `mazar-2011-iron`) match it exactly.

  The render-failure anecdote taught the same deprecated convention: a "citation key collision"
  between `mazar-2011` and `mazar-2011b`. Under the real shape those are distinct keys that
  cannot collide. It now narrates the failure the shape actually prevents — two different Mazar
  2011 papers under one key, which fails *silently* (render exits 0, one work carries the
  other's pages) — and shows the disambiguator in the year slot: `mazar-2011b-iron-age`.

- **The tutorial invited a comparison it made impossible.** It claimed the walkthrough "matches
  `examples/example-project/`" while using different slugs (`negev-fortresses-chronology-*` vs
  `low-chronology-*`), a different synthesis filename, and citation keys absent from the
  example. Identifiers are aligned; the header and the closing section now state plainly how
  far the checked-in copy runs and which artefacts exist only in the text.

- The tutorial's Phase-7 SOFT-GATE listed four conditions; the skill has five. The missing one
  (no open `review_flags`) is the condition the example project actually stops on.

- `examples/example-project/README.md` was wrong about its own tree: it claimed the log shows
  `draft` entries (there were none), called the synthesis `status: draft` (it is `review`), and
  described one ingested source (there are three). The log's `updated:` was two ingests stale.

- `scaffold-research-project` described the output tree as `output/publication/article/…` and
  `output/publication/book/…`. The template has had no `publication/` level for some time.

- **The citekey rationale under-counted its own evidence.** The audit that motivated the
  `surname-year-shorttitle` migration found **three** keys each denoting two different papers
  (`hensel-2024`, `tebes-2023`, `maeir-2021` — as the 0.23.0 entry records). Seven places said
  two, including `migrate-citekeys.py`'s own "WHY THIS EXISTS" docstring, which named only the
  first two. `ingest-source` was the one place that had it right.

## [0.30.0] — 2026-07-14

### Added

- **A duplicate key in the shared library is now caught — at both ends.**

  Check 2 has always caught a key defined twice in a *project* `.bib`. Nothing checked the
  **library**, and a duplicate there is strictly worse: `bib-subset.py` copies the winning
  entry into every project that cites the key, so one bad merge poisons all of them at once.

  BibTeX takes the **last** definition and drops the rest. Silently. Fields and all.

  Found on the live library: `rabunal-2023-unraveling` existed twice. The older entry had
  **four** authors; the newer had three — and the newer won. Javier Fernández-López de Pablo
  would have vanished from every manuscript citing that work, and nothing in the pipeline
  would have said a word. Two R-package manuals each carried a **DOI in the losing copy only**.

  - `lint-wiki.py` **check 11** reports it (hard; skipped where no library is configured, so
    CI stays green).
  - `bib-subset.py` **refuses to run**. That is the exact point of propagation, and merging
    two records is a judgement about which fields are right — not something a script should
    decide silently.

### Why it was found

Not by a check. By acquiring two PDFs: the entries only came under scrutiny because a human
went looking for the works they describe. That is the argument for the check.

## [0.29.1] — 2026-07-14

### Fixed

- **Check 10 fired on a page number that belonged to a *different* source.** Found within
  the hour, on the corpus, by the ingest it was meant to protect:

  > …converges exactly on the finding independently reached by
  > `[[source-bilotti-2024-point]]` **(pp. 10–11)**.

  Those are *Bilotti's* pages. The ingested source (Riris) is printed on 626–638, so the
  check called a correct citation a fabrication.

  Excluding `## Connections` was not enough: **cross-source comparisons live in the body**,
  which is exactly where a review wiki does its most interesting work. A page anchor that
  follows a reference to another source — a `[[source-…]]` wikilink or an `@citekey` —
  now belongs to that source and is skipped.

  An **entity** link does not suppress an anchor: "uses `[[entity-spatstat]]` (p. 6)" is
  page 6 *of this source*, because an entity has no pages of its own. Suppressing those
  would have gutted the check on precisely the pages that use it most.

  Re-verified across the corpus: the false positive is gone and **all 24 real violations
  in 9 projects still fire.**

## [0.29.0] — 2026-07-14

The release that catches a fabricated citation.

### Added

- **`lint-wiki.py` check 10 (HARD): a page anchor outside the work's printed page range.**

  `acquire-sources` downloads Open-Access PDFs — and a green-OA deposit is very often the
  author's **accepted manuscript**, not the typeset article. No printed page numbers exist
  in it. The ingester has nothing to anchor to, so it anchors to the *physical* PDF page and
  writes `(p. 3)`.

  That citation is **checkable and wrong**, which is strictly worse than no citation: it
  survives review because it looks like evidence, and `drafting-manuscript` reaches back
  into the wrong page.

  ```
  PAGE-OUT-OF-RANGE: knowledge/sources/crema2010pointprocess.md → cites p. 1, 2, 9, 10, 12,
    but 'crema-2010-probabilistic' is printed on 1118–1130.
  ```

  Across 5 live projects it found **15** such pages. One had documented its own defect in
  prose — *"page anchors are to the manuscript PDF (pp. 1–30)"* — while the article is
  printed on 33–60. A prose disclaimer does not stop a drafter from citing `(p. 11)`.

  - **HARD, not advisory.** A page outside the printed range is not a worklist item or a
    machine-specific gap. It is a false statement about a source.
  - **`## Connections` is excluded.** "Cited by `[[gillings-2009-affordance]]` (p. 344)" is
    *Gillings'* page 344, not the ingested source's — and firing on that would have made the
    check unusable. It was a real false positive on the live corpus before this fix.
  - **Continued articles keep both spans.** `pages = {26--40, 66--67}` is real (our own
    `burnett-2016-ammon`). Collapsing it to 26–67 would hide an error; taking only 26–40
    would invent one.
  - Skipped where the `.bib` prints no page range at all (PLOS, Entangled Religions …) —
    guessing one would fire on every page.

- **`scripts/check-pdf-version.py`** — screens the library for accepted manuscripts before
  they are ever ingested. Signals: a cover sheet that says so; text naming figures while the
  PDF embeds **zero** images; a Word producer where publishers use typesetters; physical
  pages ≥ 1.5 × the printed range. Across 582 library PDFs: **11 manuscripts**.

  Deliberately conservative. Line-numbering was demoted to corroborating evidence after it
  flagged a genuine typeset article whose "line numbers" were a numbered reference list — a
  false positive here sends the user hunting for a version of record they already have.

### Why both

The screen prevents the error; the lint check catches it when the screen was never run — as
on every wiki written before today.

## [0.28.1] — 2026-07-14

### Fixed

- **`.gitignore` ignored `__pycache__/` only under `output/`.** The rules were
  path-specific (`output/data-analysis/__pycache__/`, `output/code/__pycache__/`), but
  the scripts in `scripts/` import each other by path — `bib-subset.py` loads
  `library.py` and `lint-wiki.py` — so running any of them writes
  `scripts/__pycache__/`. That directory showed up as untracked noise in **all 17 live
  projects**, and in one of them a compiled `lint-wiki.cpython-314.pyc` had already been
  committed.

  Now generic: `__pycache__/`, `*.py[cod]`, `.ipynb_checkpoints/` — anywhere in the tree.

## [0.28.0] — 2026-07-14

### Added

- **`lint-wiki.py` check 9 — "acquired but NOT ingested".** Check 8 asks *does every
  source page have a PDF?* Nothing asked the reverse, so a source could be searched
  for, downloaded, and then simply forgotten: the wiki looks healthy, every check
  passes, and `drafting-manuscript` has nothing to reach back into.

  Run against the 17 live wikis, it found **146 such sources** — Aoristos had 48 of
  its 55 PDFs never ingested, Choros 15 of 15, Punctum 27 of 42. Five projects were
  clean.

  ```
    Acquired but NOT ingested (4 of 53): hensel-2022-about, lemaire-2015-levantine, …
      → run ingest-source on these; the PDFs are already in the library.
  ```

  - **Not the same as check 7.** Check 7 reports entries nobody *cites* and no page
    describes; an entry the manuscript already cites but nobody ever read into the
    wiki slips straight past it. A test pins exactly that case.
  - **An entry with no PDF is deliberately NOT reported here** — "not acquired" is
    `acquire-sources`' business. Reporting it would make every un-downloaded entry
    look like a forgotten ingest.
  - Advisory, and skipped when no library is configured — same reasoning as check 8:
    CI has no library, and a worklist is not a broken repo.

### Changed

- `wiki-lint` now documents the citekey and library checks, which it had never listed.

## [0.27.0] — 2026-07-14

Full-text search across the shared library — the last piece the library was missing.

### Added

- **`scripts/bib-search.py`** — SQLite FTS5 over every PDF in the library, **one row
  per page**. A document-level hit ("this paper mentions copper smelting") still
  leaves you hunting through 40 pages; a page-level hit composes with the rest of the
  workflow:

  ```bash
  python scripts/bib-search.py index               # incremental
  python scripts/bib-search.py "copper smelting arabah"
    → benyosef-2019-ancient · p. 2 · … «copper» producing regions in the Wadi «Arabah» …
  ```

  Measured on the real library: 505 documents / 20 422 pages indexed in **11 seconds**,
  116 MB index; the next run, nothing changed, 0 s. Indexing is cheap enough to run
  after every acquisition.

  - The page reported is the **physical** PDF page — right for *opening* the file,
    wrong for *citing*. The printed page number must be read off the page itself.
  - The index is a **local cache** (`~/.cache/research-superpowers/`), never in the
    synced folder: SQLite and file-sync corrupt each other, the same failure class as
    a git repo inside Nextcloud. It is derived — if it is lost, rebuild it.
  - **PDFs with no text layer are reported, not swallowed.** Indexing a scan silently
    as "empty" would make the library look complete when it is not. The real library
    has 4 such files.
  - Punctuation a researcher types without thinking (`ben-yosef`, `14C-dating`, an
    unbalanced quote) is not read as FTS5 operators.

- **`drafting-manuscript`: the reach-back ladder gained a rung.** Step 2 assumed the
  wiki page carries a page anchor. When it does not, the only options were reading the
  PDF end to end or bullet-reflowing. Now: `bib-search.py "…" --key <bibkey>` finds the
  page.

### Changed

- `scaffold-research-project` ships `scripts/bib-search.py` into new projects;
  `using-research-powers` now names the library scripts (`library.py`, `bib-subset.py`,
  `bib-search.py`) instead of listing only the lint and graph tools.

## [0.26.1] — 2026-07-14

Two corrections found by migrating the 17 live projects onto the library.

### Changed

- **`bib-subset.py` now KEEPS what the project already carried**; `--prune` opts into
  the strict cited-only subset. The cited-only default would have dropped 47 of
  Aoristos' 62 entries, 36 of Contexta's 51 — acquired-but-not-yet-ingested sources
  that `literaturguide.md` still lists.

  The stronger reason is metadata. Every entry is re-drawn from the master bib, so
  the library's *verified* values propagate into every project. Dropping an entry and
  letting a later `ingest-source` re-derive it from the PDF would throw that
  verification away — and building the library alone fixed four real errors (a DOI
  that does not resolve at all, a wrong title, two wrong page ranges).

### Fixed

- **`KEY-DIVERGENCE` fired on a truncated title.** The same work gets transcribed at
  different lengths: an archived bib carries *"Yahwistic Diversity and the Hebrew
  Bible"* where the current one carries the full *"…: State of the Field, Desiderata
  and Research Perspectives…"*. A prefix relation now counts as the same work — the
  same rule `wiki-global-graph.py bibkeys` already used. A linter that cries wolf
  gets switched off.

## [0.26.0] — 2026-07-14

Source PDFs move out of each project and into **one shared library**. Zotero is out
of the pipeline (see 0.25.0 for why); the library is a plain folder — no daemon, no
API key, no console, CI-friendly and offline.

    <library>/references.bib      the master bibliography
    <library>/pdf/<bibkey>.pdf    one PDF per source; the filename IS the citekey

Merging the 17 projects surfaced what duplication had been hiding: **four real
metadata errors**, each recorded correctly in one project and wrongly in another —
a DOI that does not resolve at all, a wrong title, and two wrong page ranges. You
cannot fix a thing seventeen times. One record, fixed once.

### Added

- **`scripts/library.py`** (ships into every project) — resolves the library path:
  `RESEARCH_LIBRARY` → `.research-library` in the project root → `~/.config/…`.
  **Not a symlink**: symlinks need administrator rights on Windows, and
  `input/bibliography/` is mixed-ownership — its PDFs are shared, but
  `literaturguide.md`, `acquisition-todo.md` and the audit logs are per-project and
  tracked. So the PDFs move out and the folder keeps its text artefacts.

  `LibraryNotConfigured` carries an actionable message on purpose. The failure a user
  actually hits is `ingest-source` hard-stopping, and "PDF not found" would send them
  hunting for a file when the real problem is that this machine has never been told
  where the library is.

- **`scripts/bib-subset.py`** — writes `output/bibtex/references.bib` as the subset of
  the library this project actually cites. The repo stays self-contained and zippable,
  and CI renders without the library. A cited key the library does not know is a HARD
  error: dropping it silently would leave the manuscript citing a key that is in no
  `.bib`, and Quarto renders that as `???` while exiting 0. Entries dropped because
  nothing cites them any more are reported, not vanished.

- **`scripts/build-library.py`**, **`scripts/merge-bibs.py`** — the one-time migration.
  733 PDFs collapse to 691 keys, and the duplicates are not all the same file: same
  page count → keep the larger scan; **different page count → different files**, most
  pages wins and every case is reported. That class is real: one project's
  `james-2019-guidelines` is a 4-page extract of a 15-page paper, and its
  `zissu-2023-underground` is a 0-page corrupt file. Nothing is deleted — the losers
  go to a backup.

### Changed

- `input/bibliography/` holds **no PDFs**. It keeps its tracked text artefacts.
- `acquire-sources` downloads into the library and reconciles against it — and the
  library is *shared*, so a source another project already fetched counts as present.
- `ingest-source`'s HARD-STOP now distinguishes *"the library is not configured on
  this machine"* from *"the source was never acquired"*. They need different answers.
- `drafting-manuscript` / `drafter` reach back into `<library>/pdf/<bibkey>.pdf`.
- `lint-wiki.py`'s bibkey↔PDF check reads the library. It stays **advisory** and
  resolves with `required=False`: the library is machine-local and absent in CI, so a
  hard gate would fail every build and every new contributor.
- `rename-source-pdfs.py` gained `--pdf-dir`, so it can identify the library's
  unnamed files too.

### Fixed

- `agents/source-acquirer.md` prescribed `<Lastname - Title - Year>.pdf` — contradicting
  the skill's own `autor-jahr-kurztitel` rule. Two naming rules in one contract pair.
- Check 8 of `lint_citekeys` had **no test for its non-empty branch**; a regression
  there was invisible. It has one now.

## [0.25.0] — 2026-07-14

Zotero can be the upstream for bibliographic metadata, PDFs and annotations — but
**not for the citekey**. A pilot on a 36-source project settled that, and this
release ships the tool the pilot produced.

### Added

- **`scripts/zotero-to-bib.py`** — generates `references.bib` from a Zotero
  collection, taking the key from the item's `Extra` field (where
  `zotero_add_by_bibtex` preserves it on import) and **never** from Zotero's
  native `citationKey` (which holds whatever Better BibTeX invented). Output is
  sorted by key, so a re-run is byte-identical and `git diff` shows only real
  changes. `--check` makes it a CI gate.

  Round-trip on the pilot: 36/36 keys identical, **zero** field-value differences
  across title/doi/year/pages/volume/issue/type/author, `lint-wiki.py` green, the
  knowledge graph byte-identical.

### Why not Better BibTeX

BBX auto-export is the obvious design. It does not work.

Configured with `auth.lower + '-' + year + '-' + shorttitle(1,1).lower` — the
closest its formula language comes to our convention — BBX still diverged on **8
of 36** entries:

    ours                                BBX
    ardissone-2013-information          ardissone-2013-3d
    dereu-2013-towards                  dereu-2013-threedimensional
    marinbuzon-2021-photogrammetry-sfm  marin-buzon-2021-photogrammetry
    massonmaclean-2021-digitally        masson-maclean-2021-digitally

Three independent causes, all inside BBX's `shorttitle`/`auth` implementations and
none reachable by configuration: it keeps two-character title words (`3D`) where we
drop them; it keeps hyphens in surnames where we fold them; its stopword list
differs. And `marin-buzon-2021-photogrammetry` is what it produces for **both**
Marín-Buzón 2021 papers — it re-creates exactly the collision the citekey migration
removed. `bibkey` is a cross-project JOIN KEY.

Pinning does not save it: an item pinned **both** ways — `Citation Key:` in Extra
*and* Zotero's native `citationKey` field — was still exported under BBX's own
generated key. BBX owns key generation. Its auto-export also never fires on
sync-originated changes, which is how every write from an API client arrives.

So: **we own the key, Zotero owns everything else.** Same rule the whole citekey
migration rests on — enforce an invariant with a tool; do not hope a third party
honours a convention.

## [0.24.0] — 2026-07-14

Restores the second half of the convention. The template has always mandated
`autor-jahr-kurztitel.pdf` for source PDFs — `ingest-source` HARD-STOPS without it,
and `drafting-manuscript` needs it to reach back into the PDF at the cited pages.
An audit found **2 of 733 PDFs** conform. After the citekey migration the two
conventions are the same string, so `bibkey == PDF filename stem` is now a rename,
not a redesign.

### Added

- **`scripts/rename-source-pdfs.py`** — restores `bibkey == PDF filename stem`. A
  PDF renamed onto the WRONG bibkey is worse than one left alone (`ingest-source`
  would silently read the wrong source), and `input/bibliography/*.pdf` is
  gitignored, so there is **no git undo**. The tool therefore never guesses: it
  resolves each PDF through ranked signals — the bib's own `file =` field, a
  pre-migration bibkey as the stem, a DOI found inside the PDF, surname+year in the
  filename, title overlap — and puts anything it cannot settle on a worklist
  instead of renaming on a hunch. The written map is the undo. Nested PDFs from the
  older `<slug>/<slug>.pdf` layout are flattened.

  On the first repo the DOI signal alone resolved 30 of 36 PDFs. Across 17 wikis it
  lifted conformance from **2 of 733 to 548 of 733**; what it could not settle is a
  worklist, not a guess.

### Fixed

- **Surnames with undecomposable letters were mangled into unguessable keys.** NFKD
  only splits base+diacritic, so a letter that IS a letter — Turkish dotless `ı`,
  Polish stroked `ł` — survived it untouched and was then dropped by the `[^a-z]`
  filter. Real keys produced: `Sırmaçek` → `srmacek`, `Trybała` → `trybaa`. Both
  tools now fold names through an explicit table first — and they must stay in
  step, or the PDF and the bibkey they exist to unify can never meet.

## [0.23.3] — 2026-07-14

Supersedes 0.23.2, whose release job failed on the script-mirror check (the
example copy of `wiki-global-graph.py` had not been re-synced) and therefore never
published. The mirror check did its job: without it a scaffolded project would
have shipped a `bibkeys` that still reported the Berlejung collision.

### Fixed

- Re-synced the `wiki-global-graph.py` mirror between template and example.

- **`wiki-global-graph.py bibkeys` reported collisions that did not exist.** Two
  bugs in the work fingerprint, both found by running it across 17 real wikis:
  - **LaTeX transcription.** The same paper appears as `{\c{C}}atalh{\"o}y{\"u}k`,
    `{Çatalhöyük}` and `Çatalhöyük` in three different bibs, and as `{I}ron {A}ge`
    vs `{Iron} {Age}`. Tokenising on `[a-z0-9]+` without de-LaTeX-ing and folding to
    ASCII shattered these into different words — one work, three fingerprints, a
    collision that isn't. Titles are now de-LaTeX'd and ASCII-folded first.
  - **A shared DOI now settles identity.** A DOI identifies a work uniquely, so two
    records agreeing on one are the same work even when their titles disagree — and
    they do: the same Berlejung 2025 book is titled "YHWH's Diversity: A Lot of
    Names and No Iconography?" in one project and "YHWH's Diversity and the One God"
    in another. Conversely a DOI on only ONE side proves nothing, and a differing
    DOI does not prove difference (the same book is routinely recorded once under
    its monograph DOI and once under a chapter DOI), so the title fingerprint still
    decides those.

  With both fixed, the 17-wiki portfolio reports **0 collisions and 0 splits** —
  down from 3 and 53 before the citekey migration.

## [0.23.1] — 2026-07-14

### Fixed

- **`migrate-citekeys.py` silently skipped every citation that ended a sentence.**
  The right boundary was built from pandoc's citekey *continuation* set, which
  includes `.` — so `@dereu2013dh.` was read as the key `dereu2013dh.` and left
  alone, while the `.bib` entry WAS renamed. The key then resolved nowhere and
  Quarto rendered `???` while exiting 0 — a partial migration, which is worse than
  none. Pandoc allows `.` *inside* a key; a trailing period ends the sentence.
  The boundary now rejects only what could extend the match into a *different* key
  (alphanumerics, `_`, `-`), so `@smith2016` still cannot eat `@smith2016b`.
  Caught on the first real repo: 7 citations left behind, every one of them
  sentence-final.

## [0.23.0] — 2026-07-14

The `bibkey` is not just a citation key — it is the **cross-project join key**
(`wiki-global-graph.py` matches sources across projects on it). An audit of 17
live wikis found the documented `autor-jahr` convention honoured by only **40% of
511 keys**. Nothing had ever checked it. The cost:

- **17 cross-project joins silently missed** — the same work under different keys
  (`Smith2016` vs `smith2016`, a join lost to capitalisation).
- **3 keys each denoting two different papers** — so the graph asserted a shared
  source where none existed (`hensel-2024`, `tebes-2023`, `maeir-2021`).

This release makes the convention machine-enforced instead of merely documented,
and ships the tool to migrate existing wikis onto it.

### Added

- **`scripts/migrate-citekeys.py`** — one-time re-key to `surname-year-shorttitle`,
  a deterministic function of the work's own metadata, so the same work yields the
  same key in every project. Two phases (`plan` → human reviews the map → `apply`),
  dry-run by default. Safety asserts: bijection, no chaining, single-pass
  substitution with a right boundary (so `@smith2016` cannot eat `@smith2016b` — a
  *different* work), and a proof that `[[wikilinks]]` and Quarto cross-references
  are untouched. Refuses to write untracked/gitignored files without
  `--backup-dir`, never runs git, and is idempotent.
- **`lint_citekeys()` in `lint-wiki.py`** — hard-fails on: off-shape entry keys,
  a key defined twice in one `.bib` (pandoc silently takes the last), a
  frontmatter `bibkey` that is in no `.bib`, a `[@key]` that resolves nowhere (in
  the **wiki** as well as the manuscript), a `bibliography:` path that does not
  exist, and one key meaning different works in two `.bib` files.
- **`wiki-global-graph.py bibkeys`** — portfolio audit of the join key itself.
  `overlap` compares key *strings*, so it reports a shared key as a win and cannot
  see a collision. `bibkeys` reads the `.bib` — the *work* behind the key — and
  reports **COLLISION** (one key, two works) and **SPLIT** (one work, two keys).
- `bibkey` `pattern` in `knowledge-frontmatter.schema.json` (all three mirrors).
  `lint-wiki.py` already enforces `pattern`, so this is a hard failure with no new
  code. It checks **shape, not derivability** — deliberately, so author-less
  reference works (`rgg-1998-samaria`) need no special case and human overrides
  are never fought.

### Fixed

- **`references.bib` must be committed.** The Zotero section claimed it was "not
  synced via Git". That is wrong — CI needs it on disk to render, and an ignored
  bib has no git undo. The false claim had already propagated into four projects'
  `.gitignore`, leaving their bibliographies unrecoverable.
- **The Better BibTeX citekey recommendation was `auth.lower + year`** — a key with
  no title, which collides for two same-author-same-year papers. Now
  `auth.lower + "-" + year + "-" + veryshorttitle.lower`, which reproduces the
  project convention exactly.
- **`bibkey` is the whole PDF filename stem, not its `autor-jahr` prefix.** The PDF
  schema (`autor-jahr-kurztitel.pdf`) was always right; only the derivation was
  wrong. `bibkey == PDF filename stem` is now a checkable invariant.
- **The wiki slug is not the bibkey** and never had to be — documented explicitly,
  because it was already true in most projects and the migration relies on it.
- `wiki-global-graph.py` labelled nested projects `paper#1 … paper#9` (every
  Evidentia wiki lives in `<Module>/paper/`), which told the reader nothing about
  which project a finding belonged to. Labels now disambiguate by walking up the
  path (`Aoristos/paper`).
- The `wiki-global-graph.py` docstring claimed bibkeys were "stable via Better
  BibTeX". They never were.

## [0.22.2] — 2026-07-12

### Fixed

- **`.gitignore` bibliography rule now also catches nested subfolders.** The 0.22.1 rule `input/bibliography/*.pdf` only matched PDFs *directly* in `input/bibliography/`; a project using the older per-source-subfolder layout (`input/bibliography/<slug>/<slug>.pdf`) would still commit those. Added `input/bibliography/**/*.pdf` so nested PDFs are ignored too (found while purging a real repo's history — the flat rule left ~160 MB of subfolder PDFs behind on the first pass). Text artefacts stay tracked; both patterns are commented.

### Fixed

- **Template `.gitignore` now excludes source bibliography PDFs.** `input/data/` large binaries were ignored but `input/bibliography/*.pdf` — where `acquire-sources` downloads source PDFs — was not, so a `git add -A` on a scaffolded project would sweep in the (often large, copyright-bound) source library. A real project's bibliography ran to ~590 MB. Added `input/bibliography/*.pdf` to the template `.gitignore` (text artefacts — `literaturguide.md`, `audit-log-*.json`, `references.bib` — stay tracked; use Git LFS if you do want the PDFs versioned), matching the `CLAUDE.md` convention that the bibliography lives in Zotero/Nextcloud, not git.

## [0.22.0] — 2026-07-12

### Added

- **`getty_aat_id` — a controlled-vocabulary join key for concepts (concept-vocabulary lever, step 1).** Concepts had no authority ID, so cross-project *concept* overlap — the deepest tissue of a methods portfolio (a technique recurring across modules under different slugs) — was the standing blind spot. Rather than build a bespoke glossary, this reuses the existing authority-ID machinery: a new `getty_aat_id` field (Getty AAT, pattern-validated `300xxxxxx`, 3-way mirrored) becomes a first-class `overlap` join key, and `wikidata_qid` / `gnd_id` on concept pages work as fallbacks where AAT has no term. `overlap` now matches concepts across drifted slugs (e.g. `point-process` ↔ `spp`); its blind-spot line now honestly counts *untagged* concepts instead of claiming all concepts are unmatchable. `wiki-lint` gains a `=== Vocabulary coverage (concepts) ===` advisory section (the concept analogue of authority coverage). `ingest-source` documents concept tagging. Conformance + overlap + coverage tests added.

### Fixed

- **Coverage reports no longer miscount `_meta/` pages as content.** `_meta/log.md` can carry `type: concept` to satisfy frontmatter validation; the new concept-coverage report (and the entity-coverage report) now skip `_meta/` pages, so index/log are not counted as content entities/concepts.

## [0.21.3] — 2026-07-12

### Changed

- **Contract linter now actually gates the structural rules it documents.** `docs/skill-contract.md` said `lint-plugin.py` *enforces* the agent↔skill contract, but three structural violations — a missing `implements:` field, broken agent↔skill symmetry, and a dangling agent back-pointer — were emitted as warnings and the linter exited `0`. They are now hard errors that fail the build. The one genuinely fuzzy check, the agent checklist-depth **heuristic**, stays advisory (reported, never fails) — and the doc now says so explicitly, splitting the rules into *enforced* vs *advisory*. Gate semantics locked by `tests/test_lint_plugin.py`.

## [0.21.2] — 2026-07-12

### Changed

- **CI runs the full agent↔skill contract linter.** The `Agent contract` job was a reduced shell re-implementation that only checked agent→skill existence (and printed a stale "all 6 agents"). It now runs `python scripts/lint-plugin.py` directly, which additionally verifies skill→agent existence, agent/skill symmetry, and that agent files carry no procedural checklist (that belongs in `SKILL.md`). stdlib-only, no install step. `docs/skill-contract.md` updated to say the linter *enforces* the contract (it was still described as a future, editorial-only rule).

## [0.21.1] — 2026-07-12

### Fixed

- **`wiki-lint` mis-resolved aliased / anchored wikilinks and let self-links hide orphans.** `lint_wikilinks` compared the *raw* wikilink target against page slugs, so a valid `[[b|alias]]` or `[[b#heading]]` was wrongly reported as a BROKEN link and its target `b` wrongly reported as an orphan; conversely a page linking only to itself (`[[a]]` in `a.md`) counted as its own incoming link and hid as non-orphan. Lint now normalises the target to the bare slug (reusing `_relation_target`, the same reduction the graph builder already applied) and ignores self-links — matching `wiki-to-graph.py`. Tests in `tests/test_wiki_tools.py`.
- **Stale doc counters and an unchecked CI gate.** README + `docs/README.md` still said "6 subagents" and "12 SKILL.md files"; the real counts are 7 agents and 15 skills. Corrected, and the docs-in-sync CI check (which previously pinned only "N skills") now also pins the subagent/agent counts and the layout-tree "N SKILL.md files" counts, so these can't drift unnoticed again.
- **Release negative tests no longer leak `::error::` annotations.** `scripts/release.py` deliberately emits `::error::` GitHub-Actions annotations on its failure paths; the release unit tests exercise those paths directly, so a *green* test job printed real error annotations into the Actions log. The tests now capture stdout/stderr around those calls (`tests/test_release.py`), keeping the annotations to genuine release-check runs.

## [0.21.0] — 2026-07-12

### Added

- **`orcid` as an authority field — the join key that actually covers living researchers.** A real portfolio audit exposed the limit of the existing authority IDs: across ten computational-archaeology module wikis, the genuinely shared entities were *working researchers and software tools* (the same scholar underpinning a temporal-analysis and a visibility module), recurring under drifted slugs (`enrico-crema` vs `crema`) — but `resolve_author` returned neither GND nor Wikidata for them, so `wiki-global-graph.py overlap` matched nothing. ORCID is the identifier that covers exactly those people. Added to the frontmatter schema (`orcid`, pattern-validated, on `type=entity`, 3-way mirrored), made a first-class join key in `wiki-global-graph.py overlap` (**listed first** — preferred for researchers) and in `lint-wiki.py`'s authority-coverage section, and mapped to the `person` subtype in `wiki-to-graph.py`. `ingest-source` now prefers `orcid` for living researchers (from `resolve_author`'s `orcid` field or orcid.org, never guessed). Overlap now fires on a shared ORCID *across different slugs* — the first mechanism that surfaces the real cross-module tissue of a methods portfolio. Conformance + overlap tests added.

## [0.20.1] — 2026-07-12

### Added

- **`wiki-lint` reports authority-ID coverage on entities (cross-project tagging discipline).** A new advisory `=== Authority-ID coverage (entities) ===` section reports how many `type=entity` pages carry an authority ID (`gnd_id` / `idai_gazetteer_id` / `wikidata_qid`) and lists the untagged ones (`--verbose` for the full worklist). Authority IDs are the join key that makes an entity matchable *across* projects (`wiki-global-graph.py overlap`); an untagged site or person is invisible to cross-project linkage and to a future merged graph. Advisory by design — datasets / methods / software entities legitimately have no applicable ID, so it never fails the lint, it just keeps the gap visible instead of letting it silently accumulate (a real portfolio audit found 0 of 135 entities tagged across ten wikis — the connective tissue simply wasn't there). `ingest-source` already resolves IDs for persons/places via `dao-paper-search`; this closes the loop by measuring it. Tests in `tests/test_wiki_tools.py`.

### Fixed

- **`wiki-lint` no longer false-flags the generated `GRAPH_REPORT.md` (regression from 0.18.0).** `wiki-to-graph.py` writes `GRAPH_REPORT.md` into `knowledge/_meta/graph/`; being a `.md` file, `lint-wiki.py` picked it up as a wiki page and reported it as "no valid YAML frontmatter" + an orphan. It was hidden in CI (the graph export dir is gitignored, so a fresh checkout never sees it) but hit anyone running `wiki-to-graph.py` and then `lint-wiki.py` locally. Lint now excludes the generated `_meta/graph/` export dir (both page collection and duplicate-slug detection), leaving index/log and orphan semantics untouched. Regression guard in `tests/test_wiki_tools.py`.

## [0.20.0] — 2026-07-12

### Added

- **Cross-project authority-overlap report (`wiki-global-graph.py overlap`) — step 1 of the global-graph roadmap.** A researcher running several `research-project` instances has the same real-world entities and sources recurring across them; a *global* graph would connect those. The hard part is identity resolution across projects (slugs both collide and drift), so the whole track is built on the robust join key the frontmatter already carries — `gnd_id` / `idai_gazetteer_id` / `wikidata_qid` (entities) and `bibkey` (sources) — with **no fuzzy title matching** (which would invent links). This first, cheap step does not build the merged graph: it takes N project roots and reports which authority IDs occur in ≥2 projects — the exact set of `same_as` edges a global graph would draw — and states the concept/entity-without-ID blind spot honestly, so you can decide *empirically* whether a global graph is worth building before investing. Deterministic (sorted, no timestamp), `--json`, stdlib + PyYAML, mirrored into the template + example, tested in `tests/test_global_graph.py`. Steps 2 (`merge`) and 3 (`serve`) are specced in `docs/ROADMAP.md` → "Cross-project graph" and deliberately deferred until ≥2 projects with overlapping, authority-ID-tagged entities exist.

## [0.19.1] — 2026-07-12

### Fixed

- **Empty-wiki graph build no longer breaks the Pages deploy (regression from 0.19.0).** On a *freshly scaffolded* project, `knowledge/` contains only `_example-` / `_meta` pages — both excluded from the graph — so `wiki-to-graph.py` found zero pages and exited non-zero. Under the new CI graph job that meant the `build-graph` step failed and took the **entire** Pages deploy (article + book + graph) down with it, on every project until its first ingest. An empty wiki is now treated as the legitimate pre-ingest state it is: the build prints a note, writes valid empty exports (`graph.json` / `graph.graphml` / `GRAPH_REPORT.md` / `graph.html`), and exits 0, so CI publishes an empty `/graph/` that fills in as sources are ingested. A genuinely wrong `--knowledge-dir` is still caught by the not-found check and still fails. Verified end-to-end on a fresh scaffold (lint → Quarto render → graph build → `public/` assembly, with `/graph/` populated); regression guard added (`tests/test_wiki_robustness.py::test_fresh_scaffold_build_exits_zero`) exercising the real CLI, not the internals.

## [0.19.0] — 2026-07-12

### Added

- **CI publishes the knowledge graph to Pages (auto-rebuild, no committed artefacts).** The graph exports are gitignored build artefacts and the agent queries the graph *live*, so the only thing that ever goes stale is the human-facing `graph.html` / `GRAPH_REPORT.md`. Rather than a local git post-commit hook (which, with the exports gitignored, would only refresh untracked files nobody else sees), the freshness now lives where it pays off: the template CI rebuilds the graph on every push to `main` and publishes it under **`/graph/`** on Pages, alongside the article (`/`) and book (`/book/`). The team reads an always-current interactive graph + deterministic report in the browser without running Python or committing `graph.html`. Implemented in the template `.gitlab-ci.yml` (new `build-graph` job + `/graph/` in the `pages` deploy) and **mirrored for GitHub-hosted projects** in a new `.github/workflows/pages.yml` (lint → render + graph → deploy to GitHub Pages). The just-added determinism of `GRAPH_REPORT.md` is what makes this clean — no timestamp churn. Template `CLAUDE.md` documents both pipelines and the one-time GitHub Pages source setting.

## [0.18.0] — 2026-07-12

### Added

- **`GRAPH_REPORT.md` — a deterministic prose summary of the knowledge graph.** `scripts/wiki-to-graph.py` now writes a fourth artefact alongside `graph.json` / `graph.graphml` / `graph.html`: a human-readable Markdown report with an overview (page/link/community counts, node types, inference-rate, dangling-link warning), the god nodes as a degree-ranked table, the bridges, the labelled communities, an **Asserted relations** section grouping the typed `relations:` edges by type (with `(inferred)` / `(ambiguous)` markers and each edge's `because` rationale), and a **Suggested questions** section whose prompts are generated from the structure and name real pages (the most-central hub, each bridge, each contradiction, plus a nudge when the inference-rate is high or links dangle). It is the static, git-diffable sibling of `graph.html` for a no-browser read — and, in keeping with the plugin's grounding discipline, it invents nothing: every line traces back to `graph.json`, every page is emitted as a `[[wikilink]]`, and it carries **no timestamp** so an unchanged wiki reproduces the file byte-for-byte (clean diffs, no churn). Available three ways: written automatically on the default build, printed to stdout via the new `report` sub-command (`python scripts/wiki-to-graph.py report`), and exposed as the `graph_report` MCP tool. Convergent with the report step in [Graphify](https://github.com/Graphify-Labs/graphify), adapted to the wiki's grounded, deterministic model.
- **Deterministic, LLM-free community labels.** `communities` were numbered (`community 3 (7)`); each now carries a `label` = the title of its most-connected member (its local hub, tie-broken by slug, source titles trimmed to their "Author Year" head). The label flows into `graph.json`, the cluster boxes in `graph.html`, the `communities` CLI output, `GRAPH_REPORT.md`, and the `graph_communities` MCP tool — turning anonymous cluster numbers into a readable at-a-glance sense of each theme, without an LLM call. Additive and schema-safe (existing community fields unchanged); the partition stays deterministic across runs.

### Fixed

- **`communities` sub-command help text** said "label propagation"; the implementation is greedy modularity (Clauset–Newman–Moore) — corrected in the CLI help and the module docstring.

## [0.17.0] — 2026-07-03

### Added

- **Single-page review findings as a first-class channel: `review_flags`.** Content-review findings about *one page's own content* (an overstatement, a weakly-supported or stale claim, a missing citation, an open question) now have a dedicated, structured home in that page's frontmatter — a **third axis**, deliberately kept apart from the two that already existed. `status` stays human-owned maturity (`draft → review → stable`, agents never self-promote); `relations: contradicts` records a conflict *between two* pages; `review_flags` records a concern about *this* page. This makes the case that matters representable: a `status: stable` page that a newer source now undercuts keeps its blessing **and** carries an open flag, instead of a review clobbering the user's `stable` decision. Each flag has `kind` (`overstatement | weak-support | stale | missing-citation | open-question`), `state` (`open | resolved`), `raised_by`, `detected`, an optional `detail`, and an optional `resolved` date. Schema-optional; pages without it stay valid (`schema/knowledge-frontmatter.schema.json`, mirrored into template + example; conformance cases added in `tests/test_schema_conformance.py`, stdlib-subset ⇄ jsonschema parity green).
  - **`semantic-wiki-review` now records findings on the pages**, not only in the dated `_meta/` report. The audit stays non-destructive to *content* — it writes `review_flags` (and `relations: contradicts` for page↔page conflicts) as frontmatter metadata, never touches prose, and never changes `status`. The dated report remains the human-readable digest and the sole home of the report-only categories (missing cross-references, suspect/aggregator citations). Findings are resolved in place via `state: resolved`, not by deletion.
  - **`drafting-manuscript` gates on open flags (SOFT-GATE #5).** It will not draft from a synthesis/source page carrying a `state: open` flag without a logged override in `gate-overrides.log` — so a known content concern cannot be silently baked into the manuscript. Preference is to resolve first, then draft.
  - **`wiki-lint` surfaces open flags** in a new `=== Review flags ===` section (script + Python-free fallback). Advisory by design: open flags are reported and gate drafting, but do **not** fail the lint exit code (a wiki with known, open findings is not malformed); a *malformed* flag still fails via schema validation. The example project's chronology-debate synthesis demonstrates one honest open `weak-support` flag (it leans on two stub sources and an inferred contradiction).
- **Acquisition gate inside `executing-research-plan`.** A plan run now guarantees every ingest task's original PDF is on disk *before* the first `source-ingester` is dispatched, instead of letting each ingest hard-stop one source at a time. The gate scans `input/bibliography/`, runs `acquire-sources` (dispatching the `source-acquirer` subagent for ≥ ~8 missing items) on the A+B set, and — when originals remain missing — enters an interactive resume loop: it surfaces the `acquisition-todo.md` worklist, marks the dependent ingest todos `blocked`, pauses, and on resume reconciles newly-added PDFs, offering to search open-access **alternatives** (a different OA source on the same topic, via `literature-review`) or continue with the acquired subset. Non-blocked downstream work (analysis on existing data) is not held up. Reflected in the process-flow diagram, routing table, red flags, and `using-research-powers`.
- **Weighted source table as the head of `literaturguide.md`.** `literature-review` now opens the guide with a required table (`Grade | Autor Jahr | Kurztitel | OA/Zugang | DOI/Link`) before the nine prose sections. This is the canonical weighting `acquire-sources` filters on (by `Grade`, default A+B) to build its download worklist — closing the hand-off between search and acquisition.

### Changed

- **Canonical, flat PDF naming: `autor-jahr-kurztitel.pdf`.** All source PDFs live directly in `input/bibliography/` — flat, no per-source subfolders — under one lowercase-ASCII, hyphen-separated scheme (`autor` = first author's surname with umlaut/ß folding and particles removed; `jahr` = four-digit year + disambiguation letter; `kurztitel` = 1–3 significant title words). This single flat folder is the source of truth `acquire-sources` reconciles against and `ingest-source` reads from; the wiki slug / bibkey is the `autor-jahr` prefix. `acquire-sources` writes downloads straight to this name; manual downloads are renamed to it before ingest. Applied across `acquire-sources`, `ingest-source`, the template `CLAUDE.md` / `README.md` / `input/bibliography/README.md`, `docs/tutorial.md`, and `docs/installation-cowork.md`; the example plans now carry an explicit *Acquire source PDFs* task before ingest.
- **`writing-research-plan` decomposes with an explicit acquisition step.** Plans now enumerate data sources with a status (acquire pending / on disk / already in wiki) and insert an *Acquire-sources* task before ingest tasks, so the Acquire → Ingest → Analysis → Synthesis → Draft chain has no gaps.
- **Template software directory renamed `output/app/` → `output/code/`** (with matching `.gitignore` paths and the tree in `CLAUDE.md` / `README.md`), aligning the folder name with how the skills refer to it.
- **`grant-finder`: reference path made relative** (`research-skills/dao-grant-finder/`), removing a hard-coded absolute machine path from the skill.
- **Manuscript drafting now writes with depth instead of reflowing bullets.** Drafts built straight from the deliberately terse wiki came out dense and compressed — one flat sentence per wiki bullet, no examples, no explanation. `drafting-manuscript` reframes the "wiki is the single source of truth" rule so it governs *what is claimed*, while treating the wiki as a **pointer to the depth, not the depth itself**: when a page is too thin to develop a point, the drafter reaches back to the source — the source page's `### Direct quotes` / `### Examples & illustrations`, or the original PDF in `input/bibliography/` at the cited page anchors (on disk thanks to `acquire-sources`) — and cites what it uses. A new *Writing with depth* section distinguishes grounded elaboration (from the source, cited — encouraged) from expository framing (uncited) and new-claims-from-memory (still forbidden), gives an assertion → grounding → example → significance paragraph pattern, and adds a reach-back checklist step, process-flow branch, red flags, and key principles. The `drafter` subagent contract now receives the source PDF paths and reports which it reached into.
  - **`ingest-source` captures the raw material for that depth.** A new `### Examples & illustrations (for later drafting)` subsection in each focus block records the concrete cases a source uses (artefact, site, dataset, passage) with page anchors, and the `### Direct quotes` guidance now prefers passages that carry an explanation or example. A claim-only page produces dense prose downstream.
  - **Per-project house style.** The template `CLAUDE.md` gains a *Manuscript style (drafting depth)* block — tunable per project (density, examples, register, target length) — which `drafting-manuscript` reads before drafting; the Draft workflow references it.
  - **`writing-research-plan`** now directs Draft tasks to carry a generous word count as a floor for development, since too-tight targets are the main driver of compressed prose.

## [0.16.0] — 2026-06-23

### Added

- **New acquisition phase between search and ingest: `acquire-sources`.** A new skill (with an optional `source-acquirer` subagent) sits between `literature-review` and `ingest-source`. It auto-downloads the Open-Access PDFs for the A+B graded sources into `input/bibliography/` (named `Lastname - Title - Year.pdf`), and for everything paywalled or bot-blocked it writes `input/bibliography/acquisition-todo.md` — a manual-download worklist with DOI/landing links and the exact target filename, so the user can fetch originals via university VPN. Every download is validated (HTTP 200 + `application/pdf` content-type + `%PDF-` magic bytes + size + not an HTML login/Cloudflare page), so a saved "Access Denied" page is never mistaken for a source. Re-running reconciles newly-arrived manual downloads (idempotent); a date-stamped `acquisition-log-*.json` records every resolution. Wired into the phase sequence (`hooks/session-context.md`, `using-research-powers`, README, tutorial, phase-flow).
- **`ingest-source` hard-stops on a missing original.** Previously, when the original PDF was not on disk, the agent improvised — searching for alternatives and silently falling back to a preprint, prior version, or book review (undocumented, and corrupting provenance). Ingest now expects the acquired original in `input/bibliography/` and **hard-stops** if it is missing, pointing the user to `acquisition-todo.md`. A substitute is ingested only with explicit user consent, recorded as provenance: a new optional `based_on` frontmatter field (`original` | `review` | `preprint` | `prior-version`), a `> [!warning] Provenance` callout, and a marked log line.

- **Ingest now writes typed, confidence-tagged graph relations.** `ingest-source` (and the `source-ingester` subagent) build the *typed* graph layer at ingest time: every stance-bearing connection (confirms / contradicts / builds-on / cites) is mirrored from the prose `## Connections` list into a structured `relations:` frontmatter entry — `type` from a controlled vocabulary, `confidence` (`extracted` only with a quote + page, else `inferred` / `ambiguous`), and a one-line `because` rationale. Previously the graph saw only untyped `wikilink` edges and the typed layer had to be added by hand. The block stays schema-optional; a new SOFT-GATE item checks that stance connections have a matching relation. Re-ingest unions the `relations:` block (dedupe by `(target, type)`, keep higher confidence). The example project's three source pages now demonstrate it (lint-green, 6 typed edges).

### Changed

- **Semitic-transcription fonts for PDF output.** The publication templates (`article`, `book`, `presentation`) switched their PDF font stack from Linux Libertine to a free, OFL-licensed set tuned for scholarly transcription of Semitic languages: `mainfont` → **Gentium Plus** (Latin transliteration incl. ʾ/ʿ + polytonic Greek), `sansfont` → **Noto Sans** (headings with transliterated terms), `monofont` → **Fira Code**; native Hebrew (RTL) via **Ezra SIL** through a babel block in the PDF preambles. The PDF build uses XeLaTeX or LuaLaTeX (Quarto picks one). Install + usage notes in `output/README.md` and the root README; the previously-untracked `_preamble.tex` sources are now versioned (a `.gitignore` rule had swallowed them).
- **Publication layout flattened.** `output/publication/article` and `output/publication/book` moved up one level to `output/article` and `output/book`, and the now-empty `output/publication/` wrapper was removed. `article`, `book` and `presentation` are now siblings directly under `output/`. Every path reference was updated to match — template `CLAUDE.md` / `README.md`, `.gitlab-ci.yml`, `.vscode/tasks.json`, `.gitignore`, the skills (`drafting-manuscript`, `executing-research-plan`, `requesting-peer-review`, `finishing-a-research-project`, `writing-research-plan`, `using-research-powers`), `docs/`, `hooks/session-context.md`, the `knowledge-frontmatter` schema, the OpenCode plugin mirror, the example project, and CI (`.github/workflows/lint.yml`). The in-file `bibliography` / `csl` paths in the article and book templates were corrected from `../../bibtex` to `../bibtex` to match the new depth (now consistent with `presentation`).

### Fixed

- **`make all` no longer deletes the earlier formats.** The article, book and presentation Makefiles built each format with a separate `quarto render` call, but Quarto cleans the output directory on every render — so `make all` left only the last format and silently removed the others. The `all` target is now a single `quarto render … --to all` pass that emits every declared format side by side.
- **`make all` made robust for the presentation; `make clean` no longer deletes `_preamble.tex`.** The presentation declares two PDF formats (Beamer slides + A4 handout) that collided on the shared `talk.tex` intermediate under `--to all` and on `talk.pdf` — `make all` failed and left a single half-rendered file. It now renders each format in place (no shared output-dir clean) and collects the artefacts, with distinct `output-file` names (`talk-slides.pdf` / `talk-handout.pdf`). Separately, the `clean` targets ran `rm -f *.tex`, which deleted the hand-authored `_preamble.tex`; they now remove only generated `.tex` and always preserve `_preamble.tex`. Verified by rendering all three formats to PDF (transliteration, polytonic Greek, native Hebrew all glyph-correct).

## [0.15.1] — 2026-06-08

Fixes a fake-green in the v0.15.0 install smoke: the marketplace add / install / list steps were tolerant (`|| echo`), so in the real CI run the CLI and `validate` passed but `marketplace add .` and the install actually **failed** and `list` reported no plugins — yet the job stayed green. This made the "tier 2 done / all P1–P7 complete" claim unsubstantiated.

### Fixed

- **Install smoke is now fail-closed** (`.github/workflows/install-smoke.yml`): once the CLI is available the whole sequence must succeed with no suppressed errors — `claude plugin validate ./` → `claude plugin marketplace add ./ --scope user` → `claude plugin install research-superpowers@leiverkus-research --scope user` → `claude plugin list --json`, then a check that the JSON actually contains `research-superpowers`. The path is `./` (the CLI rejects a bare `.` for `marketplace add`), and an isolated `CLAUDE_CONFIG_DIR` keeps the run self-contained. Only *obtaining* the CLI stays best-effort (honest skip with a notice if it can't be installed). Verified locally end-to-end (plugin installs, `list --json` reports `research-superpowers@leiverkus-research` v0.15.0).

## [0.15.0] — 2026-06-08

Roadmap P6 tier 2 — a best-effort, honest plugin-install smoke test. With this, all roadmap items P1–P7 are complete.

### Added

- **Plugin install smoke (roadmap P6, tier 2)**: `.github/workflows/install-smoke.yml` installs the real Claude CLI and runs `claude plugin validate .` plus a local marketplace add/install/list. Honest by design — if the CLI can't be obtained in the runner the job **skips with a notice** rather than faking success; if the CLI is available, `validate` must pass. It is intentionally **not** part of the release gate (`release.yml`), since tier 2 is environment-dependent and must never block a release.

### Docs

- `docs/ROADMAP.md` marks P6 tier 2 done; all P1–P7 items are now complete. `CONTRIBUTING.md` notes the best-effort install smoke.

## [0.14.0] — 2026-06-08

Roadmap P7: the test suite now runs on Linux, macOS and Windows, with a real hook-dispatch test per OS. This is the last planned maturity item; only the best-effort P6 tier 2 (a real `claude plugin install` in CI) remains open.

### Added

- **Cross-platform CI matrix** (roadmap P7): the unit + integration suite runs as a `tests` job on `ubuntu-24.04`, `macos-latest` and `windows-latest` (the heavy Quarto render stays Linux-only). This proves the Python tooling, the scaffold E2E, the MCP server and path handling work on all three OSes, not just Linux.
- **Hook-dispatch test** (`tests/test_hook_dispatch.py`): exercises the real `hooks/run-hook.cmd session-start` entry point per OS — the polyglot wrapper on POSIX, the cmd.exe → Git-bash path on Windows — and asserts the emitted `additionalContext` is valid JSON carrying the skill index.
- **`.gitattributes`**: forces LF on the shell hooks (`session-start`, `run-hook.cmd`, `*.sh`) so a Windows checkout (`core.autocrlf=true`) can't rewrite them to CRLF and break the bash shebang; marks the vendored cytoscape bundle as binary.

### Fixed

- **Windows UTF-8 output bug** (surfaced by the new matrix): `wiki-to-graph.py` printed JSON containing arrow glyphs (`←`/`→`) to stdout, which crashed with `UnicodeEncodeError` on a Windows cp1252 console. All three scripts now force UTF-8 on stdout/stderr (`sys.stdout.reconfigure`), the MCP server decodes the CLI subprocess as UTF-8, and `scripts/release.py` does the same for `notes`. A real bug for Windows users, not just CI.
- **`release.py bump` is now atomic**: it computes and validates every change (manifests, README badge, CHANGELOG) in memory first and only writes once all succeed — a missing README badge can no longer leave a half-bumped repo. Tested by asserting the worktree is unchanged after a failed bump.
- **Runtime validator now enforces nested `relations[]` rules**: `lint-wiki.py` previously checked only that each `relations` item was an object, so `type: 42`, `because: 42`, a bad `confidence` enum, a missing required key, or an unknown key slipped through while JSON Schema rejected them. The validator is now recursive (object `required` / `properties` / `additionalProperties`, array items), and `tests/test_schema_conformance.py` pins six new nested cases in agreement with `jsonschema`.

### Security

- **Least-privilege release workflow**: `release.yml` now defaults to `contents: read`; only the `release` job that publishes gets `contents: write` (the render/test verify jobs run read-only).

### Changed

- The single-OS `lint` job no longer runs the unit tests itself; they now run in the cross-OS `tests` job (which includes Linux), so the release gate (`release.yml` → `workflow_call`) is verified on all three platforms before a tag can publish.
- The portability matrix pins Python to the minor `3.12` (exact patches aren't built for every OS/arch); the reproducible anchor (the ubuntu `lint` + `release` jobs) keeps the exact `3.12.13` pin.

## [0.13.0] — 2026-06-08

Roadmap P5 + P6 (tier 1): a `jsonschema` golden cross-check of the hand-rolled validator, and an end-to-end test of the shipped template. No runtime dependency added — scaffolded projects still run on stdlib + PyYAML only.

### Added

- **Schema conformance cross-check** (roadmap P5, hybrid): the stdlib validator in `lint-wiki.py` stays the runtime, and `jsonschema` (pinned in the new `requirements-dev.txt`, CI/dev-only) becomes the authoritative golden check. `tests/test_schema_conformance.py` pins the hand-rolled validator and `jsonschema` in agreement on every rule the subset implements (a valid page + one fixture per single-rule violation: required, enum, date, pattern, type, conditional `bibkey`, array-item type) and validates **all shipped example/template wiki pages** with the real engine. The tests skip cleanly when `jsonschema` is absent. If the schema outgrows the stdlib subset, the cross-check fails — the signal to extend the subset or revisit a runtime dependency.
- **Scaffold end-to-end test** (roadmap P6, tier 1): `tests/test_scaffold_e2e.py` materialises a project from the shipped `templates/research-project-template/`, drops in a small connected wiki, and runs the real user path against the *copied* scripts — lint (clean) → graph build (`graph.json`) → a `neighbors` query → the MCP handshake + `graph_stats`. Proves the shipped template (not just the in-repo example) is self-consistent. (Tier 2, a real `claude plugin install` in CI, remains open.)
- **`requirements-dev.txt`** — pinned dev/CI toolchain (PyYAML 6.0.3 + jsonschema 4.25.1); CI installs from it. Documented in `CONTRIBUTING.md`.

## [0.12.0] — 2026-06-08

Roadmap P3 + P4: an automated, self-checking release process and a much broader negative/integration test suite. No user-visible behaviour change.

### Added

- **Automated, fail-closed release process** (roadmap P3): `scripts/release.py` (stdlib) is the single source of truth for the manifest versions, the git tag, and the matching CHANGELOG section — `check` (verify all three agree), `notes` (extract a section), `bump` (bump manifests + README badge + CHANGELOG skeleton; the badge replacement now fails loudly instead of silently no-op'ing). `.github/workflows/release.yml` fires on a `v*` tag and, **before** creating the release, (1) runs the **entire CI suite** on the tagged commit via `workflow_call` and (2) asserts the tagged commit is **contained in `origin/main`** — so an untested or off-main tag cannot publish a release. It then extracts the CHANGELOG section and creates the GitHub Release — no manual `gh release create`. The lint job also runs `check` on every PR, so a version bump without a CHANGELOG entry fails CI. `CONTRIBUTING.md` documents the flow.
- **Negative & integration tests** (roadmap P4): `tests/test_wiki_robustness.py` adds 21 adversarial cases — empty / single-page / all-orphan wikis, malformed wikilinks (empty brackets, aliases, headings, dangling, self-links, duplicate-weight), corrupt frontmatter (unterminated, non-dict root, tabs, BOM), MCP error paths (unknown tool, missing argument, malformed JSON-RPC frame, unknown method, non-existent node, valid call), a **1000-page** scale + determinism check (with a wall-clock budget), and subdir/stem path handling. `tests/test_release.py` covers the release helper end-to-end in a throwaway repo: full bump, idempotency, missing-badge failure, bad-semver rejection, and every `check` mismatch case.

### Changed

- The version bump for this release was produced by `scripts/release.py bump`; the GitHub Release itself is created by `release.yml` when the `v0.12.0` tag is pushed (the dogfooding of P3 is completed by that tag push, not by this commit).

## [0.11.1] — 2026-06-08

Completes the reproducible-CI work from v0.11.0 (roadmap P1) and marks the done items in the roadmap.

### Changed

- **Toolchain fully pinned** (roadmap P1, finish): Python is pinned to `3.12.13` (with `check-latest: false`) instead of the moving `3.12`, PyYAML to `6.0.3` via the Python-bundled pip (dropping the moving `pip install --upgrade pip pyyaml`), and both CI runners to `ubuntu-24.04` instead of `ubuntu-latest`. With the Action SHAs and Quarto `1.9.38` already pinned in v0.11.0, the build toolchain is now deterministic apart from the runner base image (container-by-digest noted as a possible future step).

### Docs

- **Roadmap status** (roadmap P3-doc): `docs/ROADMAP.md` now marks P1 and P2 as ✅ done with a status note, instead of still describing them as open gaps.

## [0.11.0] — 2026-06-08

First maturity pass from the post-v0.10.0 roadmap (`docs/ROADMAP.md`): pure hardening of the build pipeline, no user-visible behaviour change.

### Changed

- **Reproducible CI** (roadmap P1): GitHub Actions are now pinned to immutable commit SHAs (with a human-readable version comment) instead of moving major tags, and Quarto is pinned to an explicit version (`1.9.38`) instead of "latest". This also upgrades `actions/checkout` and `actions/setup-python` to their Node 24 majors, resolving the Node 20 deprecation that would have broken the build after 2026-06-16.

### Added

- **Script mirror-drift guard** (roadmap P2): CI now fails if the wiki scripts (`lint-wiki.py`, `wiki-to-graph.py`, `graph_mcp.py`, `vendor/cytoscape.min.js`) drift between the template and the example — previously only the JSON schema was guarded, and the example schema copy is now checked too. `CONTRIBUTING.md` documents the canonical source (the template) and the one-shot re-sync command.

## [0.10.0] — 2026-06-08

Engineering-robustness pass addressing an external review — the scripts and template were less robust than the concept.

### Fixed

- **Template build config was broken in scaffolded projects** (P1): `.gitlab-ci.yml` and the VS Code tasks referenced `artikel.qmd`/`vortrag.qmd` instead of the actual `article.qmd`/`talk.qmd`, and still tried to Quarto-build the now plain-Markdown wiki. A new CI scaffold-config smoke test guards against recurrence.
- **Invalid dates crashed the tools** (P1): `2026-99-99` raised `ValueError` in PyYAML; `lint-wiki.py` and `wiki-to-graph.py` now parse with a no-timestamp loader (dates stay strings) and catch it.
- **Schema lint was incomplete** (P1): `validate_frontmatter` now checks types, ISO date validity, patterns (wikidata/iDAI/GND IDs) and array item types — not just required fields and enums.
- **Duplicate page slugs silently merged** (P1): both the linter and the graph builder now fail loudly on colliding slugs.
- **Methodology contracts contradicted the hermeneutic default** (P1): `executing-research-plan` and `requesting-peer-review` no longer demand a pre-registered hypothesis for hermeneutic projects (`status: ready` suffices; falsification is reframed as "what would refute the thesis").
- **The gate "override-rate" was not a rate** (P2): it read 100% once ≥10 entries existed; now reports an honest count + recent-window frequency.
- **README / session-index drift** (P2): version badge (was 0.3.0), skill count (was 12), and dead migration links fixed; `hooks/session-context.md` now lists every skill.
- **Article template did not render** (P1): its `bibliography`/`csl` paths were one level too shallow (`../bibtex/` → `../../bibtex/`).
- **Book template did not render** (P1): Quarto requires the homepage at the project root, so `frontmatter/index.qmd` is now `index.qmd`.
- **Remaining doc drift** (P2): `docs/README.md` and `docs/installation.md` said "12 skills" (now 14, and the docs-in-sync check covers `docs/` too); `--strict` removed from `CONTRIBUTING.md` (the installed Claude CLI rejects it).
- **Date validation too lax** (P2): `date.fromisoformat()` also accepts `20260415` and week dates like `2026-W15-3`; a strict `YYYY-MM-DD` check is now applied first.
- **Override recency counted future dates** (P3): a 2099 entry no longer counts as "last 30 days".

### Added

- **CI drift guards & tests**: README version badge must equal `plugin.json`, skill-count mentions across README + `docs/` must equal the actual count, README links must resolve, `session-context.md` must mention every skill — plus stdlib `unittest` tests (`tests/`) for invalid frontmatter, strict dates, duplicate slugs, the override count + future-date guard, bad-YAML robustness, and deterministic communities.
- **Real publication render smoke test in CI**: a dedicated job runs `quarto render` of the article, book and presentation templates to HTML — catching broken bibliography paths / book layout that mere file-existence checks miss.
- **OpenCode integration is now versioned** (`opencode/`): the native OpenCode plugin (`plugin/research-superpowers.ts`) that replicates the SessionStart skill-index injection via `experimental.chat.system.transform` — GWDG-safe, scoped to research projects — plus its setup README are checked in instead of living untracked. Its `EMBEDDED_INDEX` fallback was re-synced to the current `hooks/session-context.md`, and a new CI step (in the docs-in-sync job) fails the build if the two ever drift again.

## [0.9.0] — 2026-06-08

Adds an optional per-relation rationale (`because`) — the lightweight first step toward rationale nodes.

### Added

- **Optional `because` rationale on relations** — a one-line "why A relates to B" attached to each `relations` entry (the lightweight first step toward rationale nodes). Additive and optional; pages without it stay valid.
  - Recorded per edge in `graph.json` / `graph.graphml`; shown in the `graph.html` info panel and in the `relations` query output (CLI + `graph_relations` MCP tool).
  - `lint-wiki.py` accepts `because` and reports the share of relations that carry a rationale (alongside the inference-rate) — the natural place to ground an `inferred` edge when hardening it to `extracted`.
  - Documented in `docs/frontmatter-schema.md` and CLAUDE.md; CI exercises it on the example project.

## [0.8.0] — 2026-06-08

Adds dependency-free community detection to the knowledge graph — automatic thematic clustering, in the CLI, the MCP, and a community-grouped HTML layout.

### Added

- **Community detection** (`scripts/wiki-to-graph.py`) — automatic thematic clustering of the wiki, dependency-free and deterministic (greedy modularity, Clauset–Newman–Moore; no `igraph`/`leidenalg`). Surfaces the sub-topics of a literature without any tagging.
  - New `communities [--min-size N]` query sub-command and `graph_communities` MCP tool (`--json` supported); each community reports its size, node-type mix, and members.
  - Every node gets a `community` id in `graph.json` / `graph.graphml`; `graph.html` **groups nodes spatially by community** (compound containers laid out by cose) and gains a **Colour: by type / by community** switch.
  - Robust on dense, hub-heavy wikis where label propagation collapses to one blob; ties broken deterministically so the partition is reproducible.
  - CI smoke-tests the community query + the `community` attribute on the example project.

## [0.7.0] — 2026-06-08

Completes the knowledge-graph Query-Layer: query the wiki live during a session, from the terminal or as native MCP tools.

### Added

- **Live graph query sub-commands** in `scripts/wiki-to-graph.py` — query the wiki *during a session*, recomputed from the `.md` on each call (always current, no stale export), deterministic (real graph traversal, not LLM-eyeballed JSON), stdlib-only:
  - `neighbors <slug> [--depth N] [--relation TYPE]`, `path <a> <b>`, `god-nodes [--top-n N]`, `bridges`, `relations [--type T] [--confidence C] [--node N]`, `search <term>`, `stats`; `--json` on any query for machine-readable output; node tokens may be a unique substring (fuzzy-resolved).
  - Backward compatible: with no sub-command the script builds the exports exactly as before (CI, scaffold and the skill are unchanged).
  - `wiki-graph` skill now queries the live graph for targeted questions (build/HTML reserved for overview and the visual); documented in CLAUDE.md; CI smoke-tests the queries on the example project.
  - This is the CLI half of the deferred Query-Layer.
- **`wiki-graph` MCP server** (`scripts/graph_mcp.py`) — the MCP half of the Query-Layer. A stdlib-only stdio JSON-RPC server (no `pip install mcp`, no network) that exposes the queries as native tools: `graph_neighbors`, `graph_path`, `graph_god_nodes`, `graph_bridges`, `graph_relations`, `graph_search`, `graph_stats`. It is a thin wrapper — each tool shells out to `wiki-to-graph.py --json`, so results are identical and equally live. Registered **per project** via `.mcp.json` (Claude Code reads it at the project root, rooted in that repo, so it auto-knows the right wiki in any session); OpenCode equivalent documented in CLAUDE.md. CI smoke-tests the handshake + a tool call.

## [0.6.0] — 2026-06-07

Two related changes: the knowledge wiki moves to plain Markdown (Quarto reserved for the publication layer), and a dependency-free knowledge-graph export layer is added on top of it.

### Added

- **Knowledge-graph export layer over the Markdown wiki.** The wiki is already a graph (pages linked by wikilinks); this makes it explicit and queryable without a new dependency or any LLM/network calls.
  - `scripts/wiki-to-graph.py` (template + example-project mirror) reads `knowledge/**/*.md` and writes `knowledge/_meta/graph/graph.json` and `knowledge/_meta/graph/graph.graphml` (Gephi/yEd). One node per page (`type` from frontmatter; optional `subtype` derived only from `gnd_id`/`idai_gazetteer_id`); edges from wikilinks (confidence `extracted`) and from the new structured `relations` block. Derived views: **god_nodes** (top-N by degree, `--top-n`, default 15) and **bridges** (entities joining ≥2 otherwise-unconnected source clusters, via union-find). CLI `--knowledge-dir` / `--out-dir`.
  - **Self-contained interactive `graph.html`** — `wiki-to-graph.py` also writes an offline HTML viz (cytoscape.js vendored under `scripts/vendor/`, inlined into one file — no install, no network). Colour by node type, size by degree (capped), gold ring on bridges; short labels (sources shown as "Author Year", not the full title); filter by node type / relation type / confidence; search; click a node to highlight its neighbourhood and list its typed relations. For readability the default view shows only the typed-relation layer (wikilinks are one toggle away) and lays out the visible subgraph. Covers everyday exploration without Gephi/yEd (those remain for heavy layout / community detection). `--no-html` skips it; the script degrades gracefully if the vendored lib is absent.
  - **Optional `relations` frontmatter field** (additive — pages without it stay valid): `target` (page slug), `type` (free vocabulary: cites, contradicts, builds-on, …), `confidence` (`extracted` | `inferred` | `ambiguous`). Documented in `docs/frontmatter-schema.md`; added identically to all three schema copies.
  - **Linter integration:** `lint-wiki.py` validates `relations` (target resolves, confidence enum, required/known keys) and reports an **inference-rate** (share of `inferred`+`ambiguous`), mirroring the SOFT-GATE override-rate as an audit signal.
  - CI builds the graph from the example project and asserts node/edge/relation counts, non-empty god_nodes + bridges, and well-formed GraphML.
  - **`wiki-graph` skill** — the intent-triggered layer over the script: builds the graph and answers structure questions grounded in `graph.json` (god nodes, bridges, relation types/confidence, dangling/orphan signals), with a Python-free fallback. Positioned as the structure-analysis sibling of `wiki-lint` (validation) and `semantic-wiki-review` (content audit). Registered in the skill catalogue (`using-research-powers`, README, `docs/concepts.md`).

### Changed

- **Knowledge wiki is now plain Markdown (`.md`), not Quarto (`.qmd`).** The wiki layer (`knowledge/`) is for thinking and steering — it needs no build step and is read directly in Foam/Obsidian or the repository browser. Quarto is now reserved exclusively for the publication layer (`output/publication/`), which genuinely needs formats, CSL, cross-references and figures. This aligns the template and example project with the convention already used in real projects.
  - Renamed every `knowledge/**/*.qmd` page to `.md` in `templates/research-project-template/` and `examples/example-project/`.
  - Removed `knowledge/_quarto.yml` and `knowledge/Makefile` from the template (the wiki has no build step).
  - `scripts/lint-wiki.py` now globs `*.md` (and skips both `_example-` and `_beispiel-` prefixes).
  - Figures in wiki pages use plain Markdown image syntax; the Quarto cross-reference form (`{#fig-…}` + `@fig-…`) is reserved for publication pages.
  - `.gitlab-ci.yml` lints the wiki (`scripts/lint-wiki.py`) instead of rendering it; only the publication is rendered and deployed to GitLab Pages.
  - Updated `.vscode/settings.json` (schema glob → `knowledge/**/*.md`), `.gitignore` (dropped stale `knowledge/_site|.quarto`), the JSON Schema descriptions, `CLAUDE.md`, both READMEs, and all skill/agent/docs references accordingly.

### Fixed

- **Template `knowledge/_meta/index.md` and `log.md` now carry valid YAML frontmatter**, so a freshly scaffolded project passes `scripts/lint-wiki.py` (0 issues) out of the box.

## [0.5.1] — 2026-05-28

Post-release housekeeping for the example project. Brings every file under `examples/example-project/` into alignment with v0.3 (SOFT-GATE / methodology-aware) and v0.5 (focus-driven ingest). No skill or schema changes.

### Changed

- **`examples/example-project/input/ideas/low-chronology-design.md`** — rewritten as a hermeneutic design doc (matches the project's `methodology: hermeneutic` declared in `input/description/project-description.md`). Removes references to a quantitative OxCal re-analysis; reframes as close reading of the foundational positions plus *Forschungsstand* with three plausible interpretive outcomes (regional variation / one-resolution / Forschungsstand reading).
- **`examples/example-project/input/ideas/low-chronology-plan.md`** — `status: pre-registered` → `status: ready`; removed `Hypothesis` and `Falsification Criteria` blocks (not used in hermeneutic projects); added `methodology: hermeneutic` and `Method sketch` / `Iteration expectation` blocks per v0.3 plan template. Task list rewritten around close reading + per-source focus-driven ingest, dropping the Bayesian / OxCal data-analysis tasks.
- **`examples/example-project/knowledge/synthesis/chronology-debate.qmd`** — modernised to v0.5 conventions: references the focus-driven Finkelstein-Piasetzky source page properly (via the `## Focus: 14C reconciliation` block); adds an argument-structure map over the four levels of the debate (data selection / calibration / phase modelling / framework choice); incorporates the new Mazar 2011 and Regev et al. 2020 stubs. Status: `review` (was: `draft`).
- **`examples/example-project/output/publication/article/main.qmd`** — rewritten as a hermeneutic article skeleton (Introduction → State of the Field → Argument Structure → Negev Case → Discussion → Conclusion). Dropped Reproducibility section with OxCal seeds (no quantitative analysis to reproduce).
- **`examples/example-project/knowledge/_meta/log.qmd`** — updated to reflect the new event sequence (plan `status: ready` rather than `pre-registered`; new ingests for Mazar 2011 and Regev et al. 2020; synthesis promoted to `review`).

### Added

- **`examples/example-project/knowledge/sources/mazar-2011.qmd`** — new focus-driven source page with one focus block ("the Modified Conventional Chronology response to the Low Chronology"), demonstrating the v0.5 structure on the Mazar counter-position.
- **`examples/example-project/knowledge/sources/regev-et-al-2020.qmd`** — new focus-driven source page with one focus block ("the current Tel Rehov 14C dataset and re-modelling under IntCal20").
- **BibTeX entries for `mazar-2011` and `regev-et-al-2020`** in `examples/example-project/output/bibtex/references.bib`.

### Removed / Fixed

- Stale "not yet ingested" markers for `mazar-2011` and `regev-et-al-2020` across the example project — these are now real stub source pages.

---

## [0.5.0] — 2026-05-27

Focus-driven `ingest-source`. Source pages now capture **what this project takes from a source under a specific focus**, not a generic summary. Re-ingest of the same source with a different focus appends a new `## Focus:` block rather than overwriting. Aligns the wiki with how researchers actually read: question-driven, not RAG-style full-text indexing. Existing source pages keep working — lint accepts both old and new structures.

### Changed

- **`skills/ingest-source/SKILL.md`** — substantial restructure. New `focus` input (smart-default from `input/description/project-description.md`). New Step 1 "Determine focus" (proposes project research question, asks user to confirm or refine; refuses to proceed without confirmed focus). New Step 5 "Check for existing source page" + re-ingest detection branch (append mode preserves prior focus blocks; replaces `## Other content in this source`; unions `## Mentioned entities` and `## Connections`; legacy-wrap option for pre-v0.5 pages). New Source Page Template body (stacked `## Focus:` blocks; explicit `## Boundary: what this source does NOT address`; one-paragraph `## Other content in this source`). Old generic sections (`Core Theses`, `Method`, `Relevant Findings`, `Positioning`) removed from the spec.
- **`agents/source-ingester.md`** — output report extended: `### Focus`, `### Re-ingest mode` (`fresh` | `append-section` | `update-existing-focus` | `legacy-wrap`); `### Claims relevant to focus` replaces `### Core theses`; `### Boundary noted` echoes the explicit boundary statement. Min. 1 verbatim quote *per focus block* (was: min. 2 per ingest).
- **`templates/research-project-template/knowledge/sources/_beispiel-finkelstein-2003.qmd`** — rewritten with two stacked focus blocks demonstrating the append pattern.
- **`examples/example-project/knowledge/sources/finkelstein-piasetzky-2003.qmd`** — rewritten with one realistic focus block aligned to the example project's research question.

### Added

- **`examples/example-project/input/description/project-description.md`** — new file. The example project now has a proper research question file so the smart-default focus elicitation has something to read.
- **`docs/concepts.md` § "Wiki is purpose-built, not a generic archive"** — explains the why behind focus-driven ingest, the append-on-reingest pattern, and how this differs from RAG.
- **`docs/migration-v0.4-to-v0.5.md`** — covers the structural change, the optional re-ingest with legacy-wrap, and what stays unchanged.
- **`docs/tutorial.md` § Phase 4** — walkthrough updated to demonstrate focus elicitation, focus refinement, and re-ingest with a different focus on the same source.

### Removed / Fixed

None (the removal of the generic body sections from the SKILL.md *spec* is a template change, not a removal from existing wiki pages).

---

## [0.4.0] — 2026-05-27

Cowork-friendly install path. The plugin now works fully click-only — no terminal, no Python, no Git required for the core workflow. Existing CLI users see no change to their flow. Purely additive; no breaking changes.

### Added

- **`skills/scaffold-research-project/SKILL.md`** — conversational project scaffolding. Asks for project name, parent directory, methodology, discipline, and languages; copies the template tree via Claude's Read+Write tools (no `cp -r`); patches CLAUDE.md frontmatter with the user's answers; optionally initialises git via Bash if available. Designed for Cowork (no shell) and as a friendlier setup for any first-time user. Skill total: 12 → 13.
- **Python-free fallback in `skills/wiki-lint/SKILL.md`** — when `scripts/lint-wiki.py`, `python3`, or `pyyaml` are missing, the skill validates frontmatter inline. Tells the user explicitly that wikilink resolution and orphan detection require the Python script (those checks are O(N²) in tokens for a full-wiki scan).
- **`docs/installation-cowork.md`** — click-only install path. What you need (just Claude), install via `/plugin marketplace add`, scaffold via natural language, what each "give up" actually costs (Python / Git / Quarto), troubleshooting, when to upgrade to the full setup.
- **`docs/migration-v0.3-to-v0.4.md`** — short note: purely additive, existing users keep their CLI flow.
- **README and `docs/installation.md` and `docs/README.md`** — cross-pointers to the Cowork install path.

### Changed

- `.claude-plugin/plugin.json` — version 0.3.0 → 0.4.0; description appended: "Works in Claude Code and Cowork — no terminal required for the core workflow."
- `.claude-plugin/marketplace.json` — version 0.4.0 (sync); description appended; new `cowork` tag added.

### Removed / Fixed

None.

---

## [0.3.1] — 2026-05-27 (post-release housekeeping, rolled into v0.4.0)

> Documented retroactively. These changes shipped to `main` between the v0.3.0 and v0.4.0 tags (commits `0e884ae`, `5432dda`, `c521d5a`) but were not separately tagged. Anyone installing `@v0.4.0` or later already has them.

### Added

- **`.github/ISSUE_TEMPLATE/`** — four YAML-form issue templates: `bug_report.yml`, `skill_behaviour.yml` (skill-dropdown + kind-of-issue), `new_skill.yml` (with the four skill-authoring criteria as required checkboxes), `docs_issue.yml`; plus `config.yml` disabling blank issues and pointing to docs + GitHub Discussions.
- **`.github/PULL_REQUEST_TEMPLATE.md`** — type-of-change checkbox, verification commands matching `CONTRIBUTING.md`, language-convention + SOFT-GATE-preservation checklist, CHANGELOG and migration-note reminders.
- **`.github/workflows/lint.yml`** — CI on every push to `main` and on every PR. 13 steps: plugin + marketplace manifests valid JSON; plugin and marketplace versions match; schema valid + mirror in sync; `python scripts/lint-wiki.py` exits 0 on `examples/example-project/`; every `agents/*.md` `implements:` references an existing skill; every `skills/*/SKILL.md` has valid YAML frontmatter with `name` + `description`; every `.github/ISSUE_TEMPLATE/*.yml` valid YAML; every internal Markdown link in `docs/*.md` resolves on disk.
- **README Lint status badge** (`actions/workflows/lint.yml/badge.svg`).
- **15 GitHub repository topics** for discoverability: `claude-code`, `claude-plugin`, `opencode`, `mcp`, `research`, `academic-writing`, `literature-review`, `peer-review`, `digital-humanities`, `biblical-archaeology`, `theology`, `ancient-history`, `hermeneutics`, `quarto`, `wiki`.

### Fixed

- **`.claude-plugin/marketplace.json`** — `claude plugin validate` (v2.1.132) rejected two fields. Removed root `displayName` (unrecognized). Changed `"source": "."` to `"source": "./"` (validator requires the explicit relative-path form).
- **`.claude-plugin/plugin.json`** — removed `displayName` and `bugs` (both unrecognized by the validator on 2.1.132). Bug reporting still discoverable via the `repository` URL.
- End-to-end install flow verified: `claude plugin marketplace add ./` → `claude plugin install research-superpowers@leiverkus-research` loads at v0.3.0 cleanly.

---

## [0.3.0] — 2026-05-27

First public release. Combines an optional MCP integration layer, the removal of the legacy OpenCode-commands shims (OpenCode now reads skills natively from `.claude/skills/`), full English internationalisation of all skill prose and templates, and a complete user-facing manual (README, Quickstart, Tutorial, Concepts). **Additive** for MCP and i18n; the removal of `opencode-commands/` is technically breaking for anyone who relied on the slash shortcuts, but they were never published. See [`docs/recommended-mcps.md`](docs/recommended-mcps.md).

### Added

- **`docs/recommended-mcps.md`** — setup guide for both MCPs (install, env vars, Docker stack for SearXNG, version pinning).
- **`docs/migration-v0.2-to-v0.3.md`** — short migration note (no required steps, optional MCP setup, optional new frontmatter fields).
- **Schema entity fields** in `schema/knowledge-frontmatter.schema.json` (and template mirror): `wikidata_qid`, `idai_gazetteer_id`, `gnd_id` — all optional, with regex patterns. Resolvable via `dao-paper-search-mcp.resolve_author` / `resolve_site`.
- **"MCP-Optimierung (recommended)" sections** in 5 skills (`literature-review`, `semantic-wiki-review`, `requesting-peer-review`, `ingest-source`, `drafting-manuscript`) and 1 agent (`literature-scout`). Each follows the soft-preference pattern: name the MCP, point to the manual fallback, never require the MCP.
- **`agents/literature-scout.md` output schema** extended with optional `source_class`, `inline_citation_markdown`, `authoritative_bibliography_line`, `wikidata_qid`, `idai_gazetteer_id` fields.
- **Authority IDs in entity template** — `_beispiel-tel-megiddo.qmd` now shows `wikidata_qid: Q173799` and `idai_gazetteer_id: "2048473"` as examples.
- **"Suspect / aggregator citations" audit category** in `semantic-wiki-review`, plus matching table column in the report format.
- **Cited Evidence Audit with `source_class`** column in `requesting-peer-review` report template.
- **Web-citation form** `[(domain — title)](url)` documented in `drafting-manuscript` Citation Rules.

### Changed

- `.claude-plugin/plugin.json` — version 0.2.0 → 0.3.0; description amended with "MCP-aware".
- `templates/research-project-template/CLAUDE.md` — added "Recommended MCPs für DAO-Workflow" subsection after the Zotero-MCP block.
- `docs/README.md` — bullet added under "What it does" naming both MCPs.
- `docs/skill-authoring.md` — new "Optional MCP integration" subsection documenting the soft-preference pattern.
- `docs/README.md`, `docs/skill-contract.md`, `docs/skill-authoring.md`, `docs/migration-v0.1-to-v0.2.md` — note that both Claude Code and OpenCode discover skills natively from `skills/<name>/SKILL.md`. OpenCode install instruction updated to symlink `skills/` under `.claude/skills/`.

### Removed

- **`opencode-commands/` directory** (all 5 remaining commands: `/ingest`, `/draft`, `/peer-review`, `/lit-review`, `/research-brainstorm`). [OpenCode v1.x](https://opencode.ai/docs/skills/) reads `SKILL.md` files natively from `.claude/skills/<name>/SKILL.md` and exposes a built-in `skill` tool. The slash-shortcut shims added no UX value over natural-language triggering or `skill({ name: ... })`. The Command artefact type is gone from the SOT pattern (`docs/skill-contract.md` now describes two types: Skill + Agent).

### Internationalisation & Manual

- **All skill prose, template content, and example project translated to English.** Domain-specific German terms (`*Quellenkritik*`, `*Formgeschichte*`, `*Forschungsstand*`) kept italicised on first use where they are standard. Frontmatter field names, JSON keys, BibTeX keys, and slugs are English.
- **New top-level `README.md`** — GitHub frontpage with hero, Why / Who / Install, 30-second example, skill topology table, docs wayfinder.
- **`LICENSE`** — MIT, Patrick Leiverkus, 2026 (the manifest already declared MIT; this is the canonical file).
- **`.gitignore`** — Python / Node / OS / Quarto outputs.
- **`CONTRIBUTING.md`** — language convention, PR verification commands (including `claude plugin validate --strict`), release procedure, skill-authoring quick reference.
- **`docs/installation.md`** — comprehensive step-by-step installation guide for non-technical users: prerequisites with version checks, three install paths (marketplace, GitHub URL, local clone), OpenCode path, verification, troubleshooting, uninstall.
- **`docs/quickstart.md`** — five-minute onboarding from install to first ingest.
- **`docs/tutorial.md`** — end-to-end walkthrough on a realistic mini-project (Iron Age IIA chronology), every phase narrated, methodology branching demonstrated.
- **`docs/concepts.md`** — narrative explainer of SOFT-GATE, methodology branching, SOT pattern, structural vs semantic review, MCP soft preference.

### Marketplace preparation

- **`.claude-plugin/marketplace.json`** — self-hosted marketplace manifest. End users can register the marketplace with `/plugin marketplace add leiverkus/research-superpowers`, then `/plugin install research-superpowers@leiverkus-research`. Same path used for community-marketplace submission.
- **`.claude-plugin/plugin.json` extended** with `displayName`, `homepage`, `repository`, `bugs` URLs and additional keywords (`ancient-history`, `hermeneutics`, `pre-registration`, `soft-gate`, `mcp`) for marketplace discovery.
- **README install section rewritten** for first-time Claude Code plugin users: leads with the `/plugin marketplace add` flow, lists prerequisites, points to the comprehensive guide.

### Fixed

None.

---

## [0.2.0] — 2026-05-27

Architecture consolidation. **Breaking** — bump major-zero version because public skill/command surface changes.

### Breaking changes

- **HARD-GATE → SOFT-GATE.** All `<HARD-GATE>` blocks in skills are replaced by `<SOFT-GATE>` blocks that prompt the user for a written override reason and log it to `knowledge/_meta/gate-overrides.log` instead of blocking. Affected skills: `brainstorming-research`, `writing-research-plan`, `literature-review`, `ingest-source`, `executing-research-plan`, `drafting-manuscript`, `requesting-peer-review`, `finishing-a-research-project`, `wiki-lint`.
- **`critical-thinking` skill removed.** Cross-cutting content folded into `executing-research-plan` (method selection) and `requesting-peer-review` (evidence audit). Remove direct invocations.
- **5 OpenCode commands deleted:** `/execute-plan`, `/finish-project`, `/grant-finder`, `/research-plan`, `/wiki-lint`. The underlying skills remain available via the `Skill` tool; the slash shortcuts added no value over the natural skill trigger.
- **Pre-registration no longer universal.** With `methodology: hermeneutic` (default), `writing-research-plan` produces a `status: ready` plan with research question + method sketch + expected sources — no frozen hypothesis. Only `methodology: quantitative` (or quantitative tasks within `mixed`) require full pre-registration.
- **Wiki lint `bibliography` no longer required.** `scripts/lint-wiki.py` previously required `bibliography` in every page's frontmatter, contradicting the docs. The field is now correctly optional. Pre-existing pages that omitted it will now pass.

### Added

- **`schema/knowledge-frontmatter.schema.json`** — central JSON Schema Draft-07. Single source of truth, mirrored into `templates/research-project-template/schema/` for project-level use.
- **`schema/README.md`** documenting consumers and sync.
- **`docs/skill-contract.md`** formalising the Skill-as-SOT pattern: Skills declare `inputs:` / `outputs:` / `agents:` in frontmatter; Agents and Commands are thin pointers.
- **`docs/migration-v0.1-to-v0.2.md`** — step-by-step project migration guide.
- **`skills/semantic-wiki-review/SKILL.md`** — new skill for the LLM content audit previously promised (but never implemented) by `wiki-lint`. Manual trigger, no CI gate.
- **`hooks/session-context.md`** — compact skill index (~25 lines) injected at SessionStart. Replaces the full SKILL.md inject from v0.1.
- **`templates/research-project-template/.vscode/settings.json` `yaml.schemas`** mapping for live frontmatter validation in VS Code.
- **`templates/research-project-template/CLAUDE.md` frontmatter** declaring project-level `methodology`, `discipline`, `languages`.
- **Gate-override reporting** in `scripts/lint-wiki.py`. New `=== Gate-Overrides ===` block surfaces the override rate over the last 10 entries; warns above 30 %.
- **Phase-flow back-edges** in `docs/phase-flow.md`: `ingest → plan`, `draft → execute`, `peer → draft` as legitimate hermeneutic iteration.
- **Sharp boundary documentation** between `literature-review` (search → `input/bibliography/`) and `ingest-source` (intake → `knowledge/`).

### Changed

- **Agents reduced** from ~82 to ~60 lines average. All 6 agents declare `implements: <skill-name>`; procedural content lives in the implemented skill.
- **OpenCode commands reduced** from 10 (avg ~55 lines) to 5 (≤ 10 lines each).
- **`hooks/session-start`** now loads `hooks/session-context.md` (~1.5 KB) instead of `using-research-powers/SKILL.md` (~7.6 KB). 80 % reduction in per-session token cost.
- **`skills/using-research-powers/SKILL.md`** — authoritarian language (`<EXTREMELY-IMPORTANT>`, "YOU DO NOT HAVE A CHOICE") replaced with sober discipline guidance.
- **`docs/frontmatter-schema.md`** slimmed from 122 to ~30 lines; narrative pointer only.
- **`templates/research-project-template/CLAUDE.md`** — inline frontmatter schema replaced with pointer to `schema/`.
- **`docs/skill-authoring.md`** — SOT-pattern documented; SOFT-GATE template; language convention with DE/EN glossary.
- **`docs/phase-flow.md`** — SOFT-GATE diamonds, methodology-aware gate labels, hermeneutic back-edges.
- **`templates/research-project-template/scripts/lint-wiki.py`** — loads `schema/knowledge-frontmatter.schema.json` instead of hardcoded constants; minimal stdlib Draft-07 validator (no `jsonschema` dep). Removed claims about semantic checks (those live in `semantic-wiki-review` now).
- **5 SOT skills** (`ingest-source`, `drafting-manuscript`, `requesting-peer-review`, `executing-research-plan`, `literature-review`) — added `inputs:`, `outputs:`, `agents:` frontmatter so agents/commands can reference them.

### Removed

- `skills/critical-thinking/` — content dissolved into `executing-research-plan` and `requesting-peer-review` as cross-cutting checklists.
- `opencode-commands/execute-plan.md`
- `opencode-commands/finish-project.md`
- `opencode-commands/grant-finder.md`
- `opencode-commands/research-plan.md`
- `opencode-commands/wiki-lint.md`
- `<EXTREMELY-IMPORTANT>` block in `using-research-powers/SKILL.md`
- Hardcoded `TYPES`, `STATUS_VALUES`, `REQUIRED_FIELDS` constants in `lint-wiki.py`
- Inline YAML frontmatter template in `ingest-source/SKILL.md` (replaced with schema reference + minimal example)

### Fixed

- `lint-wiki.py` `bibliography`-required bug — pages in `examples/example-project/` now pass frontmatter validation (they always should have).

## [0.1.0] — 2026-04-20

Initial release.
