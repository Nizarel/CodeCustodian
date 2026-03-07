"""Tests for executor modules — Phase 4.

Covers:
- BackupManager: create, restore, restore_all, cleanup, transaction log
- SafeFileEditor: replace, insert, delete, multi-file atomic, edge cases
- SafetyCheckRunner: all 5 safety checks (syntax, imports, critical path,
  concurrent changes, secrets)
- GitManager: branch naming, commit, cleanup (mocked git)
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from codecustodian.executor.backup import BackupManager
from codecustodian.executor.file_editor import SafeFileEditor
from codecustodian.executor.safety_checks import SafetyCheckRunner
from codecustodian.models import (
    ChangeType,
    FileChange,
    Finding,
    FindingType,
    RefactoringPlan,
    SafetyCheckResult,
    SafetyResult,
    SeverityLevel,
    TransactionLogEntry,
)

# ── Helpers ────────────────────────────────────────────────────────────


def _run(coro):
    """Helper to run async code in sync tests."""
    return asyncio.run(coro)


def _make_plan(**overrides) -> RefactoringPlan:
    defaults = dict(
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
    defaults.update(overrides)
    return RefactoringPlan(**defaults)


def _make_finding(**overrides) -> Finding:
    defaults = dict(
        type=FindingType.DEPRECATED_API,
        severity=SeverityLevel.HIGH,
        file="src/example.py",
        line=10,
        description="Deprecated API usage",
    )
    defaults.update(overrides)
    return Finding(**defaults)


# ═══════════════════════════════════════════════════════════════════════
# BackupManager
# ═══════════════════════════════════════════════════════════════════════


class TestBackupManager:
    def test_create_and_restore(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir) / "backups"
            manager = BackupManager(backup_dir=backup_dir)

            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("original content")

            backup_path = manager.create_backup(test_file)
            assert backup_path.exists()
            assert backup_path.read_text() == "original content"

            test_file.write_text("modified content")
            manager.restore(backup_path, test_file)
            assert test_file.read_text() == "original content"

    def test_cleanup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir) / "backups"
            manager = BackupManager(backup_dir=backup_dir, retention_days=0)

            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("content")
            manager.create_backup(test_file)

            removed = manager.cleanup()
            assert removed >= 0

    def test_transaction_log(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir) / "backups"
            manager = BackupManager(backup_dir=backup_dir)

            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("content")

            manager.create_backup(test_file)
            log = manager.transaction_log
            assert len(log) == 1
            assert log[0].action == "backup"
            assert log[0].success is True

    def test_restore_all_from_map(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir) / "backups"
            manager = BackupManager(backup_dir=backup_dir)

            f1 = Path(tmpdir) / "a.py"
            f2 = Path(tmpdir) / "b.py"
            f1.write_text("original_a")
            f2.write_text("original_b")

            manager.create_backup(f1)
            manager.create_backup(f2)

            f1.write_text("changed_a")
            f2.write_text("changed_b")

            restored = manager.restore_all()
            assert restored == 2
            assert f1.read_text() == "original_a"
            assert f2.read_text() == "original_b"

    def test_write_transaction_log(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            backup_dir = Path(tmpdir) / "backups"
            manager = BackupManager(backup_dir=backup_dir)

            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("content")
            manager.create_backup(test_file)

            log_path = manager.write_transaction_log()
            assert log_path.exists()
            import json

            data = json.loads(log_path.read_text())
            assert len(data) == 1
            assert data[0]["action"] == "backup"

    def test_restore_missing_backup_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = BackupManager(backup_dir=Path(tmpdir) / "backups")
            with pytest.raises(FileNotFoundError):
                manager.restore(Path(tmpdir) / "nonexistent.bak", Path(tmpdir) / "target.py")


# ═══════════════════════════════════════════════════════════════════════
# SafeFileEditor
# ═══════════════════════════════════════════════════════════════════════


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
                new_content="x = (",
            )

            with pytest.raises(SyntaxError):
                editor.apply_change(change)

            assert test_file.read_text() == "x = 1\n"

    def test_apply_insert(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            editor = SafeFileEditor(backup_dir=Path(tmpdir) / "backups")

            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("x = 1\ny = 2\n")

            change = FileChange(
                file_path=str(test_file),
                change_type=ChangeType.INSERT,
                new_content="z = 3",
                start_line=2,
            )

            editor.apply_change(change)
            content = test_file.read_text()
            assert "z = 3" in content

    def test_apply_delete(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            editor = SafeFileEditor(backup_dir=Path(tmpdir) / "backups")

            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("x = 1\ny = 2\nz = 3\n")

            change = FileChange(
                file_path=str(test_file),
                change_type=ChangeType.DELETE,
                start_line=2,
                end_line=2,
            )

            editor.apply_change(change)
            content = test_file.read_text()
            assert "y = 2" not in content
            assert "x = 1" in content
            assert "z = 3" in content

    def test_multi_file_atomic_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            editor = SafeFileEditor(backup_dir=Path(tmpdir) / "backups")

            f1 = Path(tmpdir) / "a.py"
            f2 = Path(tmpdir) / "b.py"
            f1.write_text("a = 1\n")
            f2.write_text("b = 2\n")

            changes = [
                FileChange(
                    file_path=str(f1),
                    change_type=ChangeType.REPLACE,
                    old_content="a = 1",
                    new_content="a = 10",
                ),
                FileChange(
                    file_path=str(f2),
                    change_type=ChangeType.REPLACE,
                    old_content="b = 2",
                    new_content="b = 20",
                ),
            ]

            backups = editor.apply_changes(changes)
            assert len(backups) == 2
            assert "a = 10" in f1.read_text()
            assert "b = 20" in f2.read_text()

    def test_multi_file_atomic_rollback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            editor = SafeFileEditor(backup_dir=Path(tmpdir) / "backups")

            f1 = Path(tmpdir) / "a.py"
            f2 = Path(tmpdir) / "b.py"
            f1.write_text("a = 1\n")
            f2.write_text("b = 2\n")

            changes = [
                FileChange(
                    file_path=str(f1),
                    change_type=ChangeType.REPLACE,
                    old_content="a = 1",
                    new_content="a = 10",
                ),
                FileChange(
                    file_path=str(f2),
                    change_type=ChangeType.REPLACE,
                    old_content="NONEXISTENT",
                    new_content="b = 20",
                ),
            ]

            with pytest.raises(ValueError, match="not found"):
                editor.apply_changes(changes)

            # f1 should be rolled back
            assert f1.read_text() == "a = 1\n"

    def test_file_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            editor = SafeFileEditor(backup_dir=Path(tmpdir) / "backups")

            change = FileChange(
                file_path=str(Path(tmpdir) / "missing.py"),
                change_type=ChangeType.REPLACE,
                old_content="x",
                new_content="y",
            )

            with pytest.raises(FileNotFoundError):
                editor.apply_change(change)

    def test_binary_file_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            editor = SafeFileEditor(backup_dir=Path(tmpdir) / "backups")

            bin_file = Path(tmpdir) / "test.bin"
            bin_file.write_bytes(b"\x00\x01\x02\x03")

            change = FileChange(
                file_path=str(bin_file),
                change_type=ChangeType.REPLACE,
                old_content="x",
                new_content="y",
            )

            with pytest.raises(ValueError, match="Binary file"):
                editor.apply_change(change)


# ═══════════════════════════════════════════════════════════════════════
# SafetyCheckRunner
# ═══════════════════════════════════════════════════════════════════════


class TestSafetyCheckRunner:
    def test_all_checks_pass(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("x = 1\n")
            # Add extra modules so blast radius stays under 30%
            for i in range(5):
                (Path(tmpdir) / f"mod{i}.py").write_text(f"v{i} = {i}\n")

            plan = _make_plan(
                changes=[
                    FileChange(
                        file_path="test.py",
                        change_type=ChangeType.REPLACE,
                        old_content="x = 1",
                        new_content="x = 2",
                    )
                ]
            )

            runner = SafetyCheckRunner(tmpdir)
            result = _run(runner.run_all_checks(plan))

            assert result.passed
            assert len(result.checks) == 7
            assert result.action == "proceed"

    def test_syntax_check_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.py"
            test_file.write_text("x = 1\n")

            plan = _make_plan(
                changes=[
                    FileChange(
                        file_path="test.py",
                        change_type=ChangeType.REPLACE,
                        old_content="x = 1",
                        new_content="x = (",
                    )
                ]
            )

            runner = SafetyCheckRunner(tmpdir)
            result = _run(runner.check_syntax(plan))

            assert not result.passed
            assert "syntax" in result.name.lower()

    def test_import_check_fails(self):
        plan = _make_plan(
            changes=[
                FileChange(
                    file_path="test.py",
                    change_type=ChangeType.REPLACE,
                    old_content="x = 1",
                    new_content="import nonexistent_module_xyz123\nx = 1",
                )
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runner = SafetyCheckRunner(tmpdir)
            result = _run(runner.check_import_availability(plan))

            assert not result.passed
            assert "nonexistent_module_xyz123" in result.message

    def test_import_check_passes_stdlib(self):
        plan = _make_plan(
            changes=[
                FileChange(
                    file_path="test.py",
                    change_type=ChangeType.REPLACE,
                    old_content="x = 1",
                    new_content="import os\nx = 1",
                )
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runner = SafetyCheckRunner(tmpdir)
            result = _run(runner.check_import_availability(plan))

            assert result.passed

    def test_critical_path_fails_low_confidence(self):
        plan = _make_plan(
            confidence_score=7,
            changes=[
                FileChange(
                    file_path="__init__.py",
                    change_type=ChangeType.REPLACE,
                    old_content="x",
                    new_content="y",
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runner = SafetyCheckRunner(tmpdir)
            result = _run(runner.check_critical_path(plan))

            assert not result.passed
            assert "confidence" in result.message.lower()

    def test_critical_path_passes_high_confidence(self):
        plan = _make_plan(
            confidence_score=9,
            changes=[
                FileChange(
                    file_path="__init__.py",
                    change_type=ChangeType.REPLACE,
                    old_content="x",
                    new_content="y",
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runner = SafetyCheckRunner(tmpdir)
            result = _run(runner.check_critical_path(plan))

            assert result.passed

    def test_secrets_detection(self):
        plan = _make_plan(
            changes=[
                FileChange(
                    file_path="test.py",
                    change_type=ChangeType.REPLACE,
                    old_content="x = 1",
                    new_content='api_key = "AKIA1234567890ABCDEF"',
                )
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runner = SafetyCheckRunner(tmpdir)
            result = _run(runner.check_secrets(plan))

            assert not result.passed
            assert "secrets" in result.message.lower() or "secret" in result.message.lower()

    def test_secrets_passes_clean_code(self):
        plan = _make_plan(
            changes=[
                FileChange(
                    file_path="test.py",
                    change_type=ChangeType.REPLACE,
                    old_content="x = 1",
                    new_content="x = os.environ.get('API_KEY', '')",
                )
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            runner = SafetyCheckRunner(tmpdir)
            result = _run(runner.check_secrets(plan))

            assert result.passed

    def test_concurrent_changes_no_sha(self):
        """When no git SHA is stored, concurrent check passes (can't detect)."""
        plan = _make_plan()

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "test.py").write_text("x = 1\n")
            runner = SafetyCheckRunner(tmpdir)
            result = _run(runner.check_concurrent_changes(plan))

            assert result.passed


