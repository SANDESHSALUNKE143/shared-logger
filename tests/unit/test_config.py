"""Configuration, levels, redaction, and registry tests."""

import json
from datetime import datetime, timezone

import pytest

from shared_logger import (
    ConfigurationError,
    ConsoleAdapter,
    LoggingConfig,
    register_adapter,
)
from shared_logger.adapters.base import LoggingAdapter
from shared_logger.config import DEFAULT_REDACTED_FIELDS
from shared_logger.event import (
    build_event,
    exception_details,
    format_timestamp,
    sanitize,
)
from shared_logger.filters import passes_minimum
from shared_logger.levels import normalize_level
from shared_logger.redaction import REDACTED, redact
from shared_logger.registry import get_adapter, registered_names


def test_normalize_level_accepts_any_case():
    assert normalize_level(" info ") == "INFO"
    assert normalize_level("critical") == "CRITICAL"


def test_normalize_level_rejects_unknown_and_non_strings():
    with pytest.raises(ConfigurationError, match="minimum_level"):
        normalize_level("verbose")
    with pytest.raises(ConfigurationError, match="string"):
        normalize_level(1)


def test_passes_minimum():
    assert passes_minimum("ERROR", "WARNING")
    assert passes_minimum("WARNING", "WARNING")
    assert not passes_minimum("INFO", "WARNING")
    assert not passes_minimum("DEBUG", "INFO")


def test_config_normalizes_and_copies_metadata():
    nested = {"team": "analytics", "owner": {"name": "ada"}}
    config = LoggingConfig(
        application=" campaign-analytics ",
        environment="production",
        destination="file",
        destination_config={"path": "./logs/application.log"},
        minimum_level="debug",
        static_metadata=nested,
        redacted_fields=[" password ", "api_key"],
    )
    assert config.application == "campaign-analytics"
    assert config.minimum_level == "DEBUG"
    assert config.redacted_fields == ("password", "api_key")
    nested["team"] = "changed"
    nested["owner"]["name"] = "changed"
    assert config.static_metadata == {"team": "analytics", "owner": {"name": "ada"}}
    assert config.active_redacted_fields == ("password", "api_key")


def test_default_redacted_fields():
    config = LoggingConfig(
        application="payment-service",
        environment="production",
        destination="file",
        destination_config={"path": "./logs/application.jsonl"},
    )
    assert config.redact_sensitive_data is True
    assert config.raise_destination_errors is False
    assert config.active_redacted_fields == DEFAULT_REDACTED_FIELDS


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("application", "", "application"),
        ("application", "   ", "application"),
        ("application", 12, "application"),
        ("environment", None, "environment"),
        ("destination", "", "destination"),
        ("destination_config", [], "destination_config"),
        ("destination_config", {1: "x"}, "destination_config"),
        ("minimum_level", "verbose", "minimum_level"),
        ("service_version", "", "service_version"),
        ("include_hostname", "yes", "include_hostname"),
        ("include_process_id", 1, "include_process_id"),
        ("redact_sensitive_data", "true", "redact_sensitive_data"),
        ("redacted_fields", "password", "redacted_fields"),
        ("redacted_fields", [""], "redacted_fields"),
        ("timestamp_format", "%", "timestamp_format"),
        ("static_metadata", [], "static_metadata"),
        ("static_metadata", {"": "x"}, "static_metadata"),
        ("custom_metadata", "nope", "custom_metadata"),
        ("raise_destination_errors", None, "raise_destination_errors"),
    ],
)
def test_invalid_config_fields(field, value, match):
    values = {
        "application": "campaign-analytics",
        "environment": "production",
        "destination": "file",
        "destination_config": {"path": "./logs/application.log"},
    }
    values[field] = value
    with pytest.raises(ConfigurationError, match=match):
        LoggingConfig(**values)


def test_direct_constructor_ignores_environment(monkeypatch):
    monkeypatch.setenv("SHARED_LOGGER_APPLICATION", "from-env")
    config = LoggingConfig(
        application="from-code",
        environment="production",
        destination="console",
        destination_config={},
    )
    assert config.application == "from-code"


