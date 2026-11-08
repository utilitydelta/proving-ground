# Harness

The bot-built correctness tooling. One workspace per language or toolchain, `harness/<language>/`, each depending on the human repo by path so targeted runs see the human's uncommitted edits. `examples/kv-python/harness/` shows the shape.

- **Probes:** builds, layout and API diffs, dependency allowlists, cycle checks. Seconds.
- **Blind oracles:** contract tests from the public surface only (`build-method:implementation-loop`).
- **Simulators (`dst`):** seeded driver, fault injection at the declared seam, independent reference model, history checker, tapes.
- **Fuzz, property tests, bounded proofs:** seeded from real encodes.
- **Crash and chaos:** torn writes, kills, device faults.
- **Benches:** pinned runs, output to `baselines/`.

A new harness lands with a `scripts/gate.sh` stage, a `coverage.tsv` row and at least one plant, in one commit.

## Depending on the human repo

`HUMAN_REPO` in `project.env` is the path. Point at it; never copy or vendor its source.

| Ecosystem | Recipe |
|---|---|
| Rust | Path dependency in the harness workspace `Cargo.toml`: `product = { path = "../../../product/crates/product" }`, declared once in `[workspace.dependencies]` |
| TypeScript | pnpm workspace link or a `file:` dependency on the human package; or `tsconfig.json` `paths` mapping onto its `src/` when it ships no build |
| Python | `PYTHONPATH=$HUMAN_REPO/src` in the stage command, or `pip install -e $HUMAN_REPO` into the harness venv |
| Go | `replace example.com/product => ../../../product` in the harness `go.mod` |
| C / C++ | Human headers on the include path, sources compiled for the host, with HAL fakes in the harness standing in for hardware |
| .NET | `<ProjectReference Include="../../../product/src/Product/Product.csproj" />` in the harness project |

A workspace pointed at lead or a scratch copy instead is listed under Platforms in `docs/ARCHITECTURE.md` with the reason.

## coverage.tsv

The machine-readable coverage map. Columns: `glob`, `command`, `tier`, `budget_s`, `plant`. `glob` matches paths in the human repo; `scripts/affected.sh [base]` prints the commands whose globs match the paths changed since `base`. `tier` is one of the `fast-feedback` tiers; `budget_s` is measured, not guessed; `plant` names the patch that proves the row can go red. A row without a measured budget or a plant is not finished.

## Plants

A plant is a deliberate break of the code under test, kept as a patch, that a named check must catch. `scripts/plants.sh <tree> <plants-dir>` copies the tree fresh for each `*.patch`, applies it with `git apply`, and runs its check from this repo's root with `TREE` set to the patched copy and `PLANT_OUT` to an empty output dir. Each distinct check also runs once on the clean tree and must be green there. Per plant:

- `OK`: the check went red. The plant is caught.
- `FAIL`: the check stayed green. The harness is blind to this bug.
- `BLIND`: the patch no longer applies, the check is red on the clean tree, or the run was refused, timed out or killed.

Keep plants in `harness/<language>/plants/`. Each file is header comment lines, then a unified diff with paths relative to the tree root:

```
# Acks a write on its append completion, before fsync. A crash before fsync loses an acked write.
# check: python3 harness/python/sim.py --tree "$TREE" --seeds 200 --tape-dir "$PLANT_OUT"
# timeout: 60
diff --git a/kvcore.py b/kvcore.py
--- a/kvcore.py
+++ b/kvcore.py
@@ ...
```

The first line says what the plant breaks. `# check:` must exit nonzero with the plant applied; `# timeout:` is optional, in seconds. `examples/kv-python/plants/` has three working plants. The gate's harness tier runs every plants dir. A plant that turns BLIND after a human change is fixed or replaced in the same session.
