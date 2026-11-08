# Agent rules

The bot side of a human-gated codebase: agents build the tooling that proves their code empirically correct and keep the provenance record; the human writes the production code (README.md says why). Each rule lives once, here or where this file points.

## Project

Fill in when adopting, with `project.env`; `scripts/lint.py --adoption` fails until both are done.

- **Human repo:** `<path>`, and what it is in one line.
- **Lead repo:** `<path>` or none.
- **Targets** and **gate configs:** platforms, sizes and flags every new test row runs at. Green at one config is not green.
- **Simulation seam:** where effects cross in the human code (a HAL, a repository interface, an IO trait), or "none yet". `dst` and `watch` flag effect drift only at a declared seam.
- **Workload shapes (optional):** `docs/workload-shapes.md`, written by the human. Trades are graded against these, never against scenarios picked after the rule.
- **Prior system:** `<path>` or none. Its promises hold unless the human drops them by name.
- **Loop cap:** 3 review loops per phase or unit (`build-method:implementation-loop`). Raise it here only with a reason.
- **Close-off trigger:** run `closeoff` once `scripts/decisions.py provisional` lists more than `<N>`.
- **House rules:** project code rules, one line each with its reason.
- **Semantic search:** collections, or none.

## The boundary

- **Never write to the human repo.** No fix, typo, format pass or generated file. Read it, build it, test against it.
- A problem in human code is a finding, never an edit. A defect in lead or harness code is fixed by agents and noted in the unit record.
- An experiment needing changed human code edits a copy in the session's `scratch/`. The copy never goes back; its diff is evidence. No symlinks to the human repo, no git inside a nested scratch copy.
- A lead repo, if any, is rebased onto the human's tree whenever it moves. Nothing reaches the human repo except through the human's typing.
- Bot tests stay here; the report lists ones worth promoting.

## Evidence before speech

No claim reaches the human without an empirical check: a failing test, a probe, a bench delta, a tape. Reading code produces hypotheses, never findings; a hypothesis that fails its check is logged and dropped. No size or cost claim without a measurement or a cited source: "it's small" is how unbounded state passes five reviews.

- **Green is not self-graded.** A check counts once it has gone red on a planted fault. Plants are patches run by `scripts/plants.sh` (format: `harness/README.md`); one that no longer applies is a harness gone blind. For plain logic, mutation testing on the diff does the planting (`build-method:writing-tests`).
- **Green over what?** A row asserts the shapes it claims occurred, a model's red tape also runs through the real adapter, and a permissive band still grades every field. Detail: `dst`.
- **A known red hides the next one.** Rerun with it filtered before other modes count.
- **Loosening review.** A harness edit that turns red rows green gets a fresh agent and a plant per edit that the old check caught.
- **The code under test is never its own oracle.** Blind oracles per `build-method:implementation-loop`. Added here: blind agents' transcripts are audited, and one read of the implementation voids the blindness.
- **The gate is the truth.** `scripts/gate.sh <tree> [quick|harness|full]` prints `OK|FAIL|BLIND <stage> <secs>s` per stage and exits 0 only when all are OK. A new test file gets a gate stage and a `harness/coverage.tsv` row in the same commit. A red suite outside the gate joins it or goes.
- **The gate runs on a snapshot**: bot trees via `git archive HEAD`, the human tree with its uncommitted edits (it prints human HEAD and a dirty hash). Targeted runs and Watch use the live tree.

## Weight

Process scales with what a change touches. The heaviest matching row wins; the pick goes in `goal.md` or the unit's queue line with one clause of why.

| The change touches | Process |
|---|---|
| A durable format, persistent state, concurrency, or a promise | Premise review, blind oracle, plant patches, two reviewers (one frame-free), unit record with `## Review` |
| A risk scored 5 to 11, or a public contract | One frame-free reviewer, plant patches |
| Plain logic | Targeted test, mutation testing on the diff |

A frame-free reviewer gets the goal, the code and primary sources: no hunt list, no orchestrator summary. Every lead unit gets a unit record, whatever its weight.

## Compute

Harnesses are CPU-heavy. `fast-feedback` picks the tier.

- **Targeted first.** The one test, row, seed or bench line the claim needs; `scripts/affected.sh [base]` prints them for a human diff. Full tiers, sweeps, fuzz, proofs and mutants run once, at phase end or in the gate.
- **Every run goes through `scripts/run.sh`**: timeout, memory cap, own log and build-output dir, real exit status. Past `RUN_TIMEOUT` (300 s) it is heavy: `-H` takes one of `HEAVY_JOBS` slots, exit 75 means busy, never route around it.
- **Nobody waits on a heavy run.** Background it (Factory: a job) and work on something it does not block.
- **Every tier has a measured budget** in `INDEX.md`; overrunning it is a harness finding.
- **`ps`** for long-running or orphaned binaries at every agent notification and every 15 minutes while agents run.
- **Every brief names** the targeted command, the highest tier allowed, and a wall-clock budget.
- **Scratch.** Each run gets a fresh `mktemp -d` under the session's `scratch/`. Nobody deletes scratch during a session. Tend and `finish` clear finished sessions' scratch with the form `scripts/hooks/no-rm-rf.sh` allows: `rm -rf` of a literal path under `sessions/<session>/scratch/`. `SCRATCH_BUDGET` caps the total.

## Modes

