"""Severity names used by the public logging methods."""

from shared_logger.exceptions import ConfigurationError

LEVELS: tuple[str, ...] = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
LEVEL_ORDER: dict[str, int] = {name: index for index, name in enumerate(LEVELS)}

# What each severity means for callers. Filtering uses the order above.
LEVEL_GUIDE: dict[str, str] = {
    "DEBUG": "Diagnostic detail used while developing or investigating.",
    "INFO": "A normal lifecycle or business event.",
    "WARNING": "An unexpected condition the application recovered from.",
    "ERROR": "An operation failed and was reported.",
    "CRITICAL": "A failure that threatens the process or a required dependency.",
}


def normalize_level(value: object, *, field: str = "minimum_level") -> str:
    """Return the canonical uppercase level name.

    Input is case-insensitive. ``"info"`` and ``"INFO"`` both become ``"INFO"``.
    """
    if not isinstance(value, str):
        raise ConfigurationError(f"{field} must be a string. Got {type(value).__name__}.")
    normalized = value.strip().upper()
    if normalized not in LEVEL_ORDER:
        allowed = ", ".join(LEVELS)
        raise ConfigurationError(f"{field} must be one of {allowed}. Got {value!r}.")
    return normalized
