from typing import Any, Protocol


class DestinationError(Exception):
    pass


class Destination(Protocol):
    """Where a rotated secret is written. Backups hold secrets: keep them in memory only."""

    def read_current(self) -> Any: ...

    def write(self, secret: str) -> None: ...

    def restore(self, backup: Any) -> None: ...
