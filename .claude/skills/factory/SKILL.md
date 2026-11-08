---
name: factory
description: Factory mode, one iteration of an unattended build-out. Use when the prompt says "Load the factory skill and run one iteration" (or "Pause iteration"), which is how scripts/factory.sh starts every claude -p orchestrator. Reads the session's state, advances one unit by its stages, hands long runs to the runner as jobs, writes state at every boundary and exits.
---

# Factory

`scripts/factory.sh <session> --until <deadline>` is a bash loop: a fresh `claude -p` per iteration, queued jobs run between iterations with no Claude process alive, sleeps through usage limits. It needs Linux, bwrap (the jail that mounts the human repo read-only) and Claude Code. Long interactive orchestrators stall at every quota hit and die with their parent. Here the disk is the orchestrator's memory and every iteration is disposable.

You orchestrate one iteration. Nobody is at the terminal. Everything waits for `report.md`.

## Carried over

Load `task` and follow its Build section. Each unit gets a weight (`AGENTS.md` Weight) on its queue line; the weight decides which stages below run in full. Units stay small (one module or slice, outside in, ending compiling and green) because reviewers need them small. The build lives in `LEAD_REPO`; units fast-forward `LEAD_TRUNK`. A write to the human repo fails with EROFS: the boundary working, never a problem to route around.

## The iteration

1. Read `session-state.md`, the tail of `log.md`, and every `jobs/done/*.out` and `.exit` newer than the last iteration line.
2. Human repo HEAD moved since the `human head:` line? Rebase lead onto it. Conflict: `Status: blocked` with the files, exit.
3. Under 30 minutes to the deadline: run `finish`, set `Status: done`, exit.
4. Prompt says `Pause iteration`: run the pause (below), go to 7. Otherwise take the first unit in `## Queue` not in `## Waiting` whose `job:` is `none` or has its `.out`. No such unit:
   - some unit waits on a job: exit without touching state; the runner runs the job and starts the next iteration;
   - every remaining unit waits on a door: follow Doors.
5. Run the unit from its recorded stage. Write the stage to `session-state.md` before launching its agents and again when it ends; a killed iteration resumes there.

   | Stage | Work |
   |---|---|
   | scope | Slice the next part of `goal.md` into units with their weight: implied parts against the prior system, prior art from at least one other system (cited, borrowed or rejected). Full weight adds the premise review and the Pushback gate. Every hole gets a queue entry; a hole noted without one is lost |
   | oracle | Full weight: blind tests against the unit's contract, transcript audited. Plants red before any green counts. Every row at every gate config |
   | build | Implementer in lead, outside in, ends compiling with targeted and quick tiers green |
   | review | Reviewers per the weight row, in parallel, each planting in its own `git archive` copy, never the unit's worktree |
   | triage | Do items back to build, up to the loop cap in `AGENTS.md` `## Project`; leftovers to `scraps.md` and an ignored red test. A fault scenario is a scored risk first; under 12 it does not widen the unit. A defect in lead is fixed, never filed as a finding |
   | gate | `scripts/gate.sh <lead> harness` and `full`, as jobs. A BLIND stage is red |
   | commit | Write the unit record, fast-forward `LEAD_TRUNK`, push, commit this repo, move the unit to `## Done` |

6. **One unit per iteration.** Stop after it completes, or earlier when context is heavy: a fresh iteration costs less than a compaction that drops rules. **Never end a turn while a subagent runs**: `-p` exits on the first final answer and the agent's work is lost. Wait for every agent, then write state, log and commit.
7. Append one line to `log.md`: unit, stages advanced, what is next.

## Long runs are jobs

Anything heavy (past `RUN_TIMEOUT`: harness and full gate, sweeps, whole-folder mutants, fuzz, proofs, soaks) is a job, never a wait. An agent waiting on a long run holds its context past the cache lifetime and pays to rebuild it.

```bash
# jobs/pending/<unit>-<what>.sh
# timeout: 1800
scripts/gate.sh ../lead full
```

The header sets the limit; then one command, output to stdout, exiting with its real status, never a closing `exit 0`. Jobs share `scripts/run.sh` heavy slots with everything else on the machine; a job that finds the slots busy is requeued, not failed. Record the job name on the unit's queue line and move on or exit.

Every subagent brief adds to the `fast-feedback` brief items: inline runs stop at the quick tier, anything heavier comes back as a job command.

## Pause iterations

Agents left alone build unit after unit with nobody asking whether the last three still fit. After every 3 units the prompt says `Pause iteration`, and nothing new is built. Two fresh agents run in parallel:

- **Tend** (`tend`, aimed at lead and this session's tests): `scripts/plants.sh` over every plants dir, duplication across recent units, dead paths, house-rule survivors, tests that kill no mutants, stale docs.
- **Think**: gets `goal.md`, the lead diff since the last pause, decisions filed since, `scraps.md`, the prior system's docs. No orchestrator summary. Does the queue still build the goal, in what order? Does every hole have a queue entry or a decision? Which provisional decision is now load-bearing? What refactor makes the next units smaller? What should be cut?

Fixes and refactors go to the front of `## Queue` as units. Log `scripts/decisions.py provisional` against the last pause's count; growth goes in `report.md` with the load-bearing ones named. End with `- pause-<n> <what changed>` in `## Done`; a pause that changes nothing says why.

## Unit records

`units/<unit-id>.md` (`sessions/README.md`) before a unit counts as done; the runner stops on a done unit without one. A later unit that changes this one appends to its `## Changed by`.

## Doors

A one-way door becomes at most three variants on lead branches `<unit>-<variant>`. The unit goes to `## Waiting` with the decision id, and the iteration moves to the next independent unit. When every remaining unit waits on a door: `Status: blocked`, a `report.md` line per door, exit.

## session-state.md

```markdown
Status: building
human head: <sha>
lead head: <sha>

## Queue
- <unit-id> <one line> | weight: <full|middle|plain> | stage: <stage> | job: <name or none>

## Waiting
- <unit-id> D-NNN: <variants>

## Done
- <unit-id> lead <sha>
```

`Status: done` or `blocked` stops the runner. Three iterations in a row that leave this file unchanged stop it too.

A session is one runner run, bounded by its deadline and ending in `finish`. The next session starts from this one's carry-over (queue, waiting, heads), never by extending it.