def test_from_env_uses_variables_and_overrides(monkeypatch):
    monkeypatch.setenv("SHARED_LOGGER_APPLICATION", "from-env")
    monkeypatch.setenv("SHARED_LOGGER_ENVIRONMENT", "staging")
    monkeypatch.setenv("SHARED_LOGGER_DESTINATION", "console")
    monkeypatch.setenv("SHARED_LOGGER_DESTINATION_CONFIG", '{"stream": "stderr"}')
    monkeypatch.setenv("SHARED_LOGGER_MINIMUM_LEVEL", "warning")
    monkeypatch.setenv("SHARED_LOGGER_SERVICE_VERSION", "1.2.3")
    monkeypatch.setenv("SHARED_LOGGER_STATIC_METADATA", '{"team": "analytics"}')
    monkeypatch.setenv("SHARED_LOGGER_CUSTOM_METADATA", '{"owner": "platform"}')
    monkeypatch.setenv("SHARED_LOGGER_INCLUDE_HOSTNAME", "yes")
    monkeypatch.setenv("SHARED_LOGGER_INCLUDE_PROCESS_ID", "0")
    monkeypatch.setenv("SHARED_LOGGER_INCLUDE_THREAD_ID", "on")
    monkeypatch.setenv("SHARED_LOGGER_REDACT_SENSITIVE_DATA", "false")
    monkeypatch.setenv("SHARED_LOGGER_REDACTED_FIELDS", "password, api_key")
    monkeypatch.setenv("SHARED_LOGGER_RAISE_DESTINATION_ERRORS", "true")
    monkeypatch.setenv("SHARED_LOGGER_COMPONENT", "worker")
    monkeypatch.setenv("SHARED_LOGGER_CLUSTER", "india")
    monkeypatch.setenv("SHARED_LOGGER_REGION", "ap-south-1")
    config = LoggingConfig.from_env(application="from-code")
    assert config.application == "from-code"
    assert config.environment == "staging"
    assert config.destination_config == {"stream": "stderr"}
    assert config.minimum_level == "WARNING"
    assert config.service_version == "1.2.3"
    assert config.static_metadata == {"team": "analytics"}
    assert config.custom_metadata == {"owner": "platform"}
    assert config.include_hostname is True
    assert config.include_process_id is False
    assert config.include_thread_id is True
    assert config.redact_sensitive_data is False
    assert config.redacted_fields == ("password", "api_key")
    assert config.raise_destination_errors is True
    assert config.component == "worker"
    assert config.cluster == "india"
    assert config.region == "ap-south-1"


def test_from_env_defaults_destination_config(monkeypatch):
    monkeypatch.setenv("SHARED_LOGGER_APPLICATION", "app")
    monkeypatch.setenv("SHARED_LOGGER_ENVIRONMENT", "dev")
    monkeypatch.setenv("SHARED_LOGGER_DESTINATION", "console")
    config = LoggingConfig.from_env()
    assert config.destination_config == {}
    assert config.minimum_level == "INFO"


def test_from_env_accepts_json_field_list(monkeypatch):
    monkeypatch.setenv("SHARED_LOGGER_APPLICATION", "app")
    monkeypatch.setenv("SHARED_LOGGER_ENVIRONMENT", "dev")
    monkeypatch.setenv("SHARED_LOGGER_DESTINATION", "console")
    monkeypatch.setenv("SHARED_LOGGER_REDACTED_FIELDS", json.dumps(["token", "secret"]))
    config = LoggingConfig.from_env()
    assert config.redacted_fields == ("token", "secret")


