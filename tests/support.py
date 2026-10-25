"""Helpers shared by unit and integration tests."""

import json
from pathlib import Path
from typing import Any

from shared_logger import ConfigurationError, LoggingAdapter


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read JSON Lines from ``path``. Missing and empty files yield no events."""
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return []
    return [json.loads(line) for line in text.splitlines() if line.strip()]


class ListAdapter(LoggingAdapter):
    """In-memory adapter. ``Logger.initialize`` constructs the instance."""

    instances: list["ListAdapter"] = []
    fail_write = False
    fail_flush = False
    fail_close = False
    init_error = ""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self.write_calls = 0
        self.closed = False
        ListAdapter.instances.append(self)

    def initialize(self, config: dict[str, Any]) -> None:
        if ListAdapter.init_error == "config":
            raise ConfigurationError("bad destination settings")
        if ListAdapter.init_error == "runtime":
            raise RuntimeError("connection refused")

    def write(self, event: dict[str, Any]) -> None:
        self.write_calls += 1
        if ListAdapter.fail_write:
            raise OSError("disk full")
        self.events.append(event)

    def flush(self) -> None:
        if ListAdapter.fail_flush:
            raise OSError("flush failed")

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        if ListAdapter.fail_close:
            raise OSError("close failed")
