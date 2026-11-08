import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from loader import DEFAULT_TREE, load_product
from sim import generate, run, worst_gap, write_tape

TREE = Path(os.environ.get("KV_TREE", DEFAULT_TREE))
HERE = Path(__file__).resolve().parent
PLANT = HERE.parent / "plants" / "ack_before_fsync.patch"


def planted_copy(into: Path) -> Path:
    """TREE with the ack_before_fsync plant applied, the same way scripts/plants.sh applies it."""
    copy = into / "tree"
    shutil.copytree(TREE, copy, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    env = {**os.environ, "GIT_CEILING_DIRECTORIES": str(into)}
    subprocess.run(["git", "apply", "-p1", str(PLANT)], cwd=copy, env=env, check=True, timeout=30)
    return copy


def replay(tape: Path, *tree: str) -> subprocess.CompletedProcess:
    args = ["--tree", tree[0]] if tree else []
    return subprocess.run(
        [sys.executable, str(HERE / "sim.py"), "--replay", str(tape), *args],
        env={k: v for k, v in os.environ.items() if k != "KV_TREE"},
        capture_output=True,
        text=True,
        timeout=60,
    )


class TapeReplay(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.planted = planted_copy(self.tmp)
        kv = load_product(self.planted)
        self.seed, self.failure = next((s, f) for s in range(200) if (f := run(kv, generate(s))))
        self.tape = write_tape(self.tmp, self.seed, self.planted, generate(self.seed), self.failure)

    def test_recorded_tape_replays_to_the_same_failure_on_its_own_tree(self):
        done = replay(self.tape)
        recorded = json.loads(self.tape.read_text())["failure"]
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn(f"step {recorded['step']} ", done.stdout)
        self.assertIn("same tree as the tape", done.stdout)
        self.assertIn(recorded["message"], done.stdout)

    def test_same_tape_is_green_on_the_clean_product(self):
        done = replay(self.tape, str(TREE))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("tape ran ", done.stdout)


# start, catching seeds, worst gap: seeds a run starting anywhere in the range needs to hit one
GAPS = [
    (0, [0], 1),
    (0, [0, 1, 2], 1),
    (0, [5], 6),
    (0, [2, 3, 9], 6),
    (100, [100, 104], 4),
]


class WorstGap(unittest.TestCase):
    def test_counts_from_the_range_start_and_between_catches(self):
        for start, caught, want in GAPS:
            with self.subTest(start=start, caught=caught):
                self.assertEqual(worst_gap(start, caught), want)


if __name__ == "__main__":
    unittest.main()
