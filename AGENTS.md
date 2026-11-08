# Agent rules

This repo is the bot side of a human-gated codebase. Agents own it: structure, harnesses, docs, skills. It has two jobs: build the tooling that proves agent code empirically correct, and keep the provenance record (sessions, decisions, risks) of everything agents did. The human writes the production code. README.md says why.

## Project

Fill this in when adopting the template. Machine-readable values live in `project.env`.

- **Human repo:** `<path>`. What it is in one line.
- **Lead repo:** `<path>` or none.
- **Targets:** the platforms the product must run on. Harness checks run on every one.
- **Gate configs:** the build or runtime configurations every new test row runs at (sizes, feature flags, platforms). A row green at one config only is not green.
- **Workload shapes:** `docs/workload-shapes.md`, written by the human: the production shapes trades are graded against. Never grade against scenarios picked after the rule was written.
- **Prior system:** `<path>` or none. A predecessor whose promises the product keeps unless the human drops them by name.
- **House rules:** project-specific code rules that every implementer and reviewer brief repeats. One line each, the reason beside it.
- **Semantic search:** collections and what each holds, or none.

## The boundary

- **Never write to the human repo.** No fix, no typo, no format pass, no generated file. Read it, build it, test against it.
- A problem in human code becomes a finding, never an edit. A defect in lead or harness code is not a finding: agents fix it, and the unit record's `## Review` or `## Changed by` says so.
- An experiment that needs changed human code copies it into the session's `scratch/` and edits the copy. The copy never goes back; its diff is evidence. Never symlink the human repo into scratch, and never run git inside a scratch copy nested in this repo.
- With a lead repo: agents build ahead there, rebased onto the human's tree whenever it moves. Nothing reaches the human repo except through the human's own typing.
- Bot tests stay here. Tests worth promoting get listed at the end of the session; the human decides.

## Evidence before speech

No claim reaches the human without an empirical check behind it: a failing test, a probe, a bench delta, a simulator tape. A hypothesis that fails its check is logged and dropped. Reading code produces hypotheses, never findings. No size or cost claim without a measurement or a cited source, the orchestrator's own included: "it's small" is how unbounded state passes five reviews.

- **Green is not self-graded.** A check counts only after it has gone red on a planted fault: a mutation of the code under test that the check exists to catch. Plants live as patches; Tend and every factory pause re-apply them all, and a plant that no longer applies is a harness gone blind.
- **Green over what?** A row or simulator scope asserts that each shape it claims actually occurred. A model's red tape is also run through the real code's adapter. A permissive answer band still grades every field the answer carries. Rig defaults that never produce the shape make a green that means nothing.
- **A known red hides the next one.** A driver red on a known defect is rerun with that defect filtered out before its other modes count.
- **A harness edit that turns red rows green gets a loosening review**: a fresh agent, with a plant per edit that the old check caught.
- **The code under test is never its own oracle.** Reference models, checkers and expected values come from the spec, the contract or the prior system, written by an agent that did not read the implementation. Blind agents' transcripts are audited for reads of it.
- **Two reviewers per unit, one without the orchestrator's frame.** The frame-free one gets the goal, the code and primary sources, no hunt list and no summary.
- **The gate is the truth.** Every harness compiles in `scripts/gate.sh`, and a new test file gets a gate stage in the same commit. A stage that did not build is BLIND, never OK. A red suite outside the gate becomes a stage or gets deleted.

## Compute

Harnesses are CPU-heavy, and untargeted runs are the commonest way a session wastes its day: a whole suite where one row would answer, a sweep for hours where a five-minute targeted run would do.

