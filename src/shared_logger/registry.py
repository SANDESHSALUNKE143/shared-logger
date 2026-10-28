"""Maps destination names to adapter classes.

Applications register a custom adapter with :func:`register_adapter` before
:meth:`~shared_logger.Logger.initialize`. Built-in names are registered when
the package is imported.
"""

from shared_logger.adapters.base import LoggingAdapter
from shared_logger.exceptions import ConfigurationError

_ADAPTERS: dict[str, type[LoggingAdapter]] = {}


def register_adapter(name: str, adapter_class: type[LoggingAdapter]) -> None:
    """Register ``adapter_class`` under ``name``.

    A second registration of the same name raises :class:`ConfigurationError`.
    ``adapter_class`` must be a :class:`LoggingAdapter` subclass.
    """
    if not isinstance(name, str) or not name.strip():
        raise ConfigurationError("Adapter name must be a non-empty string.")
    if not isinstance(adapter_class, type) or not issubclass(adapter_class, LoggingAdapter):
        raise ConfigurationError("adapter_class must be a subclass of LoggingAdapter.")
    if name in _ADAPTERS:
        raise ConfigurationError(
            f"Adapter {name!r} is already registered. Choose a different destination name."
        )
    _ADAPTERS[name] = adapter_class


def get_adapter(name: str) -> type[LoggingAdapter]:
    """Return the class registered as ``name``."""
    try:
        return _ADAPTERS[name]
    except KeyError:
        known = ", ".join(sorted(_ADAPTERS)) or "(none)"
        raise ConfigurationError(
            f"Unknown destination {name!r}. Registered destinations: {known}. "
            "This release implements azure_queue, console, file, and shared_file. "
            "Unimplemented destinations are rejected during initialization."
        ) from None


def registered_names() -> tuple[str, ...]:
    """Return the destination names currently registered."""
    return tuple(sorted(_ADAPTERS))
