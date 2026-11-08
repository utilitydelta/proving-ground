---
name: task
description: Task mode. Use when the human hands over an explicit job, such as "test X end to end", "fuzz the parser", "build a bench for the write path", "build feature Y in lead". Creates the session, picks the weight, runs the implementation loop in this repo or the lead repo. Findings in human code are reported, never fixed.
---

# Task

## Start

1. `scripts/new-session.sh task <slug>`. Record the human's ask in `human.md`, verbatim, and in `goal.md` `## Ask`.
2. `## Acceptance`: empirical checks, each a command red today and green when done. Confirm with the human if they are at the terminal; unattended, proceed and list assumptions at the top.
3. `## Delta`: inventory what exists (`INDEX.md`, `harness/coverage.tsv`, semantic search if listed, then grep). Build only the gap.
4. `## Builds on`: `scripts/decisions.py touches <path>` for the code the goal touches. A load-bearing provisional decision goes to the human before the build.
5. **Implied parts.** The human asks for A; A needs B, which the goal never names. List every such part. With a prior system, find its version of each (file and line) and keep it or file the deviation as a decision. An agent that builds its own B' without reading the prior B drops promises nobody sees until something built on the flow breaks.
6. **Weight** (`AGENTS.md` Weight): pick the row, write it in `goal.md` `## Weight` with one clause of why. It decides which of the steps below run.
7. Full weight: premise review and the Pushback gate (`AGENTS.md` Pushback) before any build.

Scope rough goals with `build-method:scout` first when the shape is unclear.

## Build

Run `build-method:implementation-loop` on the session folder, loop cap from `AGENTS.md` `## Project`. Every brief and review is saved under `briefs/` and `reviews/`. What this repo adds:

- **Blind oracle** (full weight): pin shared names (constants, error variants, env vars) in both briefs first. Audit the oracle's transcript for reads of the implementation. Contract amendments change oracle rows through the orchestrator, never the implementer.
- **Crash or concurrency properties** get their `dst` model and checker before the implementer starts. The loop does not write the test that grades it.
- **Plants** (full and middle weight): a patch per law in `harness/<language>/plants/`, red before any green counts. Plain logic: mutation testing on the diff instead (`build-method:writing-tests`).
- **Every row at every gate config** before it counts. A new test file gets a gate stage and a `coverage.tsv` row in the same commit.
- **Trades** are graded against `docs/workload-shapes.md` when it exists. Name the shape a trade favours.
- **Reviewers per the weight row.** The frame-free one gets goal, code and primary sources and "prove this wrong for a real user". Each reviewer plants in its own `git archive` copy.
- **Review findings.** A fault scenario becomes a scored risk (`scripts/new-id.sh risk`) before it becomes work. A history a real system produces (crash, retry, restart, device error, concurrency) gets built and tested. Reviewers hunt the whole class in one pass.
- **One walkthrough test per new component**: its normal life in order, linear, an assert per step, no table. The human's entry point with a debugger.
- **Decisions** as they happen, per `AGENTS.md` Decisions.
- Code briefs name `build-method:coding-rules`, `build-method:writing-tests`, the `## Project` house rules and the Compute rules.
- A problem in human code is a finding (`scripts/new-id.sh finding`) plus `triage`, with the failing test kept here.

## Compute

Per `fast-feedback`. Per edit: the targeted row (`scripts/affected.sh` for human diffs), then `scripts/gate.sh <tree> quick`. Per phase end, once: `harness` and `full` gates and whole-folder mutants, `run.sh -H`, backgrounded.

## Unit records

When a phase lands in lead, write `units/<id>.md` (`sessions/README.md`).

## Unattended

AskUserQuestion per `AGENTS.md` Interrupting; file the answer as `human-asked`. Check a subagent's premise yourself before asking from its report: can an existing structure already answer it?

## End

Run `finish`. `report.md`: what was built, the weight and why, what it proves and cannot prove, findings, new decision ids with who made each, prior-system deltas, tests worth promoting. `present` if more is earned.
