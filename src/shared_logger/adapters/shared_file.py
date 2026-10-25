"""Mounted shared-file destination.

:class:`SharedFileAdapter` uses the same writer as :class:`FileAdapter`. A
mounted network path is treated as a normal filesystem path. The adapter does
not take a distributed lock, elect a single writer, or guarantee that a
completed write survived a network fault. Concurrent writers in other
processes can interleave or tear lines. Permissions and availability are
whatever the mount provides.
"""

from shared_logger.adapters.file import FileAdapter


class SharedFileAdapter(FileAdapter):
    """Append JSON Lines to a path on a mounted filesystem."""

    destination_name = "shared_file"
