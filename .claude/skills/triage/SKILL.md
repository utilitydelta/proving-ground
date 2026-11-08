---
name: triage
description: Classify a confirmed finding against the human repo and decide whether it interrupts the human now or waits for the debrief. Use after any empirical check confirms a problem, in any mode. Not for unconfirmed hypotheses; prove those first.
---

# Triage

Input is a finding with evidence attached, filed with `scripts/new-id.sh finding`. No evidence: stop, go prove it. A defect in lead or harness code is not a finding: fix it.

## Classes

| Class | Test | Route |
|---|---|---|
| one-way-door | Fixing it later is expensive or impossible: wire or storage format, public API shape, an invariant other code will build on, a simulation seam missing from the core | Now |
| time-sink | The current direction provably fails, and continuing burns the session | Now |
| regression | Measured correctness or perf loss against a baseline | Now if large and on a hot path, else debrief |
| two-way-door | Cheap to change later: style, naming, local structure, a missed idiom | Debrief |

Early in a product's life, format changes are expected. A format change is a door only when it breaks something other code already committed to, or loses information that cannot be recovered.

## Proving an exposure

"Exposed when it should not be" is a claim about what a caller can do, so the evidence is a caller doing it: a probe against the public surface showing a suspect path accepting what the checked path refuses. To prove an item is internal, tighten its visibility in a scratch copy and build every caller; each break names a real external need. Class follows who depends on the surface: only bot code calling it makes tightening a two-way door.

## Before routing Now

- `INDEX.md` precision for the class: if the human has marked recent findings of this kind `noise`, downgrade to debrief.
- `log.md`: already raised this session? One interruption per finding per session.
- Re-run the evidence command once. Flaky evidence is not evidence.
- With a prior system: did it already fix this structurally, and does the product have the structure yet? A hazard with nothing to land on is a debrief note.
- Code the agents suggested: say so in the finding. The human took it on the agents' word.

## Record

Set `class` and `status: open` in the frontmatter. Append the route and reason to `log.md`. Route Now prints per the mode's interrupt rule (`AGENTS.md` Interrupting).
