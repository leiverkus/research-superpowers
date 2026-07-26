# Pressure-Testing a Skill

How to find out whether a HARD-STOP or SOFT-GATE actually holds.

Adopted from [obra/superpowers](https://github.com/obra/superpowers)
(`skills/writing-skills/testing-skills-with-subagents.md`), adapted to this
plugin's domain. Companion to [`skill-authoring.md`](skill-authoring.md): that
document says how to *write* a skill, this one says how to find out whether the
thing you wrote survives contact with a model under pressure.

## Why

Every HARD-STOP, SOFT-GATE and red-flag row in `skills/` exists because a model
under pressure would otherwise do the wrong thing. Until it has been tested,
that is a belief, not a finding — and the failure mode is invisible: **a gate
that silently fails to hold looks exactly like a gate that was never needed.**

The plugin's stated purpose makes this sharper than it is for a coding agent.
"Citations get hallucinated", "synthesis pages get written from memory of the
source, not the source itself" — the README names these as the failures the
skills prevent. A skill that does not actually prevent them is worse than none,
because it produces the paperwork of discipline without the discipline.

## The cycle

TDD applied to process documentation:

| Phase | What you do | What it tells you |
|---|---|---|
| **RED** | Run the scenario **without** the skill | What the model does by default — and the *exact words* it uses to justify it |
| **GREEN** | Run the same scenario **with** the skill inlined | Whether the rule holds under that pressure |
| **REFACTOR** | Turn every new rationalisation from GREEN into a red-flag row, re-run | Whether the hole is closed |

**The RED run is not optional.** Without it you do not know whether the skill
prevents the right failure, or any failure — a GREEN pass on a scenario the
model would have handled correctly anyway proves nothing. RED is also where the
value is: the verbatim rationalisation is the raw material for the red-flag row.

## Running one

```bash
python3 scripts/pressure-test.py list
python3 scripts/pressure-test.py prompt ingest-source/substitute-original --phase red
python3 scripts/pressure-test.py prompt ingest-source/substitute-original --phase green
```

Hand each prompt to a **fresh subagent** — fresh context is the whole point; an
agent that watched you set up the test is not a subject. In Claude Code:
`Agent` with `subagent_type: general-purpose`, the prompt pasted verbatim.

Two properties of the generated prompts matter:

- **RED carries the scenario alone.** No skill, no project `CLAUDE.md`. Run it
  from a neutral directory — inside a research project the model inherits the
  conventions and you are no longer measuring a baseline.
- **GREEN inlines the whole SKILL.md** rather than naming it. Naming leaves open
  whether the skill was ever loaded, which is the one thing that would make a
  GREEN result meaningless.

## Scoring

Each scenario declares `compliant:` and `violation:` outcomes in its frontmatter.
Read the verdict against those — never against a general sense of helpfulness.

**One domain difference from the source method.** For a coding agent, "stop and
ask the user" is usually a dodge. Here it is frequently the *correct* answer:
`ingest-source` hard-stops and asks; `add-to-library` refuses to write
unverified metadata and asks. Compliance is therefore never scored as "acted
autonomously and got it right". Some scenarios have several compliant
outcomes and no autonomous one.

Watch for the two results that are easy to misread:

- **Right action, wrong reason.** The model declines the shortcut but never
  names the rule — e.g. it does not ingest the review because "I could not find
  the PDF", not because substituting one is forbidden. Under a slightly
  different scenario it will substitute. Score as a partial pass and say why.
- **Compliance bought by the scenario.** If the scenario telegraphs the answer
  ("the skill says you must…"), a pass measures the scenario, not the skill.
  Keep the rule out of the scenario text — the frontmatter carries it for the
  scorer, and the generated prompt never shows the frontmatter.

## Writing a scenario

Live in `tests/pressure/<skill>/<slug>.md`, frontmatter + body.

```yaml
---
skill: ingest-source           # must match the directory and an existing skill
rule: "the single rule under test, stated as the skill states it"
pressures: [deadline, sunk-cost, plausibility, authority]   # >= 3
compliant:  ["outcome", "outcome"]
violation:  ["outcome", "outcome"]
---
```

- **Three or more combined pressures.** One pressure is not a test — a model
  declines an obviously bad shortcut easily. Real failures happen when a
  deadline, sunk cost, a plausible substitute and someone in authority saying
  "just ship it" arrive together.
- **Force a decision.** Open with *"This is a real scenario, not a hypothetical.
  Decide and act."* and end with lettered options where one is the violation,
  plus an open option so the model is not boxed in.
- **Make the shortcut genuinely attractive.** If option A is transparently
  wrong, you are testing nothing. In `substitute-original` the review really
  does quote the sentence you need.
- **Keep the rule out of the body.** The scenario describes a situation, not a
  policy.

`python3 scripts/pressure-test.py validate` enforces the mechanical parts and
runs in CI.

## Recording results

Under `docs/measurements/<date>-pressure-tests/`, beside the
[semantic-search falsification](measurements/2026-07-17-semantic-search/README.md)
and for the same reason: a result that exists only in a chat session is a result
you will re-derive from scratch. Record per scenario: RED verdict and the
rationalisation **verbatim**, GREEN verdict, and what changed in the skill as a
result. A RED that passes (the model does the right thing unprompted) is worth
recording too — it means that gate is carrying less weight than assumed.
