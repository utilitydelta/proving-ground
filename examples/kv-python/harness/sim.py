"""Seeded single-threaded simulator: product adapter against the reference model.

A seed expands into an event list up front; the run is a pure function of that
list, so a tape (the list) replays exactly with no RNG involved.

    python3 sim.py --seeds 200 --start 0 --timeout 60
    python3 sim.py --seeds 2000 --keep-going      # every seed; caught/total and the worst gap
    python3 sim.py --replay tape.json [--tree PATH]
"""

import argparse
import json
import os
import random
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from adapter import (
    CrashAfterFsync,
    CrashBeforeFsync,
    Fault,
    KvAdapter,
    LostCompletion,
    TornSector,
    TornWrite,
)
from model import Model
from loader import DEFAULT_TREE, load_product, tree_digest

KEYS = "abcd"
STEPS = 40
CRASHING = (CrashBeforeFsync, CrashAfterFsync, TornWrite, TornSector)
EXIT_RED = 1
EXIT_TIMEOUT = 3


@dataclass(frozen=True)
class Failure:
    step: int
    message: str


class Violation(Exception):
    pass


def generate(seed: int, steps: int = STEPS) -> list[dict]:
    rng = random.Random(seed)
    events: list[dict] = []
    for _ in range(steps):
        roll = rng.random()
        key = rng.choice(KEYS)
        if roll < 0.45:
            value = "".join(rng.choice("xyz") for _ in range(rng.randint(1, 6)))
            events.append({"op": "put", "key": key, "value": value, "fault": _fault(rng)})
        elif roll < 0.60:
            events.append({"op": "delete", "key": key, "fault": _fault(rng)})
        elif roll < 0.80:
            events.append({"op": "get", "key": key})
        elif roll < 0.90:
            events.append({"op": "restart"})
        else:
            events.append({"op": "bitrot", "pick": rng.random(), "byte": rng.random()})
    return events


def _fault(rng: random.Random) -> dict | None:
    if rng.random() >= 0.3:
        return None
    kind = rng.choice(["crash_before_fsync", "crash_after_fsync", "torn_write", "torn_sector", "lost_completion"])
    return {"kind": kind, "cut": rng.random()} if kind == "torn_write" else {"kind": kind}


def decode_fault(spec: dict | None) -> Fault:
    if spec is None:
        return None
    return {
        "crash_before_fsync": lambda: CrashBeforeFsync(),
        "crash_after_fsync": lambda: CrashAfterFsync(),
        "torn_write": lambda: TornWrite(spec["cut"]),
        "torn_sector": lambda: TornSector(),
        "lost_completion": lambda: LostCompletion(),
    }[spec["kind"]]()


def run(kv: ModuleType, events: list[dict], seen: Counter | None = None) -> Failure | None:
    """`seen` counts the paths exercised, so a green run can show it reached the faults."""
    seen = Counter() if seen is None else seen
    model = Model()
    try:
        subject = KvAdapter(kv)
    except Exception as exc:
        return Failure(-1, f"open of an empty log raised {exc!r}")
    for step, event in enumerate(events):
        try:
            seen[_step(kv, subject, model, event)] += 1
            if subject.snapshot() != model.snapshot():
                raise Violation(f"state {subject.snapshot()} != model {model.snapshot()}")
        except Violation as v:
            return Failure(step, str(v))
        except Exception as exc:
            return Failure(step, f"unexpected {exc!r}")
    return None


def _step(kv: ModuleType, subject: KvAdapter, model: Model, event: dict) -> str:
    op = event["op"]
    if op in ("put", "delete"):
        fault = decode_fault(event["fault"])
        try:
            if op == "put":
                acked = subject.put(event["key"], event["value"], fault)
                model.put(event["key"], event["value"])
            else:
                acked = subject.delete(event["key"], fault)
                model.delete(event["key"])
        except kv.CorruptLog as exc:
            raise Violation(f"recovery refused a torn tail after {event['fault']['kind']}: {exc}")
        model.note_ack(acked)
        if isinstance(fault, CRASHING):
            _check_recovery(subject, model)
        return event["fault"]["kind"] if fault else op
    elif op == "get":
        got, want = subject.get(event["key"]), model.get(event["key"])
        if got != want:
            raise Violation(f"get {event['key']!r} returned {got!r}, model says {want!r}")
        return op
    elif op == "restart":
        try:
            subject.restart()
        except kv.CorruptLog as exc:
            raise Violation(f"recovery refused a clean log: {exc}")
        _check_recovery(subject, model)
        return op
    return _bitrot(kv, subject, model, event)


