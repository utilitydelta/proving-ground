---
name: watch
description: Watch mode. Use when the human says watch, monitor or observe, or starts coding in the human repo and wants agents running beside it. Detects risky deltas, proves them with targeted checks, speaks only at one-way doors or time sinks, queues the rest for the debrief. Never edits human code.
---

# Watch

The human is in a long focus session. Silence is the default; every interruption costs a context switch.

## Start

1. `scripts/new-session.sh watch <date>`.
2. Record the human repo HEAD and a one-line summary of uncommitted state in `log.md`.
3. Build the harnesses against the human tree. Broken build: the human is mid-edit; wait.
4. Save checkpoints of whatever shape diffs the project has (public API, type sizes, dependency graph) into `scratch/`.

## Loop

1. Monitor on `scripts/watch-wait.sh sessions/<this-session>/scratch/watch.state 90`. It exits once the human tree changed and has been quiet for 90 seconds, printing the changed paths.
2. Compile check. Broken: go back to 1. Never hypothesise on code that does not build.
3. **Targeted checks only**, each through `scripts/run.sh -t` (`fast-feedback` Probe and Targeted tiers): `scripts/affected.sh --run` for the changed paths (`TREE` is the live human tree; quick tier and below by default; `BLIND affected` means no row covers the change, a gap for the debrief), the shape diffs against the checkpoints, a few seeds or one tape when a `dst` subject is touched. Never a full tier, sweep or whole-folder mutation run per change: the human's machine is also their editor. A full tier runs once, at the human's request or at end, via `scripts/run.sh -H`. Promote new checkpoints only when the diff scripts exited 0.
4. Check changed paths with `scripts/decisions.py trigger <module>` (revisit triggers that fired) and `scripts/decisions.py touches <path>` (provisional calls in that code). A fired trigger gets one reminder and a History line. A change that contradicts a decision is a finding against the decision: ask in the debrief which wins.
5. Read the diff. Each hypothesis goes in `log.md` before testing: what might be wrong, what would prove it. A change that raises nothing gets no log line.
6. Prove or kill it with the cheapest check that can. Killed: log, move on. Confirmed: `scripts/new-id.sh finding <slug> <session>`, fill it, then `triage`.

## What to look for

Weight toward what the human will not see while typing:

- Public shape: a removed or changed public item, a lost thread-safety property. One-way-door hypotheses.
- Formats: wire, on-disk, config. Run client suites when the wire moves.
- Simulation seam, only where `## Project` declares one: I/O, time, randomness or threads crossing it.
- Hot path: a new allocation, copy, lock or dispatch in code a bench covers. Run that bench row.
- Invariants: a mutation path that skips a repair, a version bump, a bound.
- Bot tests newly red: the human broke something (finding) or the test is stale (Tend, never the human).

Style, naming and local structure are two-way doors: note in `log.md` for the debrief, never live.

## Proving it

- Check the effect on the target, not the command's output. A guard that printed nothing proved nothing.
- Before calling a parameter dead or a value always constant, grep every caller.
- Test a generalisation at odd values, not round ones: the round sizes pass while the odd ones panic.
- Grunt work the human wants built is a Task, never Watch work. Write its `goal.md` into a new task session; the human starts it in a fresh context.
- When the human says they are about to commit or publish, re-raise every open item that gets harder to change afterwards: public names, formats, wire shapes.
- A decision the human rules on by name at the terminal is a ruling: `status: confirmed`, `decided_by: human-informed` for a new call, History line with their words.

## Speaking

Only `triage` decides to speak. Then print one block and keep watching; never wait for an answer:

```
[one-way-door] <claim in one line>
evidence: sessions/session-vN-.../findings/NNN-<slug>.md
```

## End

When the human stops or opens a `debrief`: `report.md` with findings ranked and the killed-hypothesis count. Run `finish`.
