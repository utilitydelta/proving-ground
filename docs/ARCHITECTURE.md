# Architecture

Current state of the bot side. Progressive detail: this page names each subsystem in a line and links down. Prune ruthlessly; history lives in `sessions/`.

## Is / is not

- Is: harnesses that prove the product correct (probes, oracles, simulators, fuzz, benches, the gate), the registers, session records.
- Is not: the product. Nothing here ships. Nothing here is written into the human repo.

## Invariants

- Harness code imports the product from `$TREE` at run time, never a static path (`harness/README.md`). The gate sets `TREE` to a snapshot, `scripts/plants.sh` to a planted copy, `scripts/affected.sh` and Watch to the live `HUMAN_REPO`.
- The gate never runs on a live tree. It snapshots: bot trees via `git archive HEAD`, the human tree with its uncommitted edits, and prints the human HEAD and a dirty hash so a verdict names exactly what it judged.
- Build output and run output never land in the human repo or in git: `.run/` holds them (below).
- A workspace pointed at the lead repo or a scratch copy instead of the human repo is listed under Platforms with the reason.
- Internals are reached through a surface the human chose (a snapshot, a public API, compiler output), never through copied or shadowed human source outside session scratch.
- Every claim to the human is backed by a reproducible command in this repo.

## Platforms

One workspace per language or toolchain under `harness/<language>/`. Say here which builds where, and why any workspace stands alone. Factory needs Linux with bwrap and Claude Code (`claude -p`); every other mode runs wherever the harnesses build.

## Subsystems

| Subsystem | Location | State |
|---|---|---|
| Gate | `scripts/gate.sh <tree> [quick\|harness\|full]`: a `lint` stage, then the product stages in its `# ADOPT: product stages below` block | Stub |
| Verdicts | `scripts/lib/verdict.sh`: OK, FAIL or BLIND per stage, times to two decimals; exit 0 all OK, 2 any BLIND, else 1 | Working |
| Bot tooling checks | `scripts/check-tooling.sh [quick\|harness]`, run by `finish` only when `scripts/changed-tooling.sh <base>` says `scripts/`, `.claude/` or `project.env` changed | Working |
| Bounded runs | `scripts/run.sh`: timeout, memory cap, machine-wide heavy slots (`HEAVY_DIR` in the user cache, `-H` capped by `HEAVY_TIMEOUT_MAX`) | Working |
| Run output | `.run/out/` (`RUN_OUT` per run), `.run/tmp/` (snapshots, plant copies), `.run/build/` (build caches), `.run/logs/`; gitignored, cleared by `scripts/clean-tmp.sh` | Working |
| Plants | `scripts/plants.sh`, `scripts/new-plant.sh`, `harness/<language>/plants/`; format in `harness/README.md` | Working |
| Coverage | `harness/coverage.tsv`, `scripts/affected.sh [base] [--run]` | Working; empty until harnesses exist |
| Registers | `decisions/`, `risks/`, `scripts/decisions.py`, `scripts/risks.py`, `scripts/findings.py`, `scripts/new-id.sh` | Working |
| Sessions | `sessions/`, `scripts/new-session.sh` | Working |
| Hooks | `scripts/hooks/guard-human-repo.sh`, `scripts/hooks/no-rm-rf.sh`, `scripts/hooks/pre-commit` | Working |
| Lint | `scripts/lint.py`, `scripts/lint.py --adoption` | Working |
| Push | `scripts/push.sh`, refuses the template origin; `finish` pushes through it | Working |
| Factory runner | `scripts/factory.sh`, `scripts/test_factory.sh`, `.claude/skills/factory/` | Working |
| Watch trigger | `scripts/watch-wait.sh` | Working |
| Workload shapes | `docs/workload-shapes.md` | Human-written, optional |
| Roadmap | `docs/roadmap.md` | Working |
| Worked example | `examples/kv-python/` | Delete once real harnesses exist |
