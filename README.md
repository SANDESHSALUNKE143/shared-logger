# shared-logger

Shared structured logging for applications across teams, projects, and environments. An application initializes the library once, selects a destination in configuration, and calls the same methods everywhere. Destination-specific writing stays inside adapters.

This release delivers events synchronously on the calling thread. It does not start workers, queue events, batch them, or retry them.

The package version is 0.1.0. It is not published to a public index yet. Install it from this repository.

## Repository

Push from this checkout. The `main` branch tracks `origin`:

https://github.com/SANDESHSALUNKE143/shared-logger

```bash
git push origin main
```

`origin` is `git@github.com:SANDESHSALUNKE143/shared-logger.git`. Commit the files in this directory first. The push sends the commits that are on `main`.

## Features

- `write_debug`, `write_info`, `write_warning`, `write_error`, `write_critical`, and `write_exception`
- Destinations: console, local file, and a mounted shared file path
- Structured JSON events with `schema_version` 1
- Application, environment, and optional service metadata on every event
- Keyword arguments and `bind()` context under `metadata`
- Minimum-level filtering before serialization and destination writes
- Case-insensitive redaction of structured keys
- Adapter registry for custom destinations
- `flush()` and idempotent `close()`
- Configurable destination-error policy with a stderr diagnostic

## Architecture

```mermaid
flowchart LR
  app[Application] --> sdk[Logging SDK]
  sdk --> processing[Event processing]
  processing --> adapter[Adapter]
  adapter --> destination[Destination]
```

The call path is:

Application → Logger API → event builder → level filter and redaction → `SyncDelivery` → destination adapter → console or file.

`SyncDelivery` calls `adapter.write` before the logging method returns. A later release can add another delivery class with the same `deliver`, `flush`, and `close` methods. Application calls to `write_*` stay the same. That class is not part of this release, and there is no queue behind the current one.

Importing `shared_logger` registers the built-in adapters. It does not create files or open network connections. `Logger.initialize` does that for the selected destination.

## Installation

Requires Python 3.11 or newer. Release 0.1.0 was installed and tested on Python 3.12.6. Older 3.11 interpreters were not part of that run.

In this repository:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

From an application checkout that sits next to this repository:

```bash
pip install "shared-logger @ file:../shared-logger"
```

A published release would be installed with `pip install shared-logger` once the package is on an index. Until then, install from this repository.

## Quick start

```python
from shared_logger import Logger, LoggingConfig

config = LoggingConfig(
    application="campaign-analytics",
    environment="production",
    destination="file",
    destination_config={"path": "./logs/application.log"},
    minimum_level="INFO",
)
logger = Logger.initialize(config)
try:
    logger.write_info("Application started", application_version="1.0.0")
    logger.flush()
finally:
    logger.close()
```

`examples/basic_logging.py` is this program.

## Configuration reference

`LoggingConfig(...)` uses only the arguments you pass. It does not read the environment.

`LoggingConfig.from_env()` reads `SHARED_LOGGER_*`. A keyword argument to `from_env` replaces that field's environment variable. Required variables, unless you pass them as arguments, are `SHARED_LOGGER_APPLICATION`, `SHARED_LOGGER_ENVIRONMENT`, and `SHARED_LOGGER_DESTINATION`. When `SHARED_LOGGER_DESTINATION_CONFIG` is unset, destination settings default to `{}`.

Boolean environment values accept `true`, `false`, `yes`, `no`, `on`, `off`, `1`, and `0`. Object fields are JSON objects. `SHARED_LOGGER_REDACTED_FIELDS` is a comma-separated list or a JSON array of strings.

