# Phase Flow

The research workflow as a directed graph. Boxes = phases (skills). Diamonds = SOFT-GATEs. Back-edges = legitimate iteration, not failure.

```dot
digraph research_flow {
    rankdir=TB;
    node [shape=box, style=rounded];

    start [shape=doublecircle, label="Idea / prompt"];
    brainstorm [label="brainstorming-research"];
    design_gate [shape=diamond, label="Design doc\nsigned off?"];
    plan [label="writing-research-plan"];
    prereg_gate [shape=diamond, label="Plan ready?\n(quant: pre-registered,\nherm: ready)"];
    litrev [label="literature-review"];
    ingest [label="ingest-source (loop)"];
    sources_gate [shape=diamond, label="Sources\nsufficient?"];
    execute [label="executing-research-plan"];
    review_gate [shape=diamond, label="Review pass\n(quant: spec+quality,\nherm: synthesis)"];
    synthesis_gate [shape=diamond, label="Synthesis\nstable?"];
    draft [label="drafting-manuscript"];
    peer [label="requesting-peer-review"];
    finish [label="finishing-a-research-project"];
    done [shape=doublecircle, label="Published /\narchived"];

    subgraph cluster_flex {
        label="Flexible skills (context-triggered)";
        style=dashed;
        lint [label="wiki-lint"];
        semrev [label="semantic-wiki-review"];
        grant [label="grant-finder"];
    }

    // Forward (standard run)
    start -> brainstorm;
    brainstorm -> design_gate;
    design_gate -> plan [label="yes"];
    design_gate -> brainstorm [label="no, iterate"];
    plan -> prereg_gate;
    prereg_gate -> litrev [label="yes"];
    prereg_gate -> plan [label="no, refine"];
    litrev -> ingest;
    ingest -> sources_gate;
    sources_gate -> ingest [label="no, more"];
    sources_gate -> execute [label="yes"];
    execute -> review_gate;
    review_gate -> execute [label="no, fix"];
    review_gate -> synthesis_gate [label="yes"];
    synthesis_gate -> draft [label="yes"];
    synthesis_gate -> execute [label="no, more synthesis"];
    draft -> peer;
    peer -> finish;
    finish -> done;

    // Hermeneutic back-edges — legitimate circle, not failure
    edge [color="#1e8449", style=bold, fontcolor="#1e8449"];
    ingest -> plan [label="reading revises\nresearch question", constraint=false];
    draft -> execute [label="writing exposes\nanalysis gap", constraint=false];
    peer -> draft [label="reviewer demands\nrevision", constraint=false];
    edge [color=black, style=solid, fontcolor=black];

    // Flexible skills — advisory, not a phase
    ingest -> lint [style=dotted];
    draft -> lint [style=dotted, label="soft-gate"];
    finish -> lint [style=dotted, label="soft-gate"];
    draft -> semrev [style=dotted, label="before stable"];
    finish -> grant [style=dotted, label="follow-up"];
}
```

## Notes

- **Forward edges** are the idealised path. They are neither mandatory nor sufficient — they structure what is often sensible.
- **Back-edges (green)** are legitimate hermeneutic iteration:
  - `ingest-source → writing-research-plan` — new reading revises the research question. Constitutive of the hermeneutic circle.
  - `drafting-manuscript → executing-research-plan` — writing exposes an analysis gap.
  - `requesting-peer-review → drafting-manuscript` — a reviewer finding requires revision.
- **Pre-registration** applies only when `methodology: quantitative` (fully) or `mixed` (for marked sub-studies). For `methodology: hermeneutic`, `status: ready` is enough — no frozen hypothesis. Deviations on quantitative tasks go into `knowledge/_meta/log.qmd`; downstream results are flagged `status: exploratory`.
- **Sources threshold** (~15 A/B sources for a chapter) is a rule of thumb, not magic. SOFT-GATE override with a justification is fine.
- **Reviews** in `executing-research-plan` are methodology-aware: two-stage (spec + quality) for quantitative tasks, synthesis review for hermeneutic.
- **Dotted edges** are advisory invocations, not mandatory transitions.
- **`critical-thinking`** is no longer a standalone skill (since v0.2). Its content lives as a cross-cutting checklist in `executing-research-plan` (method selection) and `requesting-peer-review` (evidence audit).

## Rendering

```bash
dot -Tpng phase-flow.dot -o phase-flow.png
# or via a Markdown preview with Graphviz support
```
