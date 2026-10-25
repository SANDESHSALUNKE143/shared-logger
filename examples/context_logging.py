"""Add correlation data with bind without changing the original logger."""

from shared_logger import Logger, LoggingConfig


def main() -> None:
    config = LoggingConfig(
        application="campaign-analytics",
        environment="production",
        destination="file",
        destination_config={"path": "./logs/context.jsonl"},
        minimum_level="INFO",
        static_metadata={"team": "analytics"},
    )
    logger = Logger.initialize(config)
    try:
        request_logger = logger.bind(correlation_id="req-123", tenant_id="tenant-456")
        request_logger.write_info("Request processing started")
        request_logger.write_info("Request processing completed", records_processed=500)
        logger.write_info("Background task started")
    finally:
        logger.close()


if __name__ == "__main__":
    main()
