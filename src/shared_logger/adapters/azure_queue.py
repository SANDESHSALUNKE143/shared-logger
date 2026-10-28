"""Azure Storage Queue destination.

Each ``write`` sends one JSON message and returns when that HTTP call
finishes. ``flush`` does nothing extra. The queue must already exist;
``initialize`` checks it and does not create it.

``destination_config`` takes ``queue_name`` and exactly one of
``connection_string`` or ``connection_string_env``. The env form names a
variable that holds the storage connection string, so the secret stays out of
application code.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from shared_logger.adapters.base import LoggingAdapter
from shared_logger.exceptions import ConfigurationError, DestinationError

_KEYS = {"queue_name", "connection_string", "connection_string_env"}
_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _settings(config: dict[str, Any]) -> tuple[str, str]:
    if not isinstance(config, dict):
        raise ConfigurationError("azure_queue destination_config must be a dictionary.")
    unknown = sorted(set(config) - _KEYS)
    if unknown:
        names = ", ".join(unknown)
        raise ConfigurationError(
            "azure_queue destination_config does not support: "
            f"{names}. Supported keys: queue_name, connection_string, connection_string_env."
        )
    queue_name = config.get("queue_name")
    if not isinstance(queue_name, str) or not queue_name.strip():
        raise ConfigurationError(
            "azure_queue destination_config['queue_name'] must be a non-empty string."
        )
    has_string = "connection_string" in config
    has_env = "connection_string_env" in config
    if has_string == has_env:
        raise ConfigurationError(
            "azure_queue destination_config requires exactly one of "
            "connection_string or connection_string_env."
        )
    if has_string:
        connection_string = config.get("connection_string")
        if not isinstance(connection_string, str) or not connection_string.strip():
            raise ConfigurationError(
                "azure_queue destination_config['connection_string'] must be a non-empty string."
            )
        return queue_name.strip(), connection_string
    env_name = config.get("connection_string_env")
    if not isinstance(env_name, str) or _ENV_NAME.match(env_name) is None:
        raise ConfigurationError(
            "azure_queue destination_config['connection_string_env'] must name "
            "an environment variable."
        )
    connection_string = os.environ.get(env_name, "")
    if not connection_string.strip():
        raise ConfigurationError(
            f"azure_queue environment variable {env_name} is empty or unset."
        )
    return queue_name.strip(), connection_string


def _load_azure() -> tuple[Any, type[BaseException]]:
    try:
        from azure.core.exceptions import ResourceNotFoundError
        from azure.storage.queue import QueueClient
    except ImportError as exc:
        raise ConfigurationError(
            "azure_queue requires the azure extra. "
            "Install with: pip install 'shared-logger[azure]'."
        ) from exc
    return QueueClient, ResourceNotFoundError


def _dump(event: dict[str, Any]) -> str:
    return json.dumps(event, ensure_ascii=False, separators=(",", ":"))


class AzureQueueAdapter(LoggingAdapter):
    """Send one shared-logger event as one Azure Storage Queue message."""

    destination_name = "azure_queue"

    def __init__(self) -> None:
        self._client: Any = None
        self._initialized = False
        self._closed = False

    def initialize(self, config: dict[str, Any]) -> None:
        """Check settings and confirm the queue exists."""
        if self._initialized:
            raise ConfigurationError("azure_queue adapter is already initialized.")
        queue_name, connection_string = _settings(config)
        queue_client, not_found = _load_azure()
        client = queue_client.from_connection_string(connection_string, queue_name)
        try:
            client.get_queue_properties()
        except not_found as exc:
            raise ConfigurationError(
                f"azure_queue queue {queue_name!r} does not exist."
            ) from exc
        except Exception as exc:
            raise ConfigurationError(
                f"azure_queue could not open queue {queue_name!r}: {exc}."
            ) from exc
        self._client = client
        self._initialized = True

    def write(self, event: dict[str, Any]) -> None:
        """Send one JSON message. The call returns when the queue accepts it."""
        if self._closed:
            raise DestinationError("azure_queue adapter is closed.")
        if not self._initialized or self._client is None:
            raise DestinationError("azure_queue adapter is not initialized.")
        try:
            self._client.send_message(_dump(event))
        except Exception as exc:
            raise DestinationError(f"azure_queue write failed: {exc}.") from exc

    def flush(self) -> None:
        """No buffered messages. Each write already finished its HTTP call."""

    def close(self) -> None:
        """Drop the client. A second call does nothing."""
        if self._closed:
            return
        self._closed = True
        self._client = None
