# Configuration

`LoggingConfig` is a frozen dataclass. Strings are stripped. Dictionaries passed as metadata or `destination_config` are copied so later edits to the caller's dict do not change the logger.

## Precedence

1. Build a `LoggingConfig` in code when the application already has settings. That path ignores environment variables.
2. Call `LoggingConfig.from_env(**overrides)` when settings come from the environment. Each keyword argument replaces the matching `SHARED_LOGGER_*` variable.
3. Adapter settings live in `destination_config`. They are not fields on `LoggingConfig`.

Missing required environment variables raise `ConfigurationError` and name the variables. Empty strings are treated as unset.

## Destination settings

Console accepts `stream`: `auto`, `stdout`, or `stderr`.

File and shared file accept `path`, `rotation`, and `retention`. Unknown keys raise `ConfigurationError` during initialization. `retention` without `rotation` is rejected. Size units are 1024-based. Retention units are seconds, minutes, hours, and days.

## Levels

Canonical names are `DEBUG`, `INFO`, `WARNING`, `ERROR`, and `CRITICAL`. Input such as `"warning"` is stored as `WARNING`. Any other value raises `ConfigurationError`.

Filtering compares severity order. An event is written when its level is greater than or equal to `minimum_level`.

## Timestamps

The default timestamp is UTC, with millisecond precision and a `Z` suffix: `2026-10-25T10:30:00.123Z`. Milliseconds are truncated, not rounded.

`timestamp_format` is a Python `strftime` pattern. It must include a date or time directive such as `%Y`, and unknown directives are rejected. The clock is still UTC.

## Metadata fields

`static_metadata` is the base map. `custom_metadata` overrides it. `bind` overrides both. Keyword arguments on a logging call override `bind`.

`correlation_id` is removed from that map and stored on the event. A reserved system name in a keyword argument is stored under `metadata` and does not replace the system field.
