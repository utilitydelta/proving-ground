import os
import unittest
from pathlib import Path

from loader import DEFAULT_TREE, load_product

kv = load_product(Path(os.environ.get("KV_TREE", DEFAULT_TREE)))


def perform(core, effects, log: bytearray, completions=("append", "fsync")) -> list[int]:
    """Performs effects against an in-memory log and feeds the chosen completions back."""
    acked = []
    for effect in effects:
        if isinstance(effect, kv.Append):
            log[effect.offset :] = effect.data
            if "append" in completions:
                acked += core.complete(kv.AppendDone(effect.op))
        elif isinstance(effect, kv.Fsync) and "fsync" in completions:
            acked += core.complete(kv.FsyncDone(effect.op))
    return acked


class ProductLife(unittest.TestCase):
    def test_writes_ack_on_fsync_and_survive_reopen(self):
        log = bytearray()
        core, effects = kv.open_log(bytes(log))
        self.assertEqual(effects, [])
        self.assertEqual(core.snapshot(), ())

        put = core.put("a", "1")
        self.assertEqual([type(e) for e in put], [kv.Append, kv.Fsync])
        self.assertEqual(core.get("a"), "1", "reads see a write before its ack")
        self.assertEqual(perform(core, put, log, completions=("append",)), [], "append alone is not an ack")
        self.assertEqual(core.complete(kv.FsyncDone(put[1].op)), [put[0].op])

        self.assertEqual(perform(core, core.put("b", "2"), log), [1])
        self.assertEqual(perform(core, core.delete("a"), log), [2])
        self.assertEqual(core.snapshot(), (("b", "2"),))

        reopened, effects = kv.open_log(bytes(log))
        self.assertEqual(effects, [])
        self.assertEqual(reopened.snapshot(), (("b", "2"),))
        self.assertIsNone(reopened.get("a"))

    def test_one_fsync_acks_every_earlier_append(self):
        log = bytearray()
        core, _ = kv.open_log(b"")
        self.assertEqual(perform(core, core.put("a", "1"), log, completions=("append",)), [])
        self.assertEqual(perform(core, core.put("b", "2"), log), [0, 1])

    def test_snapshot_is_key_ordered(self):
        log = bytearray()
        core, _ = kv.open_log(b"")
        for key in "cab":
            perform(core, core.put(key, key.upper()), log)
        self.assertEqual(core.snapshot(), (("a", "A"), ("b", "B"), ("c", "C")))


if __name__ == "__main__":
    unittest.main()