| Field | Type | Default | Validation |
| --- | --- | --- | --- |
| `application` | string | required | Non-empty. Surrounding space is removed. |
| `environment` | string | required | Non-empty. Surrounding space is removed. |
| `destination` | string | required | Must be a registered adapter name. Built-ins: `console`, `file`, `shared_file`. |
| `destination_config` | dict | required for `LoggingConfig`; `{}` for `from_env` when unset | String keys. Contents are validated by the adapter. |
| `minimum_level` | string | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`. Case-insensitive. |
| `service_version` | string or omitted | omitted | Non-empty when set. |
| `component` | string or omitted | omitted | Non-empty when set. |
| `cluster` | string or omitted | omitted | Non-empty when set. |
| `region` | string or omitted | omitted | Non-empty when set. |
| `static_metadata` | dict or omitted | omitted | String keys. Copied at construction. |
| `custom_metadata` | dict or omitted | omitted | String keys. Overrides `static_metadata` on the same key. |
| `include_hostname` | bool | `false` | When true, the event includes the hostname if the system returns one. |
| `include_process_id` | bool | `false` | When true, the event includes `os.getpid()`. |
| `include_thread_id` | bool | `false` | When true, the event includes `threading.get_ident()`. |
| `redact_sensitive_data` | bool | `true` | When false, structured keys are not redacted. |
| `redacted_fields` | list of strings or omitted | password, access_token, authorization, api_key, secret | Used only when redaction is enabled. Matching is case-insensitive. |
| `timestamp_format` | string or omitted | ISO-8601 UTC with milliseconds and a `Z` suffix | A `strftime` pattern on the UTC clock. It must include a date or time directive. Unknown directives are rejected. |
| `raise_destination_errors` | bool | `false` | See [Error handling](#error-handling). |

Invalid configuration raises `ConfigurationError` while the config object is built or while `Logger.initialize` opens the destination. Unknown destination names raise `ConfigurationError` and name the registered destinations. There are no silent placeholder adapters.

Environment names:

| Variable | Config field |
| --- | --- |
| `SHARED_LOGGER_APPLICATION` | `application` |
| `SHARED_LOGGER_ENVIRONMENT` | `environment` |
| `SHARED_LOGGER_DESTINATION` | `destination` |
| `SHARED_LOGGER_DESTINATION_CONFIG` | `destination_config` |
| `SHARED_LOGGER_MINIMUM_LEVEL` | `minimum_level` |
| `SHARED_LOGGER_SERVICE_VERSION` | `service_version` |
| `SHARED_LOGGER_COMPONENT` | `component` |
| `SHARED_LOGGER_CLUSTER` | `cluster` |
| `SHARED_LOGGER_REGION` | `region` |
| `SHARED_LOGGER_STATIC_METADATA` | `static_metadata` |
| `SHARED_LOGGER_CUSTOM_METADATA` | `custom_metadata` |
| `SHARED_LOGGER_INCLUDE_HOSTNAME` | `include_hostname` |
| `SHARED_LOGGER_INCLUDE_PROCESS_ID` | `include_process_id` |
| `SHARED_LOGGER_INCLUDE_THREAD_ID` | `include_thread_id` |
| `SHARED_LOGGER_REDACT_SENSITIVE_DATA` | `redact_sensitive_data` |
| `SHARED_LOGGER_REDACTED_FIELDS` | `redacted_fields` |
| `SHARED_LOGGER_TIMESTAMP_FORMAT` | `timestamp_format` |
| `SHARED_LOGGER_RAISE_DESTINATION_ERRORS` | `raise_destination_errors` |

## Supported destinations

| Name | Behavior |
| --- | --- |
| `console` | One JSON object per line. `destination_config.stream` is `auto` (default), `stdout`, or `stderr`. `auto` sends `ERROR` and `CRITICAL` to stderr and other levels to stdout. |
| `file` | UTF-8 JSON Lines, append mode, parent directories created when permitted. |
| `shared_file` | Same writer as `file`, aimed at a mounted path. |
| `azure_queue` | One JSON message per event on an Azure Storage Queue that already exists. Install `shared-logger[azure]`. |

File and shared-file settings:

| Key | Required | Meaning |
| --- | --- | --- |
| `path` | yes | File path. Relative paths are resolved from the process working directory. |
| `rotation` | no | Size that triggers rollover. Examples: `100 B`, `500 KB`, `10 MB`, `1 GB`. Units are multiples of 1024. |
| `retention` | no | How long rotated files are kept. Examples: `90 seconds`, `30 minutes`, `24 hours`, `7 days`. Requires `rotation`. |

When the active file is already at least `rotation` bytes, the next write renames it with a UTC timestamp suffix and opens a new file. One event larger than the limit is still written. Retention deletes only files this adapter rotated. It does not delete the active file or unrelated names in the directory.

`shared_file` does not add locking, leader election, or a durability guarantee beyond what the mount provides. Two processes appending to the same path can interleave lines. A successful return means the writer flushed its buffer, not that a network filesystem has committed the bytes.

`azure_queue` settings:

| Key | Required | Meaning |
| --- | --- | --- |
| `queue_name` | yes | Queue that already exists in the storage account. `shared-infra` uses `app-logs`. |
| `connection_string` | one of these | Storage connection string. |
| `connection_string_env` | one of these | Name of the environment variable that holds the connection string. |

Set exactly one of `connection_string` or `connection_string_env`. `initialize` checks that the queue exists and does not create it. Each `write_*` call sends one message and returns when the queue accepts it. `flush` does not send another request. Applications do not get an Elasticsearch URL. The worker on the infra VM reads the queue.

```bash
SHARED_LOGGER_DESTINATION=azure_queue
SHARED_LOGGER_DESTINATION_CONFIG={"queue_name":"app-logs","connection_string_env":"AZURE_STORAGE_CONNECTION_STRING"}
AZURE_STORAGE_CONNECTION_STRING='DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net'
```

Elasticsearch, OpenTelemetry, RabbitMQ, Azure Service Bus, Kafka, HTTP endpoints, object storage, and databases are not implemented. Selecting one of those names fails during initialization.

## Logging API

```python
logger.write_debug("Debug information", user_id=123)
logger.write_info("Application started", application_version="1.0.0")
logger.write_warning("Resource usage approaching threshold", usage_percentage=85)
logger.write_error("Unable to process request", request_id="req-123")
logger.write_critical("Critical system failure", component="data_processor")
logger.write_exception(
    "An unexpected exception occurred",
    exception=exc,
    request_id="req-123",
)
logger.flush()
logger.close()
```

`flush()` asks the adapter to flush. For files it also calls `os.fsync`. After `close()`, `flush()` does nothing.

`close()` marks the logger closed, then asks the adapter to flush and release resources. A second `close()` does nothing and does not raise. If the first cleanup flush fails, the file adapter still closes the file handle. A later `close()` does not retry that cleanup.

`write_*` after `close()` raises `LoggerClosedError`. The event is not dropped.

`destination_failure_count` counts destination failures reported for this logger, including bound loggers that share it.

Bound loggers share the destination. Closing any of them closes it for all of them.

## Structured logging

Each event is one JSON object. Optional fields are omitted when they were not configured. Keyword values are JSON objects, arrays, strings, numbers, booleans, or null. Other objects become `"<non-serializable: module.QualName>"`. Dictionary keys are stored as strings. The caller's dictionaries are not modified.

```json
{
  "schema_version": 1,
  "timestamp": "2026-10-25T10:30:00.123Z",
  "level": "INFO",
  "message": "Data processing started",
  "application": "campaign-analytics",
  "environment": "production",
  "service_version": "1.0.0",
  "component": "campaign_processor",
  "cluster": "india",
  "region": "ap-south-1",
  "metadata": {
    "team": "analytics",
    "campaign_id": "CMP-1001",
    "records_processed": 500
  }
}
```

`hostname`, `process_id`, and `thread_id` appear only when the matching `include_*` flag is true and, for the hostname, when the system returns a name.

Timestamps use UTC. The default format is `YYYY-MM-DDTHH:MM:SS.mmmZ`. A custom `timestamp_format` is passed to `strftime` on that same UTC clock.

## Context binding

```python
request_logger = logger.bind(correlation_id="req-123", tenant_id="tenant-456")
request_logger.write_info("Request processing started")
request_logger.write_info("Request processing completed")
```

`bind` returns a new logger. The original logger's context does not change. This release does not use `contextvars`, so a task must receive the bound logger if it should keep the context.

Metadata precedence, later sources winning:

1. `static_metadata`
2. `custom_metadata`
3. `bind()` context
4. Keyword arguments on the logging call

`correlation_id` is written on the event, not inside `metadata`. The logging call overrides `bind`, which overrides config metadata. Other keys from those sources go into `metadata`.

Reserved top-level names passed as keyword arguments stay inside `metadata`. They do not replace `schema_version`, `timestamp`, `level`, `message`, `application`, `environment`, identity fields, `hostname`, `process_id`, `thread_id`, `exception`, or `metadata`. The log text itself is the first argument of `write_*`. A `message` key in configured metadata stays in `metadata` and does not replace that argument.

## Exception logging

`write_exception` writes an `ERROR` event. Pass the exception you want recorded. The library does not read the active `except` clause for you. When the minimum level is above `ERROR`, the event is filtered like any other `ERROR`.

When `exception` is a `BaseException`, the event includes:

```json
{
  "exception": {
    "type": "ValueError",
    "message": "The record could not be parsed",
    "traceback": "Traceback (most recent call last):\n..."
  }
}
```

`traceback` is omitted when the exception has no traceback attached. Exception text is not redacted.

## Redaction and security

```python
LoggingConfig(
    application="payment-service",
    environment="production",
    destination="file",
    destination_config={"path": "./logs/application.jsonl"},
    redact_sensitive_data=True,
    redacted_fields=["password", "access_token", "authorization", "api_key", "secret"],
)
```

Redaction walks dictionaries and lists and replaces a matching key's entire value with `"[REDACTED]"`. Matching ignores case. It runs before the destination write. It does not change the caller's objects.

It does not scan message strings or exception text. A secret typed into a sentence is still logged. A secret stored under an unexpected key is still logged. Redaction is a structured-key filter, not a guarantee that a destination cannot leak sensitive data.

Destination failure diagnostics written to stderr include the destination name and the exception type and message. They do not include the log event. Adapters should not put event bodies into exception messages.

The library does not read secrets from hardcoded values. Pass them only through configuration or the environment, and keep them out of log messages.

## Custom adapters

Implement `LoggingAdapter`, register it, then select it with `destination`.

```python
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
    logger = Logger.initialize(
        LoggingConfig(
            application="campaign-analytics",
            environment="production",
            destination="custom",
            destination_config={"label": "demo"},
            minimum_level="INFO",
        )
    )
    try:
        logger.write_info("Application started", application_version="1.0.0")
    finally:
        logger.close()
    print(json.dumps(CollectingAdapter.events[0]))