def test_from_env_errors(monkeypatch):
    monkeypatch.delenv("SHARED_LOGGER_APPLICATION", raising=False)
    monkeypatch.delenv("SHARED_LOGGER_ENVIRONMENT", raising=False)
    monkeypatch.delenv("SHARED_LOGGER_DESTINATION", raising=False)
    with pytest.raises(ConfigurationError, match="SHARED_LOGGER_APPLICATION"):
        LoggingConfig.from_env()
    monkeypatch.setenv("SHARED_LOGGER_APPLICATION", "app")
    monkeypatch.setenv("SHARED_LOGGER_ENVIRONMENT", "dev")
    monkeypatch.setenv("SHARED_LOGGER_DESTINATION", "console")
    monkeypatch.setenv("SHARED_LOGGER_DESTINATION_CONFIG", "[]")
    with pytest.raises(ConfigurationError, match="SHARED_LOGGER_DESTINATION_CONFIG"):
        LoggingConfig.from_env()
    monkeypatch.setenv("SHARED_LOGGER_DESTINATION_CONFIG", "{")
    with pytest.raises(ConfigurationError, match="JSON"):
        LoggingConfig.from_env()
    monkeypatch.delenv("SHARED_LOGGER_DESTINATION_CONFIG")
    monkeypatch.setenv("SHARED_LOGGER_INCLUDE_HOSTNAME", "maybe")
    with pytest.raises(ConfigurationError, match="SHARED_LOGGER_INCLUDE_HOSTNAME"):
        LoggingConfig.from_env()
    monkeypatch.delenv("SHARED_LOGGER_INCLUDE_HOSTNAME")
    monkeypatch.setenv("SHARED_LOGGER_REDACTED_FIELDS", "{")
    with pytest.raises(ConfigurationError, match="SHARED_LOGGER_REDACTED_FIELDS"):
        LoggingConfig.from_env()
    monkeypatch.setenv("SHARED_LOGGER_REDACTED_FIELDS", '{"a": 1}')
    with pytest.raises(ConfigurationError, match="JSON array"):
        LoggingConfig.from_env()
    with pytest.raises(ConfigurationError, match="Unknown configuration"):
        LoggingConfig.from_env(application="app", not_a_field=True)


def test_redact_nested_case_and_lists_without_mutation():
    payload = {
        "Password": "hunter2",
        "profile": {"API_KEY": "k", "name": "ada"},
        "items": [{"access_token": "t", "n": 1}, ("secret", {"authorization": "a"})],
    }
    original = {
        "Password": "hunter2",
        "profile": {"API_KEY": "k", "name": "ada"},
        "items": [{"access_token": "t", "n": 1}, ("secret", {"authorization": "a"})],
    }
    redacted = redact(payload, ["password", "api_key", "access_token", "authorization", "secret"])
    assert payload == original
    assert redacted["Password"] == REDACTED
    assert redacted["profile"]["API_KEY"] == REDACTED
    assert redacted["profile"]["name"] == "ada"
    assert redacted["items"][0]["access_token"] == REDACTED
    assert redacted["items"][0]["n"] == 1
    assert redacted["items"][1][1]["authorization"] == REDACTED
    assert redact("plain", ["password"]) == "plain"


def test_timestamp_default_and_custom():
    moment = datetime(2026, 10, 25, 10, 30, 0, 123000, tzinfo=timezone.utc)
    assert format_timestamp(None, moment) == "2026-10-25T10:30:00.123Z"
    naive = datetime(2026, 10, 25, 10, 30, 0, 123000)
    assert format_timestamp(None, naive) == "2026-10-25T10:30:00.123Z"
    assert format_timestamp("%Y", moment) == "2026"


def test_exception_details_with_and_without_traceback():
    bare = ValueError("boom")
    details = exception_details(bare)
    assert details == {"type": "ValueError", "message": "boom"}
    try:
        raise RuntimeError("failed")
    except RuntimeError as exc:
        traced = exception_details(exc)
    assert traced["type"] == "RuntimeError"
    assert "RuntimeError" in traced["traceback"]
    assert "failed" in traced["message"]


def test_sanitize_json_types_and_placeholders():
    class Widget:
        pass

    value = {
        "ok": True,
        "n": 3,
        "f": 1.5,
        "missing": None,
        "items": (1, {"a": 2}),
        7: "seven",
        "bad": Widget(),
        "nan": float("nan"),
        "inf": float("inf"),
    }
    clean = sanitize(value)
    assert clean["ok"] is True
    assert clean["items"] == [1, {"a": 2}]
    assert clean["7"] == "seven"
    assert clean["bad"].startswith("<non-serializable:")
    assert clean["bad"].endswith("Widget>")
    assert clean["nan"].startswith("<non-serializable:")
    assert clean["inf"].startswith("<non-serializable:")
    assert value["items"] == (1, {"a": 2})


