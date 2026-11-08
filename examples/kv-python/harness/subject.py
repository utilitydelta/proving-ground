"""The seam the simulator drives. The model and the product adapter both implement it.

Crash, restart and disk faults are not on the seam: a reference model has no disk.
The adapter takes them; the model answers with the states a crash may leave.
"""

from typing import Protocol


class Subject(Protocol):
    def put(self, key: str, value: str) -> bool:
        """True when the write is acked as durable."""

    def delete(self, key: str) -> bool:
        """True when the delete is acked as durable."""

    def get(self, key: str) -> str | None: ...

    def snapshot(self) -> dict[str, str]: ...
