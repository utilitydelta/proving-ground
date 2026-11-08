# Risks

One file per scenario, `RNNN-<slug>.md`, written by `scripts/new-id.sh risk <slug> [session-dir]`. Thresholds and controls: `AGENTS.md` Risks. `scripts/risks.py check` lints scores and controls; `open` lists what needs a control or the human's acceptance. A filled-in example: `examples/kv-python/sample-records/`.

A finding is a defect in human code; a risk is a scenario the design must answer, with a control or without one.

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

## Scoring

| | Likelihood: what it takes | Consequence: the worst outcome |
|---|---|---|
| 1 | two independent rare faults, or timing no real deployment produces | a blip the user never sees |
| 2 | one rare fault plus specific timing | unavailable for seconds, self-healing |
| 3 | one ordinary fault: crash, restart, dropped message, timeout | unavailable until an operator acts, or errors the client must retry |
| 4 | routine operation: deploy, failover, load spike | a client told something untrue |
| 5 | the happy path, every time | data lost or corrupted |

Adapt the consequence column to the product's worst outcomes when adopting; keep five rows.

## Status and the check

- `open`: scored, nothing decided. `proposed`: a control is designed, not built.
- `controlled`: the control exists and runs. `accepted`: the human accepted the risk by name.

A risk at 12 or more with no control yet is still filed today: `status: open` with `control: none`, or `proposed` with the design, and `decision:` pointing at a decision with `status: open` that names the control question. It shows in `scripts/risks.py open` until it is answered. Never mark it `accepted` to quiet the list.

`scripts/risks.py check` reads every `*.md` here except this README. It refuses a `controlled` or `proposed` risk whose `control:` is `none`; only `open` may have none. A `controlled` or `accepted` risk scored 12 or more also needs a real control and a `decision:` whose status is `decided` or `confirmed`.

## Scoring notes

Likelihood comes from what the real world needs to produce the schedule, never from how many seeds fired. Seed counts measure the scheduler. When the human rescores, the History line says so.
