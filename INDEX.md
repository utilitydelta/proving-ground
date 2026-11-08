# Index

Maintained by agents. Tend rebuilds it from the tree. A wrong row is a bug. Every agent reads this first, so it stays small: no line past 400 characters (`scripts/lint.py`). Detail goes in the linked doc, never the row.

## Coverage

What covers which part of the product. Watch reads this to pick checks for a diff; Task reads it to find the delta.

| Product area | Check | Tier | Budget | Planted fault it catches | Location |
|---|---|---|---|---|---|

Tier is `probe`, `targeted`, `quick`, `harness` or `full` (`fast-feedback`). A row without a measured budget or a planted fault is not finished.

## Tier budgets

Measured wall-clock per tier on this machine, re-measured at every Tend. A run past its budget is a finding about the harness.

| Tier | Command | Budget | Measured on | Date |
|---|---|---|---|---|
| quick | `scripts/gate.sh <tree> quick` | | | |
| harness | `scripts/gate.sh <tree> harness` | | | |
| full | `scripts/gate.sh <tree> full` | | | |

## Sessions

One line each, under 150 characters: `session-vN-<mode>-<slug>`: outcome. Detail lives in the session's `report.md`.

## Precision

How often each kind of call holds up. Decisions: `scripts/decisions.py stats` (overturn rate by `decided_by`), pasted here with its date at each Tend. Findings by class and status:

| Class | Open | Adopted | Rejected | Noise |
|---|---|---|---|---|
| one-way-door | 0 | 0 | 0 | 0 |
| time-sink | 0 | 0 | 0 | 0 |
| regression | 0 | 0 | 0 | 0 |
| two-way-door | 0 | 0 | 0 | 0 |
