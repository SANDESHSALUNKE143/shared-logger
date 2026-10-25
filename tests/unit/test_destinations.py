"""File rotation, retention, and console stream selection."""

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest
from tests.support import read_jsonl

from shared_logger import (
    ConfigurationError,
    ConsoleAdapter,
    FileAdapter,
    Logger,
    LoggingConfig,
    SharedFileAdapter,
)
from shared_logger.adapters.file import parse_retention, parse_rotation


def test_rotation_and_retention_units():
    assert parse_rotation("10 MB", "file") == 10 * 1024 * 1024
    assert parse_rotation("500 KB", "file") == 500 * 1024
    assert parse_rotation("1 GB", "file") == 1024**3
    assert parse_rotation("100 B", "file") == 100
    assert parse_rotation("10 mb", "file") == 10 * 1024 * 1024
    assert parse_retention("7 days", "file").days == 7
    assert parse_retention("24 hours", "file").total_seconds() == 24 * 60 * 60
    assert parse_retention("30 minutes", "file").total_seconds() == 30 * 60
    assert parse_retention("90 seconds", "file").total_seconds() == 90
    with pytest.raises(ConfigurationError, match="rotation"):
        parse_rotation("10 megabytes", "file")
    with pytest.raises(ConfigurationError, match="greater than zero"):
        parse_rotation("0 MB", "file")
    with pytest.raises(ConfigurationError, match="retention"):
        parse_retention("soon", "file")
    with pytest.raises(ConfigurationError, match="greater than zero"):
        parse_retention("0 days", "file")
    with pytest.raises(ConfigurationError, match="string"):
        parse_rotation(10, "file")
    with pytest.raises(ConfigurationError, match="string"):
        parse_retention(7, "shared_file")


def test_rotation_moves_the_active_file(tmp_path):
    path = tmp_path / "app.log"
    adapter = FileAdapter()
    adapter.initialize({"path": str(path), "rotation": "80 B"})
    for index in range(6):
        adapter.write({"message": f"event-{index}-0123456789"})
    adapter.close()
    rotated = [
        item for item in tmp_path.iterdir() if item.name.startswith("app.log.") and item.is_file()
    ]
    assert rotated
    combined = []
    for item in [path, *rotated]:
        combined.extend(read_jsonl(item))
    assert len(combined) == 6
    assert path.exists()


def test_oversized_line_is_written(tmp_path):
    path = tmp_path / "big.log"
    adapter = FileAdapter()
    adapter.initialize({"path": str(path), "rotation": "20 B"})
    adapter.write({"message": "this line is intentionally longer than the rotation limit"})
    adapter.write({"message": "next"})
    adapter.close()
    assert path.read_text(encoding="utf-8").strip()
    assert any(item.name.startswith("big.log.") for item in tmp_path.iterdir())


def test_retention_deletes_only_expired_rotated_files(tmp_path):
    path = tmp_path / "app.log"
    path.write_text('{"message":"existing"}\n', encoding="utf-8")
    old_time = datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp()
    os.utime(path, (old_time, old_time))
    expired = Path(str(path) + ".20200101T000000000000Z")
    expired.write_text('{"message":"old"}\n', encoding="utf-8")
    os.utime(expired, (old_time, old_time))
    recent = Path(str(path) + ".20990101T000000000000Z")
    recent.write_text('{"message":"new"}\n', encoding="utf-8")
    unrelated = tmp_path / "app.log.bak"
    unrelated.write_text("keep", encoding="utf-8")
    notes = tmp_path / "notes.txt"
    notes.write_text("keep", encoding="utf-8")
    adapter = FileAdapter()
    adapter.initialize({"path": str(path), "rotation": "1 MB", "retention": "7 days"})
    adapter.close()
    assert not expired.exists()
    assert recent.exists()
    assert unrelated.read_text(encoding="utf-8") == "keep"
    assert notes.exists()
    assert "existing" in path.read_text(encoding="utf-8")


def test_file_rejects_bad_config_and_repeat_init(tmp_path):
    adapter = FileAdapter()
    with pytest.raises(ConfigurationError, match="path"):
        adapter.initialize({})
    with pytest.raises(ConfigurationError, match="dictionary"):
        adapter.initialize([])  # type: ignore[arg-type]
    adapter.initialize({"path": str(tmp_path / "once.log")})
    with pytest.raises(ConfigurationError, match="already initialized"):
        adapter.initialize({"path": str(tmp_path / "once.log")})
    adapter.close()
    blocked = tmp_path / "not-a-directory"
    blocked.write_text("x", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="Cannot create log directory"):
        FileAdapter().initialize({"path": str(blocked / "app.log")})


