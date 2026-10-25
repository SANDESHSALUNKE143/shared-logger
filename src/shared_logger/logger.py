"""Public logger.

Importing this package does not open files or connect to a destination.
Call :meth:`Logger.initialize` with a :class:`~shared_logger.LoggingConfig`.
"""

from __future__ import annotations

import sys
import threading
from typing import Any

from shared_logger.adapters.base import LoggingAdapter
from shared_logger.config import LoggingConfig
from shared_logger.event import build_event
from shared_logger.exceptions import (
    ConfigurationError,
    DestinationError,
    LoggerClosedError,
    LoggingError,
)
from shared_logger.factory import SyncDelivery, open_destination
from shared_logger.filters import passes_minimum
from shared_logger.levels import normalize_level


class _Runtime:
    """State shared by a logger and the loggers created with ``bind``."""

    def __init__(
        self,
        config: LoggingConfig,
        adapter: LoggingAdapter,
        delivery: SyncDelivery,
    ) -> None:
        self.config = config
        self.adapter = adapter
        self.delivery = delivery
        self.closed = False
        self.failure_count = 0
        self.lock = threading.Lock()


class Logger:
    """Application logging API.

    Use the ``write_*`` methods. They accept a message and structured keyword
    arguments. ``bind`` returns a new logger that adds context to later events
    and does not change the logger it was called on.

    ``close`` is safe to call more than once. Logging after ``close`` raises
    :class:`~shared_logger.LoggerClosedError` so events are not discarded.
    ``flush`` after ``close`` does nothing because no writes are still accepted.

    Bound loggers share the destination. Closing any of them closes that
    destination for all of them.
    """

    def __init__(self, runtime: _Runtime, bound: dict[str, Any] | None = None) -> None:
        self._runtime = runtime
        self._bound = dict(bound or {})

    @classmethod
    def initialize(cls, config: LoggingConfig) -> Logger:
        """Validate ``config``, open the destination, and return a logger.

        Each call creates an independent logger. The library does not attach
        handlers to the standard-library root logger, so a second call does
        not register a duplicate handler.

        Args:
            config: Validated logging settings.

        Raises:
            ConfigurationError: The config or destination settings are invalid,
                or the destination could not be opened.
        """
        if not isinstance(config, LoggingConfig):
            raise ConfigurationError(
                f"Logger.initialize expects a LoggingConfig instance. Got {type(config).__name__}."
            )
        adapter, delivery = open_destination(config)
        return cls(_Runtime(config, adapter, delivery))

    def bind(self, **context: Any) -> Logger:
        """Return a logger that includes ``context`` on later events.

        The original logger is unchanged. Later keyword arguments on a logging
        call overwrite bound keys. ``correlation_id`` is written on the event
        itself. Other keys are written under ``metadata``.
        """
        for key in context:
            if not isinstance(key, str) or not key.strip():
                raise LoggingError("Context names must be non-empty strings.")
        with self._runtime.lock:
            if self._runtime.closed:
                raise LoggerClosedError("Logger is closed. Call Logger.initialize before bind().")
            merged = {**self._bound, **context}
        return Logger(self._runtime, merged)

    def write_debug(self, message: str, **fields: Any) -> None:
        """Write a DEBUG event when the minimum level allows it."""
        self._emit("DEBUG", message, None, fields)

    def write_info(self, message: str, **fields: Any) -> None:
        """Write an INFO event when the minimum level allows it."""
        self._emit("INFO", message, None, fields)

    def write_warning(self, message: str, **fields: Any) -> None:
        """Write a WARNING event when the minimum level allows it."""
        self._emit("WARNING", message, None, fields)

    def write_error(self, message: str, **fields: Any) -> None:
        """Write an ERROR event when the minimum level allows it."""
        self._emit("ERROR", message, None, fields)

    def write_critical(self, message: str, **fields: Any) -> None:
        """Write a CRITICAL event when the minimum level allows it."""
        self._emit("CRITICAL", message, None, fields)

    def write_exception(
        self,
        message: str,
        exception: BaseException | None = None,
        **fields: Any,
    ) -> None:
        """Write an ERROR event that includes exception details.

        The event records the exception type, message, and traceback when a
        traceback is attached. Pass ``exception`` explicitly. This method does
        not read an active ``except`` clause on its own, so the recorded
        exception is the one the caller supplied.

        Exception text is not redacted. Do not put secrets in exception messages.
        """
        if exception is not None and not isinstance(exception, BaseException):
            raise LoggingError(
                f"exception must be a BaseException instance. Got {type(exception).__name__}."
            )
        self._emit("ERROR", message, exception, fields)

    def flush(self) -> None:
        """Flush writes buffered by the destination.

        Does nothing after :meth:`close`. There is no background queue in this
        release, so flush only covers what the adapter still holds.
        """
        with self._runtime.lock:
            if self._runtime.closed:
                return
            try:
                self._runtime.delivery.flush()
            except Exception as exc:
                self._report_destination_failure(exc, "flush")

    def close(self) -> None:
        """Release the destination.

        The first call marks the logger closed and then asks the adapter to
        flush and release resources. If flushing fails, the adapter still
        closes its resources. Further calls do nothing and do not raise.
        """
        with self._runtime.lock:
            if self._runtime.closed:
                return
            self._runtime.closed = True
            try:
                self._runtime.delivery.close()
            except Exception as exc:
                self._report_destination_failure(exc, "close")

    @property
    def destination_failure_count(self) -> int:
        """How many destination failures were reported for this logger."""
        return self._runtime.failure_count

    def _emit(
        self,
        level: str,
        message: str,
        exception: BaseException | None,
        fields: dict[str, Any],
    ) -> None:
        if not isinstance(message, str):
            raise LoggingError(f"Log message must be a string. Got {type(message).__name__}.")
        canonical = normalize_level(level, field="level")
        with self._runtime.lock:
            if self._runtime.closed:
                raise LoggerClosedError(
                    "Logger is closed. Call Logger.initialize before writing logs."
                )
            if not passes_minimum(canonical, self._runtime.config.minimum_level):
                return
            event = build_event(
                config=self._runtime.config,
                level=canonical,
                message=message,
                bound=self._bound,
                fields=fields,
                exception=exception,
            )
            try:
                self._runtime.delivery.deliver(event)
            except Exception as exc:
                self._report_destination_failure(exc, "write")

    def _report_destination_failure(self, exc: Exception, operation: str) -> None:
        """Count the failure and either raise or write one stderr diagnostic.

        The diagnostic names the destination and the exception type. It does
        not include the log event, so a failed write cannot echo secrets back
        through the same adapter.
        """
        self._runtime.failure_count += 1
        destination = self._runtime.config.destination
        if self._runtime.config.raise_destination_errors:
            raise DestinationError(
                f"Destination {destination!r} failed during {operation}."
            ) from exc
        kind = type(exc).__name__
        detail = str(exc).replace("\n", " ")
        diagnostic = (
            f"shared_logger: destination {destination!r} failed during {operation} "
            f"({kind}): {detail}\n"
        )
        try:
            sys.stderr.write(diagnostic)
            sys.stderr.flush()
        except Exception:
            return