# ═══════════════════════════════════════════════════════════════════════
# GitManager (mocked)
# ═══════════════════════════════════════════════════════════════════════


class TestGitManager:
    def test_create_branch_name_format(self):
        from codecustodian.executor.git_manager import GitManager

        with patch("codecustodian.executor.git_manager.Repo") as MockRepo:  # noqa: N806
            mock_repo = MagicMock()
            mock_repo.active_branch = MagicMock()
            mock_repo.active_branch.__str__ = MagicMock(return_value="main")
            MockRepo.return_value = mock_repo

            gm = GitManager("/fake/repo")
            finding = _make_finding()
            branch = gm.create_branch(finding)

            assert branch.startswith("tech-debt/deprecated-api-")
            mock_repo.git.checkout.assert_called_once()

    def test_commit_message_format(self):
        from codecustodian.executor.git_manager import GitManager

        with patch("codecustodian.executor.git_manager.Repo") as MockRepo:  # noqa: N806
            mock_repo = MagicMock()
            mock_repo.active_branch = MagicMock()
            mock_repo.active_branch.__str__ = MagicMock(return_value="main")
            mock_repo.is_dirty.return_value = True
            mock_repo.head.commit.hexsha = "abc123def456"
            MockRepo.return_value = mock_repo

            gm = GitManager("/fake/repo")
            finding = _make_finding()
            plan = _make_plan()

            sha = gm.commit(finding, plan)
            assert sha == "abc123def456"
            mock_repo.git.add.assert_called_once_with("-A")
            mock_repo.git.commit.assert_called_once()

            # The commit call uses ("-m", commit_msg, author=...) positional args
            commit_call = mock_repo.git.commit.call_args
            commit_msg = commit_call[0][1]  # second positional arg after "-m"
            assert commit_msg.startswith("refactor:")

    def test_cleanup_returns_to_original(self):
        from codecustodian.executor.git_manager import GitManager

        with patch("codecustodian.executor.git_manager.Repo") as MockRepo:  # noqa: N806
            mock_repo = MagicMock()
            mock_repo.active_branch = MagicMock()
            mock_repo.active_branch.__str__ = MagicMock(return_value="main")
            MockRepo.return_value = mock_repo

            gm = GitManager("/fake/repo")
            finding = _make_finding()
            branch = gm.create_branch(finding)

            gm.cleanup(branch)
            # Should have checked out main, then deleted branch
            checkout_calls = mock_repo.git.checkout.call_args_list
            assert len(checkout_calls) >= 2  # create + return
            mock_repo.git.branch.assert_called_once_with("-D", branch)

    def test_push_auth_error(self):
        from git import GitCommandError

        from codecustodian.exceptions import ExecutorError
        from codecustodian.executor.git_manager import GitManager

        with patch("codecustodian.executor.git_manager.Repo") as MockRepo:  # noqa: N806
            mock_repo = MagicMock()
            MockRepo.return_value = mock_repo
            mock_repo.git.push.side_effect = GitCommandError("push", "Authentication failed")

            gm = GitManager("/fake/repo")
            with pytest.raises(ExecutorError, match="Authentication"):
                gm.push("feature-branch")


