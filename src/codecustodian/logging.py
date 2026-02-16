"""Structured logging for CodeCustodian.

Provides JSON-formatted structured logs with Rich console output and
context injection (finding_id, pipeline stage, file paths).
"""

from __future__ import annotations

import logging
import re
import sys
from typing import Any

from rich.console import Console
from rich.logging import RichHandler

_console = Console(stderr=True)

# Shared logger name
LOGGER_NAME = "codecustodian"

_SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9\-_]{20,}\b"),
    re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    re.compile(
        r"(?i)(password|passwd|secret|token|api[_-]?key|authorization)\s*"
        r"([:=])\s*([^,\s;]+)"
    ),
    re.compile(r"(?i)(Bearer\s+)([A-Za-z0-9\-._~+/]+=*)"),
    re.compile(
        r"(?i)(InstrumentationKey|AccountKey|SharedAccessKey|Sig)="
        r"([^;\s]+)"
    ),
]


def _mask_secrets(text: str) -> str:
    """Redact common token and secret patterns from log text."""
    masked = text
    for pattern in _SECRET_PATTERNS:
        if "Bearer" in pattern.pattern:
            masked = pattern.sub(r"\1***REDACTED***", masked)
        elif "password|passwd|secret|token|api" in pattern.pattern:
            masked = pattern.sub(r"\1\2***REDACTED***", masked)
        elif "InstrumentationKey" in pattern.pattern:
            masked = pattern.sub(r"\1=***REDACTED***", masked)
        else:
            masked = pattern.sub("***REDACTED***", masked)
    return masked


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a child logger under the ``codecustodian`` namespace.

    Example::

        logger = get_logger("scanner.deprecated_api")
        logger.info("Found %d deprecated calls", 5)
    """
    full_name = f"{LOGGER_NAME}.{name}" if name else LOGGER_NAME
    return logging.getLogger(full_name)


def setup_logging(
    *,
    level: str = "INFO",
    json_output: bool = False,
    log_file: str | None = None,
) -> None:
    """Configure the root ``codecustodian`` logger.

    Parameters
    ----------
    level:
        Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    json_output:
        If ``True``, emit JSON lines instead of Rich formatting.
    log_file:
        Optional path to a log file for persistent output.
    """
    root = logging.getLogger(LOGGER_NAME)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers.clear()

    if json_output:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(_JsonFormatter())
    else:
        handler = RichHandler(
            console=_console,
            show_path=False,
            rich_tracebacks=True,
            tracebacks_show_locals=False,
        )

    root.addHandler(handler)

    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(_JsonFormatter())
        root.addHandler(fh)


class _JsonFormatter(logging.Formatter):
    """Minimal JSON-lines formatter."""

    def format(self, record: logging.LogRecord) -> str:
        import json

        message = _mask_secrets(record.getMessage())
        entry: dict[str, Any] = {
            "ts": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "msg": message,
        }
        if record.exc_info and record.exc_info[1]:
            entry["exception"] = _mask_secrets(str(record.exc_info[1]))
        # Merge extra context injected via `logger.info("…", extra={…})`
        for key in ("finding_id", "stage", "file_path", "duration"):
            val = getattr(record, key, None)
            if val is not None:
                entry[key] = val
        return json.dumps(entry)
