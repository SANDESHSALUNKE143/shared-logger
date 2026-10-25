"""Console destination.

Writes one compact JSON object per line. With ``stream`` set to ``auto``
(the default), ERROR and CRITICAL go to stderr and every other level goes to
stdout. ``stdout`` and ``stderr`` force a single stream.

The adapter flushes the selected stream after each event. It does not close
``sys.stdout`` or ``sys.stderr``.
"""

from __future__ import annotations

import json
import sys
from typing import Any, TextIO

from shared_logger.adapters.base import LoggingAdapter
from shared_logger.exceptions import ConfigurationError, DestinationError

_STREAMS = {"auto", "stdout", "stderr"}
_STDERR_LEVELS = {"ERROR", "CRITICAL"}


def _dump(event: dict[str, Any]) -> str:
    return json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"


class ConsoleAdapter(LoggingAdapter):
    """Write structured JSON to stdout or stderr."""

    def __init__(self) -> None:
        self._mode = "auto"
        self._initialized = False
        self._closed = False

    def initialize(self, config: dict[str, Any]) -> None:
        """Validate ``stream`` and mark the adapter ready."""
        if self._initialized:
            raise ConfigurationError("console adapter is already initialized.")
        if not isinstance(config, dict):
            raise ConfigurationError("console destination_config must be a dictionary.")
        unknown = sorted(set(config) - {"stream"})
        if unknown:
            names = ", ".join(unknown)
            raise ConfigurationError(
                f"console destination_config does not support: {names}. Supported key: stream."
            )
        mode = config.get("stream", "auto")
        if not isinstance(mode, str) or mode not in _STREAMS:
            raise ConfigurationError(
                "console destination_config['stream'] must be 'auto', 'stdout', or 'stderr'. "
                f"Got {mode!r}."
            )
        self._mode = mode
        self._initialized = True

    def write(self, event: dict[str, Any]) -> None:
        """Write one JSON line and flush the selected stream."""
        self._require_open()
        stream = self._select(event)
        stream.write(_dump(event))
        stream.flush()

    def flush(self) -> None:
        """Flush stdout and stderr."""
        if not self._initialized or self._closed:
            return
        sys.stdout.flush()
        sys.stderr.flush()

    def close(self) -> None:
        """Mark the adapter closed without closing process streams."""
        if self._closed:
            return
        self._closed = True
        if not self._initialized:
            return
        try:
            sys.stdout.flush()
        finally:
            sys.stderr.flush()

    def _require_open(self) -> None:
        if not self._initialized:
            raise DestinationError("console adapter is not initialized.")
        if self._closed:
            raise DestinationError("console adapter is closed.")

    def _select(self, event: dict[str, Any]) -> TextIO:
        if self._mode == "stdout":
            return sys.stdout
        if self._mode == "stderr":
            return sys.stderr
        if event.get("level") in _STDERR_LEVELS:
            return sys.stderr
        return sys.stdout
