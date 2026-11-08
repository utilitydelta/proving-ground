# Agent rules

The bot side of a human-gated codebase: agents build the tooling that proves their code correct and keep the provenance record; the human writes the production code. Each rule lives once, here or where this file points. Orientation: `INDEX.md`, then `docs/ARCHITECTURE.md`, then the human repo, the truth.

## Project

Fill in with `project.env` when adopting; `scripts/lint.py --adoption` fails while a placeholder is left.

- **Human repo:** `<path>`, and what it is in one line.
- **Lead repo:** `<path>` or none.
- **Targets** and **gate configs:** `<platforms, sizes and flags every new test row runs at>`. Green at one config is not green.
- **Simulation seam:** `<where effects cross in the human code: a HAL, a repository interface, an IO trait; or none yet>`. `dst` and `watch` flag effect drift only at a declared seam.
- **Workload shapes:** `<docs/workload-shapes.md, written by the human; or none>`.
- **Prior system:** `<path>` or none. Its promises hold unless the human drops them by name.
- **Loop cap:** `<3>` review loops per phase or unit (`build-method:implementation-loop`).
- **Close-off trigger:** run `closeoff` once `scripts/decisions.py provisional` lists more than `<N>`.
- **House rules:** `<project code rules, one line each with its reason>`.
- **Semantic search:** `<collections, or none>`.

## The boundary

- **Never write to the human repo.** No fix, typo, format pass or generated file. Read it, build it out of tree. `scripts/run.sh` points build caches at `.run/build/`; an install or build that must write into its tree (npm install, dotnet obj/bin, pip -e, make) runs on a snapshot copy.
- A problem in human code is a finding, never an edit. A defect in lead or harness code is fixed by agents and noted in the unit record.
- An experiment needing changed human code edits a copy in the session's `scratch/`. The copy never goes back; its diff is evidence. No symlinks to it, no git inside the copy.
- A lead repo, if any, is rebased onto the human's tree whenever it moves. Nothing reaches the human repo except through the human's typing.
- Bot tests stay here; the report lists ones worth promoting.

## Evidence before speech

No claim reaches the human without an empirical check: a failing test, a probe, a bench delta, a tape. Reading code yields hypotheses; one that fails its check is logged and dropped. No size or cost claim without a measurement or a cited source.

- **Green is not self-graded.** A check counts once it has gone red on a planted fault. Plants are patches, each proven through its coverage row (format: `harness/README.md`); one that no longer applies is a harness gone blind. For plain logic, mutation testing on the diff does the planting (`build-method:writing-tests`).
- **Green over what?** A row asserts the shapes it claims occurred; a model's red tape also runs through the real adapter. Detail: `dst`.
- **A known red hides the next one.** Rerun with it filtered before other modes count.
- **Loosening review.** A harness edit that turns red rows green gets a fresh agent and a plant the old check caught.
- **The code under test is never its own oracle.** Blind oracles per `build-method:implementation-loop`. Added here: blind agents' transcripts are audited, and one read of the implementation voids the blindness.
- **The gate is the truth.** `scripts/gate.sh <tree> [quick|harness|full]` runs `lint` and the product stages, one line each: `OK|FAIL|BLIND <stage> <secs>s`. BLIND graded nothing: timeout, kill, busy heavy slot, cannot run, build failure. Exit 0 all OK, 2 any BLIND, else 1. A new test file gets a gate stage and a `harness/coverage.tsv` row in the same commit; the harness tier proves each row green on a clean copy and red with its plant. A red suite outside the gate joins it or goes. This repo's scripts answer to `scripts/check-tooling.sh`.
- **One tree variable.** Harness code reads `TREE` and imports the product from it at run time, never through a static path (`harness/README.md`), so plants and snapshots grade the code they name. The gate sets `TREE` to a snapshot (the human tree with uncommitted edits, printed as HEAD plus a dirty hash) and runs stages from this repo's committed snapshot, so uncommitted tooling edits cannot change a verdict. `scripts/affected.sh` and Watch set `TREE` to the live `HUMAN_REPO`.

## Weight

Process scales with what a change touches. Heaviest matching row wins; the pick goes in `goal.md` `## Weight` or the unit's queue line with one clause of why.

| The change touches | Process |
|---|---|
| A durable format, persistent state, concurrency, or a promise | Premise review, blind oracle, plant patches, two reviewers (one frame-free), unit record with `## Review` |
| A risk scored 5 to 11, or a public contract | One frame-free reviewer, plant patches |
| Plain logic | Targeted test, mutation testing on the diff |

A frame-free reviewer gets goal, code and primary sources: no hunt list, no orchestrator summary. Every lead unit gets a unit record.

## Compute

`fast-feedback` picks the tier.

- **Targeted first.** The one test, row, seed or bench line the claim needs; `scripts/affected.sh [base] [--run] [--tier quick|harness|full]` prints the coverage rows a human diff touches (up to quick by default), or runs them. Full tiers, sweeps, fuzz, proofs and mutants run once, at phase end or in the gate.
- **Every run goes through `scripts/run.sh`**: timeout, memory cap, own log, real exit status. Past `RUN_TIMEOUT` it is heavy: `-H` takes a heavy slot, exit 75 means busy, never route around it. Slots are machine-wide (`HEAVY_DIR`), shared by every clone and project; `HEAVY_TIMEOUT_MAX` caps `-H`.
- **Nobody waits on a heavy run.** Background it (Factory: a job) and work on.
- **Every tier has a measured budget** in `INDEX.md`; an overrun is a harness finding.
- **`ps`** for orphaned binaries at every agent notification and every 15 minutes.
- **Every brief names** the targeted command, the highest tier allowed, and a wall-clock budget.
- **One home per kind of output.** `scripts/run.sh` owns run output under `.run/` (`out/` with a fresh `RUN_OUT` per run, `tmp/`, `build/`, `logs/`); `scripts/clean-tmp.sh` clears it. The session's `scratch/` holds only evidence the agent keeps: a cited tape, an edited copy of human code. Never deleted mid-session; Tend and `finish` clear finished sessions' with one literal `rm -rf sessions/<session>/scratch/<dir>`. `SCRATCH_BUDGET` caps it.

