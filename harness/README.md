# Harness

The bot-built correctness tooling. One workspace per language or toolchain: `harness/<language>/`. Each depends on the human repo by path.

What goes here, per product layer:

- **Probes:** builds, layout and API diffs, dependency allowlists, cycle checks. Seconds.
- **Blind oracles:** contract tests from the public surface only, written by an agent that never saw the implementation.
- **Simulators (`dst` skill):** seeded driver, fault injection at the effect boundary, independent reference model, history checker, tapes. One `Subject` seam per layer: the model implements it directly, real code through a thin adapter.
- **Fuzz, property tests, bounded proofs:** seeded from real encodes.
- **Crash and chaos:** torn writes, kills, device faults.
- **Benches:** quick pinned runs, output to `baselines/`.

Every harness gets an `INDEX.md` coverage row with its tier, measured budget and the planted fault it catches, and a stage in `scripts/gate.sh` in the same commit. `examples/kv-python/harness/` shows the shape.