def test_build_event_precedence_and_reserved_fields(monkeypatch):
    monkeypatch.setattr("shared_logger.event.socket.gethostname", lambda: "worker-01")
    config = LoggingConfig(
        application="campaign-analytics",
        environment="production",
        destination="console",
        destination_config={},
        service_version="1.0.0",
        component="campaign_processor",
        cluster="india",
        region="ap-south-1",
        include_hostname=True,
        include_process_id=True,
        include_thread_id=True,
        static_metadata={"team": "analytics", "correlation_id": "from-static"},
        custom_metadata={"team": "platform", "owner": "static"},
        timestamp_format="%Y-%m-%d",
    )
    moment = datetime(2026, 10, 25, tzinfo=timezone.utc)
    event = build_event(
        config=config,
        level="INFO",
        message="Data processing started",
        bound={"team": "bound", "tenant_id": "tenant-456", "correlation_id": "from-bind"},
        fields={
            "team": "call",
            "records_processed": 500,
            "application": "other",
            "level": "DEBUG",
            "message": "nope",
            "correlation_id": "req-123",
        },
        moment=moment,
    )
    assert event["schema_version"] == 1
    assert event["timestamp"] == "2026-10-25"
    assert event["level"] == "INFO"
    assert event["message"] == "Data processing started"
    assert event["application"] == "campaign-analytics"
    assert event["hostname"] == "worker-01"
    assert isinstance(event["process_id"], int)
    assert isinstance(event["thread_id"], int)
    assert event["correlation_id"] == "req-123"
    assert event["metadata"]["team"] == "call"
    assert event["metadata"]["owner"] == "static"
    assert event["metadata"]["tenant_id"] == "tenant-456"
    assert event["metadata"]["application"] == "other"
    assert event["metadata"]["level"] == "DEBUG"
    assert event["metadata"]["message"] == "nope"
    assert "correlation_id" not in event["metadata"]


def test_build_event_omits_unset_fields_and_empty_hostname(monkeypatch):
    monkeypatch.setattr("shared_logger.event.socket.gethostname", lambda: "")
    config = LoggingConfig(
        application="app",
        environment="dev",
        destination="console",
        destination_config={},
        include_hostname=True,
    )
    event = build_event(
        config=config,
        level="DEBUG",
        message="quiet",
        bound={},
        fields={},
    )
    assert "hostname" not in event
    assert "metadata" not in event
    assert "service_version" not in event
    assert "correlation_id" not in event


def test_build_event_hostname_failure_is_omitted(monkeypatch):
    def explode():
        raise OSError("no host")

    monkeypatch.setattr("shared_logger.event.socket.gethostname", explode)
    config = LoggingConfig(
        application="app",
        environment="dev",
        destination="console",
        destination_config={},
        include_hostname=True,
    )
    event = build_event(config=config, level="INFO", message="up", bound={}, fields={})
    assert "hostname" not in event


def test_correlation_id_nested_secrets_are_redacted():
    config = LoggingConfig(
        application="app",
        environment="dev",
        destination="console",
        destination_config={},
    )
    event = build_event(
        config=config,
        level="INFO",
        message="bound",
        bound={"correlation_id": {"id": "req-1", "password": "hide-me"}},
        fields={},
    )
    assert event["correlation_id"]["id"] == "req-1"
    assert event["correlation_id"]["password"] == REDACTED


def test_registry_rejects_bad_registration_and_unknown_names():
    class NotAdapter:
        pass

    with pytest.raises(ConfigurationError, match="non-empty"):
        register_adapter("  ", ConsoleAdapter)
    with pytest.raises(ConfigurationError, match="LoggingAdapter"):
        register_adapter("custom", NotAdapter)  # type: ignore[arg-type]
    with pytest.raises(ConfigurationError, match="already registered"):
        register_adapter("console", ConsoleAdapter)
    with pytest.raises(ConfigurationError, match="kafka"):
        get_adapter("kafka")
    assert "console" in registered_names()
    assert "file" in registered_names()
    assert "shared_file" in registered_names()


def test_register_custom_adapter():
    class Extra(LoggingAdapter):
        def initialize(self, config):
            return None

        def write(self, event):
            return None

    register_adapter("extra-one", Extra)
    assert get_adapter("extra-one") is Extra