- **Targeted first.** Run the one test, row, seed or bench line the claim needs. Full tiers, sweeps, fuzz, proofs and mutants run once, at the end of a phase or in the gate, never as the first move.
- **Every run is bounded** through `scripts/run.sh`: a hard timeout (`RUN_TIMEOUT`), a memory cap (`MEMORY_MAX`), its own log path and build-output dir, and the command's real exit status. An unbounded driver once took the editor down with it; an OOM-killed mutation run once read as a pass.
- **Every tier has a measured budget** in `INDEX.md`. A run past its budget is a finding about the harness, not a reason to wait longer.
- **One heavy job at a time** (`HEAVY_JOBS`). Sweeps, fuzz, proofs, mutants and full suites run with `scripts/run.sh -H`, which refuses a second one.
- **Past five minutes it is a job.** No agent sits waiting on a long run; it goes to the background (Factory: the job queue) and work continues on something not blocked by it.
- **Watch the processes.** The orchestrator checks `ps` for long-running or orphaned binaries at every agent notification and every 15 minutes while agents run.
- **Every brief names the targeted command to start with, the highest tier the agent may climb to, and a wall-clock budget.**
- **Scratch has a disk budget** (`SCRATCH_BUDGET`). Agents never delete in scratch: each run gets a fresh `mktemp -d` under the session's `scratch/`, and Tend clears it.
- Checks on checks cost compute and tokens too. Scale a seed sweep by ten before calling a model green only when that sweep is the main proof of a safety rule, and run the rerun as a budgeted job.

`fast-feedback` picks the tier.

## Modes

Every session runs exactly one mode. Load its skill before doing anything else.

| Mode | Started by | Skill |
|---|---|---|
| Watch | Human, coding in another terminal | `watch` |
| Task | Human hands over an explicit job | `task` |
| Factory | Human runs `scripts/factory.sh <session> --until <deadline>`; unattended build-out | `factory` |
| Tend | Human asks for cleanup | `tend` |
| Debrief | Human, after a coding chunk or a finished Task | `debrief` |
| Close-off | Human, to rule on provisional decisions | `closeoff` |
| Invariant | Human, to work two or three system promises before code builds on them | `invariant` |

Work that does not touch the product (tooling, config, repo chores) is not a session: no folder, no INDEX row, just a commit.

## Sessions

The append-only history. One folder per session. After `finish`, a session's files are frozen except two fields written later: a finding's `status` and `adopted_in`, and a unit record's `## Changed by`.

- Folder: `sessions/session-vN-<mode>-<slug>/`. `scripts/new-session.sh <mode> <slug>` picks N and writes the skeleton.
- Every session keeps:
  - `goal.md`: the ask, empirical acceptance checks, the delta against existing coverage, and `## Builds on`: the provisional decisions this work rests on (`scripts/decisions.py touches`).
  - `log.md`: timestamped, append-only. Hypotheses, proofs, kills, decisions taken. Not a narration of edits.
  - `human.md`: the human's statements of intent, verbatim, one line each. Not questions, chat or answers to agents' questions.
  - `report.md`: what the human reads. Short.
  - `scraps.md`: every hole, defer and leftover review item, one line each. A deferred edge case is also an ignored red test in the code, so it cannot be forgotten.
  - `findings/NNN-<slug>.md`: one per confirmed finding.
  - `briefs/`, `reviews/`: every subagent brief and review as a file. Retros need them.
  - `scratch/`: gitignored. Anything worth keeping moves into `harness/`, `scripts/` or the lead repo before the session ends.
- Task and Factory sessions that build in lead add `units/<id>.md`, one per unit: `## Contract` (public surface, invariants with decision ids, named refusals, the walkthrough test), `## Decisions` (every decision filed or leaned on, the alternative and why not, prior-system deltas, prior art), `## Commits` (lead base and head, the tests that pin it). Optional `## Review` and `## Changed by`. The human rewrites from these records; a diff alone loses every "chose X over Y because". The factory runner stops on a done unit without one.
- Factory adds `session-state.md` (status, queue, waiting, done, heads), `progress.md` and `jobs/`.
- **One component at a time, closed completely.** A component is done when its edge cases are built or refused by name and its tests prove them. Loop caps: Task 5 review loops per phase, Factory 3 per unit. A Do still open at the cap goes to `scraps.md` and the roadmap.
- Every hole lands in the queue, the roadmap or `scraps.md`. "Owed by a later unit" in prose is lost.
- Only the next session gets a folder ahead of time. Later work goes into `docs/roadmap.md`. No loose proposal files at the repo root.
- Every session ends with `finish`: clean tree, gate run, current docs, lint, INDEX line, commit and push.

