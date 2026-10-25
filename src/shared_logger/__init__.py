"""Structured logging with one public API and pluggable destinations.

Importing this package registers the built-in destinations and does not create
files or connect to external services. Call :meth:`Logger.initialize` before
writing events.
"""

from shared_logger.adapters.base import LoggingAdapter
from shared_logger.adapters.console import ConsoleAdapter
from shared_logger.adapters.file import FileAdapter
from shared_logger.adapters.shared_file import SharedFileAdapter
from shared_logger.config import LoggingConfig
from shared_logger.exceptions import (
    ConfigurationError,
    DestinationError,
    LoggerClosedError,
    LoggingError,
)
from shared_logger.logger import Logger
from shared_logger.registry import register_adapter

__all__ = [
    "ConfigurationError",
    "ConsoleAdapter",
    "DestinationError",
    "FileAdapter",
    "Logger",
    "LoggerClosedError",
    "LoggingAdapter",
    "LoggingConfig",
    "LoggingError",
    "SharedFileAdapter",
    "register_adapter",
]

__version__ = "0.1.0"
