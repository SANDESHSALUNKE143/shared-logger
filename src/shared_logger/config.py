"""Typed logging configuration.

:class:`LoggingConfig` does not read the process environment. Use
:meth:`LoggingConfig.from_env` when configuration should come from
``SHARED_LOGGER_*`` variables. Keyword arguments passed to ``from_env``
replace the matching environment variables.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields
from datetime import datetime, timezone
from typing import Any

from shared_logger.exceptions import ConfigurationError
from shared_logger.levels import normalize_level

DEFAULT_REDACTED_FIELDS: tuple[str, ...] = (
    "password",
    "access_token",
    "authorization",
    "api_key",
    "secret",
)

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}

_ENV = {
    "application": "SHARED_LOGGER_APPLICATION",
    "environment": "SHARED_LOGGER_ENVIRONMENT",
    "destination": "SHARED_LOGGER_DESTINATION",
    "destination_config": "SHARED_LOGGER_DESTINATION_CONFIG",
    "minimum_level": "SHARED_LOGGER_MINIMUM_LEVEL",
    "service_version": "SHARED_LOGGER_SERVICE_VERSION",
    "component": "SHARED_LOGGER_COMPONENT",
    "cluster": "SHARED_LOGGER_CLUSTER",
    "region": "SHARED_LOGGER_REGION",
    "static_metadata": "SHARED_LOGGER_STATIC_METADATA",
    "include_hostname": "SHARED_LOGGER_INCLUDE_HOSTNAME",
    "include_process_id": "SHARED_LOGGER_INCLUDE_PROCESS_ID",
    "include_thread_id": "SHARED_LOGGER_INCLUDE_THREAD_ID",
    "redact_sensitive_data": "SHARED_LOGGER_REDACT_SENSITIVE_DATA",
    "redacted_fields": "SHARED_LOGGER_REDACTED_FIELDS",
    "timestamp_format": "SHARED_LOGGER_TIMESTAMP_FORMAT",
    "raise_destination_errors": "SHARED_LOGGER_RAISE_DESTINATION_ERRORS",
    "custom_metadata": "SHARED_LOGGER_CUSTOM_METADATA",
}

_JSON_FIELDS = {"destination_config", "static_metadata", "custom_metadata"}
_BOOL_FIELDS = {
    "include_hostname",
    "include_process_id",
    "include_thread_id",
    "redact_sensitive_data",
    "raise_destination_errors",
}
_REQUIRED_ENV = ("application", "environment", "destination")


def _copy_tree(value: Any) -> Any:
    """Copy mappings and sequences so later caller edits do not change config."""
    if isinstance(value, Mapping):
        return {key: _copy_tree(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_copy_tree(item) for item in value]
    if isinstance(value, tuple):
        return [_copy_tree(item) for item in value]
    return value


def _require_text(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise ConfigurationError(f"{field} must be a string. Got {type(value).__name__}.")
    text = value.strip()
    if not text:
        raise ConfigurationError(f"{field} must be a non-empty string.")
    return text


def _optional_text(value: object, field: str) -> str | None:
    if value is None:
        return None
    return _require_text(value, field)


def _require_bool(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigurationError(f"{field} must be true or false. Got {type(value).__name__}.")
    return value


def _require_mapping(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConfigurationError(f"{field} must be a dictionary. Got {type(value).__name__}.")
    copied: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key.strip():
            raise ConfigurationError(f"{field} keys must be non-empty strings.")
        copied[key] = _copy_tree(item)
    return copied


def _optional_mapping(value: object, field: str) -> dict[str, Any] | None:
    if value is None:
        return None
    return _require_mapping(value, field)


def _optional_fields(value: object) -> tuple[str, ...] | None:
    if value is None:
        return None
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ConfigurationError(
            f"redacted_fields must be a list of strings. Got {type(value).__name__}."
        )
    names: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ConfigurationError(
                f"redacted_fields[{index}] must be a non-empty string. Got {item!r}."
            )
        names.append(item.strip())
    return tuple(names)


_STRFTIME_CODES = frozenset("aAbBcdfGHIjmMpSUuVWwxXyYzZ%")


def _optional_timestamp_format(value: object) -> str | None:
    if value is None:
        return None
    text = _require_text(value, "timestamp_format")
    saw_directive = False
    index = 0
    while index < len(text):
        if text[index] != "%":
            index += 1
            continue
        if index + 1 >= len(text):
            raise ConfigurationError(f"timestamp_format has a trailing '%'. Got {text!r}.")
        code = text[index + 1]
        if code not in _STRFTIME_CODES:
            raise ConfigurationError(
                f"timestamp_format has an unknown directive '%{code}'. Got {text!r}."
            )
        if code != "%":
            saw_directive = True
        index += 2
    if not saw_directive:
        raise ConfigurationError(
            f"timestamp_format must include a date or time directive such as %Y. Got {text!r}."
        )
    try:
        datetime.now(timezone.utc).strftime(text)
    except ValueError as exc:
        raise ConfigurationError(
            f"timestamp_format is not a valid strftime pattern. Got {text!r}."
        ) from exc
    return text


def _parse_bool(raw: str, env_name: str) -> bool:
    key = raw.strip().casefold()
    if key in _TRUE:
        return True
    if key in _FALSE:
        return False
    raise ConfigurationError(f"{env_name} must be true or false. Got {raw!r}.")


def _parse_object(raw: str, env_name: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigurationError(f"{env_name} must be a JSON object. {exc.msg}.") from exc
    if not isinstance(value, dict):
        raise ConfigurationError(f"{env_name} must be a JSON object.")
    return value


def _parse_fields(raw: str, env_name: str) -> list[str]:
    text = raw.strip()
    if text.startswith("[") or text.startswith("{"):
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ConfigurationError(
                f"{env_name} must be a JSON array of strings or a comma-separated list. {exc.msg}."
            ) from exc
        if not isinstance(value, list):
            raise ConfigurationError(f"{env_name} must be a JSON array of strings.")
        return value
    return [part.strip() for part in text.split(",") if part.strip()]


def _parse_env(field: str, raw: str) -> Any:
    env_name = _ENV[field]
    if field in _BOOL_FIELDS:
        return _parse_bool(raw, env_name)
    if field in _JSON_FIELDS:
        return _parse_object(raw, env_name)
    if field == "redacted_fields":
        return _parse_fields(raw, env_name)
    return raw


@dataclass(frozen=True)
class LoggingConfig:
    """Settings for one logger.

    Required fields identify the application and the destination. Destination
    settings belong in ``destination_config``, not as extra attributes here.
    """

    application: str
    environment: str
    destination: str
    destination_config: dict[str, Any]
    minimum_level: str = "INFO"
    service_version: str | None = None
    component: str | None = None
    cluster: str | None = None
    region: str | None = None
    static_metadata: dict[str, Any] | None = None
    include_hostname: bool = False
    include_process_id: bool = False
    include_thread_id: bool = False
    redact_sensitive_data: bool = True
    redacted_fields: tuple[str, ...] | list[str] | None = None
    timestamp_format: str | None = None
    raise_destination_errors: bool = False
    custom_metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        updates = {
            "application": _require_text(self.application, "application"),
            "environment": _require_text(self.environment, "environment"),
            "destination": _require_text(self.destination, "destination"),
            "destination_config": _require_mapping(self.destination_config, "destination_config"),
            "minimum_level": normalize_level(self.minimum_level),
            "service_version": _optional_text(self.service_version, "service_version"),
            "component": _optional_text(self.component, "component"),
            "cluster": _optional_text(self.cluster, "cluster"),
            "region": _optional_text(self.region, "region"),
            "static_metadata": _optional_mapping(self.static_metadata, "static_metadata"),
            "include_hostname": _require_bool(self.include_hostname, "include_hostname"),
            "include_process_id": _require_bool(self.include_process_id, "include_process_id"),
            "include_thread_id": _require_bool(self.include_thread_id, "include_thread_id"),
            "redact_sensitive_data": _require_bool(
                self.redact_sensitive_data, "redact_sensitive_data"
            ),
            "redacted_fields": _optional_fields(self.redacted_fields),
            "timestamp_format": _optional_timestamp_format(self.timestamp_format),
            "raise_destination_errors": _require_bool(
                self.raise_destination_errors, "raise_destination_errors"
            ),
            "custom_metadata": _optional_mapping(self.custom_metadata, "custom_metadata"),
        }
        for name, value in updates.items():
            object.__setattr__(self, name, value)

    @property
    def active_redacted_fields(self) -> tuple[str, ...]:
        """Field names used when redaction is enabled."""
        if self.redacted_fields is None:
            return DEFAULT_REDACTED_FIELDS
        return self.redacted_fields

    @classmethod
    def from_env(cls, **overrides: Any) -> LoggingConfig:
        """Build a config from ``SHARED_LOGGER_*`` variables.

        A keyword argument replaces that field's environment variable. Direct
        construction of :class:`LoggingConfig` does not read the environment.

        ``SHARED_LOGGER_APPLICATION``, ``SHARED_LOGGER_ENVIRONMENT``, and
        ``SHARED_LOGGER_DESTINATION`` are required unless passed as overrides.
        ``SHARED_LOGGER_DESTINATION_CONFIG`` is a JSON object. When it is unset
        and not overridden, destination settings default to an empty dictionary.
        """
        known = {item.name for item in fields(cls)}
        unknown = sorted(set(overrides) - known)
        if unknown:
            names = ", ".join(unknown)
            raise ConfigurationError(f"Unknown configuration fields: {names}.")

        values: dict[str, Any] = {}
        for field_name, env_name in _ENV.items():
            if field_name in overrides:
                values[field_name] = overrides[field_name]
                continue
            raw = os.environ.get(env_name)
            if raw is None or not raw.strip():
                continue
            values[field_name] = _parse_env(field_name, raw)

        missing = [name for name in _REQUIRED_ENV if name not in values]
        if missing:
            env_names = ", ".join(_ENV[name] for name in missing)
            raise ConfigurationError(
                f"Missing required configuration: {', '.join(missing)}. Set {env_names}."
            )
        if "destination_config" not in values:
            values["destination_config"] = {}
        return cls(**values)
