# Index

Maintained by agents; Tend rebuilds it from the tree. A wrong row is a bug. Every agent reads this first, so it stays small: detail goes in the linked doc, never the row.

## Coverage

`harness/coverage.tsv` maps human-repo paths to checks, with tier, measured budget and the plant each row must catch, proven by the harness tier (columns in `harness/README.md`). `scripts/affected.sh [base] [--run] [--tier quick|harness|full]` prints the rows a diff touches, or runs them. Watch picks checks from it; Task reads it to find the delta.

## Tier budgets

Measured wall-clock per tier on this machine, re-measured at every Tend. Fill from `scripts/gate.sh` output: the `<secs>s` on each stage line, summed per tier. Empty until measured; never a guess. The gate rows below are the kv-python example's numbers on the template author's machine: replace them after adoption. A run past its budget is a finding about the harness.

| Tier | Command | Budget | Measured on | Date |
|---|---|---|---|---|
| quick | `scripts/gate.sh <tree> quick` | 5 s | 0.38 to 0.68 s (lint 0.06, unit 0.19, sim 0.13) | 2026-11-09 |
| harness | `scripts/gate.sh <tree> harness` | 10 s | 1.8 s (adds compile 0.05, coverage-plants 1.36) | 2026-11-09 |
| full | `scripts/gate.sh <tree> full` | 30 s | 2.5 s (adds sweep 0.70) | 2026-11-09 |
| tooling quick | `scripts/check-tooling.sh quick` | 30 s | 22.3 s | 2026-11-09 |
| tooling harness | `scripts/check-tooling.sh harness` | 150 s | 94.5 s (test_factory 72.5) | 2026-11-09 |
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
