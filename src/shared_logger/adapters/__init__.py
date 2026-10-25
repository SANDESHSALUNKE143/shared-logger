"""Built-in destinations.

Importing this module registers the adapters. It does not open files or
attach handlers.
"""

from shared_logger.adapters.console import ConsoleAdapter
from shared_logger.adapters.file import FileAdapter
from shared_logger.adapters.shared_file import SharedFileAdapter
from shared_logger.registry import register_adapter

register_adapter("console", ConsoleAdapter)
register_adapter("file", FileAdapter)
register_adapter("shared_file", SharedFileAdapter)

__all__ = ["ConsoleAdapter", "FileAdapter", "SharedFileAdapter"]
