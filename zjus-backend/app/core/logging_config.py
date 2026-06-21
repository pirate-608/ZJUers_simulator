"""Structured logging configuration.

Copyright (c) 2026 pirate-608. Licensed under the MIT License.

Notes:
    Development uses a readable console format, while production emits JSON
    suitable for ELK, Loki, or similar collectors.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Optional


class JSONFormatter(logging.Formatter):
    """Production JSON log formatter."""

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as structured JSON."""
        log_entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key in ("user_id", "action", "duration_ms"):
            if key in record.__dict__:
                log_entry[key] = record.__dict__[key]

        if record.exc_info and record.exc_info[1]:
            exc_type = record.exc_info[0]
            log_entry["exception"] = {
                "type": exc_type.__name__ if exc_type else "Exception",
                "message": str(record.exc_info[1]),
            }
            if record.exc_text:
                log_entry["exception"]["traceback"] = record.exc_text
            else:
                log_entry["exception"]["traceback"] = self.formatException(
                    record.exc_info
                )

        if record.levelno >= logging.WARNING:
            log_entry["source"] = {
                "file": record.pathname,
                "line": record.lineno,
                "function": record.funcName,
            }

        return json.dumps(log_entry, ensure_ascii=False, default=str)


class DevFormatter(logging.Formatter):
    """Readable colorized log formatter for development."""

    COLORS = {
        "DEBUG": "\033[36m",     # cyan
        "INFO": "\033[32m",      # green
        "WARNING": "\033[33m",   # yellow
        "ERROR": "\033[31m",     # red
        "CRITICAL": "\033[1;31m",  # bold red
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record for local console output."""
        color = self.COLORS.get(record.levelname, self.RESET)
        timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        level = f"{color}{record.levelname:<8}{self.RESET}"
        name = f"\033[90m{record.name}\033[0m"

        msg = f"{timestamp} {level} {name} │ {record.getMessage()}"

        extras = []
        for key in ("user_id", "action", "duration_ms"):
            if hasattr(record, key):
                extras.append(f"{key}={getattr(record, key)}")
        if extras:
            msg += f"  \033[90m({', '.join(extras)})\033[0m"

        if record.exc_info and record.exc_info[1]:
            msg += f"\n{self.formatException(record.exc_info)}"

        return msg


def setup_logging(
    environment: str = "development",
    level: Optional[str] = None,
) -> None:
    """Initialize global logging once during application startup.

    Args:
        environment: Runtime environment, usually `development` or `production`.
        level: Optional explicit logging level. Defaults to DEBUG in
            development and INFO in production.
    """
    is_prod = environment.lower() in ("production", "prod")

    if level is None:
        log_level = logging.INFO if is_prod else logging.DEBUG
    else:
        log_level = getattr(logging, level.upper(), logging.INFO)

    if is_prod:
        formatter = JSONFormatter()
    else:
        formatter = DevFormatter()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Replace existing handlers to avoid duplicate records after reloads/tests.
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Keep dependency noise below application logs.
    for noisy_logger in (
        "uvicorn.access",
        "uvicorn.error",
        "httpcore",
        "httpx",
        "asyncio",
        "sqlalchemy.engine",
    ):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    # Uvicorn startup/shutdown lines should remain visible in production.
    logging.getLogger("uvicorn").setLevel(logging.INFO)

    logging.getLogger(__name__).info(
        "Logging initialized: env=%s, level=%s, format=%s",
        environment,
        logging.getLevelName(log_level),
        "JSON" if is_prod else "colored",
    )
