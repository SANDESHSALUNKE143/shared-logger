"""JSON Lines file destination.

The active file is opened in UTF-8 append mode. Parent directories are created
when the process is allowed to create them. Each ``write`` appends one JSON
object and flushes the file object. :meth:`FileAdapter.flush` and
:meth:`FileAdapter.close` also call ``os.fsync``.

``rotation`` is a size such as ``10 MB``, ``500 KB``, ``1 GB``, or ``100 B``.
When the active file is already at least that large, the next write renames it
with a UTC timestamp and opens a new file. A single event larger than the
limit is still written; the following event rotates first.

``retention`` is a duration such as ``7 days`` or ``24 hours``. It is only
valid together with ``rotation``. Rotated files older than the duration are
deleted. The active file is never deleted by retention. Names that do not
match the rotation suffix are left alone.

This adapter locks writes inside one process. It does not coordinate writers
in other processes.
"""

from __future__ import annotations

import json
import os
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, TextIO

from shared_logger.adapters.base import LoggingAdapter
from shared_logger.exceptions import ConfigurationError, DestinationError

_SIZE = re.compile(r"^(\d+)\s*(B|KB|MB|GB)$", re.IGNORECASE)
_RETENTION = re.compile(
    r"^(\d+)\s*(second|seconds|minute|minutes|hour|hours|day|days)$",
    re.IGNORECASE,
)
_ROTATED_SUFFIX = re.compile(r"^\d{8}T\d{6}\d{6}Z(?:\.\d+)?$")
_SIZE_UNITS = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}
_RETENTION_UNITS = {
    "second": 1,
    "seconds": 1,
    "minute": 60,
    "minutes": 60,
    "hour": 60 * 60,
    "hours": 60 * 60,
    "day": 24 * 60 * 60,
    "days": 24 * 60 * 60,
}
_FILE_KEYS = {"path", "rotation", "retention"}


def parse_rotation(value: object, destination: str) -> int:
    """Return the rotation limit in bytes."""
    if not isinstance(value, str):
        raise ConfigurationError(
            f"{destination} rotation must be a string such as '10 MB'. Got {type(value).__name__}."
        )
    match = _SIZE.match(value.strip())
    if match is None:
        raise ConfigurationError(
            f"{destination} rotation must look like '10 MB', '500 KB', '1 GB', or '100 B'. "
            f"Got {value!r}."
        )
    amount = int(match.group(1))
    if amount <= 0:
        raise ConfigurationError(f"{destination} rotation must be greater than zero.")
    return amount * _SIZE_UNITS[match.group(2).upper()]


def parse_retention(value: object, destination: str) -> timedelta:
    """Return how long a rotated file is kept."""
    if not isinstance(value, str):
        raise ConfigurationError(
            f"{destination} retention must be a string such as '7 days'. "
            f"Got {type(value).__name__}."
        )
    match = _RETENTION.match(value.strip())
    if match is None:
        raise ConfigurationError(
            f"{destination} retention must look like '7 days', '24 hours', "
            f"'30 minutes', or '90 seconds'. Got {value!r}."
        )
    amount = int(match.group(1))
    if amount <= 0:
        raise ConfigurationError(f"{destination} retention must be greater than zero.")
    seconds = amount * _RETENTION_UNITS[match.group(2).lower()]
    return timedelta(seconds=seconds)


def _dump(event: dict[str, Any]) -> str:
    return json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"


@dataclass
class _FileSettings:
    path: Path
    rotation: int | None
    retention: timedelta | None


def _settings(config: dict[str, Any], destination: str) -> _FileSettings:
    if not isinstance(config, dict):
        raise ConfigurationError(f"{destination} destination_config must be a dictionary.")
    unknown = sorted(set(config) - _FILE_KEYS)
    if unknown:
        names = ", ".join(unknown)
        raise ConfigurationError(
            f"{destination} destination_config does not support: {names}. "
            "Supported keys: path, rotation, retention."
        )
    raw_path = config.get("path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ConfigurationError(
            f"{destination} destination_config['path'] must be a non-empty string."
        )
    rotation = None
    if "rotation" in config:
        rotation = parse_rotation(config["rotation"], destination)
    retention = None
    if "retention" in config:
        retention = parse_retention(config["retention"], destination)
    if retention is not None and rotation is None:
        raise ConfigurationError(
            f"{destination} retention requires rotation. "
            "Set destination_config['rotation'] as well, for example '10 MB'."
        )
    return _FileSettings(path=Path(raw_path), rotation=rotation, retention=retention)


