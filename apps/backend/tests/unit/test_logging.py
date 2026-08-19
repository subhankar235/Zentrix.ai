"""
Unit tests for structured logging.
Step 4 verification: logger factory, formatters, and contextual fields.
"""

import json
import logging
from app.core.logging import (
    get_logger,
    StructuredJSONFormatter,
    DevelopmentFormatter,
)


def test_get_logger_returns_logger():
    """Verify get_logger returns a properly configured logging.Logger."""
    logger = get_logger("test_module")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test_module"


def test_json_formatter_produces_valid_json_with_context():
    """Verify StructuredJSONFormatter produces valid JSON with extra context."""
    formatter = StructuredJSONFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=42,
        msg="Test structured log message",
        args=(),
        exc_info=None,
    )
    record.request_id = "req-12345"
    record.agent_id = "agent-planner"
    record.experiment_id = "exp-789"
    record.connection_id = "conn-001"

    formatted = formatter.format(record)
    parsed = json.loads(formatted)

    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "test_logger"
    assert parsed["message"] == "Test structured log message"
    assert parsed["request_id"] == "req-12345"
    assert parsed["agent_id"] == "agent-planner"
    assert parsed["experiment_id"] == "exp-789"
    assert parsed["connection_id"] == "conn-001"
    assert "timestamp" in parsed


def test_development_formatter():
    """Verify DevelopmentFormatter includes level and contextual attributes."""
    formatter = DevelopmentFormatter()
    record = logging.LogRecord(
        name="dev_logger",
        level=logging.WARNING,
        pathname=__file__,
        lineno=100,
        msg="Resource alert",
        args=(),
        exc_info=None,
    )
    record.connection_id = "conn-002"
    formatted = formatter.format(record)

    assert "WARNING" in formatted
    assert "Resource alert" in formatted
    assert "connection_id=conn-002" in formatted


def test_no_duplicate_zentrix_handlers():
    """Verify repeated get_logger calls do not duplicate zentrix stream handlers."""
    get_logger("dup_test_1")
    get_logger("dup_test_2")
    zentrix_handlers = [
        h for h in logging.getLogger().handlers if getattr(h, "_zentrix_handler", False)
    ]
    assert len(zentrix_handlers) == 1
