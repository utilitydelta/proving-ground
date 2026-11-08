---
name: invariant
description: Invariant mode. Use when the human asks for an invariant session, or to work out what a system promise implies before code builds on it (a fault promise, a delete end condition, an ordering or identity rule). Takes two or three invariants, shows what breaks with executed tapes or tests, prices each in state and risk, and collects the human's ruling by name.
---

# Invariant

Invariants yo-yo when one gets picked up front without its implications: a field added for an easy promise turns into a record that lives forever, and the cost surfaces weeks later when code already builds on it. This mode works a few promises through first.

Two or three per session. Each needs the human's attention with its evidence in front of them.

## Start

1. `scripts/new-session.sh invariant <slug>`.
2. Pick the invariants from the human's ask or `docs/roadmap.md`.
3. For each, collect what exists: `scripts/decisions.py touches <symbol>`, `scripts/risks.py`, the prior system's promise, the code in the human repo and lead.

## Per invariant

One page per invariant in the session folder, `sessions/<session>/invariants/NN-<slug>.md`, in this order:

1. **The promise**, one sentence a client could rely on, and the targets it holds on.
2. **Scenarios**, each executed: a `dst` tape, a probe, a red test. A scenario nobody ran is a guess; mark it or drop it. Targeted runs per `fast-feedback`; a sweep is a budgeted heavy run.
3. **What breaks** without it, or under each variant: the smallest event sequence that ends with a client told something untrue, data lost, or a system that will not start.
4. **Cost in state**: fields, record kinds, bytes per entity, the end condition of each. The pushback questions (`AGENTS.md` Pushback): what ends it, how many at the largest scale, derived or stored, which live decisions collide.
5. **Risks**, scored per `risks/README.md`. 12 and up needs a control; write the case against the control too.
6. **Variants**, numbered, at most three, only where they change code shape. A recommendation.

## Ruling

Show each page with its tapes. The human picks a variant by name. File:

- a decision per ruling (`scripts/new-id.sh decision`), `decided_by: human-informed`, `status: confirmed`, with History lines on every decision it supersedes or collides with;
- a risk entry per scored scenario (`scripts/new-id.sh risk`), with its control or `accepted`;
- a red test or tape for every promise ruled, so the build has something to turn green.

What the human leaves open stays open with the reason. Never confirm on silence.

## End

Run `finish`. `report.md`: each invariant, its ruling or why it stays open, decisions and risks filed, red tests added.
