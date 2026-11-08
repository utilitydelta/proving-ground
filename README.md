# proving-ground

A template for the bot side of a human-gated codebase. Agents own this repo. They build the harnesses that prove their code correct, and they keep a record of every call they made on the way. The human reads what agents built, rules on the calls, and writes the production code themselves. Agent code is a proven draft, never the shipped product.

## The problem

Agents write code by inference. The code reads well, compiles, passes the tests the same agent wrote, and is full of bugs at the edges: the crash between two writes, the retry that lands twice, the cap nobody named. More review by the same kind of agent does not fix that. Review is also inference.

The second problem is quieter. The human gives intent, a high-level spec. Building it forces hundreds of micro-decisions the spec never mentions: what happens on a torn write, which error wins, whether a field is stored or derived. Agents make those calls silently, bury them in code, and the human finds them months later when something built on top breaks.

The third problem comes from fixing the first. Empirical harnesses are CPU-heavy: seed sweeps, fuzzers, proofs, mutation runs, full suites. Agents reach for the whole suite when one row would answer the question, start a second sweep while the first still runs, and forget a binary that grinds for an hour. The build slows to a crawl and nobody notices until the quota or the deadline does. Compute is a budget here, stated before a run starts and checked after.

## What this repo is for

Two jobs.

1. **A proving ground for empirical correctness.** Agents get a space to build their own tooling: deterministic simulators, reference models, blind oracles, fuzzers, crash probes, benches, a gate. Nothing counts as working until a check that can fail says so, and every check is proven able to fail first by planting a bug and watching it go red.
2. **A provenance register.** An append-only history of everything the agents did, grouped by session, with the current state kept in `docs/` and two registers beside it: `decisions/` for every micro-decision (and whether the human has actually ruled on it) and `risks/` for every edge case the harnesses surface, scored before anyone adds state for it.

Nothing ships unread. The human reads and rules on everything that matters, and types the production code. What agents add is evidence for each claim and a log of every call, so the human spends attention on rulings and not on hunting for bugs. Arr, every plank gets tested before the captain walks on it.

## The three trees

| Tree | Who writes | Role |
|---|---|---|
| Human repo | The human, every line | The product. Agents read, build and test against it. Never write |
| This repo (bots) | Agents | Harnesses, sessions, registers, docs, the agents' own skills |
| Lead repo (optional) | Agents | Product code agents build ahead of the human, proven by this repo's harnesses. The human reads it, rules on its decisions and rewrites it in the human repo |

A repo boundary is physical. A folder convention or a commit trailer drifts the first time someone is in a hurry; a bot edit in the wrong repo is visible.

Skip the lead repo when agents only test and advise. Add it when agents build product code ahead of the human.

## How it fits with the other plugins

| Concern | Lives in |
|---|---|
| How to write code, tests, prose, docs; performance discipline; the implementation loop; scouting a goal | `build-method` plugin |
| Turning a build-out into something the human replays and learns from: sandboxes, replay guides, podcasts, diagrams | `human-replay` plugin |
| The boundary, session modes, the registers, the correctness harness, the unattended factory runner | this template |

Skills here name plugin skills by full name (`build-method:writing-tests`) and never copy them.

## Adopting it

1. Make your copy next to the human repo, private, with its own origin:
   ```
   gh repo create <name> --private --template utilitydelta/proving-ground --clone
   ```
   Or clone it and run `git remote set-url origin <your repo>`. `scripts/push.sh` refuses to push to the template.
2. Fill `project.env` (paths, read-only dirs, run caps) and every `<...>` in the `## Project` section of `AGENTS.md`. The human replaces the example row in `docs/workload-shapes.md` with real shapes, or the file goes and `## Project` says none.
3. `scripts/hooks/install.sh`. The Claude Code hooks (`.claude/settings.json`) refuse writes, installs and in-tree builds under the human repo, and recursive deletes outside session scratch.
4. Load the `task` skill with "build the first harness and the gate". It creates `session-v1`, so the decisions the first harness forces have a session to land in.
5. In that session, write the product stages in `scripts/gate.sh` under `# ADOPT: product stages below`; the header holds the contract. Until then the stub prints BLIND and exits 2 for any tree but the example's.
6. Add harness workspaces under `harness/<language>/`. They import the product from `$TREE` at run time; `harness/README.md` has a recipe per ecosystem, the `coverage.tsv` columns and the plant format. Add the first plant with `scripts/new-plant.sh`.
7. Delete the example: `examples/`, the sample-records links in `decisions/README.md` and `risks/README.md`, the line in `scripts/gate.sh` that delegates to the example, and the example's rows in `harness/coverage.tsv`. Set the Gate row in `docs/ARCHITECTURE.md` to what your gate runs.
8. Done when `scripts/lint.py --adoption` passes. It fails on any `<...>` left in `## Project`, the `EXAMPLE ROW` still in `docs/workload-shapes.md`, the ARCHITECTURE Gate row still saying `Stub`, or origin still pointing at the template.

`examples/kv-python/` is a worked example: a toy key-value store as the "human" code, a seeded simulator with a reference model, a checker, planted bugs the checker catches, and a gate. Read it before writing your first harness.

## Week one

Start with four skills: `task`, `fast-feedback`, `triage`, `finish`. That is enough to build a harness, prove it can fail, and leave a clean record. Add the rest when their trigger fires:

| Mode | Start it when |
|---|---|
| `invariant` | Code is about to build on a promise nobody has priced (a fault rule, an end condition, an ordering) |
| `closeoff` | `scripts/decisions.py provisional` passes the count the project picked in `## Project` |
| `watch` | The human codes in the human repo and wants checks running beside them |
| `debrief` | After a Watch chunk or a finished Task, to collect verdicts by name |
| `tend` | Budgets drift, plants go BLIND, or scratch nears its budget |
| `factory` | The gate and plants exist and are green; never before |

Factory needs Linux, bwrap and Claude Code (`claude -p`). `.agents/skills` links the skills for Codex, which serves every other mode.

## Map

- `AGENTS.md`: the rules. Read first.
- `INDEX.md`: what covers what, the session list, how often each kind of call holds up.
- `docs/ARCHITECTURE.md`: current state of the harnesses, progressive detail.
- `decisions/`, `risks/`: the registers. `scripts/decisions.py` and `scripts/risks.py` query and lint them.
- `sessions/`: append-only history, one folder per session.
- `.claude/skills/`: the modes and supporting skills. `.agents/skills` links to them for Codex.
- `scripts/factory.sh`: unattended runner, one fresh `claude -p` per iteration, state on disk.
