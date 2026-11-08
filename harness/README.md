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

Harness code reads one variable, `TREE`, and loads the product from it when it runs. The gate sets it to a snapshot, `scripts/coverage-plants.sh` and `scripts/plants.sh` to clean and planted copies, `scripts/affected.sh` to the live `HUMAN_REPO`. A static path to `HUMAN_REPO` in a manifest grades the live tree every time: the plant goes uncaught and the snapshot is ignored, and both still print OK. Never copy or vendor the product's source.

Build output never lands in `TREE`: `scripts/run.sh` points caches at `.run/build/`. A toolchain that must write into the tree it builds (npm install, dotnet obj/bin, pip -e, make) builds a snapshot copy under `.run/tmp/`.

| Ecosystem | Recipe |
|---|---|
| Rust | A `path` dependency is fixed in the manifest, so declare the product as a registry dependency (`product = "0.1"`, matching its version) and have the stage patch it per run: `cargo test --offline --config 'patch.crates-io.product.path="'"$TREE"'/crates/product"'`. Awkward, but every run builds the tree it names, offline. `CARGO_TARGET_DIR` stays under `.run/build/` |
| TypeScript / JS | `await import(path.join(process.env.TREE, "src/index.ts"))` through a runner that loads TS (tsx), or the built JS from a snapshot copy. No `file:` dependency |
| Python | `sys.path.insert(0, os.environ["TREE"])` (or `TREE/src`) before the product import |
| Go | One wrapper, `harness/go/go.sh`, for every go subcommand: it writes a `go.work` into `$RUN_OUT` that uses the harness module and `$TREE`, exports `GOWORK` to it and runs `go "$@"`. vet, build and test all need the workspace, so no stage calls `go` bare. Workspace mode rejects `-mod=mod`: keep it out of `GOFLAGS` |
| C / C++ | `-I$TREE/include` and the product sources compiled from `$TREE`, objects under `.run/build/`, HAL fakes from the harness standing in for hardware |
| .NET | `<ProjectReference Include="$(TREE)/src/Product/Product.csproj" />`, `TREE` passed as an MSBuild property; build a snapshot copy, since obj/ and bin/ land beside the project |

A workspace pointed at lead or a scratch copy is listed under Platforms in `docs/ARCHITECTURE.md` with the reason.

## coverage.tsv

The machine-readable coverage map; `scripts/lint.py` fails when it is missing or empty. Columns: `glob`, `command`, `tier`, `budget_s`, `plant`.

- `glob` matches paths in the human repo. `scripts/affected.sh [base] [--run] [--tier quick|harness|full]` prints the rows whose globs match the paths changed since `base`, up to the quick tier unless `--tier` raises it; `--run` runs them under `scripts/run.sh`. A diff no row matches under `--run` prints `BLIND affected` and exits 2.
- `command` is bare (no `scripts/run.sh` inside: the caller wraps it) and reads the product through `$TREE`.
- `tier` is one of the `fast-feedback` tiers; `budget_s` is measured, not guessed.
- `plant` names the patch the row must catch. The gate's harness tier proves it with `scripts/coverage-plants.sh <tree>`: the row's command runs with `TREE` on a clean copy, where it must be green, and on a copy with that plant applied, where it must be red. FAIL there usually means the command reads a fixed path instead of `$TREE`. A plant no row names is only a standalone `scripts/plants.sh` check, and the harness tier warns about it.

A row without a measured budget or a proven plant is not finished.

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

The first line says what the plant breaks. `# check:` must exit nonzero with the plant applied; `# timeout:` is optional, in seconds. `examples/kv-python/plants/` has three working plants. The gate's harness tier grades plants through their coverage rows (`scripts/coverage-plants.sh`), with the row's command, not the plant's `# check:` line; `scripts/plants.sh` is the standalone check by `# check:` that Tend runs over every plants dir. A plant that turns BLIND after a human change is fixed or replaced in the same session.
