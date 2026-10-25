"""Initialize a file logger, write one event, and close it."""

from shared_logger import Logger, LoggingConfig


def main() -> None:
    config = LoggingConfig(
        application="campaign-analytics",
        environment="production",
        destination="file",
        destination_config={"path": "./logs/application.log"},
        minimum_level="INFO",
    )
    logger = Logger.initialize(config)
    try:
        logger.write_info("Application started", application_version="1.0.0")
        logger.flush()
    finally:
        logger.close()


if __name__ == "__main__":
    main()
