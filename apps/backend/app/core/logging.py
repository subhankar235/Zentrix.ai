"""
Structured logging configuration, correlation tracing, and logger factory.
Reference: ARCHITECTURE.md §4, §15 & BACKEND_STEPS.md Step 4, Step 31
"""

import contextvars
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.config import get_settings

# ContextVar storing active request/agent/experiment correlation attributes
_correlation_context: contextvars.ContextVar[Dict[str, Any]] = contextvars.ContextVar(
    "zentrix_correlation_context", default={}
)


def set_correlation_context(**kwargs: Any) -> None:
    """Set or update the active correlation context for the current async task."""
    current = dict(_correlation_context.get())
    for k, v in kwargs.items():
        if v is not None:
            current[k] = str(v) if not isinstance(v, (int, float, bool, dict, list)) else v
        elif k in current:
            del current[k]
    _correlation_context.set(current)


def get_correlation_context() -> Dict[str, Any]:
    """Retrieve the active correlation context dictionary."""
    return dict(_correlation_context.get())


def clear_correlation_context() -> None:
    """Clear all correlation context for the current async task."""
    _correlation_context.set({})


import re

# Sensitive credential redaction patterns
_PASSWORD_DSN_REGEX = re.compile(
    r"(postgres(?:ql)?://[^:]+:)(?:.+?)(@[^/:\s]+(?::\d+)?(?:/[^\s]*)?)",
    re.IGNORECASE,
)
_BEARER_TOKEN_REGEX = re.compile(
    r"(Bearer\s+)[A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+\.?[A-Za-z0-9\-_.+/=]*",
    re.IGNORECASE,
)


def mask_sensitive_data(text: Any) -> Any:
    """Mask credentials, passwords, and tokens in string records."""
    if not isinstance(text, str):
        return text
    masked = re.sub(
        r"(postgres(?:ql)?://[^:\s]+:)(.+?)(@[A-Za-z0-9_.-]+(?::\d+)?/[^\s]*)",
        r"\1***\3",
        text,
        flags=re.IGNORECASE,
    )
    masked = _BEARER_TOKEN_REGEX.sub(r"\1***", masked)
    return masked


class StructuredJSONFormatter(logging.Formatter):
    """
    JSON formatter emitting machine-readable structured log records
    containing timestamp, log level, module, message, and contextual IDs
    (e.g., request_id, agent_id, experiment_id, connection_id).
    """

    def format(self, record: logging.LogRecord) -> str:
        ctx = get_correlation_context()
        raw_msg = record.getMessage()
        masked_msg = mask_sensitive_data(raw_msg)

        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "message": masked_msg,
        }

        # Merge ContextVar correlation attributes
        for field, val in ctx.items():
            log_entry[field] = val

        # Include standard contextual tracing fields if present in extra
        for field in ("request_id", "agent_id", "experiment_id", "connection_id", "user_id", "trace_id", "action"):
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
        ctx = get_correlation_context()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        context_parts = []

        # Merge ContextVar and record extras
        merged_context = dict(ctx)
        for field in ("request_id", "agent_id", "experiment_id", "connection_id", "action"):
            val = getattr(record, field, None)
            if val is not None:
                merged_context[field] = val

        for field, val in merged_context.items():
            context_parts.append(f"{field}={val}")

        context_str = f" [{', '.join(context_parts)}]" if context_parts else ""
        masked_msg = mask_sensitive_data(record.getMessage())
        msg = f"{timestamp} | {record.levelname:<8} | {record.name}:{record.lineno} | {masked_msg}{context_str}"

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


def log_agent_execution(
    agent_name: str,
    action: str,
    evidence: Optional[Dict[str, Any]] = None,
    confidence: Optional[float] = None,
    connection_id: Optional[str] = None,
    experiment_id: Optional[str] = None,
) -> None:
    """Structured logging helper for multi-agent graph execution per PRD.md §15."""
    logger = get_logger(f"agent.{agent_name}")
    extra: Dict[str, Any] = {
        "agent_id": agent_name,
        "action": action,
    }
    if connection_id:
        extra["connection_id"] = connection_id
    if experiment_id:
        extra["experiment_id"] = experiment_id
    if confidence is not None:
        extra["confidence"] = confidence

    details_str = f" [evidence_keys={list(evidence.keys())}]" if evidence else ""
    conf_str = f" [confidence={confidence:.2f}]" if confidence is not None else ""
    logger.info(f"Agent '{agent_name}' executed '{action}'{details_str}{conf_str}", extra=extra)


# Alias for backward and forward compatibility
setup_logging = setup_root_logger


