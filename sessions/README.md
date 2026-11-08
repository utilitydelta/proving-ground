# Sessions

Append-only history. One folder per session, `session-vN-<mode>-<slug>/`, made by `scripts/new-session.sh <mode> <slug>`, frozen after `finish` (rules: `AGENTS.md` Sessions).

## Files

| File | Holds |
|---|---|
| `goal.md` | `## Ask`, `## Acceptance` (empirical checks: red today, green when done), `## Delta` against existing coverage, `## Builds on` (provisional decisions the work rests on, from `scripts/decisions.py touches`) |
| `log.md` | Timestamped, append-only: hypotheses, proofs, kills, decisions taken. Not a narration of edits |
| `human.md` | The human's statements of intent, verbatim, one line each. Not questions, chat or answers to agents |
| `report.md` | What the human reads. Short |
| `scraps.md` | Every hole, defer and leftover review item, one line each with its owner |
| `findings/NNN-<slug>.md` | One per confirmed finding |
| `briefs/`, `reviews/` | Every subagent brief and review, as files |
| `scratch/` | Gitignored. Anything worth keeping moves to `harness/`, `scripts/` or lead before the session ends |

Task and Factory sessions that build in lead add `units/<id>.md`. Factory adds `session-state.md`, `progress.md` and `jobs/`.

## Findings

`scripts/new-id.sh finding <slug> <session-dir>` writes the skeleton.

```markdown
---
class: one-way-door | time-sink | regression | two-way-door
status: open | adopted | rejected | noise
touches: <path::Symbol in the human repo, as of the finding>
evidence: <one command that reproduces it from this repo>
---
<Claim in one sentence. Evidence output. What the human might do about it.>
```

`status` and `adopted_in: <sha>` are the only fields written after `finish`.

## Unit records

One per unit built in lead. The human rewrites from these; a diff alone loses every "chose X over Y because".

- `## Contract`: public surface, invariants with decision ids, named refusals, the walkthrough test.
- `## Decisions`: every decision filed or leaned on, the alternative and why not, prior-system deltas, prior art.
- `## Commits`: lead base and head, the tests that pin it.
- `## Review` (full weight): findings and their disposal.
- `## Changed by`: appended by later units, `- <unit-id>: <what, why>`.

The factory runner stops on a done unit missing `## Contract`, `## Decisions` or `## Commits`.