One mode per session; load its skill first. Modes, who starts each, and routing: `.claude/skills/README.md`. Tooling, config and repo chores are not sessions: just a commit.

## Sessions

Append-only history, one folder per session from `scripts/new-session.sh <mode> <slug>`. Files, findings fields and unit records: `sessions/README.md`.

- After `finish` a session is frozen, except a finding's `status` and `adopted_in` and a unit record's `## Changed by`.
- **One component at a time, closed completely**: edge cases built or refused by name, tests proving each. A Do open at the loop cap goes to `scraps.md` and the roadmap.
- Every hole lands in the queue, the roadmap or `scraps.md`, and a deferred edge case is also an ignored red test. "Owed by a later unit" in prose is lost.
- Only the next session gets a folder ahead of time; later work goes in `docs/roadmap.md`.
- Every session ends with `finish`.

## Findings

A confirmed defect in human code, written by `scripts/new-id.sh finding <slug> <session-dir>` (never an id read off the folder). `triage` decides its worth and whether it interrupts. The human marks status in the debrief. Human commits carry nothing bot-related; when an adopted fix lands, agents add `adopted_in: <sha>`.

## Decisions

Building the human's intent forces micro-decisions the spec never named. Each real one is filed the moment it is made, whoever made it: `scripts/new-id.sh decision <slug>`, fields in `decisions/README.md`.

- **What counts:** a choice that changes behaviour, a contract, a durable shape or a promise. Bookkeeping, layout and measured values go in the log or unit record; a register flooded with trivia hides the calls that matter.
- `confirmed` only when the human rules on it by name with recap and code in front of them: Close-off, Invariant, Debrief, or a `human-informed` call. Typing past a line confirms nothing.
- `bot` and `human-asked` calls are provisional. Record and keep working; ask only when one blocks the task. Work built on them lists them in `goal.md` `## Builds on`; a load-bearing one goes to the human first.
- Ask the human about behaviour; settle sizes, caps and tunings by measurement. Check a question's premise first.
- A decision that changes an invariant greps every consumer in the same session. A ruling stretched to a new site is a new decision.
- An overturn purges the old concept from docs, harnesses and skills in the same session.

## Risks

Simulators surface edge cases faster than they matter. Each is filed with `scripts/new-id.sh risk <slug>` and scored (`risks/README.md`) before anyone adds state or a rule.

- 12 and up: a control is required, with the case against it written first. 5 to 11: a control, or the human accepts it by name. 4 and under: accept, no new state or rule.
- A control's cost in state is part of the entry. A cheap check on data already carried beats a new field. Misuse only our own code can commit gets one control at the choke point.
- The human may rescore. Their score wins.

## Pushback

Before building on a call that adds a durable field or record kind, creates state with no end condition, drops a promise, or is `human-asked`, a fresh agent answers with an executed check where one exists:

- What ends this state, and how many exist at the product's largest scale?
- Derived or stored?
- Which live decisions does it collide with?

A goal adding a structure, state, component or format first gets a premise review: a fresh agent with primary sources only (goal, touched code, prior system) says what it breaks, assumes or leaves out. An unchecked premise reaches every phase.

## Interrupting

Human at the terminal (Watch, attended Task): print the finding in the session. Unattended: AskUserQuestion only for a one-way door, a time sink, or a decision that blocks the task; the rest waits for `report.md`.

## Rules need checks

A rule that lives only as a paragraph does not hold. A new process rule arrives with a check or joins the unchecked list.

| Rule | Check |
|---|---|
| Never write the human repo | `scripts/hooks/guard-human-repo.sh` (PreToolUse); Factory jail mounts it read-only |
| Bounded runs, heavy slots | `scripts/run.sh` |
| Recursive deletes only in session scratch | `scripts/hooks/no-rm-rf.sh` |
| No scratch or huge files in git | `scripts/hooks/pre-commit` |
| Register shapes, scores, triggers | `scripts/decisions.py check`, `scripts/risks.py check` |
| INDEX session lines, frozen sessions, skill size, loose root files, scratch budget | `scripts/lint.py` |
| Template adopted | `scripts/lint.py --adoption` |
| Harnesses compile, plants still go red | `scripts/gate.sh <tree> harness`, `scripts/plants.sh` |
| Targeted runs for a human diff | `scripts/affected.sh` |
| Unit records exist | `scripts/factory.sh` stops |

**Unchecked**, held only by briefs and reviews: targeted-first beyond what `affected.sh` prints, the 15-minute `ps` cadence, two reviewers on full-weight work, the blind transcript audit, the weight picked.

## Finding your way

`INDEX.md`, then `docs/ARCHITECTURE.md` (follow links down, stop when you have enough), semantic search if listed, then the human repo: the truth for what the product does today.

## House rules

- Durable guidance goes into git. Agents keep no private memory for this project.
- Prose, tests, perf claims, code and docs follow `build-method:` `writing-style`, `writing-tests`, `performance-discipline`, `coding-rules`, `hierarchical-context-docs`.
- Counts in docs come from a script and carry a date.
- Every implementer and reviewer brief repeats the `## Project` house rules and the Compute rules.
- Comments in lead code are for agents: a non-obvious invariant, a decision id, a trap. Never a restatement.
- No self-anthropomorphising in records: "agents" or the session name.
- Skills belong to agents. A session that teaches something improves the skill in its own commit: rules, one clause of evidence each, under the `scripts/lint.py` cap.
- `scripts/hooks/install.sh` once per clone.
