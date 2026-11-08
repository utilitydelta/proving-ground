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

Gate stages print OK, FAIL or BLIND. BLIND means the stage did not build or graded nothing. It is never OK, and a gate with a BLIND stage is red.

Measured budgets per tier live in `INDEX.md` with date and machine. A tier with no budget gets one the first time it runs. A run past its budget is a finding about the harness: stop it, record it, fix the tier. Never wait longer.

## Every run

- **Through `scripts/run.sh [-t secs] [-H] [-l log] -- cmd`**: hard timeout (`RUN_TIMEOUT` at most), memory cap (`MEMORY_MAX`), its own log and build-output dir, the command's real exit status. An unbounded driver under a mutant once took the editor down with it; an OOM-killed mutation run once read as a pass.
- **Heavy runs take `-H`**: sweeps, fuzz, proofs, mutants, full suites. `run.sh -H` refuses a run past `HEAVY_JOBS`. Never route around the refusal.
- **Past five minutes it is a job.** No agent waits on a long run. Background it (Factory: `jobs/pending/`) and work on something it does not block. An agent idle behind a long run holds its context past the cache lifetime and pays to rebuild it.
- **Watch the processes.** `ps` for long-running or orphaned test binaries at every agent notification and every 15 minutes while agents run. An agent past its budget finishes the run in flight and reports.
- **Bound every driver loop** with a step cap, never "until the system settles".
- **Scratch.** Each run gets a fresh `mktemp -d` under the session's `scratch/`. Agents never delete in scratch; Tend clears it against `SCRATCH_BUDGET`.

## Briefs

Every brief that runs anything names:

1. the targeted command the agent starts with,
2. the highest tier it may climb to, and when,
3. a wall-clock budget for the agent,
4. that anything past five minutes comes back as a job command, not a wait.

## Picking a tool by input shape

| The law is over | Use |
|---|---|
| scalars, small structs, fixed short buffers | bounded proofs (a model checker) or exhaustive enumeration: every input, seconds |
| a variable-length decoder or parser | fuzzing with dishonest inputs, judged at fixed offsets, not by round trip |
| effects, crashes, retries, interleavings | `dst` |
| whether the tests can fail at all | mutation testing: scoped to the diff per edit, whole folder at phase end |
| speed | instruction counts for a gate; pinned wall-clock benches for ranking |

A wide property range rarely draws the edge: give the edge a fixed case. A symbolic length over symbolic bytes blows up a solver; one proof per edge length is cheap.

## Which rows

`INDEX.md` maps product areas to checks. Run the rows the diff touches. Every new row runs at every gate config (`AGENTS.md` `## Project`) before it counts: rows green at the round configs go red at the odd ones. A changed area with no row is a coverage gap for Tend or the next Task.

## Checks on checks

They cost compute and tokens too. Add one where a defect escaped the existing checks, not on speculation. Rerun a green seed sweep at ten times the seeds only when that sweep is the main proof of a safety rule, as a budgeted heavy job: a sweep green at one count has been red at ten times it.

## Numbers

Perf claims follow `build-method:performance-discipline`: baseline, new number, command, machine. Wall-clock benches move run to run; compare differences of 2x or more, pin to a core, warm the heap, gate on instruction counts. Baselines live in `baselines/`, dated, with the commit they measured. No number, no claim.
