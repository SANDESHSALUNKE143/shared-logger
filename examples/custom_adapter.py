"""Register an adapter that stores events in memory and prints them.

Run this file once per process. Registering the same destination name twice
raises ConfigurationError.
"""

import json

from shared_logger import (
    ConfigurationError,
    DestinationError,
    Logger,
    LoggingAdapter,
    LoggingConfig,
    register_adapter,
)


class CollectingAdapter(LoggingAdapter):
    """Keep events on the class so the example can print them after close."""

    events: list[dict] = []

    def __init__(self) -> None:
        self._label = ""
        self._closed = False

    def initialize(self, config: dict) -> None:
        label = config.get("label")
        if not isinstance(label, str) or not label.strip():
            raise ConfigurationError(
                "custom destination_config['label'] must be a non-empty string."
            )
        self._label = label

    def write(self, event: dict) -> None:
        if self._closed:
            raise DestinationError("custom adapter is closed.")
        stored = dict(event)
        stored["label"] = self._label
        CollectingAdapter.events.append(stored)

    def flush(self) -> None:
        return None

    def close(self) -> None:
        self._closed = True


def main() -> None:
    register_adapter("custom", CollectingAdapter)
    config = LoggingConfig(
        application="campaign-analytics",
        environment="production",
        destination="custom",
        destination_config={"label": "demo"},
        minimum_level="INFO",
    )
    logger = Logger.initialize(config)
    try:
        logger.write_info("Application started", application_version="1.0.0")
    finally:
        logger.close()
    print(json.dumps(CollectingAdapter.events[0]))


if __name__ == "__main__":
    main()
