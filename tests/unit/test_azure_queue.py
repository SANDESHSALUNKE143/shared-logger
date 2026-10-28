"""Azure Storage Queue adapter."""

import json
import sys

import pytest

from shared_logger import AzureQueueAdapter, ConfigurationError, DestinationError, Logger
from shared_logger.adapters.azure_queue import _load_azure, _settings


class FakeQueue:
    def __init__(self, *, missing=False, fail=None, fail_send=None):
        self.missing = missing
        self.fail = fail
        self.fail_send = fail_send
        self.messages = []

    def get_queue_properties(self):
        if self.missing:
            _queue_client, not_found = _load_azure()
            raise not_found("missing")
        if self.fail is not None:
            raise self.fail
        return object()

    def send_message(self, content):
        if self.fail_send is not None:
            raise self.fail_send
        self.messages.append(content)


@pytest.fixture
def fake_queue(monkeypatch):
    holder = {}

    class Factory:
        @staticmethod
        def from_connection_string(connection_string, queue_name):
            holder["connection_string"] = connection_string
            holder["queue_name"] = queue_name
            return holder["client"]

    queue_client, not_found = _load_azure()
    monkeypatch.setattr(
        "shared_logger.adapters.azure_queue._load_azure",
        lambda: (Factory, not_found),
    )
    holder["client"] = FakeQueue()
    return holder


def test_settings_require_one_connection_source():
    with pytest.raises(ConfigurationError, match="exactly one"):
        _settings({"queue_name": "app-logs"})
    with pytest.raises(ConfigurationError, match="exactly one"):
        _settings(
            {
                "queue_name": "app-logs",
                "connection_string": "conn",
                "connection_string_env": "AZURE_STORAGE_CONNECTION_STRING",
            }
        )
    with pytest.raises(ConfigurationError, match="queue_name"):
        _settings({"connection_string": "conn"})
    with pytest.raises(ConfigurationError, match="connection_string"):
        _settings({"queue_name": "app-logs", "connection_string": "  "})
    with pytest.raises(ConfigurationError, match="does not support"):
        _settings({"queue_name": "app-logs", "connection_string": "conn", "topic": "x"})
    with pytest.raises(ConfigurationError, match="dictionary"):
        _settings([])  # type: ignore[arg-type]


def test_connection_string_env_reads_the_variable(monkeypatch):
    monkeypatch.setenv("AZURE_STORAGE_CONNECTION_STRING", "from-env")
    queue_name, connection_string = _settings(
        {"queue_name": " app-logs ", "connection_string_env": "AZURE_STORAGE_CONNECTION_STRING"}
    )
    assert queue_name == "app-logs"
    assert connection_string == "from-env"
    monkeypatch.delenv("AZURE_STORAGE_CONNECTION_STRING")
    with pytest.raises(ConfigurationError, match="AZURE_STORAGE_CONNECTION_STRING"):
        _settings(
            {
                "queue_name": "app-logs",
                "connection_string_env": "AZURE_STORAGE_CONNECTION_STRING",
            }
        )
    with pytest.raises(ConfigurationError, match="environment variable"):
        _settings({"queue_name": "app-logs", "connection_string_env": "1bad"})


def test_write_sends_one_json_message(fake_queue):
    adapter = AzureQueueAdapter()
    with pytest.raises(DestinationError, match="not initialized"):
        adapter.write({"schema_version": 1})
    adapter.initialize({"queue_name": "app-logs", "connection_string": "conn"})
    with pytest.raises(ConfigurationError, match="already initialized"):
        adapter.initialize({"queue_name": "app-logs", "connection_string": "conn"})
    event = {"schema_version": 1, "message": "hello", "environment": "dev"}
    adapter.write(event)
    adapter.flush()
    adapter.close()
    adapter.close()
    adapter.flush()
    with pytest.raises(DestinationError, match="closed"):
        adapter.write(event)
    assert fake_queue["queue_name"] == "app-logs"
    assert json.loads(fake_queue["client"].messages[0])["message"] == "hello"


def test_missing_queue_is_a_configuration_error(fake_queue):
    fake_queue["client"] = FakeQueue(missing=True)
    adapter = AzureQueueAdapter()
    with pytest.raises(ConfigurationError, match="does not exist"):
        adapter.initialize({"queue_name": "app-logs", "connection_string": "conn"})


def test_open_and_write_failures(fake_queue):
    fake_queue["client"] = FakeQueue(fail=RuntimeError("down"))
    adapter = AzureQueueAdapter()
    with pytest.raises(ConfigurationError, match="could not open"):
        adapter.initialize({"queue_name": "app-logs", "connection_string": "conn"})

    fake_queue["client"] = FakeQueue(fail_send=RuntimeError("full"))
    adapter = AzureQueueAdapter()
    adapter.initialize({"queue_name": "app-logs", "connection_string": "conn"})
    with pytest.raises(DestinationError, match="write failed"):
        adapter.write({"schema_version": 1})


def test_logger_uses_the_adapter(fake_queue, make_config):
    logger = Logger.initialize(
        make_config(
            destination="azure_queue",
            destination_config={"queue_name": "app-logs", "connection_string": "conn"},
        )
    )
    logger.write_info("from the logger")
    logger.close()
    body = json.loads(fake_queue["client"].messages[0])
    assert body["message"] == "from the logger"
    assert body["schema_version"] == 1


def test_missing_sdk_names_the_extra(monkeypatch):
    monkeypatch.setitem(sys.modules, "azure.storage.queue", None)
    monkeypatch.setitem(sys.modules, "azure.core.exceptions", None)
    with pytest.raises(ConfigurationError, match="shared-logger\\[azure\\]"):
        _load_azure()
