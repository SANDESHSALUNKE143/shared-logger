"""Per-logger context added with :meth:`~shared_logger.Logger.bind`.

``bind`` copies context onto a new logger. It does not change the original
logger and it does not use :mod:`contextvars`. A task or thread that should
carry the context must receive the bound logger. A later release can add
context-local storage behind the same ``write_*`` methods.
"""

from collections.abc import Mapping
from typing import Any

CORRELATION_FIELD = "correlation_id"

# Top-level event keys owned by the library. Call-site values for these names
# stay inside ``metadata`` and do not replace the system fields. ``correlation_id``
# is promoted to the top level instead of being stored in ``metadata``.
RESERVED_FIELDS = frozenset(
    {
        "schema_version",
        "timestamp",
        "level",
        "message",
        "application",
        "environment",
        "service_version",
        "component",
        "cluster",
        "region",
        "hostname",
        "process_id",
        "thread_id",
        "exception",
        "metadata",
        CORRELATION_FIELD,
    }
)


def merge_metadata(
    static_metadata: Mapping[str, Any] | None,
    custom_metadata: Mapping[str, Any] | None,
    bound: Mapping[str, Any],
    fields: Mapping[str, Any],
) -> dict[str, Any]:
    """Merge metadata sources. Later sources overwrite earlier keys.

    Order: ``static_metadata``, ``custom_metadata``, bound context, then
    keyword arguments on the logging call. ``correlation_id`` is omitted here
    because the event builder promotes it.
    """
    merged: dict[str, Any] = {}
    for source in (static_metadata, custom_metadata, bound, fields):
        if not source:
            continue
        for key, value in source.items():
            if key == CORRELATION_FIELD:
                continue
            merged[str(key)] = value
    return merged


def take_correlation(*sources: Mapping[str, Any] | None) -> tuple[bool, Any]:
    """Return the correlation id from the last source that set it.

    ``sources`` are in precedence order: static metadata, custom metadata,
    bound context, then the logging call. An explicit ``None`` is kept when a
    source sets the key.
    """
    present = False
    value: Any = None
    for source in sources:
        if source is not None and CORRELATION_FIELD in source:
            present = True
            value = source[CORRELATION_FIELD]
    return present, value
