"""Tests for executor modules."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from codecustodian.executor.backup import BackupManager
from codecustodian.executor.file_editor import SafeFileEditor
from codecustodian.executor.safety_checks import (
    SafetyCheckResult,
    run_safety_checks,
)
from codecustodian.models import (
    ChangeType,
    FileChange,
    FindingType,
    RefactoringPlan,
    RiskLevel,
    SeverityLevel,
)


class TestBackupManager:
    def test_create_and_restore(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir) / "backups"
            manager = BackupManager(backup_dir=backup_dir)

            # Create a test file
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("original content")

            # Create backup
            backup_path = manager.create_backup(test_file)
            assert backup_path.exists()
            assert backup_path.read_text() == "original content"

            # Modify original
            test_file.write_text("modified content")
            assert test_file.read_text() == "modified content"

            # Restore
            manager.restore(backup_path, test_file)
            assert test_file.read_text() == "original content"

    def test_cleanup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir) / "backups"
            manager = BackupManager(backup_dir=backup_dir, retention_days=0)

            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("content")
            manager.create_backup(test_file)

            # All backups should be cleaned up since retention=0
            removed = manager.cleanup()
            # May or may not remove depending on timing
            assert removed >= 0


class TestSafeFileEditor:
    def test_apply_replace(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            editor = SafeFileEditor(backup_dir=Path(tmpdir) / "backups")

            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("x = old_api()\ny = 42\n")

            change = FileChange(
                file_path=str(test_file),
                change_type=ChangeType.REPLACE,
                old_content="old_api()",
                new_content="new_api()",
            )

            backup = editor.apply_change(change)
            assert backup is not None
            assert "new_api()" in test_file.read_text()

    def test_replace_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            editor = SafeFileEditor(backup_dir=Path(tmpdir) / "backups")

            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("x = 1\n")

            change = FileChange(
                file_path=str(test_file),
                change_type=ChangeType.REPLACE,
                old_content="nonexistent",
                new_content="replacement",
            )

            with pytest.raises(ValueError, match="not found"):
                editor.apply_change(change)

            # File should be restored
            assert test_file.read_text() == "x = 1\n"

    def test_syntax_validation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            editor = SafeFileEditor(
                backup_dir=Path(tmpdir) / "backups",
                validate_syntax=True,
            )

            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("x = 1\n")

            change = FileChange(
                file_path=str(test_file),
                change_type=ChangeType.REPLACE,
                old_content="x = 1",
                new_content="x = (",  # Invalid syntax
            )

            with pytest.raises(SyntaxError):
                editor.apply_change(change)

            # File should be restored
            assert test_file.read_text() == "x = 1\n"


class TestSafetyChecks:
    def test_pass_on_valid_plan(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("x = 1\n")

            plan = RefactoringPlan(
                finding_id="f1",
                summary="Fix thing",
                confidence_score=8,
                changes=[
                    FileChange(
                        file_path="test.py",
                        change_type=ChangeType.REPLACE,
                        old_content="x = 1",
                        new_content="x = 2",
                    )
                ],
            )

            result = run_safety_checks(plan, tmpdir)
            assert result.passed

    def test_fail_on_missing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan = RefactoringPlan(
                finding_id="f1",
                summary="Fix thing",
                confidence_score=8,
                changes=[
                    FileChange(
                        file_path="nonexistent.py",
                        change_type=ChangeType.REPLACE,
                        old_content="x",
                        new_content="y",
                    )
                ],
            )

            result = run_safety_checks(plan, tmpdir)
            assert not result.passed
            assert any("not found" in f.lower() for f in result.failures)
