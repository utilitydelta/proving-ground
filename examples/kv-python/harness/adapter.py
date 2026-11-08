"""Thin adapter: the product core onto Subject, effects performed against a simulated disk.

Faults land at the effect boundary, between the core asking for I/O and the
completion coming back. The adapter holds no KV logic of its own.
"""

from dataclasses import dataclass, field
from types import ModuleType


@dataclass(frozen=True)
class CrashBeforeFsync:
    pass


@dataclass(frozen=True)
class CrashAfterFsync:
    """The fsync reached the disk; the process died before the completion arrived."""


@dataclass(frozen=True)
class TornWrite:
    """Crash mid-append: only the first `cut` fraction of the record reached the disk."""

    cut: float


@dataclass(frozen=True)
class TornSector:
    """Crash after the append: the record's full length is on disk but its last byte is lost."""


@dataclass(frozen=True)
class LostCompletion:
    """The fsync happened; its completion never reached the core. No crash."""


Fault = CrashBeforeFsync | CrashAfterFsync | TornWrite | TornSector | LostCompletion | None


class DiskError(Exception):
    pass


@dataclass
class SimDisk:
    durable: bytearray = field(default_factory=bytearray)
    volatile: bytearray = field(default_factory=bytearray)
    record_starts: list[int] = field(default_factory=list)

    def append(self, offset: int, data: bytes) -> None:
        end = len(self.durable) + len(self.volatile)
        if offset != end:
            raise DiskError(f"append at {offset}, log ends at {end}")
        self.record_starts.append(end)
        self.volatile += data

    def fsync(self) -> None:
        self.durable += self.volatile
        self.volatile.clear()

    def crash(self, keep: int) -> None:
        self.durable += self.volatile[:keep]
        self.volatile.clear()
        self._forget_past(len(self.durable))

    def truncate(self, length: int) -> None:
        if self.volatile or length > len(self.durable):
            raise DiskError(f"truncate to {length} over {len(self.durable)} durable bytes")
        del self.durable[length:]
        self._forget_past(length)

    def _forget_past(self, length: int) -> None:
        self.record_starts = [s for s in self.record_starts if s < length]


class KvAdapter:
    def __init__(self, kv: ModuleType):
        self._kv = kv
        self.disk = SimDisk()
        self._core = self._recover()

    def put(self, key: str, value: str, fault: Fault = None) -> bool:
        return self._mutate(self._core.put(key, value), fault)

    def delete(self, key: str, fault: Fault = None) -> bool:
        return self._mutate(self._core.delete(key), fault)

    def get(self, key: str) -> str | None:
        return self._core.get(key)

    def snapshot(self) -> dict[str, str]:
        return dict(self._core.snapshot())

    def restart(self) -> None:
        """Crash with nothing in flight and recover. Raises the product's CorruptLog on refusal."""
        self.disk.crash(keep=0)
        self._core = self._recover()

    def _recover(self):
        core, effects = self._kv.open_log(bytes(self.disk.durable))
        for effect in effects:
            self.disk.truncate(effect.length)
        return core

    def _mutate(self, effects: list, fault: Fault) -> bool:
        kv, disk = self._kv, self.disk
        acked: list[int] = []
        op = effects[0].op
        for effect in effects:
            if isinstance(effect, kv.Append):
                if isinstance(fault, TornWrite):
                    disk.append(effect.offset, effect.data)
                    self._crash(keep=int(len(effect.data) * fault.cut))
                    return False
                disk.append(effect.offset, effect.data)
                if isinstance(fault, TornSector):
                    disk.volatile[-1] ^= 0xFF
                    self._crash(keep=len(disk.volatile))
                    return False
                acked += self._core.complete(kv.AppendDone(effect.op))
            elif isinstance(effect, kv.Fsync):
                if isinstance(fault, CrashBeforeFsync):
                    self._crash(keep=0)
                    # An ack the core already gave out reached the client before the crash.
                    return op in acked
                disk.fsync()
                if isinstance(fault, CrashAfterFsync):
                    self._crash(keep=0)
                    return op in acked
                if isinstance(fault, LostCompletion):
                    return op in acked
                acked += self._core.complete(kv.FsyncDone(effect.op))
            else:
                raise DiskError(f"unexpected effect from a mutation: {effect!r}")
        return op in acked

    def _crash(self, keep: int) -> None:
        self.disk.crash(keep)
        self._core = self._recover()
