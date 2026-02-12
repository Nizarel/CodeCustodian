"""Structured logging for CodeCustodian.

Provides JSON-formatted structured logs with Rich console output and
context injection (finding_id, pipeline stage, file paths).
"""

from __future__ import annotations

import logging
import sys
from typing import Any

from rich.console import Console
from rich.logging import RichHandler

_console = Console(stderr=True)

# Shared logger name
LOGGER_NAME = "codecustodian"


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

        entry: dict[str, Any] = {
            "ts": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            entry["exception"] = str(record.exc_info[1])
        # Merge extra context injected via `logger.info("…", extra={…})`
        for key in ("finding_id", "stage", "file_path", "duration"):
            val = getattr(record, key, None)
            if val is not None:
                entry[key] = val
        return json.dumps(entry)
