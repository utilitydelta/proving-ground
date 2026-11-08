# Architecture

Current state of the bot side. Progressive detail: this page names each subsystem in a line and links down. Prune ruthlessly; history lives in `sessions/`.

## Is / is not

- Is: harnesses that prove the product correct (probes, oracles, simulators, fuzz, benches, the gate), the registers, session records.
- Is not: the product. Nothing here ships. Nothing here is written into the human repo.

## Invariants

- Harness workspaces depend on the human repo by path, so every check sees the human's latest uncommitted edits. A crate or package pointed at the lead repo or a scratch copy is listed under Platforms with the reason.
- Internals are reached through a surface the human chose (a snapshot, a public API, compiler output), never through copied or shadowed human source outside session scratch.
- Every claim to the human is backed by a reproducible command in this repo.

## Platforms

One workspace per language or toolchain under `harness/<language>/`. Say here which builds where, and why any workspace stands alone.

## Subsystems

| Subsystem | Location | State |
|---|---|---|
| Registers | `decisions/`, `risks/`, `scripts/decisions.py`, `scripts/risks.py` | Working |
| Sessions | `sessions/`, `scripts/new-session.sh` | Working |
| Bounded runs | `scripts/run.sh` | Working |
| Gate | `scripts/gate.sh` | Stub; runs the example until written |
| Factory runner | `scripts/factory.sh`, `scripts/test_factory.sh`, `.claude/skills/factory/` | Working |
| Watch trigger | `scripts/watch-wait.sh` | Working |
| Worked example | `examples/kv-python/` | Delete once real harnesses exist |