```

`examples/custom_adapter.py` is this program. Registering a name that already exists raises `ConfigurationError`. The logger never imports a destination SDK for a destination you did not register.

A custom adapter must not log failures through the same logger. That would call the adapter again.

## Error handling

| Situation | Result |
| --- | --- |
| Invalid `LoggingConfig` | `ConfigurationError` at construction |
| Unknown destination or invalid destination settings | `ConfigurationError` during `Logger.initialize` |
| File cannot be created or opened | `ConfigurationError` during `Logger.initialize`, including the path and the operating-system message |
| Destination write or flush fails and `raise_destination_errors` is true | `DestinationError`. The original error is the cause. The event was not acknowledged as written. |
| Destination write, flush, or close fails and `raise_destination_errors` is false | The call returns. `destination_failure_count` increases by one. One line is written to stderr. The failing adapter is not asked to log that failure. |
| `close()` called again | No error |
| Logging or `bind()` after close | `LoggerClosedError` |

The default is `raise_destination_errors=False`, so a logging failure does not replace the application's own exception. Turn it on when a caller must know that the event was not written. Suppressed failures are still counted and reported on stderr. If stderr itself cannot be written, the count still increases and the application exception is not replaced.

Events below `minimum_level` are not written. That is filtering, not a destination failure.

## Levels

| Level | When to use it |
| --- | --- |
| `DEBUG` | Diagnostic detail used while developing or investigating. |
| `INFO` | A normal lifecycle or business event. |
| `WARNING` | An unexpected condition the application recovered from. |
| `ERROR` | An operation failed and was reported. `write_exception` uses this level. |
| `CRITICAL` | A failure that threatens the process or a required dependency. |

`minimum_level="WARNING"` drops `DEBUG` and `INFO` before redaction, JSON encoding, and the adapter call.

## Testing

From the repository root, with the development extra installed:

```bash
pytest
```

`pytest` runs unit, integration, and adapter contract tests and fails when line coverage of `shared_logger` is under 90 percent. Tests use temporary directories.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
ruff check src tests examples
ruff format --check src tests examples
pytest
python -m build
```