class FileAdapter(LoggingAdapter):
    """Append JSON Lines to a local file, with optional size rotation."""

    destination_name = "file"

    def __init__(self) -> None:
        self._path: Path | None = None
        self._rotation: int | None = None
        self._retention: timedelta | None = None
        self._handle: TextIO | None = None
        self._size = 0
        self._initialized = False
        self._closed = False
        self._lock = threading.Lock()

    def initialize(self, config: dict[str, Any]) -> None:
        """Create parent directories, open the file, and apply retention."""
        if self._initialized:
            raise ConfigurationError(f"{self.destination_name} adapter is already initialized.")
        settings = _settings(config, self.destination_name)
        parent = settings.path.parent
        if str(parent) not in ("", "."):
            try:
                parent.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise ConfigurationError(
                    f"Cannot create log directory {str(parent)!r} for "
                    f"{self.destination_name}: {exc.strerror or exc}."
                ) from exc
        try:
            handle = open(settings.path, "a", encoding="utf-8", newline="\n")
        except OSError as exc:
            raise ConfigurationError(
                f"Cannot open log file {str(settings.path)!r} for "
                f"{self.destination_name}: {exc.strerror or exc}."
            ) from exc
        self._path = settings.path
        self._rotation = settings.rotation
        self._retention = settings.retention
        self._handle = handle
        try:
            self._size = settings.path.stat().st_size
        except OSError as exc:
            handle.close()
            self._handle = None
            raise ConfigurationError(
                f"Cannot read log file size for {str(settings.path)!r}: {exc.strerror or exc}."
            ) from exc
        try:
            self._delete_expired()
        except Exception:
            self._handle = None
            handle.close()
            raise
        self._initialized = True

    def write(self, event: dict[str, Any]) -> None:
        """Append one JSON line, rotating first when the size limit is already met."""
        line = _dump(event)
        encoded = len(line.encode("utf-8"))
        with self._lock:
            self._require_open()
            if self._rotation is not None and self._size >= self._rotation:
                self._rotate()
            handle = self._handle
            if handle is None:
                raise DestinationError(f"{self.destination_name} adapter is not open.")
            handle.write(line)
            handle.flush()
            self._size += encoded

    def flush(self) -> None:
        """Flush and fsync the active file."""
        with self._lock:
            if self._closed or self._handle is None:
                return
            self._handle.flush()
            os.fsync(self._handle.fileno())

    def close(self) -> None:
        """Flush, fsync, and close the active file.

        The file is closed even when flush or fsync fails. A second call does
        nothing.
        """
        with self._lock:
            if self._closed:
                return
            self._closed = True
            handle = self._handle
            self._handle = None
            if handle is None:
                return
            try:
                handle.flush()
                os.fsync(handle.fileno())
            finally:
                handle.close()

    def _require_open(self) -> None:
        if self._closed:
            raise DestinationError(f"{self.destination_name} adapter is closed.")
        if not self._initialized or self._handle is None:
            raise DestinationError(f"{self.destination_name} adapter is not initialized.")

    def _rotate(self) -> None:
        """Rename the active file and open a new one. Caller holds ``_lock``."""
        path = self._path
        handle = self._handle
        if path is None or handle is None:
            raise DestinationError(f"{self.destination_name} adapter is not open.")
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
        self._handle = None
        try:
            os.replace(path, self._rotated_target(path))
            self._handle = open(path, "a", encoding="utf-8", newline="\n")
            self._size = 0
            self._delete_expired()
        except Exception:
            if self._handle is None and path.exists():
                try:
                    self._handle = open(path, "a", encoding="utf-8", newline="\n")
                    self._size = path.stat().st_size
                except OSError:
                    self._handle = None
            raise

    def _rotated_target(self, path: Path) -> Path:
        now = datetime.now(timezone.utc)
        stamp = now.strftime("%Y%m%dT%H%M%S") + f"{now.microsecond:06d}Z"
        candidate = Path(f"{path}.{stamp}")
        counter = 0
        while candidate.exists():
            counter += 1
            candidate = Path(f"{path}.{stamp}.{counter}")
        return candidate

    def _delete_expired(self) -> None:
        path = self._path
        retention = self._retention
        if path is None or retention is None:
            return
        cutoff = datetime.now(timezone.utc).timestamp() - retention.total_seconds()
        directory = path.parent if str(path.parent) not in ("", ".") else Path(".")
        if not directory.exists():
            return
        prefix = path.name + "."
        for candidate in directory.iterdir():
            if not candidate.is_file():
                continue
            if not candidate.name.startswith(prefix):
                continue
            suffix = candidate.name[len(prefix) :]
            if _ROTATED_SUFFIX.match(suffix) is None:
                continue
            try:
                modified = candidate.stat().st_mtime
            except OSError:
                continue
            if modified >= cutoff:
                continue
            try:
                candidate.unlink()
            except OSError as exc:
                raise DestinationError(
                    f"Cannot delete expired log file {str(candidate)!r}: {exc.strerror or exc}."
                ) from exc