## Modes

One mode per session; load its skill first. Modes, who starts each, and routing: `.claude/skills/README.md`. Tooling, config and repo chores are not sessions: just a commit.

## Sessions

Append-only history, one folder per session from `scripts/new-session.sh <mode> <slug>`. Files, findings fields and unit records: `sessions/README.md`.

- After `finish` a session is frozen, except a finding's `status` and `adopted_in` and a unit record's `## Changed by`.
- **One component at a time, closed completely**: edge cases built or refused by name, tests proving each. A Do open at the loop cap goes to `scraps.md` and the roadmap.
- Every hole lands in the queue, the roadmap or `scraps.md`; a deferred edge case is also an ignored red test.
- Only the next session gets a folder ahead of time; later work goes in `docs/roadmap.md`.

## Findings

A confirmed defect in human code, from `scripts/new-id.sh finding <slug> <session-dir>`. `triage` decides its worth and whether it interrupts. The human marks status in the debrief. Human commits carry nothing bot-related; when an adopted fix lands, agents add `adopted_in: <sha>`.

## Decisions

Each real micro-decision is filed the moment it is made, whoever made it: `scripts/new-id.sh decision <slug>`, fields in `decisions/README.md`.

- **What counts:** a choice that changes behaviour, a contract, a durable shape or a promise. Bookkeeping and measured values go in the log; trivia hides the calls that matter.
- `confirmed` only when the human rules on it by name with recap and code in front of them: Close-off, Invariant, Debrief, or a `human-informed` call. Typing past a line confirms nothing.
- `bot` and `human-asked` calls are provisional. Record and keep working; ask only when one blocks the task. Work built on them lists them in `goal.md` `## Builds on`; a load-bearing one goes to the human first.
- Ask the human about behaviour; settle sizes and caps by measurement.
- A decision that changes an invariant greps every consumer in the same session. A ruling stretched to a new site is a new decision.

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

A goal adding a structure, state, component or format first gets a premise review: a fresh agent with primary sources only (goal, touched code, prior system) says what it breaks, assumes or leaves out.

## Interrupting

Attended: print the finding in the session. Unattended: AskUserQuestion only for a one-way door, a time sink or a blocking decision; the rest waits for `report.md`.

## Rules need checks

A rule that lives only as a paragraph does not hold. A new process rule arrives with a check or joins the unchecked list.

| Rule | Check |
|---|---|
| Never write the human repo | Factory: the bwrap jail mounts it read-only, the hard boundary. Interactive Claude Code: `scripts/hooks/guard-human-repo.sh`, best effort over common write forms (file edits, redirects, in-place editors, copy and archive destinations, git writes), refusing unparseable input or an unset `HUMAN_REPO`. Codex has no hooks. Consider an OS-level sandbox excluding `HUMAN_REPO` for interactive sessions |
| Bounded runs, heavy slots | `scripts/run.sh`, only for runs started through it. A bare command is unchecked |
| Recursive deletes only in session scratch | `scripts/hooks/no-rm-rf.sh` |
| No scratch or huge files in git | `scripts/hooks/pre-commit` |
| Register shapes, scores, triggers | `scripts/decisions.py check`, `scripts/risks.py check`, `scripts/findings.py check` |
| INDEX session lines, frozen sessions, skill size, loose root files, scratch budget | `scripts/lint.py`, the gate's `lint` stage |
| Template adopted, no push to the template | `scripts/lint.py --adoption`, `scripts/push.sh` |
| Harnesses compile, plants still go red, coverage rows catch their plants | `scripts/gate.sh <tree> harness` (its `coverage-plants` stage), `scripts/plants.sh`; lint fails on a missing or empty `harness/coverage.tsv` |
| Targeted runs for a human diff | `scripts/affected.sh` |
| Unit records exist | `scripts/factory.sh` stops |

**Unchecked**, held only by briefs and reviews: no install, formatter or in-tree build inside the human repo in interactive sessions; a new test file getting its gate stage and coverage row; targeted-first beyond what `affected.sh` prints; the 15-minute `ps` cadence; two reviewers on full-weight work; the blind transcript audit; the weight picked.

## House rules

- Durable guidance goes into git, never private agent memory.
- Prose, tests, perf claims, code and docs follow `build-method:` `writing-style`, `writing-tests`, `performance-discipline`, `coding-rules`, `hierarchical-context-docs`.
- Every implementer and reviewer brief repeats the `## Project` house rules and the Compute rules.
- Comments in lead code are for agents: a non-obvious invariant, a decision id, a trap. Never a restatement.
- No self-anthropomorphising in records: "agents" or the session name.
- Skills belong to agents. A session that teaches something improves the skill in its commit: rules, one clause of evidence each.
- `scripts/hooks/install.sh` once per clone.
