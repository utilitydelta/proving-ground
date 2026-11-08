"""Log-structured KV store core, sans-IO.

The core never touches a disk. Mutations return effects (Append, Fsync) for the
caller to perform; the caller feeds completions back and learns which ops are
acked. Recovery scans the log bytes the caller read and may ask for a Truncate.

Record: header = body_len u32 | body_crc u32 | header_crc u32 (crc of the first 8),
body = kind u8 | key_len u16 | key | value. All little-endian, UTF-8 text.
"""

import struct
import zlib
from dataclasses import dataclass

HEADER = struct.Struct("<II")
HEADER_LEN = HEADER.size + 4
KEY_LEN = struct.Struct("<H")
PUT = 1
DELETE = 2


@dataclass(frozen=True)
class Append:
    op: int
    offset: int
    data: bytes


@dataclass(frozen=True)
class Fsync:
    op: int


@dataclass(frozen=True)
class Truncate:
    length: int


@dataclass(frozen=True)
class AppendDone:
    op: int


@dataclass(frozen=True)
class FsyncDone:
    op: int


Effect = Append | Fsync | Truncate
Completion = AppendDone | FsyncDone


class CorruptLog(Exception):
    def __init__(self, offset: int, reason: str):
        super().__init__(f"corrupt log at offset {offset}: {reason}")
        self.offset = offset
        self.reason = reason


@dataclass(frozen=True)
class Record:
    kind: int
    key: str
    value: str
    end: int


@dataclass(frozen=True)
class Bad:
    reason: str
    at_tail: bool


def encode(kind: int, key: str, value: str) -> bytes:
    key_bytes = key.encode()
    body = bytes([kind]) + KEY_LEN.pack(len(key_bytes)) + key_bytes + value.encode()
    head = HEADER.pack(len(body), zlib.crc32(body))
    return head + struct.pack("<I", zlib.crc32(head)) + body


def read_record(log: bytes, pos: int) -> Record | Bad:
    # A torn write persists a prefix of the record, so it can only show up as a
    # short header, a short body, or (sector loss) a bad body that ends the log.
    # A complete header with a bad checksum is never a torn write.
    if len(log) - pos < HEADER_LEN:
        return Bad("short header", at_tail=True)
    head = log[pos : pos + HEADER.size]
    (header_crc,) = struct.unpack_from("<I", log, pos + HEADER.size)
    if zlib.crc32(head) != header_crc:
        return Bad("header checksum mismatch", at_tail=False)
    body_len, body_crc = HEADER.unpack(head)
    start = pos + HEADER_LEN
    end = start + body_len
    if end > len(log):
        return Bad("short body", at_tail=True)
    body = log[start:end]
    if zlib.crc32(body) != body_crc:
        return Bad("body checksum mismatch", at_tail=end == len(log))
    if body_len < 1 + KEY_LEN.size or body[0] not in (PUT, DELETE):
        return Bad("malformed body", at_tail=False)
    (key_len,) = KEY_LEN.unpack_from(body, 1)
    key_end = 1 + KEY_LEN.size + key_len
    if key_end > body_len:
        return Bad("key overruns body", at_tail=False)
    key = body[1 + KEY_LEN.size : key_end].decode()
    return Record(body[0], key, body[key_end:].decode(), end)


def apply(state: dict[str, str], kind: int, key: str, value: str) -> None:
    if kind == PUT:
        state[key] = value
    else:
        state.pop(key, None)


def open_log(log: bytes) -> tuple["KvCore", list[Effect]]:
    """Rebuild state from the log. Drops a torn tail; refuses corruption by name."""
    state: dict[str, str] = {}
    pos = 0
    while pos < len(log):
        rec = read_record(log, pos)
        if isinstance(rec, Bad):
            if rec.at_tail:
                return KvCore(state, pos), [Truncate(pos)]
            raise CorruptLog(pos, rec.reason)
        apply(state, rec.kind, rec.key, rec.value)
        pos = rec.end
    return KvCore(state, pos), []


class KvCore:
    """Build with open_log. Reads see writes before they are acked."""

    def __init__(self, state: dict[str, str], end: int):
        self._state = state
        self._end = end
        self._next_op = 0
        self._pending: dict[int, int] = {}

    def put(self, key: str, value: str) -> list[Effect]:
        return self._append(PUT, key, value)

    def delete(self, key: str) -> list[Effect]:
        return self._append(DELETE, key, "")

    def get(self, key: str) -> str | None:
        return self._state.get(key)

    def snapshot(self) -> tuple[tuple[str, str], ...]:
        return tuple(sorted(self._state.items()))

    def complete(self, done: Completion) -> list[int]:
        """Returns the ops acked by this completion. An fsync covers every earlier append."""
        if isinstance(done, AppendDone):
            return []
        return self._ack_through(self._pending.get(done.op, -1))

    def _append(self, kind: int, key: str, value: str) -> list[Effect]:
        data = encode(kind, key, value)
        op = self._next_op
        self._next_op += 1
        offset = self._end
        self._end += len(data)
        self._pending[op] = self._end
        apply(self._state, kind, key, value)
        return [Append(op, offset, data), Fsync(op)]

    def _ack_through(self, end: int) -> list[int]:
        acked = [op for op, op_end in self._pending.items() if op_end <= end]
        for op in acked:
            del self._pending[op]
        return acked
