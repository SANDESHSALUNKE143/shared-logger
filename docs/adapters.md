# Adapters

## Contract

```python
class LoggingAdapter(ABC):
    def initialize(self, config: dict[str, Any]) -> None: ...
    def write(self, event: dict[str, Any]) -> None: ...
    def flush(self) -> None: ...
    def close(self) -> None: ...
```

`initialize` validates settings and makes the destination ready. `write` accepts one event dictionary that is already JSON-compatible. `flush` pushes buffered bytes. `close` releases resources and must succeed when called again.

Register a class with `register_adapter(name, adapter_class)` before `Logger.initialize`. Duplicate names raise `ConfigurationError`.

## Console

`ConsoleAdapter` writes one compact JSON line and flushes the selected stream. It does not close `sys.stdout` or `sys.stderr`.

`stream=auto` uses stderr for `ERROR` and `CRITICAL` and stdout otherwise.

## File

`FileAdapter` opens `path` in UTF-8 append mode with newline `\n`. It creates parent directories when the process is allowed to. Each `write` appends one line and flushes the file object. `flush` and `close` also call `os.fsync`.

Rotation renames the active file to `path.YYYYMMDDTHHMMSSMMMMMMZ` when its size is already at least the configured limit. A numeric suffix is added if that name exists. Retention deletes rotated files whose modification time is older than the configured duration. Other files in the directory are left in place.

Permission errors and full disks surface as operating-system errors. During initialization they become `ConfigurationError`. During `write` they follow `raise_destination_errors`.

If `close` cannot fsync, it still closes the file handle and then raises.

The adapter uses a lock so threads in one process do not interleave JSON lines. The lock does not cross processes.

## Shared file

`SharedFileAdapter` is the file writer with destination name `shared_file`. Use it for a mounted path. Documented limits:

- No cross-process lock. Concurrent appends can tear or interleave lines.
- No distributed coordination and no single-writer election.
- `fsync` reports only what the operating system reports for that path. A network filesystem can acknowledge a write and then lose it.
- Availability and permissions are the mount's.

A relative path is still accepted so local tests can exercise the same code. Production configuration should pass the mounted absolute path.

## Azure Storage Queue

`AzureQueueAdapter` is destination `azure_queue`. Install `shared-logger[azure]`. `destination_config` takes `queue_name` and exactly one of `connection_string` or `connection_string_env`. `initialize` calls the queue and fails if it does not exist. `write` sends the event as one JSON message. `flush` does not send a second request. `close` can be called twice.

The queue is the handoff to `shared-infra`. Applications do not open Elasticsearch.

## Not implemented

Do not register empty adapters for Elasticsearch, OpenTelemetry, RabbitMQ, Azure Service Bus, Kafka, HTTP, object storage, or databases. `Logger.initialize` must fail with `ConfigurationError` when the name is unknown.
