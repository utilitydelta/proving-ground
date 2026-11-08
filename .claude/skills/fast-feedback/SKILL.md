---
name: fast-feedback
description: Pick the cheapest empirical check that can prove or kill a hypothesis, and bound every run in time, memory and CPU. Use before starting any test, sweep, fuzz, proof, mutation or bench run, when writing a brief that runs one, when adding a tier or harness, and when a perf claim needs a number.
---

# Fast feedback

A slow check does not get run, and an untargeted one starves every other run on the machine. The commonest waste: the whole suite where one row would answer, a second sweep started while the first still grinds, a forgotten binary eating a core for an hour. Pick the cheapest tier that can falsify the claim. Climb only when it passes.

## Tiers

| Tier | Typical wall-clock | What | When |
|---|---|---|---|
| probe | seconds | one assertion in scratch, a compile check, a shape diff, one seed replayed from its tape | every hypothesis, every edit |
| targeted | seconds to a minute | the one test, row, seed or bench line the claim needs | every edit, every review point |
| quick | about a minute | `scripts/gate.sh <tree> quick`: unit suites, a few seeds, bounded proofs on changed functions | once the targeted check is green |
| harness | minutes | `scripts/gate.sh <tree> harness`: every harness compiles against the tree, every plant patch still applies and goes red | after a harness or API change; phase end |
| full | minutes and up | `scripts/gate.sh <tree> full`, sweeps, fuzz, whole-folder mutants, soaks | once per phase end, or as a job |

Verdicts are `OK`, `FAIL` or `BLIND`, with times to two decimals. BLIND graded nothing: timeout (124), kill (137), heavy slot busy (75), cannot run (126, 127), build failure. The gate exits 0 when all are OK, 2 on any BLIND, else 1. BLIND is red, never a pass with a caveat. A tier with no budget in `INDEX.md` gets one the first time it runs. A run past its budget: stop it, record it, fix the tier. Never wait longer.

## Every run

The rules are in `AGENTS.md` Compute. The mechanics:

- `scripts/run.sh [-t secs] [-H] [-l log] -- cmd`. Default timeout `RUN_TIMEOUT`; `-t` above it is refused unless `-H`, and `HEAVY_TIMEOUT_MAX` caps `-H`. The exit status is the command's.
- Output homes: `RUN_OUT` (fresh under `.run/out/`) for tapes and results, `.run/tmp/` for copies, `.run/build/` for build caches (`CARGO_TARGET_DIR`, `PYTHONPYCACHEPREFIX`, `PYTHONDONTWRITEBYTECODE`), `.run/logs/` unless `-l`. Nothing builds inside the human repo; a tool that must write its tree runs on a snapshot copy. Evidence the report cites gets copied into the session's `scratch/`.
- `-H` takes a heavy slot. Slots are machine-wide, shared across clones. Exit 75 means every slot is busy: do something else and retry later, or hand it to Factory as a job. Never run it without `run.sh`.
- An agent past its budget finishes the run in flight and reports.
- Bound every driver loop with a step cap, never "until the system settles".

## Briefs

The three items in `AGENTS.md` Compute, plus: anything heavier than the allowed tier comes back as a job command, not a wait.

## Picking a tool by input shape

| The law is over | Use |
|---|---|
| scalars, small structs, fixed short buffers | bounded proofs (a model checker) or exhaustive enumeration: every input, seconds |
| a variable-length decoder or parser | fuzzing with dishonest inputs, judged at fixed offsets, not by round trip |
| effects, crashes, retries, interleavings | `dst` |
| whether the tests can fail at all | mutation testing per `build-method:writing-tests`, on a copy, never the human tree in place; plant patches for laws a mutator cannot reach |
| speed | instruction counts for a gate; pinned wall-clock benches for ranking |

A wide property range rarely draws the edge: give the edge a fixed case. A symbolic length over symbolic bytes blows up a solver; one proof per edge length is cheap.

## Which rows

`scripts/affected.sh [base]` prints the `harness/coverage.tsv` commands for the paths a human diff touches; `--run` runs each through `run.sh` with `TREE` set to the live `HUMAN_REPO`. Harness code reads one tree variable, `TREE`: the gate and `plants.sh` set it to a snapshot or a planted copy, `affected.sh` to the live tree. A command with a hard-coded path grades the wrong code. Every new row runs at every gate config (`AGENTS.md` `## Project`) before it counts: rows green at the round configs go red at the odd ones. A changed area with no row is a coverage gap for Tend or the next Task.

## Checks on checks

They cost compute and tokens too. Add one where a defect escaped the existing checks, not on speculation. The 10x seed rerun and when it is earned: `dst` Compute.

## Numbers

Perf claims follow `build-method:performance-discipline`. Raw output goes to `baselines/`, dated, with the commit it measured. No number, no claim.