## Findings

A finding is a confirmed defect in human code.

```markdown
---
class: one-way-door | time-sink | regression | two-way-door
status: open | adopted | rejected | noise
touches: <path::Symbol in the human repo, as of the finding>
evidence: <one command that reproduces it from this repo>
---
<Claim in one sentence. Evidence output. What the human might do about it.>
```

The human marks status in the debrief. Human commits carry nothing bot-related. When an adopted finding's fix lands, agents add `adopted_in: <sha>`. `triage` decides what a finding is worth and when it interrupts. Ids come from `scripts/new-id.sh`, never from reading the folder.

## Decisions

The spec is the human's intent. Building it forces micro-decisions the spec never named. Each real one lands in `decisions/NNN-<slug>.md` the moment it is made, whoever made it.

**What counts:** a choice that changes behaviour, a contract, a durable shape, or a promise. Not bookkeeping, file layout or a value a measurement settles; those go in the log or the unit record. A register flooded with trivia hides the calls that matter: the source repo grew past 500 provisional decisions, and the human asked of a batch "do these really need to be documented as decisions?".

```markdown
---
status: open | decided | deferred | confirmed | overturned
decided_by: bot | human-asked | human-informed | none
touches: <path::Symbol, in the human repo, lead or a harness>
revisit_when: <an event: a module lands, a bench exists; never a session number>
session: session-vN
replaced_by: <D-NNN, only when overturned>
---
# D-NNN: <the decision in one line>

<Why, in a sentence or two. Alternatives and why not. Evidence: command or file.>

## History
- <date> <session>: <decided, asked, confirmed at close-off, overturned>
```

- `bot`: decided without asking. `human-asked`: the human answered a bot's question, usually accepting the recommendation without reading the code. `human-informed`: the human ruled with the code or evidence in front of them. `none`: open or deferred.
- `confirmed` only when the human rules on that decision by name with its recap and code in front of them: Close-off, Invariant, Debrief, or a `human-informed` call. Typing past a line confirms nothing.
- `bot` and `human-asked` decisions are provisional. Record and keep working; ask only when a decision blocks the task. Before new work builds on a provisional decision, list it in the goal's `## Builds on`; a load-bearing one goes to the human first.
- Ask the human about behaviour and product calls. Sizes, caps and tunings get settled by measurement. Check a question's premise before asking it.
- A decision that changes an invariant greps every consumer of it in the same session. A ruling stretched to a new site is a new decision.
- An overturn purges the overturned concept from docs, harnesses and skills in the same session.
- `scripts/decisions.py` lists the register; `stats` gives the overturn rate per `decided_by`, the real measure of how far provisional calls can be trusted. Ids come from `scripts/new-id.sh`.

## Risks

Simulators and reviewers surface edge cases faster than they matter. Each scenario goes into `risks/RNNN-<slug>.md` and is scored before anyone adds state or a rule for it. A finding is a defect in human code; a risk is a scenario the design must answer, with a control or without one.

```markdown
---
likelihood: 1-5
consequence: 1-5
score: <likelihood x consequence>
control: <rule, mechanism or obligation that answers it; none>
status: controlled | accepted | proposed | open
decision: <D-NNN behind the control or the acceptance>
session: session-vN
evidence: <command, test or tape that shows the scenario>
---
# RNNN: <the scenario in one line>

<What happens, step by step. Why this likelihood and consequence. The control and its cost in state, or why none.>

## History
- <date> <session>: <raised, scored, rescored by the human, control built>
```

| | Likelihood: what it takes | Consequence: the worst outcome |
|---|---|---|
| 1 | two independent rare faults, or timing no real deployment produces | a blip the user never sees |
| 2 | one rare fault plus specific timing | unavailable for seconds, self-healing |
| 3 | one ordinary fault: crash, restart, dropped message, timeout | unavailable until an operator acts, or errors the client must retry |
| 4 | routine operation: deploy, failover, load spike | a client told something untrue |
| 5 | the happy path, every time | data lost or corrupted |

