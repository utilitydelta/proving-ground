---
name: task
description: Task mode. Use when the human hands over an explicit job, such as "test X end to end", "fuzz the parser", "build a bench for the write path", "build feature Y in lead". Runs the implementation loop in this repo or the lead repo. Findings in human code are reported, never fixed.
---

# Task

## Start

1. `scripts/new-session.sh task <slug>`. Record the human's ask in `human.md`, verbatim.
2. Write `goal.md` with acceptance checks that are empirical: a command red today, green when done. Confirm with the human if they are at the terminal; unattended, proceed and list assumptions at the top.
3. **Delta.** Inventory what exists: `INDEX.md`, semantic search if `AGENTS.md` lists collections, then grep. The gap goes under `## Delta`. Build only the delta.
4. **Builds on.** `scripts/decisions.py touches <path>` for the code the goal touches. Every provisional decision the work rests on goes under `## Builds on`. A load-bearing one goes to the human before the build, not after.
5. **Implied parts.** The human asks for A; A needs B, which the goal never names. List every such part. With a prior system, find its version of each (file and line) and keep it or file the deviation as a decision. Agents that build their own B' without reading the prior B drop promises nobody sees until something built on the flow breaks.
6. **Premise review** when the goal adds a structure, state, component or format: a fresh agent with primary sources only (the goal, the code it touches, the prior system's docs and code), never orchestrator reports. It answers what the goal breaks, assumes or leaves out, with evidence. Each answer becomes a goal amendment, a decision or a rejection with its reason.
7. **Pushback gate** (`AGENTS.md` Pushback) on every call that adds a durable field, creates state with no end condition, drops a promise, or is `human-asked`.

Scope rough goals with `build-method:scout` first when the shape is unclear.

## Build

Run `build-method:implementation-loop` on the session folder. Every brief and review is saved under `briefs/` and `reviews/`. Additions:

- **One component at a time, closed completely**: edge cases built or refused by name, tests proving each. A defer is an ignored red test in the code plus a `scraps.md` line naming the owner. Prose "owed later" is lost.
- **Blind oracle before build.** A separate agent writes tests from the contract and public surface only. Pin shared names (constants, error variants, env vars) in both briefs first. Audit the oracle's transcript for reads of the implementation; a read voids its blindness. Contract amendments change oracle rows through the orchestrator, never the implementer.
- **Crash or concurrency properties** get their `dst` model and checker before the implementer starts. The loop does not write the test that grades it.
- **Planted faults.** No oracle green counts until it goes red on a plant, kept as a patch. A harness edit that turns red rows green gets a loosening review: a fresh agent, a plant per edit that the old check caught.
- **Green over what?** Each row asserts that the shape it claims occurred. A model's red tape also runs through the real adapter. Every field an answer carries is graded, even in a permissive band. A driver red on a known defect reruns with it filtered before its other modes count.
- **Every row at every gate config** before it counts. Every new test file gets a gate stage in the same commit.
- **Trades are graded against `docs/workload-shapes.md`**, never against scenarios picked after the rule was written. Name the shape a trade favours.
- **Two reviewers per phase, in parallel.** One framed, with the hunt list. One frame-free: goal, code, primary sources, "prove this wrong for a real user". Each plants in its own `git archive` copy.
- **Triage review findings.** A fault scenario is a risk entry, scored with `scripts/new-id.sh risk`, before it becomes work. A history a real system can produce (crash, retry, restart, device error, concurrency) gets built and tested. Our own misuse gets one control at the choke point for the class. Reviewers hunt the whole class in one pass.
- **Loop cap: 5 review loops per phase.** A Do still open goes to `scraps.md` and `docs/roadmap.md` with its measurements.
- **One walkthrough test per new component**: its normal life in order, linear, an assert per step, no table. The human's entry point with a debugger.
- **Decisions.** File with `scripts/new-id.sh decision <slug>`, never by reading the folder. A decision is a choice that changes behaviour, a contract, a durable shape or a promise; bookkeeping, layout and values a measurement settles go in the log or unit record. Ask the human about behaviour; settle sizes by measurement. A decision that changes an invariant greps every consumer in the same session.
- Code briefs name `build-method:coding-rules`, `build-method:writing-tests`, the `## Project` house rules and the Compute rules. Comments in lead are for agents only.
- A problem in human code is a finding (`scripts/new-id.sh finding`) plus `triage`, with the failing test kept here. A defect in lead or harness code is not a finding: fix it and say so in the unit record.

## Compute

Per `fast-feedback`:

- **Per edit:** the targeted test or row, then `scripts/gate.sh <tree> quick`, and mutation testing scoped to the diff.
- **Per phase end, once:** `scripts/gate.sh <tree> harness` and `full`, whole-folder mutants, sweeps, through `scripts/run.sh -H`. Past five minutes, backgrounded. Gate a commit from an archive, never a tree an agent is editing.
- Every brief: the targeted command, the highest tier, the agent's wall-clock budget, "never delete in scratch".
- `ps` for orphaned binaries at every agent notification and every 15 minutes.

## Unit records

When a phase lands in lead, write `units/<id>.md` (`AGENTS.md` Sessions): `## Contract`, `## Decisions`, `## Commits`, and `## Review`.

## Unattended

AskUserQuestion only for a one-way door or a decision that blocks the goal; file the answer as `human-asked`. Check a subagent's premise yourself before asking from its report: can an existing structure already answer it?

## End

Run `finish`. `report.md`: what was built, what it proves, what it cannot prove, findings, new decision ids with who made each, prior-system deltas, tests worth promoting. `present` if more is earned.
