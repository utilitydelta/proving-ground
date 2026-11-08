# kv-python: a worked harness in miniature

A toy log-structured KV store plays the human's product. Everything else is the bot side: a seam, a reference model, an adapter, a seeded simulator with fault injection, planted faults that prove the simulator can fail, and a gate. Python 3 standard library only.

Why bother for a toy? Because the shape is the point. Copy the shape, not the code.

## Layout

| Path | What it demonstrates | AGENTS.md rule |
|---|---|---|
| `product/kvcore.py` | Sans-IO core: returns `Append`/`Fsync`/`Truncate` effects, takes completions, recovers from log bytes | The boundary: stands in for the human repo, never written by agents |
| `harness/subject.py` | The seam both model and product sit behind | The code under test is never its own oracle |
| `harness/model.py` | Reference model from the contract: an op list, an ack floor, the set of states a crash may leave | The code under test is never its own oracle |
| `harness/adapter.py` | Thin adapter: performs effects on a simulated disk, injects faults between effect and completion | Faults at the effect boundary, no KV logic in the harness |
| `harness/loader.py` | Imports the product from any tree without writing `__pycache__` into it; digest of the source a tape ran | Agents never write in the human tree |
| `harness/sim.py` | Seeded driver, checker, tapes, `--replay`, `--keep-going` | Evidence before speech: a tape is a claim anyone can rerun |
| `harness/test_*.py` | Walkthrough of the product's life, torn-tail table, tape replay, gap arithmetic | `build-method:writing-tests` |
| `plants/*.patch` | Planted bugs as unified diffs against `product/`, each naming the check that must go red | Green is not self-graded |
| `../../scripts/plants.sh` | Applies each plant to a copy of the tree and runs its check; language-agnostic | An experiment on human code edits a copy, never the tree |
| `gate.sh` | Snapshot, then stages under `scripts/run.sh`, one `OK/FAIL/BLIND` line each | Every run has a hard timeout; every tier has a measured budget |
| `sample-records/` | D-001 (torn tail drop vs refuse) and R001 (crash between write and fsync), filled in | Decisions, Risks |

## What the checker holds the product to

- An acked op survives any crash, and so does every op before it.
- After a crash the store holds some prefix of the op history that contains every acked op. Nothing else.
- Every read and every post-step snapshot matches the model.
- Recovery never refuses a torn tail (short header, short body, or bad body ending the log).
- Recovery always refuses mid-log corruption, by raising `CorruptLog` with the offset.

Faults: crash before fsync, crash after fsync with the completion lost, torn append (a prefix persists), torn sector (full length, last byte bad), lost completion without a crash, and bitrot in any record that has a successor. A green run prints how many times it hit each path, so a sim that quietly stopped injecting a fault shows that path missing from the list.

A seed expands into an event list before the run starts. The run is a pure function of that list, so a tape replays with no RNG in the loop.

## Plants

A plant is a bug written down as a patch, so the harness has to prove it can see it. Each file in `plants/` is a plain unified diff with paths relative to the product root (`a/kvcore.py`), headed by comment lines:

```
# Acks a write on its append completion, before fsync. A crash before fsync then loses an acked write.
# check: python3 examples/kv-python/harness/sim.py --tree "$TREE" --seeds 200 --tape-dir "$PLANT_OUT"
# timeout: 60
diff --git a/kvcore.py b/kvcore.py
...
```

`scripts/plants.sh <tree> <plants-dir>` copies the tree into a fresh `mktemp -d` per plant, `git apply`s the patch there, and runs the check from the repo root with `TREE` set to the patched copy. It runs each distinct check once on an unpatched copy too, which must be green: a check that crashes on its own would otherwise "catch" every plant. One line per plant: `OK` (check red), `FAIL` (check green, the harness is blind to this bug), `BLIND` (no check line, patch no longer applies, check red on the clean tree, or the run timed out or was refused). A patch that stops applying after the human edits the product is BLIND, never quietly skipped.