def _bitrot(kv: ModuleType, subject: KvAdapter, model: Model, event: dict) -> str:
    disk = subject.disk
    starts = disk.record_starts
    if len(starts) < 2:
        return "bitrot_skipped"
    index = int(event["pick"] * (len(starts) - 1))
    start, end = starts[index], starts[index + 1]
    pos = start + int(event["byte"] * (end - start))
    disk.durable[pos] ^= 0xFF
    try:
        subject.restart()
    except kv.CorruptLog:
        disk.durable[pos] ^= 0xFF
        subject.restart()
        _check_recovery(subject, model)
        return "bitrot_refused"
    raise Violation(f"recovery accepted corruption at byte {pos} in record {index} of {len(starts)}")


def _check_recovery(subject: KvAdapter, model: Model) -> None:
    snapshot = subject.snapshot()
    outcomes = model.crash_outcomes()
    matches = [k for k, state in outcomes if state == snapshot]
    if matches:
        model.adopt(max(matches))
        return
    acked = outcomes[0][0]
    lost = [k for k, state in model.crash_outcomes(floor=0) if state == snapshot and k < acked]
    if lost:
        raise Violation(f"acked write lost: recovered {max(lost)} ops of history, {acked} were acked")
    raise Violation(f"recovered {snapshot} matches no prefix of the op history")


def write_tape(tape_dir: Path, seed: int, tree: Path, events: list[dict], failure: Failure) -> Path:
    tape = {
        "seed": seed,
        "tree": str(tree.resolve()),
        "digest": tree_digest(tree),
        "failure": {"step": failure.step, "message": failure.message},
        "events": events,
    }
    tape_dir.mkdir(parents=True, exist_ok=True)
    path = tape_dir / f"tape-{tape['digest']}-seed{seed}.json"
    path.write_text(json.dumps(tape, indent=1) + "\n")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seeds", type=int, default=200)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--steps", type=int, default=STEPS)
    parser.add_argument("--timeout", type=float, default=60.0, help="wall-clock cap; past it the run is red")
    parser.add_argument("--tree", type=Path, help="product tree; default KV_TREE, then the example's product/")
    parser.add_argument("--tape-dir", type=Path, default=Path("."))
    parser.add_argument("--replay", type=Path, help="run one recorded tape instead of seeds; --tree defaults to the tape's")
    parser.add_argument("--keep-going", action="store_true", help="run every seed, report caught/total and the worst gap")
    args = parser.parse_args()

    given = args.tree or (Path(os.environ["KV_TREE"]) if os.environ.get("KV_TREE") else None)
    if args.replay:
        return replay_tape(given, args.replay)

    tree = given or DEFAULT_TREE
    kv = load_product(tree)
    began = time.monotonic()
    seen: Counter = Counter()
    caught: list[int] = []
    for seed in range(args.start, args.start + args.seeds):
        if time.monotonic() - began > args.timeout:
            print(f"sim: TIMEOUT after {seed - args.start} of {args.seeds} seeds ({args.timeout}s)")
            return EXIT_TIMEOUT
        events = generate(seed, args.steps)
        failure = run(kv, events, seen)
        if failure is None:
            continue
        if not caught:
            path = write_tape(args.tape_dir, seed, tree, events, failure)
            print(f"sim: RED seed {seed} step {failure.step} (tree {tree_digest(tree)}): {failure.message}")
            print(f"sim: tape {path}")
        caught.append(seed)
        if not args.keep_going:
            print(json.dumps({"seed": seed, "events": events[: failure.step + 1]}))
            return EXIT_RED
    elapsed = time.monotonic() - began
    if caught:
        print(f"sim: RED on {len(caught)}/{args.seeds} seeds from {args.start}, worst gap "
              f"{worst_gap(args.start, caught)}, {elapsed:.2f}s")
        return EXIT_RED
    print(f"sim: GREEN {args.seeds} seeds from {args.start}, {args.steps} steps, tree {tree_digest(tree)}, "
          f"{elapsed:.2f}s")
    print("sim: exercised " + " ".join(f"{k}={v}" for k, v in sorted(seen.items())))
    return 0


def worst_gap(start: int, caught: list[int]) -> int:
    """Most seeds a run starting anywhere in the range needs to reach a catching seed, counting that seed."""
    marks = [start - 1, *caught]
    return max(b - a for a, b in zip(marks, marks[1:]))


def replay_tape(tree: Path | None, path: Path) -> int:
    """Replays against the tape's own tree unless one is given."""
    tape = json.loads(path.read_text())
    tree = Path(tape["tree"]) if tree is None else tree
    digest = tree_digest(tree)
    same = "same tree as the tape" if digest == tape["digest"] else f"tape ran {tape['digest']}"
    failure = run(load_product(tree), tape["events"])
    if failure is None:
        print(f"replay: GREEN {path} on tree {digest} ({same})")
        return 0
    print(f"replay: RED step {failure.step} on tree {digest} ({same}): {failure.message}")
    return EXIT_RED


if __name__ == "__main__":
    sys.exit(main())
