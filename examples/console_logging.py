"""Write JSON logs to stdout and stderr.

ERROR and CRITICAL go to stderr. Other levels go to stdout.
"""

from shared_logger import Logger, LoggingConfig


def main() -> None:
    config = LoggingConfig(
        application="campaign-analytics",
        environment="production",
        destination="console",
        destination_config={"stream": "auto"},
        minimum_level="DEBUG",
    )
    logger = Logger.initialize(config)
    try:
        logger.write_debug("Debug information", user_id=123)
        logger.write_info("Application started", application_version="1.0.0")
        logger.write_warning("Resource usage approaching threshold", usage_percentage=85)
        logger.write_error("Unable to process request", request_id="req-123")
        logger.write_critical("Critical system failure", component="data_processor")
    finally:
        logger.close()


if __name__ == "__main__":
    main()
