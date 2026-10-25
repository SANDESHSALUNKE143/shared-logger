"""Key-based redaction of structured values.

Redaction walks dictionaries and lists and replaces values whose keys match
the configured set. Matching is case-insensitive. The input is not modified.

Free-text messages and exception tracebacks are not scanned. A secret that
appears only inside a sentence is left as-is.
"""

from collections.abc import Mapping, Sequence
from typing import Any

REDACTED = "[REDACTED]"


def redact(value: Any, field_names: Sequence[str]) -> Any:
    """Return a redacted copy of ``value``.

    Dictionary keys are compared to ``field_names`` without case sensitivity.
    A matching key is replaced entirely, including nested values under it.
    """
    blocked = {name.casefold() for name in field_names}
    return _redact(value, blocked)


def _redact(value: Any, blocked: set[str]) -> Any:
    if isinstance(value, Mapping):
        redacted: dict[Any, Any] = {}
        for key, item in value.items():
            if isinstance(key, str) and key.casefold() in blocked:
                redacted[key] = REDACTED
            else:
                redacted[key] = _redact(item, blocked)
        return redacted
    if isinstance(value, list):
        return [_redact(item, blocked) for item in value]
    if isinstance(value, tuple):
        return [_redact(item, blocked) for item in value]
    return value
