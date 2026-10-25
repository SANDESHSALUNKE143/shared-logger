"""Level filtering.

The logger checks the minimum level before it builds, redacts, or serializes
an event, and before it calls the destination.
"""

from shared_logger.levels import LEVEL_ORDER


def passes_minimum(level: str, minimum_level: str) -> bool:
    """Return whether ``level`` is at least ``minimum_level``.

    Both arguments must already be canonical level names.
    """
    return LEVEL_ORDER[level] >= LEVEL_ORDER[minimum_level]
