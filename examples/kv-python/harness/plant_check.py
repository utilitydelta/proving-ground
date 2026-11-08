"""Proves the sim can fail: each plant must go red within the seed budget, the clean tree green.

    python3 plant_check.py [--tree PATH] [--seeds 200]

Runs sim.py as a subprocess per plant, so a plant can never leak into another run.
Exit 0 only when every plant is caught and the clean tree passes.
"""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from mutations import DEFAULT_TREE, PLANTS

HERE = Path(__file__).resolve().parent
SEED_BUDGET = 200


def run_sim(tree: Path, plant: str | None, seeds: int, tape_dir: str) -> tuple[int, str]:
    env = {**os.environ, "KV_PLANT": plant or ""}
    cmd = [sys.executable, str(HERE / "sim.py"), "--tree", str(tree), "--seeds", str(seeds), "--tape-dir", tape_dir]
    done = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=120)
    first = (done.stdout or done.stderr).splitlines()[:1]
    return done.returncode, first[0] if first else "(no output)"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tree", type=Path, default=Path(os.environ.get("KV_TREE", DEFAULT_TREE)))
    parser.add_argument("--seeds", type=int, default=SEED_BUDGET)
    args = parser.parse_args()

    bad = 0
    with tempfile.TemporaryDirectory(prefix="kv-plant-tapes-") as tapes:
        code, line = run_sim(args.tree, None, args.seeds, tapes)
        ok = code == 0
        bad += not ok
        print(f"plant_check: {'ok  ' if ok else 'FAIL'} clean            expect green: {line}")
        for name, plant in PLANTS.items():
            code, line = run_sim(args.tree, name, args.seeds, tapes)
            ok = code == 1 and line.startswith("sim: RED")
            bad += not ok
            print(f"plant_check: {'ok  ' if ok else 'FAIL'} {name:<25} expect red ({plant.catches}): {line}")
    print(f"plant_check: {'GREEN' if bad == 0 else f'RED, {bad} wrong'} ({len(PLANTS)} plants, {args.seeds} seeds each)")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
