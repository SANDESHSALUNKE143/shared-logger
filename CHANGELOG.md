# Changelog

## Unreleased

- `azure_queue` sends one JSON event per call to an existing Azure Storage Queue. Install `shared-logger[azure]`.

## 0.1.0 - 2026-10-25

Initial release.

- Synchronous structured logging through `Logger` and `LoggingConfig`.
- Console, local file, and mounted shared-file adapters.
- Level filtering, key redaction, context binding, and exception details.
- Custom adapter registration.
