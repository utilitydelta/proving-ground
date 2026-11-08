---
name: factory
description: Factory mode, one iteration of an unattended build-out. Use when the prompt says "Load the factory skill and run one iteration" (or "Pause iteration"), which is how scripts/factory.sh starts every claude -p orchestrator. Reads the session's state, advances one unit by its stages, hands long runs to the runner as jobs, writes state at every boundary and exits.
---

# Factory

`scripts/factory.sh <session> --until <deadline>` is a bash loop: a fresh `claude -p` per iteration, queued jobs run between iterations with no Claude process alive, sleeps through usage limits. Long interactive orchestrators stall at every quota hit and die with their parent. Here the disk is the orchestrator's memory and every iteration is disposable.

You orchestrate one iteration. Nobody is at the terminal. Everything waits for `report.md`.

## Carried over

Load `task` and follow its Build and Compute sections. Units stay small (one module or slice, outside in, ending compiling and green) because reviewers need them small. The build lives in `LEAD_REPO` (`project.env`); units fast-forward `LEAD_TRUNK`. The human repo is mounted read-only by the runner: a write fails with EROFS. That is the boundary working, never a problem to route around.

## The iteration

1. Read `session-state.md`, the tail of `log.md`, and every `jobs/done/*.out` and `.exit` newer than the last iteration line.
2. Human repo HEAD moved since the `human head:` line? Rebase lead onto it. Conflict: `Status: blocked` with the files, exit.
3. Under 30 minutes to the deadline: run `finish`, set `Status: done`, exit.
4. Prompt says `Pause iteration`: run the pause (below), go to 7. Otherwise take the first unit in `## Queue` not in `## Waiting` whose `job:` is `none` or has its `.out`. Every unit waiting on a door or job: exit without touching state; the runner waits.
5. Run the unit from its recorded stage. Write the stage to `session-state.md` before launching its agents and again when it ends; a killed iteration resumes there.

   | Stage | Work |
   |---|---|
   | scope | Slice the next part of `goal.md` into units: implied parts against the prior system, prior art from at least one other system (cited, borrowed or rejected), premise review by a fresh agent on primary sources, pushback gate. Every hole a scope or review finds gets a queue entry; a hole noted without one is lost |
   | oracle | Blind tests against the unit's contract, transcript audited for reads of the implementation; plant patches red before any green counts; every row at every gate config; each row asserts the shape it claims occurred |
   | build | Implementer in lead, outside in, ends compiling with targeted and quick tiers green |
   | review | Framed and frame-free reviewers in parallel, each planting faults in its own `git archive` copy, never the unit's worktree |
   | triage | Do items back to build, at most 3 loops; leftovers to `scraps.md` and an ignored red test. A fault scenario is a risk entry first, scored. Under 12 and a two-way door: accept (4 and under) or park for the human (5 to 11); it does not widen the unit. A defect in lead is fixed, never filed as a finding |
   | gate | `scripts/gate.sh <lead> harness` and `full`, as jobs. A BLIND stage is red |
   | commit | Write the unit record, fast-forward `LEAD_TRUNK`, push, commit this repo, move the unit to `## Done` |

6. **One unit per iteration.** Stop after it completes, or earlier when context is heavy: a fresh iteration costs less than a compaction that drops rules. **Never end a turn while a subagent runs**: `-p` exits on the first final answer and the agent's work is lost. Wait for every agent, then write state, log and commit.
7. Append one line to `log.md`: unit, stages advanced, what is next.

## Long runs are jobs

Anything past five minutes (harness and full gate, sweeps, whole-folder mutants, fuzz, proofs, soaks) is a job, never a wait. Write `jobs/pending/<unit>-<what>.sh`: one command through `scripts/run.sh` with its own timeout and memory cap, output to stdout, exiting with the command's real status, never a closing `exit 0`. Record the job name under the unit and move on or exit. The runner runs `HEAVY_JOBS` at a time. An agent waiting on a long run holds its context past the cache lifetime and pays to rebuild it.

Every subagent brief names the targeted command, the highest tier it may run inline (quick), a wall-clock budget, and says anything longer comes back as a job command. `ps` for orphaned binaries at every agent notification and every 15 minutes.

## Pause iterations

Agents left alone build unit after unit with nobody asking whether the last three still fit; the result is holes, piles of provisional decisions and quiet failures. After every 3 units the prompt says `Pause iteration`, and nothing new is built. Two fresh agents run in parallel:

- **Tend** (`tend`, aimed at lead and this session's tests): re-apply every plant patch (one that no longer applies or no longer goes red is a harness gone blind), duplication across recent units, dead paths, house-rule survivors, tests that kill no mutants, stale docs.
- **Think**: gets `goal.md`, the lead diff since the last pause, decisions filed since, `scraps.md`, the prior system's docs. No orchestrator summary. Does the queue still build the goal, in what order? Does every hole have a queue entry or a decision? Which provisional decision is now load-bearing? What refactor makes the next units smaller? What should be cut?

Fixes and refactors go to the front of `## Queue` as units, through the full stages. Log the provisional decision count (`scripts/decisions.py provisional`) against the last pause's; growth goes in `report.md` with the load-bearing ones named, so the human knows a close-off is due. End with `- pause-<n> <what changed>` in `## Done`; a pause that changes nothing says why.

## Unit records

`units/<unit-id>.md` before a unit counts as done. The runner stops when a unit in `## Done` lacks any of `## Contract`, `## Decisions`, `## Commits` (contents in `AGENTS.md` Sessions). Briefs and reviews go under `briefs/` and `reviews/`. Add `## Review` (findings and their disposal). A later unit that changes this one appends `- <unit-id>: <what, why>` under `## Changed by`.

## Doors

A one-way door becomes at most three variants on lead branches `<unit>-<variant>`. The unit goes to `## Waiting` with the decision id; the iteration moves to the next independent unit. All waiting: `Status: blocked`, exit.

## session-state.md

```markdown
Status: building
human head: <sha>
lead head: <sha>

## Queue
- <unit-id> <one line> | stage: <stage> | job: <name or none>

## Waiting
- <unit-id> D-NNN: <variants>

## Done
- <unit-id> lead <sha>
```

`Status: done` or `blocked` stops the runner. Three iterations in a row that leave this file unchanged stop it too.

A session is one runner run, bounded by its deadline and ending in `finish`. The next session starts from this one's carry-over (queue, waiting, heads), never by extending it.