Adapt the consequence column to the product's worst outcomes when adopting; keep five rows.

- 12 and up: a control is required. 5 to 11: a control, or the human accepts it by name. 4 and under: accept; add no state or rule for it.
- Likelihood comes from what the real world needs to produce the schedule, never from how many seeds fired. Seed counts measure the scheduler.
- A control's cost in state is part of the entry. A cheap check on data already carried beats a new field. Edge cases reachable only through our own misuse get one hard control, not a loop each.
- The human may rescore. Their score wins, and the History says so.
- `scripts/risks.py` lists and lints the register.

## Pushback

Before building on a call that adds a durable field or record kind, creates state with no end condition, drops a promise the product or its prior system made, or is `human-asked`, a fresh agent answers, with an executed check where one exists:

- What ends this state, and how many exist at the product's largest scale?
- Derived or stored?
- Which live decisions does it collide with?

A risk scored 12 or more gets the case against written down before building. A goal that adds a structure, state, component or format first gets a premise review: a fresh agent with only primary sources (the goal, the code it touches, the prior system's docs and code) answers what the goal breaks, assumes or leaves out. Subagents trust their brief; an unchecked premise reaches every phase.

## Interrupting

- **Human at the terminal** (Watch, attended Task): print the finding in the session.
- **Unattended:** ask with AskUserQuestion only for a one-way door, a time sink, or a decision that blocks the task. Everything else waits for `report.md`. Put designs that add permanent code paths to the human early; put numbers to a measurement.

## Rules need checks

A rule that lives only as a paragraph does not hold. Each one that matters has a check that refuses a violation.

| Rule | Check |
|---|---|
| Never write the human repo | Factory jail mounts it read-only |
| Bounded runs, one heavy job | `scripts/run.sh` |
| No variable-built recursive deletes | `scripts/hooks/no-rm-rf.sh` (Claude Code PreToolUse) |
| No scratch or huge files in git | `scripts/hooks/pre-commit` |
| Register shapes, scores, event triggers | `scripts/decisions.py check`, `scripts/risks.py check` |
| INDEX size, skill size, loose root files, scratch budget | `scripts/lint.py` |
| Every harness compiles and every plant still applies | `scripts/gate.sh <tree> harness` |
| Unit records exist | `scripts/factory.sh` refuses to continue |

A new process rule arrives with its check, or is written down as unchecked in this table.

## Finding your way

1. `INDEX.md`: coverage, budgets, sessions, precision. `scripts/decisions.py` and `scripts/risks.py`.
2. `docs/ARCHITECTURE.md`: follow links down, stop when you have enough.
3. Semantic search (if `## Project` lists collections) before building anything: has this been seen before?
4. The human repo's own source and docs: the truth for what the product does today.

## House rules

- Durable guidance goes into git: decisions, docs, this file, the skills. Agents keep no private memory for this project; Tend checks for rules that live only in agent memory.
- Prose follows `build-method:writing-style`. Tests follow `build-method:writing-tests`. Perf claims follow `build-method:performance-discipline`. Code follows `build-method:coding-rules`. Docs follow `build-method:hierarchical-context-docs`: current state only.
- Counts and metrics in docs come from a script and carry a date. A typed count goes stale within a week.
- Every implementer and reviewer brief repeats the `## Project` house rules and the Compute rules.
- Comments in lead code are for agents, not the human: a non-obvious invariant, the decision id behind a shape, a trap. Never a restatement of the code. The human drops them when rewriting; the reason lives in the unit record and docs.
- No self-anthropomorphising in records: say "agents" or name the session (session-v12 did X).
- Skills in `.claude/skills/` belong to the agents. Improve them when a session teaches something, in that session's commit. A skill holds rules, not a lesson log: one clause of evidence per rule, under the size `scripts/lint.py` enforces. Adding a rule means merging or pruning another.
- `scripts/hooks/install.sh` once per clone.
