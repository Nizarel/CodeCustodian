"""Phase 9 security, RAI, and observability implementation tests."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from codecustodian.enterprise.audit import AuditEntry, AuditLogger
from codecustodian.executor.file_editor import SafeFileEditor
from codecustodian.executor.safety_checks import SafetyCheckRunner
from codecustodian.logging import _JsonFormatter
from codecustodian.models import ChangeType, FileChange, RefactoringPlan


def test_json_formatter_masks_tokens() -> None:
    formatter = _JsonFormatter()
    record = {
        "name": "codecustodian.test",
        "level": 20,
        "pathname": __file__,
        "lineno": 1,
        "msg": "token=ghp_abcdefghijklmnopqrstuvwxyz123456 and Authorization: Bearer sk-abcdefghijklmnopqrstuvwxyz123456",
        "args": (),
        "exc_info": None,
    }
    log_record = logging.makeLogRecord(record)

    output = formatter.format(log_record)
    payload = json.loads(output)

    assert "ghp_" not in payload["msg"]
    assert "sk-" not in payload["msg"]
    assert "***REDACTED***" in payload["msg"]


def test_file_editor_blocks_path_traversal(tmp_path: Path) -> None:
    editor = SafeFileEditor(repo_root=tmp_path)

    change = FileChange(
        file_path="../outside.py",
        change_type=ChangeType.INSERT,
        new_content="print('blocked')",
    )

    with pytest.raises(ValueError, match="Path traversal"):
        editor.apply_change(change)


def test_file_editor_blocks_paths_outside_repo_root(tmp_path: Path) -> None:
    editor = SafeFileEditor(repo_root=tmp_path)
    outside_file = tmp_path.parent / "outside-security-test.py"

    change = FileChange(
        file_path=str(outside_file),
        change_type=ChangeType.INSERT,
        new_content="print('blocked')",
    )

    with pytest.raises(ValueError, match="within repository root"):
        editor.apply_change(change)


@pytest.mark.asyncio
async def test_dangerous_function_check_blocks_eval(tmp_path: Path) -> None:
    runner = SafetyCheckRunner(repo_path=tmp_path)
    plan = RefactoringPlan(
        finding_id="finding-1",
        summary="test dangerous function detection",
        confidence_score=9,
        changes=[
            FileChange(
                file_path="src/example.py",
                change_type=ChangeType.REPLACE,
                old_content="x = 1",
                new_content="value = eval('1 + 1')",
            )
        ],
    )

    check = await runner.check_dangerous_functions(plan)

    assert not check.passed
    assert check.name == "dangerous_functions"
    assert "eval" in check.message


@pytest.mark.asyncio
async def test_run_all_checks_fails_on_dangerous_function(tmp_path: Path) -> None:
    runner = SafetyCheckRunner(repo_path=tmp_path)
    plan = RefactoringPlan(
        finding_id="finding-2",
        summary="test all checks",
        confidence_score=9,
        changes=[
            FileChange(
                file_path="src/example.py",
                change_type=ChangeType.REPLACE,
                old_content="x = 1",
                new_content="result = compile('1+1', '<x>', 'eval')",
            )
        ],
    )

    result = await runner.run_all_checks(plan)

    assert not result.passed
    assert any(check.name == "dangerous_functions" and check.failed for check in result.checks)


def test_audit_entry_generates_sha256_hash() -> None:
    entry = AuditEntry(action="apply_change", file_path="src/app.py")

    assert len(entry.entry_hash) == 64
    assert entry.entry_hash == entry.compute_hash()


def test_audit_logger_writes_extended_fields(tmp_path: Path) -> None:
    emitted: list[dict[str, object]] = []

    logger = AuditLogger(log_dir=tmp_path, monitor_sink=emitted.append)
    logger.log(
        "apply_change",
        target="src/app.py",
        event_type="refactor_applied",
        finding_id="f-123",
        file_path="src/app.py",
        lines_added=8,
        lines_removed=3,
        tests_passed=True,
        linting_passed=True,
        security_passed=True,
        ai_reasoning="Replace deprecated API",
        confidence_score=8.5,
        pr_number=101,
        approver="engineer-a",
        merge_date="2026-02-15",
    )

    entries = logger.query(limit=1)

    assert len(entries) == 1
    entry = entries[0]
    assert entry.event_type == "refactor_applied"
    assert entry.finding_id == "f-123"
    assert entry.changes["lines_added"] == 8
    assert entry.verification["tests_passed"] is True
    assert entry.pr_number == 101
    assert len(entry.entry_hash) == 64

    assert len(emitted) == 1
    assert emitted[0]["entry_hash"] == entry.entry_hash
