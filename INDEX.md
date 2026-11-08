# Index

Maintained by agents; Tend rebuilds it from the tree. A wrong row is a bug. Every agent reads this first, so it stays small: detail goes in the linked doc, never the row.

## Coverage

`harness/coverage.tsv` maps human-repo paths to checks, with tier, measured budget and the plant each row proves it catches (columns in `harness/README.md`). `scripts/affected.sh [base] [--run]` prints the targeted commands for a diff, or runs them. Watch picks checks from it; Task reads it to find the delta.

## Tier budgets

Measured wall-clock per tier on this machine, re-measured at every Tend. Fill from `scripts/gate.sh` output: the `<secs>s` on each stage line, summed per tier. Empty until measured; never a guess. A run past its budget is a finding about the harness.

| Tier | Command | Budget | Measured on | Date |
|---|---|---|---|---|
| quick | `scripts/gate.sh <tree> quick` | | | |
| harness | `scripts/gate.sh <tree> harness` | | | |
| full | `scripts/gate.sh <tree> full` | | | |
| mutants | Tend's mutation run over files changed since the last Tend, per file | | | |

## Sessions

One line each, under 150 characters (`scripts/lint.py`): `session-vN-<mode>-<slug>: outcome`. Detail lives in the session's `report.md`.

## Precision

How often each kind of call holds up, pasted with its date at each Tend and debrief. Decisions: `scripts/decisions.py stats` (overturn rate by `decided_by`). Findings by class and status, from `scripts/findings.py stats`:

| Class | Open | Adopted | Rejected | Noise |
|---|---|---|---|---|
| one-way-door | 0 | 0 | 0 | 0 |
| time-sink | 0 | 0 | 0 | 0 |
| regression | 0 | 0 | 0 | 0 |
| two-way-door | 0 | 0 | 0 | 0 |
