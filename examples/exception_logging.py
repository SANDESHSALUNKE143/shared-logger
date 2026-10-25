"""Record an exception type, message, and traceback."""

from shared_logger import Logger, LoggingConfig


def main() -> None:
    config = LoggingConfig(
        application="campaign-analytics",
        environment="production",
        destination="file",
        destination_config={"path": "./logs/exceptions.jsonl"},
        minimum_level="INFO",
    )
    logger = Logger.initialize(config)
    try:
        try:
            raise ValueError("The record could not be parsed")
        except ValueError as exc:
            logger.write_exception(
                "An unexpected exception occurred",
                exception=exc,
                request_id="req-123",
            )
    finally:
        logger.close()


if __name__ == "__main__":
    main()
