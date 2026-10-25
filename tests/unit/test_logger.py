"""Logger lifecycle, filtering, redaction, and destination error policy."""

import json
import threading

import pytest
from tests.support import ListAdapter, read_jsonl

from shared_logger import (
    ConfigurationError,
    DestinationError,
    Logger,
    LoggerClosedError,
    LoggingError,
)


def test_initialize_rejects_non_config():
    with pytest.raises(ConfigurationError, match="LoggingConfig"):
        Logger.initialize({"destination": "console"})  # type: ignore[arg-type]


def test_import_creates_no_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import shared_logger  # noqa: F401

    assert list(tmp_path.iterdir()) == []


def test_file_logging_appends_valid_json(make_config, log_path):
    logger = Logger.initialize(make_config(minimum_level="INFO"))
    logger.write_debug("hidden", user_id=1)
    logger.write_info("Application started", application_version="1.0.0")
    logger.write_warning("Resource usage approaching threshold", usage_percentage=85)
    logger.write_error("Unable to process request", request_id="req-123")
    logger.write_critical("Critical system failure", component="data_processor")
    logger.flush()
    logger.close()
    logger.close()
    events = read_jsonl(log_path)
    assert [event["level"] for event in events] == ["INFO", "WARNING", "ERROR", "CRITICAL"]
    assert events[0]["metadata"]["application_version"] == "1.0.0"
    assert events[0]["timestamp"].endswith("Z")
    assert events[2]["metadata"]["request_id"] == "req-123"
    for line in log_path.read_text(encoding="utf-8").splitlines():
        json.loads(line)


def test_two_loggers_do_not_duplicate_events(make_config, log_path):
    first = Logger.initialize(make_config())
    second = Logger.initialize(make_config())
    first.write_info("one")
    second.write_info("two")
    first.close()
    second.write_info("three")
    second.close()
    messages = [event["message"] for event in read_jsonl(log_path)]
    assert messages == ["one", "two", "three"]


def test_unicode_and_parent_directory(make_config, tmp_path):
    path = tmp_path / "nested" / "logs" / "app.log"
    logger = Logger.initialize(make_config(destination_config={"path": str(path)}))
    logger.write_info("café")
    logger.close()
    assert read_jsonl(path)[0]["message"] == "café"


def test_minimum_level_skips_the_destination(make_config, memory_name):
    logger = Logger.initialize(
        make_config(destination=memory_name, destination_config={}, minimum_level="WARNING")
    )
    logger.write_info("skipped", password="super-secret-value")
    logger.write_error("kept")
    logger.close()
    adapter = ListAdapter.instances[-1]
    assert adapter.write_calls == 1
    assert adapter.events[0]["level"] == "ERROR"


def test_bound_context_does_not_change_parent(make_config, log_path):
    logger = Logger.initialize(
        make_config(
            static_metadata={"team": "analytics"},
            custom_metadata={"team": "platform", "owner": "a"},
        )
    )
    request_logger = logger.bind(correlation_id="req-123", tenant_id="tenant-456", team="bound")
    request_logger.write_info("Request processing started")
    request_logger.write_info("Request processing completed", team="call", records_processed=2)
    logger.write_info("parent")
    other = request_logger.bind(correlation_id="req-999")
    other.write_info("child override")
    request_logger.write_info("original binding")
    logger.close()
    events = read_jsonl(log_path)
    assert events[0]["correlation_id"] == "req-123"
    assert events[0]["metadata"]["tenant_id"] == "tenant-456"
    assert events[0]["metadata"]["team"] == "bound"
    assert events[0]["metadata"]["owner"] == "a"
    assert events[1]["metadata"]["team"] == "call"
    assert events[1]["correlation_id"] == "req-123"
    assert "correlation_id" not in events[2]
    assert "tenant_id" not in events[2].get("metadata", {})
    assert events[3]["correlation_id"] == "req-999"
    assert events[4]["correlation_id"] == "req-123"


def test_reserved_fields_stay_in_metadata(make_config, log_path):
    logger = Logger.initialize(
        make_config(service_version="1.0.0", static_metadata={"message": "from-config"})
    )
    caller = {"application": "other", "nested": {"n": 1}}
    logger.write_info("hello", application="other", level="DEBUG", payload=caller)
    logger.close()
    event = read_jsonl(log_path)[0]
    assert event["application"] == "campaign-analytics"
    assert event["level"] == "INFO"
    assert event["message"] == "hello"
    assert event["service_version"] == "1.0.0"
    assert event["metadata"]["application"] == "other"
    assert event["metadata"]["level"] == "DEBUG"
    assert event["metadata"]["message"] == "from-config"
    assert caller["nested"]["n"] == 1


