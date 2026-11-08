import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from mutations import DEFAULT_TREE, load_product
from sim import generate, run, write_tape

TREE = Path(os.environ.get("KV_TREE", DEFAULT_TREE))
HERE = Path(__file__).resolve().parent


class TapeReplay(unittest.TestCase):
    def test_recorded_tape_replays_to_the_same_failure(self):
        kv = load_product(TREE, "ack_before_fsync")
        seed, failure = next((s, f) for s in range(200) if (f := run(kv, generate(s))))
        with tempfile.TemporaryDirectory() as tmp:
            tape = write_tape(Path(tmp), seed, "ack_before_fsync", generate(seed), failure)
            done = subprocess.run(
                [sys.executable, str(HERE / "sim.py"), "--tree", str(TREE), "--replay", str(tape)],
                env={k: v for k, v in os.environ.items() if k != "KV_PLANT"},
                capture_output=True,
                text=True,
                timeout=60,
            )
            recorded = json.loads(tape.read_text())["failure"]
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn(f"step {recorded['step']} ", done.stdout)
        self.assertIn(recorded["message"], done.stdout)

    def test_same_tape_is_green_on_the_clean_product(self):
        planted = load_product(TREE, "ack_before_fsync")
        seed = next(s for s in range(200) if run(planted, generate(s)))
        self.assertIsNone(run(load_product(TREE), generate(seed)))


if __name__ == "__main__":
    unittest.main()
