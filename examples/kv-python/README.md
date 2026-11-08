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
| `harness/sim.py` | Seeded driver, checker, tapes, `--replay` | Evidence before speech: a tape is a claim anyone can rerun |
| `harness/mutations.py` | Plants as text patches on a temp copy of the product | An experiment on human code edits a copy, never the tree |
| `harness/plant_check.py` | Each plant goes red, the clean tree goes green | Green is not self-graded |
| `harness/test_*.py` | Walkthrough of the product's life, torn-tail table, tape replay | `build-method:writing-tests` |
| `gate.sh` | Stages under `timeout`, wall-clock per stage, nonzero on any red | Every run has a hard timeout; every tier has a measured budget |
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

| `KV_PLANT` | Bug | Measured catch rate, seeds 0..1999 | Worst gap between catching seeds |
|---|---|---|---|
| `ack_before_fsync` | ack on append completion | 1454 / 2000 | 6 |
| `accept_mid_log_corruption` | every bad record treated as a torn tail | 1954 / 2000 | 2 |
| `refuse_torn_tail` | a short body refused as corruption | 818 / 2000 | 14 |

The seed budget is 200 per plant, over ten times the worst measured gap. A plant whose anchor text no longer matches the product raises `PlantError` instead of applying nothing: a stale plant must never grade the sim green.

## Commands

From `harness/`:

```sh
python3 -m unittest discover -s . -p 'test_*.py'
python3 sim.py --seeds 200 --start 0 --timeout 60
KV_PLANT=ack_before_fsync python3 sim.py --seeds 200      # red, writes tape-ack_before_fsync-seed3.json
python3 sim.py --replay tape-ack_before_fsync-seed3.json   # same step, same message
KV_PLANT= python3 sim.py --replay tape-ack_before_fsync-seed3.json   # same tape on the clean product: green
python3 plant_check.py
```

Replay uses the plant named in the tape unless `KV_PLANT` is set; empty means the clean tree. `--tree PATH` (or `KV_TREE`) points any of them at another product tree.

From this folder:

```sh
./gate.sh                    # quick: unit, sim 200 seeds, plant_check
./gate.sh path/to/tree full  # adds a 2000-seed sweep (seeds 200..2199)
```

## Measured budgets

This machine, 32 cores (the gate uses one), Python 3.12.3, three runs each:

| Tier | Wall-clock | Stage `timeout` |
|---|---|---|
| quick | 0.42 to 0.45 s | unit 60 s, sim 60 s, plant_check 120 s |
| full | 1.12 to 1.18 s | quick plus sweep 300 s |

Per stage in one full run: unit 0.09 s, sim-quick 0.11 s, plant-check 0.23 s, sim-sweep 0.74 s. The timeouts are far above the budgets on purpose for a toy; in a real harness set them near the measured number, so a slow run turns red instead of eating the afternoon.

Run against each planted copy of the product, the gate goes red on all three stages and exits 1.
