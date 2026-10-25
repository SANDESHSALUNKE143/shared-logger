"""Append JSON Lines to a local file with size rotation and retention."""

from shared_logger import Logger, LoggingConfig


def main() -> None:
    config = LoggingConfig(
        application="data-processing",
        environment="development",
        destination="file",
        destination_config={
            "path": "./logs/data-processing.jsonl",
            "rotation": "10 MB",
            "retention": "7 days",
        },
        minimum_level="DEBUG",
        static_metadata={"team": "analytics"},
    )
    logger = Logger.initialize(config)
    try:
        logger.write_debug("Debug information", user_id=123)
        logger.write_info("Data processing started", records_processed=500)
        logger.write_warning("Resource usage approaching threshold", usage_percentage=85)
        logger.flush()
    finally:
        logger.close()


if __name__ == "__main__":
    main()
