"""Reference model, written from the contract, never from kvcore.py.

Contract: every op applies in order and reads see it at once. An acked op survives
any crash, and so does every op before it. After a crash the store holds some
prefix of the op history that includes every acked op, and nothing else.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Op:
    key: str
    value: str | None


def replay(ops: list[Op]) -> dict[str, str]:
    state: dict[str, str] = {}
    for op in ops:
        if op.value is None:
            state.pop(op.key, None)
        else:
            state[op.key] = op.value
    return state


class Model:
    def __init__(self):
        self._ops: list[Op] = []
        self._acked = 0
        self._state: dict[str, str] = {}

    def put(self, key: str, value: str) -> bool:
        return self._record(Op(key, value))

    def delete(self, key: str) -> bool:
        return self._record(Op(key, None))

    def get(self, key: str) -> str | None:
        return self._state.get(key)

    def snapshot(self) -> dict[str, str]:
        return dict(self._state)

    def note_ack(self, acked: bool) -> None:
        """The subject under test acked (or not) the latest op; acks cover all earlier ops."""
        if acked:
            self._acked = len(self._ops)

    def crash_outcomes(self, floor: int | None = None) -> list[tuple[int, dict[str, str]]]:
        """Every (prefix length, state) a crash may legally leave. A lower `floor` widens it for diagnosis."""
        start = self._acked if floor is None else floor
        return [(k, replay(self._ops[:k])) for k in range(start, len(self._ops) + 1)]

    def adopt(self, prefix: int) -> None:
        """After a checked recovery, the surviving prefix is the new durable history."""
        self._ops = self._ops[:prefix]
        self._acked = prefix
        self._state = replay(self._ops)

    def _record(self, op: Op) -> bool:
        self._ops.append(op)
        if op.value is None:
            self._state.pop(op.key, None)
        else:
            self._state[op.key] = op.value
        return True
