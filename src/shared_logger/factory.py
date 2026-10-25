"""Create the destination and the synchronous delivery strategy.

:class:`SyncDelivery` writes on the calling thread. A future release can add
another class with the same ``deliver``, ``flush``, and ``close`` methods and
pass it to the logger without changing application logging calls. This release
does not queue, batch, or retry events.
"""

from typing import Any

from shared_logger.adapters.base import LoggingAdapter
from shared_logger.config import LoggingConfig
from shared_logger.exceptions import ConfigurationError
from shared_logger.registry import get_adapter


class SyncDelivery:
    """Send each event to the adapter before the logging call returns."""

    def __init__(self, adapter: LoggingAdapter) -> None:
        self._adapter = adapter

    def deliver(self, event: dict[str, Any]) -> None:
        """Write one event."""
        self._adapter.write(event)

    def flush(self) -> None:
        """Flush the adapter."""
        self._adapter.flush()

    def close(self) -> None:
        """Close the adapter."""
        self._adapter.close()


def create_adapter(name: str) -> LoggingAdapter:
    """Construct the adapter registered under ``name``."""
    return get_adapter(name)()


def open_destination(config: LoggingConfig) -> tuple[LoggingAdapter, SyncDelivery]:
    """Initialize the configured adapter and wrap it for synchronous delivery.

    Initialization failures propagate as :class:`ConfigurationError`. The
    returned adapter is ready to accept events.
    """
    adapter = create_adapter(config.destination)
    try:
        adapter.initialize(dict(config.destination_config))
    except ConfigurationError:
        raise
    except Exception as exc:
        raise ConfigurationError(
            f"Destination {config.destination!r} failed to initialize: {exc}"
        ) from exc
    return adapter, SyncDelivery(adapter)
