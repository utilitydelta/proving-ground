import os
import unittest
from pathlib import Path

from mutations import DEFAULT_TREE, load_product

kv = load_product(Path(os.environ.get("KV_TREE", DEFAULT_TREE)))

RECORDS = [kv.encode(kv.PUT, "a", "1"), kv.encode(kv.PUT, "b", "22"), kv.encode(kv.PUT, "c", "333")]
LOG = b"".join(RECORDS)
LAST = len(RECORDS[0]) + len(RECORDS[1])


def flip(log: bytes, pos: int) -> bytes:
    return log[:pos] + bytes([log[pos] ^ 0xFF]) + log[pos + 1 :]


# name, damaged log, expected: ("keep", snapshot, truncate_to) or ("refuse", offset)
CASES = [
    ("clean log", LOG, ("keep", "abc", None)),
    ("tail cut inside the header", LOG[: LAST + 5], ("keep", "ab", LAST)),
    ("tail cut inside the body", LOG[:-2], ("keep", "ab", LAST)),
    ("tail last byte lost", flip(LOG, len(LOG) - 1), ("keep", "ab", LAST)),
    ("tail header byte flipped", flip(LOG, LAST + 1), ("refuse", LAST)),
    ("mid-log body byte flipped", flip(LOG, len(RECORDS[0]) - 1), ("refuse", 0)),
    ("mid-log header byte flipped", flip(LOG, 2), ("refuse", 0)),
    ("second record body flipped", flip(LOG, LAST - 1), ("refuse", len(RECORDS[0]))),
]


class TornTailRule(unittest.TestCase):
    def test_torn_tail_drops_and_mid_log_corruption_refuses(self):
        for name, log, want in CASES:
            with self.subTest(name):
                if want[0] == "refuse":
                    with self.assertRaises(kv.CorruptLog) as caught:
                        kv.open_log(log)
                    self.assertEqual(caught.exception.offset, want[1])
                    continue
                core, effects = kv.open_log(log)
                self.assertEqual("".join(k for k, _ in core.snapshot()), want[1])
                truncate = [e.length for e in effects if isinstance(e, kv.Truncate)]
                self.assertEqual(truncate, [] if want[2] is None else [want[2]])


if __name__ == "__main__":
    unittest.main()
