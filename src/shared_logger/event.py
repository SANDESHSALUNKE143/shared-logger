"""Structured events.

Every event carries ``schema_version``, a UTC timestamp, severity, message,
application, and environment. Optional identity fields are omitted when they
were not configured. Keyword arguments and bound context go into ``metadata``
unless the key is ``correlation_id``, which is written at the top level.

System fields are written by this module after metadata is assembled, so a
keyword argument cannot replace them. A reserved name passed by the caller
remains inside ``metadata``.
"""

from __future__ import annotations

import os
import socket
import threading
import traceback
from datetime import datetime, timezone
from typing import Any

from shared_logger.config import LoggingConfig
from shared_logger.context import merge_metadata, take_correlation
from shared_logger.redaction import redact

SCHEMA_VERSION = 1


def format_timestamp(pattern: str | None, moment: datetime | None = None) -> str:
    """Format a UTC timestamp.

    The default shape is ``YYYY-MM-DDTHH:MM:SS.mmmZ``. A custom pattern is a
    :meth:`datetime.strftime` pattern applied to the UTC clock.
    """
    current = moment or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    else:
        current = current.astimezone(timezone.utc)
    if pattern is None:
        millis = current.microsecond // 1000
        return current.strftime("%Y-%m-%dT%H:%M:%S.") + f"{millis:03d}Z"
    return current.strftime(pattern)


def exception_details(exc: BaseException) -> dict[str, str]:
    """Capture the exception type, message, and traceback when one exists."""
    details = {"type": type(exc).__name__, "message": str(exc)}
    if exc.__traceback__ is not None:
        details["traceback"] = "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        )
    return details


def placeholder(value: object) -> str:
    """Describe a value that cannot be encoded as JSON."""
    kind = type(value)
    return f"<non-serializable: {kind.__module__}.{kind.__qualname__}>"


def sanitize(value: Any) -> Any:
    """Return a JSON-compatible copy of ``value``.

    Dictionaries, lists, strings, booleans, finite numbers, and ``None`` are
    preserved. Other objects become a placeholder string. Dictionary keys are
    converted to strings. The input is not modified.
    """
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return placeholder(value)
        return value
    if isinstance(value, dict):
        return {str(key): sanitize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in value]
    return placeholder(value)


def _hostname() -> str | None:
    try:
        name = socket.gethostname()
    except OSError:
        return None
    if not name:
        return None
    return name


def build_event(
    *,
    config: LoggingConfig,
    level: str,
    message: str,
    bound: dict[str, Any],
    fields: dict[str, Any],
    exception: BaseException | None = None,
    moment: datetime | None = None,
) -> dict[str, Any]:
    """Assemble one event dictionary ready for a destination adapter."""
    metadata = merge_metadata(
        config.static_metadata,
        config.custom_metadata,
        bound,
        fields,
    )
    if config.redact_sensitive_data:
        metadata = redact(metadata, config.active_redacted_fields)

    event: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "timestamp": format_timestamp(config.timestamp_format, moment),
        "level": level,
        "message": message,
        "application": config.application,
        "environment": config.environment,
    }
    if config.service_version is not None:
        event["service_version"] = config.service_version
    if config.component is not None:
        event["component"] = config.component
    if config.cluster is not None:
        event["cluster"] = config.cluster
    if config.region is not None:
        event["region"] = config.region
    if config.include_hostname:
        hostname = _hostname()
        if hostname is not None:
            event["hostname"] = hostname
    if config.include_process_id:
        event["process_id"] = os.getpid()
    if config.include_thread_id:
        event["thread_id"] = threading.get_ident()
    present, correlation = take_correlation(
        config.static_metadata,
        config.custom_metadata,
        bound,
        fields,
    )
    if present:
        if config.redact_sensitive_data:
            correlation = redact(correlation, config.active_redacted_fields)
        event["correlation_id"] = correlation
    if exception is not None:
        event["exception"] = exception_details(exception)
    if metadata:
        event["metadata"] = metadata
    return sanitize(event)
