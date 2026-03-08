"""Unit tests for the remote repository cloner (executor.repo_cloner)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from codecustodian.exceptions import ExecutorError
from codecustodian.executor.repo_cloner import (
    cleanup_clone,
    clone_repo,
    validate_clone_url,
)

# ── validate_clone_url ────────────────────────────────────────────────────


class TestValidateCloneUrl:
    """URL validation: protocol, host allow-list, path structure."""

    def test_valid_github_url(self) -> None:
        url = "https://github.com/owner/repo"
        assert validate_clone_url(url) == url

    def test_valid_github_url_with_git_suffix(self) -> None:
        url = "https://github.com/owner/repo.git"
        assert validate_clone_url(url) == url

    def test_valid_gitlab_url(self) -> None:
        url = "https://gitlab.com/owner/project"
        assert validate_clone_url(url) == url

    def test_valid_azure_devops_url(self) -> None:
        url = "https://dev.azure.com/org/project/_git/repo"
        assert validate_clone_url(url) == url

    def test_valid_bitbucket_url(self) -> None:
        url = "https://bitbucket.org/owner/repo"
        assert validate_clone_url(url) == url

    def test_rejects_ssh_url(self) -> None:
        with pytest.raises(ExecutorError, match="Only HTTPS"):
            validate_clone_url("git@github.com:owner/repo.git")

    def test_rejects_http_url(self) -> None:
        with pytest.raises(ExecutorError, match="Only HTTPS"):
            validate_clone_url("http://github.com/owner/repo")

    def test_rejects_file_url(self) -> None:
        with pytest.raises(ExecutorError, match="Only HTTPS"):
            validate_clone_url("file:///tmp/repo")

    def test_rejects_unknown_host(self) -> None:
        with pytest.raises(ExecutorError, match="not in the allow-list"):
            validate_clone_url("https://example.com/owner/repo")

    def test_rejects_short_path(self) -> None:
        with pytest.raises(ExecutorError, match="owner/repo"):
            validate_clone_url("https://github.com/owner")


# ── clone_repo ────────────────────────────────────────────────────────────


class TestCloneRepo:
    """clone_repo delegates to GitPython and handles failures."""

    @patch("codecustodian.executor.repo_cloner.Repo")
    def test_clone_creates_tmpdir_and_calls_clone_from(self, mock_repo_cls: MagicMock) -> None:
        url = "https://github.com/owner/repo"
        path = clone_repo(url)
        try:
            mock_repo_cls.clone_from.assert_called_once()
            args, kwargs = mock_repo_cls.clone_from.call_args
            assert args[0] == url
            assert kwargs["depth"] == 1
            assert Path(args[1]).exists()
        finally:
            cleanup_clone(path)

    @patch("codecustodian.executor.repo_cloner.Repo")
    def test_clone_with_branch(self, mock_repo_cls: MagicMock) -> None:
        url = "https://github.com/owner/repo"
        path = clone_repo(url, branch="develop")
        try:
            _, kwargs = mock_repo_cls.clone_from.call_args
            assert kwargs["branch"] == "develop"
        finally:
            cleanup_clone(path)

    @patch("codecustodian.executor.repo_cloner.Repo")
    def test_clone_failure_cleans_tmpdir(self, mock_repo_cls: MagicMock) -> None:
        from git import GitCommandError

        mock_repo_cls.clone_from.side_effect = GitCommandError("clone", "fail")
        with pytest.raises(ExecutorError, match="Git clone failed"):
            clone_repo("https://github.com/owner/repo")

    @patch("codecustodian.executor.repo_cloner.Repo")
    def test_clone_with_token_injects_auth_for_github(self, mock_repo_cls: MagicMock) -> None:
        url = "https://github.com/owner/repo"
        path = clone_repo(url, token="ghp_test123")
        try:
            args, _ = mock_repo_cls.clone_from.call_args
            assert args[0] == "https://x-access-token:ghp_test123@github.com/owner/repo"
        finally:
            cleanup_clone(path)

    @patch("codecustodian.executor.repo_cloner.Repo")
    def test_clone_with_token_ignores_non_github_hosts(self, mock_repo_cls: MagicMock) -> None:
        url = "https://gitlab.com/owner/repo"
        path = clone_repo(url, token="glpat_test456")
        try:
            args, _ = mock_repo_cls.clone_from.call_args
            # Token must NOT be injected for non-github.com hosts
            assert args[0] == url
        finally:
            cleanup_clone(path)

    @patch("codecustodian.executor.repo_cloner.Repo")
    def test_clone_without_token_uses_original_url(self, mock_repo_cls: MagicMock) -> None:
        url = "https://github.com/owner/repo"
        path = clone_repo(url, token=None)
        try:
            args, _ = mock_repo_cls.clone_from.call_args
            assert args[0] == url
        finally:
            cleanup_clone(path)

    @patch("codecustodian.executor.repo_cloner.Repo")
    def test_clone_error_message_does_not_leak_token(self, mock_repo_cls: MagicMock) -> None:
        from git import GitCommandError

        mock_repo_cls.clone_from.side_effect = GitCommandError("clone", "fail")
        with pytest.raises(ExecutorError, match="github.com/owner/repo") as exc_info:
            clone_repo("https://github.com/owner/repo", token="ghp_secret")
        # The token must never appear in the error message
        assert "ghp_secret" not in str(exc_info.value)


# ── cleanup_clone ─────────────────────────────────────────────────────────


class TestCleanupClone:
    """cleanup_clone removes the directory safely."""

    def test_removes_existing_directory(self, tmp_path: Path) -> None:
        target = tmp_path / "clone_test"
        target.mkdir()
        (target / "file.txt").write_text("hello")
        cleanup_clone(target)
        assert not target.exists()

    def test_noop_if_directory_missing(self, tmp_path: Path) -> None:
        missing = tmp_path / "does_not_exist"
        cleanup_clone(missing)  # should not raise
