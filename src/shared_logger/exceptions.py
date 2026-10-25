"""Errors raised by the logging library."""


class LoggingError(Exception):
    """Base class for errors callers can handle."""


class ConfigurationError(LoggingError):
    """The configuration is missing or invalid.

    Raised while building :class:`~shared_logger.LoggingConfig` or during
    :meth:`~shared_logger.Logger.initialize`. The message names the field and
    the value the library expected.
    """


class LoggerClosedError(LoggingError):
    """A logging method was called after :meth:`~shared_logger.Logger.close`."""


class DestinationError(LoggingError):
    """A destination failed while writing, flushing, or closing.

    When ``raise_destination_errors`` is true, write and flush failures are
    raised as this error. Adapters also raise it when used before
    initialization or after they have been closed.
    """
