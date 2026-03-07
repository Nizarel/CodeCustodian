"""Executor edge-case tests for file editor and safety checks."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from codecustodian.executor.file_editor import SafeFileEditor
from codecustodian.executor.safety_checks import SafetyCheckRunner
from codecustodian.models import ChangeType, FileChange, RefactoringPlan


def _run(coro):
    return asyncio.run(coro)


def _make_plan(change: FileChange, confidence: int = 8) -> RefactoringPlan:
    return RefactoringPlan(
        finding_id="f1",
        summary="test",
        confidence_score=confidence,
        changes=[change],
    )


class TestFileEditorEdgeCases:
    def test_validate_path_traversal_rejected(self, tmp_path: Path) -> None:
        editor = SafeFileEditor(repo_root=tmp_path)
        change = FileChange(
            file_path="../outside.py",
            change_type=ChangeType.INSERT,
            new_content="print('x')",
        )
        with pytest.raises(ValueError, match="Path traversal"):
            editor.apply_change(change)

    def test_validate_repo_boundary_rejected(self, tmp_path: Path) -> None:
        outside = tmp_path.parent / "outside.py"
        outside.write_text("x = 1\n")
        editor = SafeFileEditor(repo_root=tmp_path)
        change = FileChange(
            file_path=str(outside),
            change_type=ChangeType.REPLACE,
            old_content="x = 1",
            new_content="x = 2",
        )
        with pytest.raises(ValueError, match="within repository root"):
            editor.apply_change(change)

    def test_validate_symlink_rejected(self, tmp_path: Path) -> None:
        target = tmp_path / "target.py"
        target.write_text("x = 1\n")
        link = tmp_path / "link.py"
        try:
            link.symlink_to(target)
        except OSError:
            pytest.skip("Symlink creation not available in this environment")

        editor = SafeFileEditor(repo_root=tmp_path)
        change = FileChange(
            file_path=str(link),
            change_type=ChangeType.REPLACE,
            old_content="x = 1",
            new_content="x = 2",
        )
        with pytest.raises(ValueError, match="Symlink"):
            editor.apply_change(change)

    def test_apply_insert_new_file(self, tmp_path: Path) -> None:
        editor = SafeFileEditor(repo_root=tmp_path)
        change = FileChange(
            file_path=str(tmp_path / "new_file.py"),
            change_type=ChangeType.INSERT,
            new_content="def f():\n    return 1\n",
        )
        backup = editor.apply_change(change)
        assert backup == (tmp_path / "new_file.py")
        assert (tmp_path / "new_file.py").exists()

    def test_apply_change_unsupported_type(self, tmp_path: Path) -> None:
        file_path = tmp_path / "test.py"
        file_path.write_text("x = 1\n")

        editor = SafeFileEditor(repo_root=tmp_path)
        fake_change = SimpleNamespace(
            file_path=str(file_path),
            change_type="unknown",
            old_content="x = 1",
            new_content="x = 2",
            start_line=None,
            end_line=None,
        )
        with pytest.raises(ValueError, match="Unsupported change type"):
            editor.apply_change(fake_change)


class TestSafetyChecksEdgeCases:
    def test_import_check_missing_import(self, tmp_path: Path, monkeypatch) -> None:
        runner = SafetyCheckRunner(tmp_path)
        change = FileChange(
            file_path="src/demo.py",
            change_type=ChangeType.REPLACE,
            old_content="",
            new_content="import definitely_missing_module\n",
        )
        plan = _make_plan(change)

        monkeypatch.setattr(
            SafetyCheckRunner, "_is_module_available", lambda *_args, **_kwargs: False
        )
        result = _run(runner.check_import_availability(plan))
        assert result.passed is False
        assert "Missing imports" in result.message

    def test_critical_path_dir_pattern_requires_high_confidence(self, tmp_path: Path) -> None:
        runner = SafetyCheckRunner(tmp_path)
        change = FileChange(
            file_path="src/api/handler.py",
            change_type=ChangeType.REPLACE,
            old_content="x = 1",
            new_content="x = 2",
        )
        plan = _make_plan(change, confidence=7)

        result = _run(runner.check_critical_path(plan))
        assert result.passed is False

    def test_get_file_git_sha_success(self, tmp_path: Path, monkeypatch) -> None:
        runner = SafetyCheckRunner(tmp_path)

        class _Result:
            returncode = 0
            stdout = "abc123\n"

        monkeypatch.setattr(
            "codecustodian.executor.safety_checks.subprocess.run",
            lambda *_args, **_kwargs: _Result(),
        )
        assert runner._get_file_git_sha("x.py") == "abc123"

    def test_check_secrets_detects_token(self, tmp_path: Path) -> None:
        runner = SafetyCheckRunner(tmp_path)
        change = FileChange(
            file_path="src/secrets.py",
            change_type=ChangeType.REPLACE,
            old_content="",
            new_content='api_key = "AAAAAAAAAAAAAAAAAAAAAAAA"\n',
        )
        plan = _make_plan(change)
        result = _run(runner.check_secrets(plan))
        assert result.passed is False

    def test_check_dangerous_functions_clean_code_passes(self, tmp_path: Path) -> None:
        runner = SafetyCheckRunner(tmp_path)
        change = FileChange(
            file_path="src/safe.py",
            change_type=ChangeType.REPLACE,
            old_content="",
            new_content="def square(x):\n    return x * x\n",
        )
        plan = _make_plan(change)
        result = _run(runner.check_dangerous_functions(plan))
        assert result.passed is True