# ═══════════════════════════════════════════════════════════════════════
# Verifier components
# ═══════════════════════════════════════════════════════════════════════


class TestTestRunner:
    def test_discover_tests(self):
        from codecustodian.verifier.test_runner import TestRunner

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            tests_dir = repo / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_models.py").write_text("# test")
            (tests_dir / "test_config.py").write_text("# test")

            runner = TestRunner()
            found = runner._discover_tests([Path("models.py"), Path("other.py")], repo)
            assert any("test_models" in str(f) for f in found)

    def test_parse_junit_xml(self):
        from codecustodian.verifier.test_runner import TestRunner

        with tempfile.TemporaryDirectory() as tmpdir:
            xml_content = """<?xml version="1.0" encoding="utf-8"?>
<testsuite tests="3" errors="0" failures="1" skipped="1">
  <testcase classname="tests.test_a" name="test_pass" time="0.1"/>
  <testcase classname="tests.test_a" name="test_fail" time="0.2">
    <failure message="assert False">AssertionError</failure>
  </testcase>
  <testcase classname="tests.test_a" name="test_skip" time="0.0">
    <skipped message="reason"/>
  </testcase>
</testsuite>"""
            xml_path = Path(tmpdir) / "results.xml"
            xml_path.write_text(xml_content)

            total, passed, failed, skipped, msgs = TestRunner._parse_junit_xml(xml_path)
            assert total == 3
            assert passed == 1
            assert failed == 1
            assert skipped == 1
            assert len(msgs) == 1

    def test_parse_coverage(self):
        from codecustodian.verifier.test_runner import TestRunner

        with tempfile.TemporaryDirectory() as tmpdir:
            import json

            cov_data = {"totals": {"percent_covered": 85.5}}
            cov_path = Path(tmpdir) / "coverage.json"
            cov_path.write_text(json.dumps(cov_data))

            result = TestRunner._parse_coverage(cov_path)
            assert result == 85.5

    def test_parse_coverage_missing_file(self):
        from codecustodian.verifier.test_runner import TestRunner

        result = TestRunner._parse_coverage(Path("/nonexistent/coverage.json"))
        assert result == 0.0


