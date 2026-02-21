"""Additional executor tests to raise critical-path coverage."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from git import GitCommandError, InvalidGitRepositoryError, Repo

from codecustodian.exceptions import ExecutorError
from codecustodian.executor.backup import BackupManager
from codecustodian.executor.git_manager import GitManager
from codecustodian.executor.safety_checks import SafetyCheckRunner
from codecustodian.models import ChangeType, FileChange, Finding, FindingType, RefactoringPlan, SeverityLevel


def _run(coro):
    return asyncio.run(coro)


def _make_finding(**overrides: Any) -> Finding:
    defaults: dict[str, Any] = dict(
        type=FindingType.DEPRECATED_API,
        severity=SeverityLevel.HIGH,
        file="src/example.py",
        line=10,
        description="Deprecated API usage",
    )
    defaults.update(overrides)
    return Finding(**defaults)


def _make_plan(**overrides: Any) -> RefactoringPlan:
    defaults: dict[str, Any] = dict(
        finding_id="f1",
        summary="Fix thing",
        confidence_score=8,
        changes=[
            FileChange(
                file_path="src/example.py",
                change_type=ChangeType.REPLACE,
                old_content="x = 1",
                new_content="x = 2",
            )
        ],
    )
    defaults.update(overrides)
    return RefactoringPlan(**defaults)


class TestGitManagerAdditional:
    def test_invalid_repo_raises_executor_error(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "codecustodian.executor.git_manager.Repo",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(InvalidGitRepositoryError("bad repo")),
        )
        with pytest.raises(ExecutorError):
            GitManager("/not-a-repo")

    def test_is_clean_property(self, tmp_path: Path) -> None:
        Repo.init(tmp_path)
        gm = GitManager(tmp_path)
        gm.repo = MagicMock()
        gm.repo.is_dirty.return_value = False
        assert gm.is_clean is True
        gm.repo.is_dirty.return_value = True
        assert gm.is_clean is False

    def test_pull_latest_swallow_git_error(self, tmp_path: Path) -> None:
        Repo.init(tmp_path)
        gm = GitManager(tmp_path)
        gm.repo = MagicMock()
        gm.repo.active_branch = "main"
        gm.repo.git.pull.side_effect = GitCommandError("pull", 1)
        gm.pull_latest()

    def test_get_file_sha_returns_none_on_git_error(self, tmp_path: Path) -> None:
        Repo.init(tmp_path)
        gm = GitManager(tmp_path)
        gm.repo = MagicMock()
        gm.repo.git.hash_object.side_effect = GitCommandError("hash-object", 1)
        assert gm.get_file_sha("missing.py") is None

    def test_checkout_raises_executor_error(self, tmp_path: Path) -> None:
        Repo.init(tmp_path)
        gm = GitManager(tmp_path)
        gm.repo = MagicMock()
        gm.repo.git.checkout.side_effect = GitCommandError("checkout", 1)
        with pytest.raises(ExecutorError):
            gm.checkout("missing-branch")

    def test_get_repo_name_override_and_remote_parse(self, tmp_path: Path) -> None:
        Repo.init(tmp_path)
        gm = GitManager(tmp_path)
        gm.repo = MagicMock()

        assert gm.get_repo_name(config_override="owner/repo") == "owner/repo"

        remote = MagicMock()
        remote.urls = iter(["https://github.com/acme/demo.git"])
        gm.repo.remote.return_value = remote
        assert gm.get_repo_name() == "acme/demo"

        remote.urls = iter(["git@github.com:acme/demo.git"])
        assert gm.get_repo_name() == "acme/demo"

    def test_get_repo_name_raises_when_not_resolvable(self, tmp_path: Path) -> None:
        Repo.init(tmp_path)
        gm = GitManager(tmp_path)
        gm.repo = MagicMock()
        gm.repo.remote.side_effect = ValueError("no remote")
        with pytest.raises(ExecutorError):
            gm.get_repo_name()

    def test_stash_and_stash_pop_delegate(self, tmp_path: Path) -> None:
        Repo.init(tmp_path)
        gm = GitManager(tmp_path)
        gm.repo = MagicMock()
        gm.stash()
        gm.stash_pop()
        gm.repo.git.stash.assert_any_call()
        gm.repo.git.stash.assert_any_call("pop")


class TestSafetyChecksAdditional:
    def test_syntax_check_new_file_insert_with_error(self, tmp_path: Path) -> None:
        runner = SafetyCheckRunner(tmp_path)
        plan = _make_plan(
            changes=[
                FileChange(
                    file_path="new_file.py",
                    change_type=ChangeType.INSERT,
                    old_content="",
                    new_content="def broken(:\n    pass",
                )
            ]
        )
        result = _run(runner.check_syntax(plan))
        assert result.passed is False

    def test_concurrent_changes_detects_mismatch(self, tmp_path: Path, monkeypatch) -> None:
        file_path = tmp_path / "src" / "example.py"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("x = 1\n")

        runner = SafetyCheckRunner(tmp_path)
        plan = _make_plan(
            changes=[
                FileChange(
                    file_path="src/example.py",
                    change_type=ChangeType.REPLACE,
                    old_content="x = 1",
                    new_content="x = 2",
                    metadata={"git_sha": "expected123"},
                )
            ]
        )
        monkeypatch.setattr(SafetyCheckRunner, "_get_file_git_sha", lambda self, _fp: "actual999")
        result = _run(runner.check_concurrent_changes(plan))
        assert result.passed is False

    def test_get_file_git_sha_handles_timeout(self, tmp_path: Path, monkeypatch) -> None:
        runner = SafetyCheckRunner(tmp_path)

        def _raise(*_args, **_kwargs):
            import subprocess

            raise subprocess.TimeoutExpired(cmd="git hash-object", timeout=1)

        monkeypatch.setattr("codecustodian.executor.safety_checks.subprocess.run", _raise)
        assert runner._get_file_git_sha("x.py") is None

    def test_module_available_handles_value_error(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "codecustodian.executor.safety_checks.importlib.util.find_spec",
            lambda _name: (_ for _ in ()).throw(ValueError("bad module name")),
        )
        assert SafetyCheckRunner._is_module_available("bad") is False

    def test_dangerous_functions_detect_eval(self, tmp_path: Path) -> None:
        runner = SafetyCheckRunner(tmp_path)
        plan = _make_plan(
            changes=[
                FileChange(
                    file_path="src/unsafe.py",
                    change_type=ChangeType.REPLACE,
                    old_content="",
                    new_content="def f(x):\n    return eval(x)\n",
                )
            ]
        )
        result = _run(runner.check_dangerous_functions(plan))
        assert result.passed is False


class TestBackupAdditional:
    def test_restore_all_fallback_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            manager = BackupManager(backup_dir=root / "backups")
            source = root / "example.py"
            source.write_text("original")
            backup = manager.create_backup(source)
            source.write_text("modified")

            manager.clear_session()
            restored = manager.restore_all([str(backup)], repo_path=root)
            assert restored == 1
            assert source.read_text() == "original"

    def test_clear_session_empties_backup_map(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            manager = BackupManager(backup_dir=root / "backups")
            source = root / "example.py"
            source.write_text("content")
            manager.create_backup(source)
            manager.clear_session()
            assert manager.restore_all(repo_path=root) == 0
