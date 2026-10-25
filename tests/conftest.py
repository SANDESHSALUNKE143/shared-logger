"""Shared pytest fixtures."""

import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from shared_logger import LoggingConfig, register_adapter
from tests.support import ListAdapter


@pytest.fixture
def log_path(tmp_path: Path) -> Path:
    return tmp_path / "application.log"


@pytest.fixture
def make_config(log_path: Path) -> Callable[..., LoggingConfig]:
    def _make(**overrides: Any) -> LoggingConfig:
        values: dict[str, Any] = {
            "application": "campaign-analytics",
            "environment": "production",
            "destination": "file",
            "destination_config": {"path": str(log_path)},
            "minimum_level": "DEBUG",
        }
        values.update(overrides)
        return LoggingConfig(**values)

    return _make


@pytest.fixture
def memory_name() -> Iterator[str]:
    """Register a fresh in-memory destination and return its name."""
    ListAdapter.instances = []
    ListAdapter.fail_write = False
    ListAdapter.fail_flush = False
    ListAdapter.fail_close = False
    ListAdapter.init_error = ""
    name = "memory_" + uuid.uuid4().hex
    register_adapter(name, ListAdapter)
    yield name
    ListAdapter.fail_write = False
    ListAdapter.fail_flush = False
    ListAdapter.fail_close = False
    ListAdapter.init_error = ""