class TestLinterRunner:
    def test_filter_new_violations(self):
        from codecustodian.models import LintViolation
        from codecustodian.verifier.linter import LinterRunner

        baseline = [
            LintViolation(file="a.py", line=1, code="E501", message="old", tool="ruff"),
        ]
        current = [
            LintViolation(file="a.py", line=1, code="E501", message="old", tool="ruff"),
            LintViolation(file="b.py", line=5, code="F401", message="new", tool="ruff"),
        ]

        new_only = LinterRunner.filter_new_violations(current, baseline)
        assert len(new_only) == 1
        assert new_only[0].file == "b.py"

    def test_run_all_empty_files(self):
        from codecustodian.verifier.linter import LinterRunner

        runner = LinterRunner()
        result = runner.run_all([])
        assert result == []


class TestSecurityVerifier:
    def test_generate_sarif(self):
        from codecustodian.models import SecurityIssue
        from codecustodian.verifier.security_scanner import SecurityVerifier

        issues = [
            SecurityIssue(
                file="app.py",
                line=10,
                severity="HIGH",
                description="Hardcoded password",
                test_id="B105",
                tool="bandit",
                cwe="259",
            )
        ]

        sarif = SecurityVerifier.generate_sarif(issues)
        assert sarif["version"] == "2.1.0"
        assert len(sarif["runs"]) == 1
        assert len(sarif["runs"][0]["results"]) == 1
        assert sarif["runs"][0]["results"][0]["level"] == "error"

    def test_verify_empty_files(self):
        from codecustodian.verifier.security_scanner import SecurityVerifier

        verifier = SecurityVerifier()
        result = verifier.verify([])
        assert result["passed"] is True
        assert result["total_issues"] == 0
        assert "sarif" in result


