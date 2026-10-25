# Security

## What redaction does

When `redact_sensitive_data` is true, the library walks structured metadata and a structured `correlation_id`. A dictionary key that matches `redacted_fields`, ignoring case, is replaced with `"[REDACTED]"`. The replacement covers the whole value, including nested objects. Lists and tuples are walked. The caller's original objects stay unchanged.

The default field names are `password`, `access_token`, `authorization`, `api_key`, and `secret`.

Redaction runs after metadata is merged and before the adapter writes.

## What redaction does not do

- It does not read the message string.
- It does not read exception messages or tracebacks.
- It does not detect secrets under a key that is not listed.
- It does not encrypt the file or restrict who can read the destination.
- It does not stop a custom adapter from copying an event into another system.

Treat redaction as a last filter for known key names. Keep secrets out of messages. Prefer a narrow `redacted_fields` list for application-specific names, and keep the defaults.

## Destination failures

The stderr diagnostic names the destination, the operation (`write`, `flush`, or `close`), and the exception type and text. It does not attach the event. A secret that exists only in the event is not copied into that line by the logger.

Adapters in this package raise operating-system errors without embedding the event. A custom adapter should do the same.

## Configuration secrets

The library has no built-in secret values. `from_env` reads the process environment. Do not commit environment files that contain credentials, and do not put credentials in `static_metadata` unless those keys are redacted and you accept the limits above.

## Closure

`close` drops the file handle. It does not shred the file. Retention deletes old rotated files with `unlink`. That is ordinary file deletion, not secure erasure.
