# Workload shapes

Written by the human, not agents. Optional; `AGENTS.md` `## Project` says whether this project uses it.

Why it exists: agents grade a trade (a cache size, a batching rule, a cap) against whatever scenario makes it look good, picked after the rule was written. Shapes written here first are the only ones a trade may be graded against. A trade names the shape it favours and the shape it costs.

One row per production shape. Numbers come from production or a cited source; a guess is marked as one.

| Shape | Who produces it | Mix | Sizes | Rate and burst | Data volume | Source |
|---|---|---|---|---|---|---|
| EXAMPLE ROW: sensor ingest | Field devices | 95% append, 5% range read | 64 to 512 B records | steady per device, bursts on reconnect | months retained | Invented to show the shape; replace with a real row (`scripts/lint.py --adoption` fails while this one stays) |