# ═══════════════════════════════════════════════════════════════════════
# Pydantic model tests
# ═══════════════════════════════════════════════════════════════════════


class TestPhase4Models:
    def test_safety_check_result(self):
        r = SafetyCheckResult(name="syntax", passed=True, message="OK")
        assert not r.failed
        assert r.name == "syntax"

    def test_safety_check_result_failed(self):
        r = SafetyCheckResult(name="secrets", passed=False, message="Found secrets")
        assert r.failed

    def test_safety_result_failures(self):
        checks = [
            SafetyCheckResult(name="syntax", passed=True, message="OK"),
            SafetyCheckResult(name="imports", passed=False, message="Missing import"),
        ]
        result = SafetyResult(passed=False, checks=checks, action="abort_or_propose")
        assert len(result.failures) == 1
        assert result.failures[0].name == "imports"

    def test_transaction_log_entry(self):
        entry = TransactionLogEntry(
            action="backup",
            file_path="test.py",
            backup_path="/backups/test.py.bak",
        )
        assert entry.success is True
        assert entry.action == "backup"

    def test_execution_result_with_new_fields(self):
        from codecustodian.models import ExecutionResult

        result = ExecutionResult(
            plan_id="p1",
            success=True,
            safety_result=SafetyResult(passed=True, checks=[]),
            transaction_log=[
                TransactionLogEntry(action="backup", file_path="a.py"),
            ],
        )
        assert result.safety_result is not None
        assert len(result.transaction_log) == 1

    def test_verification_result_with_typed_violations(self):
        from codecustodian.models import LintViolation, SecurityIssue, VerificationResult

        result = VerificationResult(
            passed=True,
            lint_violations=[
                LintViolation(file="a.py", code="E501", message="line too long", tool="ruff"),
            ],
            security_issues=[
                SecurityIssue(file="b.py", severity="LOW", description="eval", tool="bandit"),
            ],
        )
        assert len(result.lint_violations) == 1
        assert result.lint_violations[0].tool == "ruff"
        assert len(result.security_issues) == 1

    def test_file_change_metadata(self):
        change = FileChange(
            file_path="test.py",
            change_type=ChangeType.REPLACE,
            old_content="x",
            new_content="y",
            metadata={"git_sha": "abc123"},
        )
        assert change.metadata["git_sha"] == "abc123"