def test_close_releases_file_when_fsync_fails(tmp_path, monkeypatch):
    adapter = FileAdapter()
    adapter.initialize({"path": str(tmp_path / "a.log")})
    adapter.write({"message": "before"})
    handle = adapter._handle

    def explode(_fd: int) -> None:
        raise OSError("fsync failed")

    monkeypatch.setattr(os, "fsync", explode)
    with pytest.raises(OSError, match="fsync failed"):
        adapter.close()
    assert handle is not None
    assert handle.closed
    assert adapter._handle is None
    adapter.close()


def test_flush_fsyncs(tmp_path, monkeypatch):
    adapter = FileAdapter()
    adapter.initialize({"path": str(tmp_path / "a.log")})
    calls: list[int] = []

    def record(fd: int) -> None:
        calls.append(fd)

    monkeypatch.setattr(os, "fsync", record)
    adapter.write({"message": "line"})
    adapter.flush()
    adapter.close()
    assert calls


def test_console_routes_streams_and_rejects_bad_config(capsys):
    adapter = ConsoleAdapter()
    adapter.initialize({})
    adapter.write({"level": "INFO", "message": "out"})
    adapter.write({"level": "ERROR", "message": "err"})
    adapter.write({"level": "CRITICAL", "message": "crit"})
    adapter.flush()
    adapter.close()
    adapter.close()
    captured = capsys.readouterr()
    assert '"message":"out"' in captured.out
    assert '"message":"err"' in captured.err
    assert '"message":"crit"' in captured.err

    forced = ConsoleAdapter()
    forced.initialize({"stream": "stdout"})
    forced.write({"level": "ERROR", "message": "still-out"})
    forced.close()
    assert "still-out" in capsys.readouterr().out

    err = ConsoleAdapter()
    err.initialize({"stream": "stderr"})
    err.write({"level": "INFO", "message": "still-err"})
    err.close()
    assert "still-err" in capsys.readouterr().err

    with pytest.raises(ConfigurationError, match="stream"):
        ConsoleAdapter().initialize({"stream": "file"})
    with pytest.raises(ConfigurationError, match="does not support"):
        ConsoleAdapter().initialize({"path": "x"})
    with pytest.raises(ConfigurationError, match="dictionary"):
        ConsoleAdapter().initialize("nope")  # type: ignore[arg-type]
    started = ConsoleAdapter()
    started.initialize({})
    with pytest.raises(ConfigurationError, match="already initialized"):
        started.initialize({})
    started.close()


def test_console_write_before_and_after_close():
    from shared_logger import DestinationError

    adapter = ConsoleAdapter()
    with pytest.raises(DestinationError, match="not initialized"):
        adapter.write({"level": "INFO", "message": "x"})
    adapter.initialize({})
    adapter.close()
    with pytest.raises(DestinationError, match="closed"):
        adapter.write({"level": "INFO", "message": "x"})
    adapter.flush()


def test_shared_file_uses_the_same_writer(tmp_path):
    path = tmp_path / "mounted" / "application.jsonl"
    logger = Logger.initialize(
        LoggingConfig(
            application="data-processing",
            environment="development",
            destination="shared_file",
            destination_config={"path": str(path), "rotation": "1 MB", "retention": "7 days"},
            minimum_level="DEBUG",
        )
    )
    logger.write_info("shared write", records=1)
    logger.close()
    assert read_jsonl(path)[0]["message"] == "shared write"
    with pytest.raises(ConfigurationError, match="shared_file"):
        SharedFileAdapter().initialize({})


def test_append_does_not_truncate(tmp_path):
    path = tmp_path / "existing.log"
    path.write_text('{"message":"previous"}\n', encoding="utf-8")
    logger = Logger.initialize(
        LoggingConfig(
            application="app",
            environment="dev",
            destination="file",
            destination_config={"path": str(path)},
        )
    )
    logger.write_info("next")
    logger.close()
    messages = [event["message"] for event in read_jsonl(path)]
    assert messages == ["previous", "next"]
