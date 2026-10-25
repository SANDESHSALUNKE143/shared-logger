"""End-to-end destination behavior through the public logger."""

from tests.support import read_jsonl

from shared_logger import Logger, LoggingConfig


def test_console_logger_splits_stdout_and_stderr(capsys):
    logger = Logger.initialize(
        LoggingConfig(
            application="campaign-analytics",
            environment="production",
            destination="console",
            destination_config={},
            minimum_level="DEBUG",
            service_version="1.0.0",
        )
    )
    logger.write_debug("Debug information", user_id=123)
    logger.write_info("Application started", application_version="1.0.0")
    logger.write_warning("Resource usage approaching threshold", usage_percentage=85)
    logger.write_error("Unable to process request", request_id="req-123")
    logger.write_critical("Critical system failure", component="data_processor")
    logger.close()
    captured = capsys.readouterr()
    stdout = [line for line in captured.out.splitlines() if line.strip()]
    stderr = [line for line in captured.err.splitlines() if line.strip()]
    assert len(stdout) == 3
    assert len(stderr) == 2
    assert "Application started" in captured.out
    assert "Unable to process request" in captured.err
    assert "user_id" in captured.out


def test_configured_identity_is_on_every_event(tmp_path):
    path = tmp_path / "identity.log"
    logger = Logger.initialize(
        LoggingConfig(
            application="campaign-analytics",
            environment="production",
            destination="file",
            destination_config={"path": str(path)},
            service_version="1.0.0",
            component="campaign_processor",
            cluster="india",
            region="ap-south-1",
            static_metadata={"team": "analytics"},
        )
    )
    logger.write_info("Data processing started", campaign_id="CMP-1001", records_processed=500)
    logger.close()
    event = read_jsonl(path)[0]
    assert event["schema_version"] == 1
    assert event["application"] == "campaign-analytics"
    assert event["environment"] == "production"
    assert event["service_version"] == "1.0.0"
    assert event["component"] == "campaign_processor"
    assert event["cluster"] == "india"
    assert event["region"] == "ap-south-1"
    assert event["metadata"]["team"] == "analytics"
    assert event["metadata"]["campaign_id"] == "CMP-1001"
    assert event["metadata"]["records_processed"] == 500