The verified interpreter for release 0.1.0 is Python 3.12.6. The package declares `requires-python >= 3.11`. Compatibility with 3.11 was not executed in this release.

## Limitations

- Delivery is synchronous. A slow disk or stream blocks the caller.
- Durability is whatever the destination does. Console output lasts as long as the process streams do. File `write` flushes the Python buffer. `flush` and `close` also `fsync`. A shared mount may ignore `fsync` or fail independently of this process.
- `shared_file` does not coordinate concurrent writers and does not promise that a write survived a network fault.
- In-process threads are serialized on one logger. Other processes are not.
- Key redaction does not cover free text, exception messages, or unknown key names.
- `bind()` is explicit. Context does not follow a thread or task unless you pass the bound logger.
- There is no batching, retry, or background delivery.

## Future roadmap

These are not implemented and are rejected if selected as a destination today:

- Asynchronous delivery behind the same logging methods
- In-memory queues, batching, and retry workers
- Elasticsearch and OpenTelemetry exporters
- RabbitMQ, Azure Service Bus, and Kafka
- HTTP endpoints, object storage, and database-backed logging

Each of those would be a new adapter module or an optional extra. The core install would still have no client for those systems.

## Versioning and contribution

Versions follow semantic versioning.

| Change | Bump |
| --- | --- |
| A new optional config field, destination, or logging method | Minor (`0.2.0`) |
| A renamed method, removed destination, or event field that existing callers depend on | Major (`1.0.0`) |
| A fix that preserves the public API and event schema | Patch (`0.1.1`) |

`schema_version` stays `1` until the event shape changes in a way older readers cannot ignore. Adding an optional field does not require a new schema version. Removing or renaming a field does.

To add a destination, subclass `LoggingAdapter`, validate its settings in `initialize`, and call `register_adapter` from application code or from an optional module. Do not add the dependency to the core install. See [CONTRIBUTING.md](CONTRIBUTING.md).