def test_redaction_in_file_output(make_config, log_path):
    logger = Logger.initialize(make_config())
    payload = {"Password": "secret-value", "name": "ada"}
    logger.write_info(
        "paid",
        user=payload,
        items=[{"API_KEY": "k-value"}],
    )
    logger.close()
    event = read_jsonl(log_path)[0]
    assert event["metadata"]["user"]["Password"] == "[REDACTED]"
    assert event["metadata"]["user"]["name"] == "ada"
    assert event["metadata"]["items"][0]["API_KEY"] == "[REDACTED]"
    assert payload["Password"] == "secret-value"
    assert "secret-value" not in log_path.read_text(encoding="utf-8")
    assert "k-value" not in log_path.read_text(encoding="utf-8")


def test_redaction_can_be_disabled_or_narrowed(make_config, log_path, tmp_path):
    open_logger = Logger.initialize(make_config(redact_sensitive_data=False))
    open_logger.write_info("open", password="visible")
    open_logger.close()
    assert read_jsonl(log_path)[0]["metadata"]["password"] == "visible"
    other = tmp_path / "narrow.log"
    narrow = Logger.initialize(
        make_config(
            destination_config={"path": str(other)},
            redacted_fields=["token"],
        )
    )
    narrow.write_info("narrow", password="visible", token="hide")
    narrow.close()
    event = read_jsonl(other)[0]
    assert event["metadata"]["password"] == "visible"
    assert event["metadata"]["token"] == "[REDACTED]"


def test_exception_logging_preserves_diagnostics(make_config, log_path):
    logger = Logger.initialize(make_config())
    try:
        raise ValueError("password=hunter2")
    except ValueError as exc:
        logger.write_exception(
            "An unexpected exception occurred",
            exception=exc,
            request_id="req-123",
        )
    logger.write_exception("No exception object was supplied")
    logger.close()
    events = read_jsonl(log_path)
    assert events[0]["level"] == "ERROR"
    assert events[0]["exception"]["type"] == "ValueError"
    assert events[0]["exception"]["message"] == "password=hunter2"
    assert "Traceback" in events[0]["exception"]["traceback"]
    assert events[0]["metadata"]["request_id"] == "req-123"
    assert "exception" not in events[1]
    assert "hunter2" in log_path.read_text(encoding="utf-8")


def test_non_serializable_metadata(make_config, log_path):
    class Tool:
        pass

    logger = Logger.initialize(make_config())
    logger.write_info("tool", item=Tool(), value=float("nan"))
    logger.close()
    metadata = read_jsonl(log_path)[0]["metadata"]
    assert metadata["item"].startswith("<non-serializable:")
    assert metadata["item"].endswith("Tool>")
    assert metadata["value"].startswith("<non-serializable:")


def test_write_api_validation(make_config, memory_name):
    logger = Logger.initialize(make_config(destination=memory_name, destination_config={}))
    with pytest.raises(LoggingError, match="string"):
        logger.write_info(12)  # type: ignore[arg-type]
    with pytest.raises(LoggingError, match="BaseException"):
        logger.write_exception("bad", exception="nope")  # type: ignore[arg-type]
    with pytest.raises(LoggingError, match="Context names"):
        logger.bind(**{"": "x"})
    logger.close()


def test_logging_after_close_raises(make_config, log_path):
    logger = Logger.initialize(make_config())
    bound = logger.bind(correlation_id="req-1")
    logger.close()
    logger.close()
    logger.flush()
    with pytest.raises(LoggerClosedError):
        logger.write_info("after")
    with pytest.raises(LoggerClosedError):
        bound.write_warning("after")
    with pytest.raises(LoggerClosedError):
        logger.bind(correlation_id="later")
    assert read_jsonl(log_path) == []


