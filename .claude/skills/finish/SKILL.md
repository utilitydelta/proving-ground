---
name: finish
description: Finish a session. Use at the end of every session in any mode, at the end of a Factory run, or when the human says finish up, wrap up or close out. Cleans the tree, runs the gate, makes docs and skills current for the next agent, keeps the report short, fights slop, passes lint, adds the INDEX line, commits and pushes.
---

# Finish

The next agent arrives cold and reads the repo, not this session. Leave it the current state, short and true. A session that only adds is not finished.

Load `build-method:writing-style` and `build-method:hierarchical-context-docs` first.

## 1. Clean the tree

- `git status --short`. Every untracked or modified file is kept with a reason, moved or deleted. No loose proposal or note files at the repo root: they go in the session folder or `docs/roadmap.md`.
- `git config core.hooksPath` says `scripts/hooks`; if not, `scripts/hooks/install.sh`. Without the hook, scratch gets force-added and the push is refused for size.
- Throwaway tests and bins outside `scratch/` are deleted or promoted with a name that says what they prove. Dead code the session left: delete.
- Scratch over `SCRATCH_BUDGET` (`scripts/lint.py` says): clear finished sessions' scratch, never this one's, one literal `rm -rf sessions/<session>/scratch/<dir>` per entry (`AGENTS.md` Compute).
- Background processes the session started: `ps`, then stop them. No test binary outlives the session. Then `scripts/clean-tmp.sh` clears `.run/tmp`, `.run/out` and `.run/logs`; evidence the report cites lives in `scratch/`, not there.
- The human repo is untouched: `git -C <human repo> status` shows only the human's own changes.

## 2. Gate

The gate judges bot trees at HEAD, so commit the work locally first; step 8 amends that commit and pushes.

- `scripts/gate.sh <tree> quick` and `harness`; `full` too when the session changed a harness or lead code. Its `lint` stage covers this repo's hygiene. Heavy tiers go through `scripts/run.sh -H -t <secs>`, with `-t` taken from the tier's budget in `INDEX.md` `## Tier budgets`, never guessed.
- `scripts/changed-tooling.sh <session base>` says the session touched `scripts/`, `.claude/` or `project.env`: run `scripts/check-tooling.sh quick` (`harness` when a script changed). Otherwise skip it.
- **Factory:** run the quick gate inline; queue `harness` and `full` as jobs (`factory` Long runs are jobs) and exit. The iteration that finds their `.out` writes the verdicts into `report.md` and carries on from step 3. Never wait on them inline.

State each command and its verdicts in `report.md`, stage by stage when any is FAIL or BLIND. BLIND graded nothing and is red. Red is reported red, never smoothed.

## 3. Docs: current state only

For each doc the session touched (`docs/`, `INDEX.md`, `AGENTS.md` `## Project`):

- What is true now and why, once. A decision is a rule plus one sentence. Evidence lives in the session; the doc carries at most one deciding number and a pointer.
- Cut session narrative ("session-vN found", "was changed to"), anything the code says, anything no longer true. One fact, one place. Counts come from a script, dated.
- Each decision the session overturned: its concept is purged from docs, harnesses and skills now, not at the next Tend.
- `INDEX.md` coverage rows and tier budgets match what exists. `docs/ARCHITECTURE.md` links every doc that exists and nothing that does not.

Read `git diff docs/ INDEX.md .claude/` once more: would the next agent miss each added line? If not, cut it.

## 4. Skills

A lesson the session paid for goes into the skill that would have prevented it, as one rule with one clause of evidence. No lesson, no edit. Remove rules the session proved wrong. Merge or prune before adding; `scripts/lint.py` caps skill size.

## 5. Stop doing

Check the session did none of these; one found goes in `report.md` and the next goal:

- Media the human did not ask for.
- A review that checked code against its brief and never questioned the brief.
- A new process rule with no check that refuses its violation.
- A heavy run started untargeted, stacked on another, waited on past five minutes, or left running.

## 6. Report and session files

- `report.md` for the human: outcome first, what it proves and cannot prove, gate result, findings, new decision ids with who made each, what is open for them. Tables over paragraphs. No process story.
- `scraps.md`: every hole and defer, one line each, with its owner. `human.md` holds only statements of intent.
- Findings are defects in human code only, with frontmatter and an evidence command that runs from this repo. A defect in lead or a harness was fixed and is noted in the unit record, not filed.
- Every real choice made, asked or parked has a decision from `scripts/new-id.sh`. For each decision filed or changed, `scripts/decisions.py touches <symbol>` and read every live hit: the new file says whether it supersedes, conflicts or composes; a conflict goes to the human by name. Agent work is locally coherent and globally decoherent unless someone checks.

## 7. Slop check and lint

```
grep -n -P "\x{2014}|key insight|it's worth noting|comprehensive|robust|seamless|delve|leverag|in order to" <files>
```

Also: hedges, fake balance, wrap-up sentences, numbers with no command or file behind them, TODOs without an owner. Fix each. Then `scripts/lint.py`, `scripts/decisions.py check`, `scripts/risks.py check` and `scripts/findings.py check` pass.

## 8. Commit and push

Add the session line to `INDEX.md` `## Sessions`: `session-vN-<mode>-<slug>: outcome`, under 150 characters. One commit for the session: code, docs, skills, session folder. Push with `scripts/push.sh`, never bare `git push`: it refuses the template origin. Tell the human the commit and the one or two things they need to decide.
