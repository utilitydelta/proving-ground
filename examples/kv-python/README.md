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
| `harness/loader.py` | Imports the product from the tree named in `TREE` (no fallback) without writing `__pycache__` into it; digest of the source a tape ran | Agents never write in the human tree |
| `harness/sim.py` | Seeded driver, checker, tapes, `--replay`, `--keep-going` | Evidence before speech: a tape is a claim anyone can rerun |
| `harness/test_*.py` | Walkthrough of the product's life, torn-tail table, tape replay, gap arithmetic | `build-method:writing-tests` |
| `plants/*.patch` | Planted bugs as unified diffs against `product/`, each naming the check that must go red | Green is not self-graded |
| `../../scripts/coverage-plants.sh` | Runs each `harness/coverage.tsv` row on a clean copy (green) and a copy with the row's plant (red); language-agnostic | Green is not self-graded; an experiment on human code edits a copy |
| `../../scripts/gate.sh` ADOPT block | The example's stages: unit and sim at quick, compile and coverage-plants at harness, sweep at full | Every run has a hard timeout; every tier has a measured budget |
| `../../harness/coverage.tsv` | The example's rows: glob, bare command reading `$TREE`, tier, measured budget, plant | A new test file gets a coverage row |
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

A plant is a bug written down as a patch, so the harness has to prove it can see it. Each file in `plants/` is a plain unified diff with paths relative to the product root (`a/kvcore.py`). The coverage row that names it is what grades it: `scripts/coverage-plants.sh` runs the row's own command on a clean copy, where it must be green, and on a copy with the plant applied, where it must be red. The unit row catches `refuse_torn_tail` through the torn-tail table; the 200-seed sim row catches `ack_before_fsync`; the 2000-seed sweep row catches `accept_mid_log_corruption`. The comment lines that head each patch also let `scripts/plants.sh` run it standalone:

```
# Acks a write on its append completion, before fsync. A crash before fsync then loses an acked write.
# check: python3 examples/kv-python/harness/sim.py --tree "$TREE" --seeds 200 --tape-dir "$PLANT_OUT"
# timeout: 60
diff --git a/kvcore.py b/kvcore.py
...
```

Both graders copy the tree into a fresh `mktemp -d`, `git apply` the patch there, and run from the repo root with `TREE` set to the copy, after one run on an unpatched copy that must be green: a command that crashes on its own would otherwise "catch" every plant. One line each: `OK` (red with the plant), `FAIL` (green with the plant: blind to this bug), `BLIND` (patch no longer applies, red on the clean copy, or the run timed out or was refused). A patch that stops applying after the human edits the product is BLIND, never quietly skipped. `scripts/plants.sh` warns about a plant no coverage row names: a free-form `# check:` is not a product row.

Nothing here is Python-specific. A C or TypeScript adopter writes the same patch files against their own tree and a row such as `make -C "$TREE" test` or `npm --prefix "$TREE" test`, and `coverage-plants.sh` grades them the same way. The only contract is: patch applies with `-p1` at the tree root, the row's command exits nonzero when it catches the bug.

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
TREE=product python3 -m unittest discover -s harness -p 'test_*.py'     # TREE is required; unset, every test errors
python3 harness/sim.py --seeds 200 --timeout 60                        # clean product, green
python3 harness/sim.py --tree "$d/tree" --seeds 200 --tape-dir "$d"     # planted copy: red, writes a tape
python3 harness/sim.py --replay "$d"/tape-*-seed3.json                   # replays on the tape's own tree: same step, same message
python3 harness/sim.py --replay "$d"/tape-*-seed3.json --tree product   # same tape on the clean product: green
../../scripts/coverage-plants.sh product                                # every coverage row OK on its plant
../../scripts/plants.sh product plants                                  # standalone: each plant's # check:
../../scripts/gate.sh product quick                                     # or harness, or full; committed tooling
```

A red run writes its tape to `--tape-dir`, else `RUN_OUT` (set by `scripts/run.sh`), else the current dir. A tape records the tree path and a digest of `kvcore.py`; replay says whether the tree it ran matches. `--tree PATH` (or `TREE`) points the sim at another product tree; unset, the sim uses `product/`. The unit tests take the tree from `TREE` only and error without it, so a row that forgets it cannot grade a fixed tree and stay green.

## Gate tiers

The example's stages sit in the ADOPT block of `scripts/gate.sh`: that block is the pattern an adopter copies and then replaces. `scripts/gate.sh <tree> [quick|harness|full]` snapshots the tree (uncommitted edits included for `HUMAN_REPO`) and this repo at `HEAD`, then runs each stage from the snapshot under its own `scripts/run.sh` with `TREE` set to the tree snapshot. Uncommitted harness or tooling edits do not reach the verdict: commit first. Verdicts come from `scripts/lib/verdict.sh`: exit 0 when every stage is OK, 2 when any is BLIND, else 1.

| Tier | Stages added | Stage `-t` | Wall-clock, gate total |
|---|---|---|---|
| quick | lint, unit, sim 200 seeds | 60, 60 | 0.38 to 0.68 s |
| harness | compile (`compile()` every harness module, no `.pyc` written), coverage-plants | 60, 240 | 1.79 to 1.81 s |
| full | sweep (seeds 200..2199, heavy `-H`) | 300 | 2.49 to 2.55 s |

Three runs per tier on 2026-11-09, 32 cores (the gate uses one), Python 3.12.3, from a committed clone. Per stage in one full run: lint 0.06 s, unit 0.19 s, sim 0.13 s, compile 0.05 s, coverage-plants 1.37 s (three rows: unit 0.19 s, sim 0.06 s, sweep 0.06 s on their planted copies, plus the clean runs and copies), sweep 0.70 s. The first quick run in a fresh clone took 0.68 s, the next two 0.38 and 0.41 s. The timeouts sit far above the budgets for a toy; in a real harness set them near the measured number, so a slow run turns red instead of eating the afternoon.

Run against a planted copy of the product, `scripts/gate.sh <copy> quick` fails both the unit and sim stages and exits 1 (checked with `refuse_torn_tail` and `ack_before_fsync`). A plant that no longer applies makes the harness tier BLIND and exit 2.
