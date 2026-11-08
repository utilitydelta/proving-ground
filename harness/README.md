# Harness

The bot-built correctness tooling. One workspace per language or toolchain, `harness/<language>/`, each importing the product from `$TREE` at run time. `examples/kv-python/harness/` shows the shape.

- **Probes:** builds, layout and API diffs, dependency allowlists, cycle checks. Seconds.
- **Blind oracles:** contract tests from the public surface only (`build-method:implementation-loop`).
- **Simulators (`dst`):** seeded driver, fault injection at the declared seam, independent reference model, history checker, tapes.
- **Fuzz, property tests, bounded proofs:** seeded from real encodes.
- **Crash and chaos:** torn writes, kills, device faults.
- **Benches:** pinned runs, output to `baselines/`.

A new harness lands with a `scripts/gate.sh` stage, a `coverage.tsv` row and at least one plant, in one commit.

## Importing the product from TREE

Harness code reads one variable, `TREE`, and loads the product from it when it runs. The gate sets it to a snapshot, `scripts/plants.sh` to a planted copy, `scripts/affected.sh` to the live `HUMAN_REPO`. A static path to `HUMAN_REPO` in a manifest grades the live tree every time: the plant goes uncaught and the snapshot is ignored, and both still print OK. Never copy or vendor the product's source.

Build output never lands in `TREE`: `scripts/run.sh` points caches at `.run/build/`. A toolchain that must write into the tree it builds (npm install, dotnet obj/bin, pip -e, make) builds a snapshot copy under `.run/tmp/`.

| Ecosystem | Recipe |
|---|---|
| Rust | A `path` dependency is fixed in the manifest, so declare the product as a registry dependency (`product = "0.1"`, matching its version) and have the stage patch it per run: `cargo test --offline --config 'patch.crates-io.product.path="'"$TREE"'/crates/product"'`. Awkward, but every run builds the tree it names, offline. `CARGO_TARGET_DIR` stays under `.run/build/` |
| TypeScript / JS | `await import(path.join(process.env.TREE, "src/index.ts"))` through a runner that loads TS (tsx), or the built JS from a snapshot copy. No `file:` dependency |
| Python | `sys.path.insert(0, os.environ["TREE"])` (or `TREE/src`) before the product import |
| Go | The stage writes a `go.work` (or a `replace` into a copied `go.mod`) under `.run/tmp/` pointing at `$TREE`, then runs with `GOWORK` set to it |
| C / C++ | `-I$TREE/include` and the product sources compiled from `$TREE`, objects under `.run/build/`, HAL fakes from the harness standing in for hardware |
| .NET | `<ProjectReference Include="$(TREE)/src/Product/Product.csproj" />`, `TREE` passed as an MSBuild property; build a snapshot copy, since obj/ and bin/ land beside the project |

A workspace pointed at lead or a scratch copy is listed under Platforms in `docs/ARCHITECTURE.md` with the reason.

## coverage.tsv

The machine-readable coverage map. Columns: `glob`, `command`, `tier`, `budget_s`, `plant`. `glob` matches paths in the human repo; `scripts/affected.sh [base]` prints the commands whose globs match the paths changed since `base`. `tier` is one of the `fast-feedback` tiers; `budget_s` is measured, not guessed; `plant` names the patch that proves the row can go red. A row without a measured budget or a plant is not finished.

## Plants

A plant is a deliberate break of the code under test, kept as a patch, that a named check must catch. `scripts/new-plant.sh` writes one from an edited copy. `scripts/plants.sh <tree> <plants-dir>` first runs each distinct check once on a clean copy, where it must be green; then, per `*.patch`, it copies the tree fresh, applies the patch with `git apply`, and runs the check from this repo's root under `scripts/run.sh` with `TREE` set to the patched copy and `PLANT_OUT` to an empty dir for tapes. Per plant:

- `OK`: the check went red. The plant is caught.
- `FAIL`: the check stayed green. The harness is blind to this bug.
- `BLIND`: no `# check:` line, the patch no longer applies, the check is red on the clean tree, or the run was refused, timed out or killed.

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

The first line says what the plant breaks. `# check:` must exit nonzero with the plant applied; `# timeout:` is optional, in seconds. `examples/kv-python/plants/` has three working plants. The gate's harness tier runs the plants dirs listed in its ADOPT block; a new plants dir joins that list in the commit that adds it. A plant that turns BLIND after a human change is fixed or replaced in the same session.
