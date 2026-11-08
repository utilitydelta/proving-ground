---
name: dst
description: Deterministic simulation testing. Use when building or running a seeded driver, reference model, history checker, event tapes or fault injection against code that returns effects, when a seed fails and needs reducing to a replayable tape, or when deciding whether a property needs simulation at all.
---

# DST

Crash, retry and interleaving bugs live in schedules no unit test writes by hand. A seeded simulator explores them; a reference model and checker grade every step. The human's side writes simulation-ready code; everything else lives in `harness/`.

## The shape the code under test needs

A core that takes commands and completions and **returns effects** (write this, send that, set a timer) instead of performing them. No I/O, clock, randomness or threads inside it. State valid between any two calls. Flag a drift from this as a one-way door: cheap now, expensive once code builds on it.

## Bot side owns

- **Driver.** Seeded, single-threaded. Calls the core, collects effects, picks the order completions come back. Same seed, same run, byte for byte. Every loop has a step cap.
- **Fault injection at the effect boundary.** Device errors, torn and lost writes, dropped and duplicate messages, stale completions, crashes between any two effects, persistent faults that later clear, callers that stop listening while the effect still completes.
- **Ambiguous external errors.** An external store's error is ambiguous unless its protocol says otherwise: a 5xx may have stored the object. Modelled as definite, the checker blesses a client told "not written" for data the store holds.
- **Reference model and history checker**, independent of the code under test, written from the contract or prior system by an agent that never read the implementation. The core is never its own oracle.
- **Tapes.** Every run records the seed and the ordered event list. A failing seed becomes a fixed tape and a replay test.
- **Liveness.** A rule that blocks progress (an eligibility gate, a debt to repay) gets a check that something eventually proceeds. A safety checker that judges only runs that made progress never sees the runs that stopped.

## The Subject seam

Each simulator owns one `Subject` trait or interface. The reference model implements it directly; real code implements it through a thin adapter. The checker grades every subject from effects and device state alone. New real code gets an adapter onto the existing `Subject`, not a new harness. Never build a generic simulator ahead of its subject: one built that way sat unused while each simulator grew its own seam, and was deleted.

## Internals

The checker reaches internals only through a surface the human chose: `snapshot()` returning ordered, comparable canonical state, and ideally `check_invariants()` naming the broken relationship. Derived structures belong to the check, not the snapshot. A missing surface is a finding asking for it, never a workaround that reaches into private state.

## Green over what?

- **Each scope asserts the shapes it claims occurred.** A scope named for a crash mid-write counts the runs that crashed mid-write. Rig defaults that never produce the shape make a green that means nothing.
- **A model's red tape also runs through the real adapter**, and goes red there.
- **Grade every field an answer carries**, not only its kind, even inside a permissive band.
- **A known red hides the next one.** A driver red on a known defect reruns with that defect filtered out before its other modes count.

## Teeth

- **Mutations as patches.** Each deliberate break (premature ack, skipped version bump, missing repair) fails at a documented seed. A model toggle per load-bearing rule. `scripts/gate.sh <tree> harness` re-applies them.
- **One tape per check** whose only violation is that check. A toggle test that asserts only "violations > 0" lets most checks carry no weight.
- A model column labelled "prior system" gets each branch checked against the code line it cites before a conclusion rests on it.

## Compute

Per `fast-feedback`:

1. **Targeted first.** A red seed replays alone from its tape in seconds. Fix against the tape, not a sweep.
2. **Quick tier:** a handful of seeds, inline.
3. **Sweep:** `scripts/run.sh -H` or a Factory job, with seed count and wall-clock budget written down first.
4. **10x rerun, conditional.** When the sweep is the main proof of a safety rule, rerun green at ten times the seeds before calling the model green: a sweep green at one count has been red at ten times it. It is its own budgeted heavy job, never beside another. Not every sweep earns it.

Likelihood in `risks/` comes from what the real world needs to produce the schedule, never from how many seeds fired.
