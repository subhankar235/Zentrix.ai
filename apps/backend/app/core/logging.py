"""
Structured logging configuration and logger factory.
Reference: ARCHITECTURE.md §4 & BACKEND_STEPS.md Step 4
"""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from app.core.config import get_settings


class StructuredJSONFormatter(logging.Formatter):
    """
    JSON formatter emitting machine-readable structured log records
    containing timestamp, log level, module, message, and contextual IDs
    (e.g., request_id, agent_id, experiment_id, connection_id).
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }

        # Include standard contextual tracing fields if present in extra
        for field in ("request_id", "agent_id", "experiment_id", "connection_id", "user_id"):
            val = getattr(record, field, None)
            if val is not None:
                log_entry[field] = val

        # Include any custom extra dictionary data
        if hasattr(record, "extra_data") and isinstance(record.extra_data, dict):
            log_entry["data"] = record.extra_data

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


class DevelopmentFormatter(logging.Formatter):
    """
    Human-readable structured formatter for local development.
    """

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        context_parts = []
        for field in ("request_id", "agent_id", "experiment_id", "connection_id"):
            val = getattr(record, field, None)
            if val is not None:
                context_parts.append(f"{field}={val}")

        context_str = f" [{', '.join(context_parts)}]" if context_parts else ""
        msg = f"{timestamp} | {record.levelname:<8} | {record.name}:{record.lineno} | {record.getMessage()}{context_str}"

        if record.exc_info:
            msg += f"\n{self.formatException(record.exc_info)}"
        return msg


def setup_root_logger(
    environment: Optional[str] = None,
    log_level: Optional[int | str] = None,
) -> None:
    """
    Configure the root logger with the appropriate formatter and log level
    based on application settings.
    """
    settings = get_settings()
    env = (environment or settings.ENVIRONMENT).lower()

    if log_level is None:
        level = logging.DEBUG if env in ("development", "test", "dev") else logging.INFO
    elif isinstance(log_level, str):
        level = getattr(logging, log_level.upper(), logging.INFO)
    else:
        level = log_level

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Avoid adding duplicate handlers if setup is called multiple times
    if not any(getattr(h, "_zentrix_handler", False) for h in root_logger.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler._zentrix_handler = True  # type: ignore

        if env in ("production", "prod"):
            handler.setFormatter(StructuredJSONFormatter())
        else:
            handler.setFormatter(DevelopmentFormatter())

        root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """
    Factory function returning a configured structured logger.

    Usage:
        logger = get_logger(__name__)
        logger.info("Database connection established", extra={"connection_id": "conn_123"})
    """
    setup_root_logger()
    return logging.getLogger(name)


# Alias for backward and forward compatibility
setup_logging = setup_root_logger

