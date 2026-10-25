"""Every built-in adapter honors the same lifecycle contract."""

import json

import pytest

from shared_logger import DestinationError
from shared_logger.registry import get_adapter


@pytest.mark.parametrize("destination", ["console", "file", "shared_file"])
def test_adapter_contract(destination, tmp_path, capsys):
    config: dict[str, str] = {}
    path = tmp_path / f"{destination}.log"
    if destination != "console":
        config = {"path": str(path)}
    fresh = get_adapter(destination)()
    with pytest.raises(DestinationError):
        fresh.write({"level": "INFO", "message": "too soon"})

    adapter = get_adapter(destination)()
    adapter.initialize(config)
    event = {"schema_version": 1, "level": "INFO", "message": "contract"}
    adapter.write(event)
    adapter.flush()
    adapter.close()
    adapter.close()
    with pytest.raises(DestinationError, match="closed"):
        adapter.write(event)

    if destination == "console":
        payload = capsys.readouterr().out
    else:
        payload = path.read_text(encoding="utf-8")
    assert json.loads(payload.strip())["message"] == "contract"
