# Skills

Agents own these. Every session loads exactly one mode skill first; the mode pulls in supporting skills when it needs them. Week one needs only `task`, `fast-feedback`, `triage` and `finish`; README.md says when to add the rest. `.agents/skills/` links here for Codex, which runs every mode but Factory.

## Modes

| Skill | Started by | Does |
|---|---|---|
| `watch` | Human, coding in another terminal | Targeted checks on each change, speaks only at one-way doors |
| `task` | Human hands over a job | Creates the session, picks the weight, runs the implementation loop |
| `factory` | `scripts/factory.sh <session> --until <deadline>`; Linux, bwrap, Claude Code | One iteration of an unattended build-out in lead, state on disk |
| `tend` | Human asks for cleanup; Factory pauses | Deletes dead, slow and orphan tests and docs; re-measures budgets; runs plants; audits intent |
| `debrief` | Human, after a coding chunk or a run | Findings, praise, verdicts and rulings by name |
| `closeoff` | Human, to drain provisional decisions | Recap with code, ruling by name, History lines |
| `invariant` | Human, before code builds on a promise | Two or three promises, executed tapes, priced in state and risk |

## Supporting

| Skill | Role | Called from |
|---|---|---|
| `fast-feedback` | Picks the tier, bounds every run, owns compute discipline | every mode that runs anything |
| `dst` | Seeded simulator at the declared seam, reference model, checker, tapes | `task`, `factory`, `invariant`, `watch` when a subject is touched |
| `triage` | Classifies a confirmed finding, decides whether it interrupts | `watch`, `task`, `factory`, any confirmed finding |
| `finish` | Clean tree, current docs, INDEX row, commit, push | end of every session |
| `present` | Picks a format beyond `report.md` | `task`, `tend`, `factory`, `debrief` at the end |

## Routing

```
watch     -> fast-feedback (probe/targeted only) -> triage -> finish
task      -> build-method:scout? -> build-method:implementation-loop
             -> dst, fast-feedback, triage -> finish -> present
factory   -> task (Build) -> fast-feedback (heavy = job) -> triage
             -> pause: tend + think agents -> finish under 30 min to deadline
tend      -> fast-feedback (budgets, mutants) -> finish
debrief   -> present? -> commit
closeoff, invariant -> dst (tapes) -> finish
```

Plugin skills are named by full name and never copied: `build-method:*` for code, tests, prose, docs and perf; `human-replay:*` for podcasts, diagrams and explainers.
