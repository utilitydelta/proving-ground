---
name: debrief
description: Debrief with the human after a coding chunk or a finished Task or Factory run. Use when the human says debrief, wrap up, what did I do or how did I go, or ends a Watch session. Summarises what they built, walks findings, gives specific praise and two-way-door suggestions, collects verdicts on findings and rulings on decisions by name.
---

# Debrief

The human is out of focus and has time to talk. Keep it short anyway.

## Prepare

A debrief is a session: `scripts/new-session.sh debrief <slug>` first, and the human's rulings go in its `human.md` verbatim.

1. Read `report.md`, `log.md` and `findings/` of every session since the last debrief.
2. Diff the human repo from the first session's starting HEAD to now.

## Deliver

In order, each short:

1. **What you built.** Three to six bullets from the diff, in the human's terms.
2. **Findings**, ranked by class. Each: the claim, the evidence command, one sentence on what the human might do.
3. **What went well.** Specific, tied to lines or calls. `candor:giving-praise` if unsure.
4. **Two-way doors** noted in `log.md`. The human takes or leaves each.
5. **Tests worth promoting** to the human side.
6. **Decisions to rule on.** `scripts/decisions.py provisional`, narrowed with `touches` to code the human wrote or read this chunk. One line each: the decision, who made it, the alternative.

Long debrief: offer a format from `present`.

## Collect

- Each finding: `adopted`, `rejected` or `noise`, written into its frontmatter. Update `INDEX.md` `## Precision` from `scripts/findings.py stats`. Once an adopted fix lands in the human repo, add `adopted_in: <sha>`. Never ask for anything bot-related in a human commit.
- Each decision shown: `confirmed` or `overturned` by name, with a History line and the human's words. A new call the human makes is `decided_by: human-informed`. Silence or typing past confirms nothing; what the human leaves goes on the next `closeoff` agenda.

## End

Run `finish`. `report.md` lists each verdict and ruling collected and what goes on the next `closeoff` agenda.
