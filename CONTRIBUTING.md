# Contributing

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Run `ruff check`, `ruff format`, and `pytest` before opening a change. `pytest` includes coverage for `shared_logger` and fails under 90 percent.

## Versioning

The public surface is `Logger`, `LoggingConfig`, `register_adapter`, `LoggingAdapter`, and the exception types exported from `shared_logger`. Event field names and `schema_version` are part of that surface.

- Patch: bug fix with the same calls and the same event fields.
- Minor: a new optional field, method, or destination.
- Major: a breaking change to a call, a destination name, or an event field.

## Adding an adapter

1. Subclass `LoggingAdapter`.
2. Validate `destination_config` in `initialize`. Reject unknown keys. Raise `ConfigurationError` with the field name and the expected value.
3. Implement `write`. Raise a normal exception on failure. Do not catch it and log it through `Logger`.
4. Implement `flush` and `close` when the destination holds a resource. `close` must be safe to call twice and must release the resource even if an earlier flush fails.
5. Register it with `register_adapter("name", Adapter)`. Do not register a built-in name.
6. Keep client libraries for that destination out of the core dependencies. An optional extra is the right place for them.
7. Add contract coverage: initialize, write, flush, close, close again, and write after close.
8. Document the destination, including what it does not guarantee.

Do not add a destination that succeeds at initialization and then discards events. If the destination is not ready, initialization must fail.

## Tests

Use `tmp_path` for files. Do not write to a fixed path in the repository. Do not require a network service for the default test run.
