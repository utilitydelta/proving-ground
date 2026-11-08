---
name: closeoff
description: Close-off mode. Use when the human asks to close off, recap or walk the provisional decisions, drain the decision backlog, or rule on cross-module doors. Recaps each decision in plain words with its code and evidence, collects the human's ruling by name, and writes it into the register.
---

# Close-off

Building forces micro-decisions the spec never named. Agents file them as they go, and they stay provisional until the human rules with the code in front of them. Close-off drains that backlog. Typing past a line confirms nothing; silence confirms nothing.

## Prepare

1. `scripts/new-session.sh closeoff <slug>`.
2. Agenda from `scripts/decisions.py provisional` and `open`, ordered by how much later work builds on each: count the live decisions, `## Builds on` lines and unit records that cite it. The most leaned-on go first. Note the code each `touches`.
3. Cross-module doors no single component owns go on one recap page: the door, whom it binds, variants, a recommendation.
4. Re-check every item against the register and the code right before the session: parallel sessions change decisions. Drop items already ruled.
5. Questions the human raised elsewhere (debrief, report) go at the top.

## Deliver

One theme at a time, short:

1. The rule in one plain sentence, who made it (`bot`, or the human's answer before reading code), and what breaks without it.
2. Where it lives: `file:line` in the human repo or lead, or "not built".
3. The proposed ruling with its evidence command: confirm, overturn (name the replacement), defer (name the trigger event) or reopen.

Group decisions that stand or fall together only when the human says so.

## Collect

- Each ruling is a History line: date, session, `confirmed at close-off`, `overturned`, `deferred` or `reopened`, with the human's words when they gave reasons. Set `status`; `replaced_by` on an overturn.
- A decision the human changes becomes a new decision (`scripts/new-id.sh decision`), `decided_by: human-informed`, `status: confirmed`, and the old one is overturned. History lines on every decision it collides with.
- **Overturn purge.** Each overturn lists in `report.md` the docs, harnesses, skills and lead code that carry the old concept (grep its wording). Purge docs, harnesses and skills this session; lead code becomes a queued unit or a `scraps.md` line.
- `scripts/decisions.py stats` before and after into `report.md`; `scripts/decisions.py check` passes.
- **Trigger.** Check the close-off count in `AGENTS.md` `## Project` against what this session saw. A rising overturn rate for `bot` calls is the case for lowering it; propose the new count to the human.
- What the human leaves open stays on the agenda with the reason.

Run `finish`.