Nothing here is Python-specific. A C or TypeScript adopter writes the same patch files against their own tree with `# check: make -C "$TREE" test` or `# check: npm --prefix "$TREE" test`, and `plants.sh` grades them the same way. The only contract is: patch applies with `-p1` at the tree root, check exits nonzero when it catches the bug.

Measured from this folder; the last line of each command's output carries the numbers, e.g. `sim: RED on 1454/2000 seeds from 0, worst gap 6, 0.40s`. Worst gap is the most seeds a run starting anywhere in the range needs before it hits a catching seed.

| Plant | Bug | Caught, seeds 0..1999 | Worst gap | Reproduce |
|---|---|---|---|---|
| `ack_before_fsync` | ack on append completion | 1454 / 2000 | 6 | `d=$(mktemp -d) && cp -a product "$d/tree" && git -C "$d/tree" apply "$PWD/plants/ack_before_fsync.patch" && python3 harness/sim.py --tree "$d/tree" --seeds 2000 --keep-going --tape-dir "$d"` |
| `accept_mid_log_corruption` | every bad record treated as a torn tail | 1954 / 2000 | 2 | `d=$(mktemp -d) && cp -a product "$d/tree" && git -C "$d/tree" apply "$PWD/plants/accept_mid_log_corruption.patch" && python3 harness/sim.py --tree "$d/tree" --seeds 2000 --keep-going --tape-dir "$d"` |
| `refuse_torn_tail` | a short body refused as corruption | 818 / 2000 | 14 | `d=$(mktemp -d) && cp -a product "$d/tree" && git -C "$d/tree" apply "$PWD/plants/refuse_torn_tail.patch" && python3 harness/sim.py --tree "$d/tree" --seeds 2000 --keep-going --tape-dir "$d"` |

The check's budget is 200 seeds, over ten times the worst measured gap.

## Commands

From this folder; `$d` is a planted copy made as in the plant table:

```sh
python3 -m unittest discover -s harness -p 'test_*.py'
python3 harness/sim.py --seeds 200 --timeout 60                        # clean product, green
python3 harness/sim.py --tree "$d/tree" --seeds 200 --tape-dir "$d"     # planted copy: red, writes a tape
python3 harness/sim.py --replay "$d"/tape-*-seed3.json                   # replays on the tape's own tree: same step, same message
python3 harness/sim.py --replay "$d"/tape-*-seed3.json --tree product   # same tape on the clean product: green
../../scripts/plants.sh product plants                                  # every plant OK
./gate.sh product quick                                                 # or harness, or full
```

A tape records the tree path and a digest of `kvcore.py`; replay says whether the tree it ran matches. `--tree PATH` (or `KV_TREE`) points the sim and the unit tests at another product tree.

## Gate tiers

`./gate.sh <tree> [quick|harness|full]`. `scripts/gate.sh` delegates here. The tree is snapshotted first, uncommitted edits included, into a fresh `mktemp -d` under `.run/tmp/`; every stage runs on the snapshot under `scripts/run.sh` with its own log. The run dir is printed on stderr and kept (logs, tapes); `scripts/clean-tmp.sh` clears them.

| Tier | Stages | Wall-clock, three runs | Stage `-t` |
|---|---|---|---|
| quick | unit, sim 200 seeds | 0.40 to 0.41 s | 60, 60 |
| harness | compile (`py_compile` every harness module), plants | 0.47 to 0.50 s | 60, 240 |
| full | quick, harness, then sweep (seeds 200..2199, heavy `-H`) | 1.45 to 1.47 s | plus 300 |

This machine, 32 cores (the gate uses one), Python 3.12.3. Per stage in one full run: unit 0.27 s, sim 0.13 s, compile 0.04 s, plants 0.32 s, sweep 0.71 s. The timeouts sit far above the budgets for a toy; in a real harness set them near the measured number, so a slow run turns red instead of eating the afternoon.

Run against each planted copy of the product, `gate.sh <copy> quick` fails both stages and exits 1.
