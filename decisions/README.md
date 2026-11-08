# Decisions

One file per micro-decision, `NNN-<slug>.md`, written by `scripts/new-id.sh decision <slug> [session-dir]`. What counts as a decision and when one is confirmed: `AGENTS.md` Decisions. `scripts/decisions.py check` lints every `*.md` here except this README; `provisional` lists what still needs the human's ruling by name; `stats` gives the overturn rate per `decided_by`, the real measure of how far provisional calls can be trusted. A filled-in example: `examples/kv-python/sample-records/`.

```markdown
---
status: open | decided | deferred | confirmed | overturned
decided_by: bot | human-asked | human-informed | none
touches: <path::Symbol, in the human repo, lead or a harness>
revisit_when: <an event: a module lands, a bench exists; never a session number>
session: session-vN
replaced_by: <D-NNN, only when overturned>
---
# D-NNN: <the decision in one line>

<Why, in a sentence or two. Alternatives and why not. Evidence: command or file.>

## History
- <date> <session>: <decided, asked, confirmed at close-off, overturned>
```

`decided_by`:

- `bot`: decided without asking.
- `human-asked`: the human answered a bot's question, usually accepting the recommendation without reading the code.
- `human-informed`: the human ruled with the code or evidence in front of them.
- `none`: open or deferred.
