# Architecture

Current state of the bot side. Progressive detail: this page names each subsystem in a line and links down. Prune ruthlessly; history lives in `sessions/`.

## Is / is not

- Is: harnesses that prove the product correct (probes, oracles, simulators, fuzz, benches, the gate), the registers, session records.
- Is not: the product. Nothing here ships. Nothing here is written into the human repo.

## Invariants

- Harness workspaces depend on the human repo by path (`harness/README.md`), so targeted runs and Watch see the human's live tree, uncommitted edits included.
- The gate never runs on a live tree. It snapshots: bot trees via `git archive HEAD`, the human tree with its uncommitted edits, and prints the human HEAD and a dirty hash so a verdict names exactly what it judged.
- A workspace pointed at the lead repo or a scratch copy instead of the human repo is listed under Platforms with the reason.
- Internals are reached through a surface the human chose (a snapshot, a public API, compiler output), never through copied or shadowed human source outside session scratch.
- Every claim to the human is backed by a reproducible command in this repo.

## Platforms

One workspace per language or toolchain under `harness/<language>/`. Say here which builds where, and why any workspace stands alone. Factory needs Linux with bwrap and Claude Code (`claude -p`); every other mode runs wherever the harnesses build.

## Subsystems

| Subsystem | Location | State |
|---|---|---|
| Registers | `decisions/`, `risks/`, `scripts/decisions.py`, `scripts/risks.py`, `scripts/new-id.sh` | Working |
| Sessions | `sessions/`, `scripts/new-session.sh` | Working |
| Bounded runs | `scripts/run.sh` | Working |
| Gate | `scripts/gate.sh` | Stub: runs the example for `examples/kv-python/product`, BLIND exit 2 for any other tree until stages are written |
| Plants | `scripts/plants.sh`, `harness/<language>/plants/` | Working; format in `harness/README.md` |
| Coverage | `harness/coverage.tsv`, `scripts/affected.sh` | Working; empty until harnesses exist |
| Hooks | `scripts/hooks/guard-human-repo.sh`, `scripts/hooks/no-rm-rf.sh`, `scripts/hooks/pre-commit` | Working |
| Lint | `scripts/lint.py`, `scripts/lint.py --adoption` | Working |
| Factory runner | `scripts/factory.sh`, `scripts/test_factory.sh`, `.claude/skills/factory/` | Working |
| Watch trigger | `scripts/watch-wait.sh` | Working |
| Workload shapes | `docs/workload-shapes.md` | Human-written, optional |
| Roadmap | `docs/roadmap.md` | Working |
| Worked example | `examples/kv-python/` | Delete once real harnesses exist |