def test_unknown_destination_and_bad_settings(make_config, tmp_path):
    with pytest.raises(ConfigurationError, match="kafka"):
        Logger.initialize(make_config(destination="kafka", destination_config={}))
    with pytest.raises(ConfigurationError, match="elasticsearch"):
        Logger.initialize(make_config(destination="elasticsearch", destination_config={}))
    with pytest.raises(ConfigurationError, match="Cannot open"):
        Logger.initialize(make_config(destination_config={"path": str(tmp_path)}))
    with pytest.raises(ConfigurationError, match="does not support"):
        Logger.initialize(
            make_config(destination_config={"path": str(tmp_path / "a.log"), "batch": True})
        )
    with pytest.raises(ConfigurationError, match="retention requires rotation"):
        Logger.initialize(
            make_config(destination_config={"path": str(tmp_path / "a.log"), "retention": "7 days"})
        )


def test_destination_write_failure_is_raised(make_config, memory_name):
    ListAdapter.fail_write = True
    logger = Logger.initialize(
        make_config(
            destination=memory_name,
            destination_config={},
            raise_destination_errors=True,
        )
    )
    with pytest.raises(DestinationError, match="write") as caught:
        logger.write_info("token-phrase", password="super-secret-value")
    assert isinstance(caught.value.__cause__, OSError)
    assert logger.destination_failure_count == 1
    assert ListAdapter.instances[-1].write_calls == 1
    logger.close()


def test_destination_write_failure_is_reported_on_stderr(make_config, memory_name, capsys):
    ListAdapter.fail_write = True
    logger = Logger.initialize(make_config(destination=memory_name, destination_config={}))
    logger.write_info("token-phrase", password="super-secret-value")
    logger.close()
    error = capsys.readouterr().err
    assert "failed during write" in error
    assert "OSError" in error
    assert "token-phrase" not in error
    assert "super-secret-value" not in error
    assert logger.destination_failure_count == 1
    assert ListAdapter.instances[-1].write_calls == 1


def test_flush_and_close_failure_modes(make_config, memory_name, capsys):
    ListAdapter.fail_flush = True
    logger = Logger.initialize(
        make_config(
            destination=memory_name,
            destination_config={},
            raise_destination_errors=True,
        )
    )
    with pytest.raises(DestinationError, match="flush"):
        logger.flush()
    assert logger.destination_failure_count == 1
    logger.close()

    ListAdapter.fail_flush = False
    ListAdapter.fail_close = True
    closing = Logger.initialize(make_config(destination=memory_name, destination_config={}))
    closing.close()
    closing.close()
    error = capsys.readouterr().err
    assert "failed during close" in error
    assert closing.destination_failure_count == 1
    assert ListAdapter.instances[-1].closed is True


def test_close_failure_can_propagate(make_config, memory_name):
    ListAdapter.fail_close = True
    logger = Logger.initialize(
        make_config(
            destination=memory_name,
            destination_config={},
            raise_destination_errors=True,
        )
    )
    with pytest.raises(DestinationError, match="close"):
        logger.close()
    logger.close()
    assert logger.destination_failure_count == 1


def test_init_errors_from_adapter(make_config, memory_name):
    ListAdapter.init_error = "config"
    with pytest.raises(ConfigurationError, match="bad destination settings"):
        Logger.initialize(make_config(destination=memory_name, destination_config={}))
    ListAdapter.init_error = "runtime"
    with pytest.raises(ConfigurationError, match="connection refused"):
        Logger.initialize(make_config(destination=memory_name, destination_config={}))


def test_threaded_file_writes_stay_valid_json(make_config, log_path):
    logger = Logger.initialize(make_config())

    def worker(index: int) -> None:
        for number in range(20):
            logger.write_info("line", worker=index, n=number)

    threads = [threading.Thread(target=worker, args=(index,)) for index in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    logger.close()
    events = read_jsonl(log_path)
    assert len(events) == 80


def test_critical_minimum_filters_exceptions(make_config, log_path):
    logger = Logger.initialize(make_config(minimum_level="CRITICAL"))
    try:
        raise RuntimeError("nope")
    except RuntimeError as exc:
        logger.write_exception("hidden", exception=exc)
    logger.write_critical("visible")
    logger.close()
    events = read_jsonl(log_path)
    assert [event["message"] for event in events] == ["visible"]


def test_diagnostic_survives_stderr_failure(make_config, memory_name, monkeypatch):
    ListAdapter.fail_write = True
    logger = Logger.initialize(make_config(destination=memory_name, destination_config={}))

    class BrokenStream:
        def write(self, _text: str) -> None:
            raise OSError("stderr closed")

        def flush(self) -> None:
            return None

    monkeypatch.setattr("shared_logger.logger.sys.stderr", BrokenStream())
    logger.write_info("still counted")
    assert logger.destination_failure_count == 1
    logger.close()
