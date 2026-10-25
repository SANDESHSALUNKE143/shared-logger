"""Write JSON Lines to a path on a mounted filesystem.

The shared file adapter uses the same writer as the local file adapter.
It does not lock other processes or guarantee durability across a network mount.
"""

from shared_logger import Logger, LoggingConfig


def main() -> None:
    config = LoggingConfig(
        application="data-processing",
        environment="development",
        destination="shared_file",
        destination_config={
            "path": "./logs/shared/application.jsonl",
            "rotation": "10 MB",
            "retention": "7 days",
        },
        minimum_level="INFO",
    )
    logger = Logger.initialize(config)
    try:
        logger.write_info("Shared file event", records_processed=500)
        logger.flush()
    finally:
        logger.close()


if __name__ == "__main__":
    main()
