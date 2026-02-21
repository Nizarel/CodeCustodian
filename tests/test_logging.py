"""Tests for structured logging and secret masking."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from codecustodian.logging import _JsonFormatter, _mask_secrets, get_logger, setup_logging


def test_mask_secrets_redacts_common_patterns() -> None:
    text = (
        "token=abc123 "
        "Bearer my.jwt.token "
        "ghp_1234567890abcdefghijklmnopqrstuvwxyz "
        "InstrumentationKey=abcd-1234"
    )
    masked = _mask_secrets(text)

    assert "***REDACTED***" in masked
    assert "ghp_1234567890abcdefghijklmnopqrstuvwxyz" not in masked
    assert "my.jwt.token" not in masked
    assert "abcd-1234" not in masked


def test_json_formatter_emits_json_with_context() -> None:
    formatter = _JsonFormatter()
    record = logging.LogRecord(
        name="codecustodian.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="authorization=secret-token",
        args=(),
        exc_info=None,
    )
    record.finding_id = "f-1"
    record.stage = "scan"

    payload = formatter.format(record)
    data = json.loads(payload)

    assert data["logger"] == "codecustodian.test"
    assert data["finding_id"] == "f-1"
    assert data["stage"] == "scan"
    assert "***REDACTED***" in data["msg"]


def test_setup_logging_with_file_output(tmp_path: Path) -> None:
    log_file = tmp_path / "codecustodian.log"
    setup_logging(level="INFO", json_output=True, log_file=str(log_file))

    logger = get_logger("tests")
    logger.info("password=secret123")

    content = log_file.read_text(encoding="utf-8")
    assert "***REDACTED***" in content


def test_get_logger_namespace() -> None:
    logger = get_logger("scanner")
    assert logger.name == "codecustodian.scanner"
