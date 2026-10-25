"""Destination adapter contract.

Adapters own destination setup, one-event writes, flushing, and cleanup.
The logger does not open files, sockets, or other destination resources itself.
"""

from abc import ABC, abstractmethod
from typing import Any


class LoggingAdapter(ABC):
    """Interface implemented by every destination."""

    @abstractmethod
    def initialize(self, config: dict[str, Any]) -> None:
        """Validate destination settings and prepare the destination."""

    @abstractmethod
    def write(self, event: dict[str, Any]) -> None:
        """Write one already-built event."""

    def flush(self) -> None:
        """Flush writes the destination still has buffered."""

    def close(self) -> None:
        """Release destination resources. Extra calls must not fail."""
