"""Git workflow manager.

Handles branching, commits, push, and cleanup for refactoring PRs.
Implements convention for branch naming: ``tech-debt/{category}-{file}-{timestamp}``.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from git import GitCommandError, InvalidGitRepositoryError, Repo

from codecustodian.exceptions import ExecutorError
from codecustodian.logging import get_logger
from codecustodian.models import Finding, RefactoringPlan

if TYPE_CHECKING:
    pass

logger = get_logger("executor.git_manager")

# Patterns for parsing GitHub remote URLs
_HTTPS_PATTERN = re.compile(r"github\.com[/:]([^/]+/[^/.]+?)(?:\.git)?$")
_SSH_PATTERN = re.compile(r"git@github\.com:([^/]+/[^/.]+?)(?:\.git)?$")


class GitManager:
    """Manage git operations for the refactoring workflow.

    Usage::

        gm = GitManager("/path/to/repo")
        branch = gm.create_branch(finding)
        # ... apply changes ...
        sha = gm.commit(finding, plan)
        gm.push(branch)
        gm.cleanup(branch)
    """

    def __init__(self, repo_path: str | Path) -> None:
        try:
            self.repo = Repo(str(repo_path))
        except InvalidGitRepositoryError as exc:
            raise ExecutorError(
                f"Not a git repository: {repo_path}",
                details={"repo_path": str(repo_path)},
            ) from exc
        self.repo_path = Path(repo_path)
        self._original_branch: str | None = None

    @property
    def current_branch(self) -> str:
        """Return the name of the currently checked-out branch."""
        return str(self.repo.active_branch)

    @property
    def is_clean(self) -> bool:
        """Return True if the working tree has no uncommitted changes."""
        return not self.repo.is_dirty(untracked_files=True)

    def pull_latest(self, remote: str = "origin", branch: str | None = None) -> None:
        """Pull latest changes from remote.

        Args:
            remote: Remote name (default: ``origin``).
            branch: Branch to pull. Defaults to current branch.
        """
        target = branch or self.current_branch
        try:
            self.repo.git.pull(remote, target, "--rebase")
            logger.info("Pulled latest from %s/%s", remote, target)
        except GitCommandError as exc:
            logger.warning("Pull failed (may not have remote): %s", exc)

    def get_file_sha(self, file_path: str) -> str | None:
        """Get the git blob SHA for a tracked file.

        Returns None if the file is untracked or the command fails.
        """
        try:
            sha = self.repo.git.hash_object(str(self.repo_path / file_path))
            return sha.strip()
        except GitCommandError:
            return None

    def create_branch(self, finding: Finding, prefix: str = "tech-debt") -> str:
        """Create and checkout a new branch for a refactoring.

        Saves the original branch name so ``cleanup()`` can return to it.
        Returns the branch name.
        """
        self._original_branch = self.current_branch

        category = finding.type.value.replace("_", "-")
        file_short = Path(finding.file).stem[:20]
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M")
        branch_name = f"{prefix}/{category}-{file_short}-{timestamp}"

        try:
            self.repo.git.checkout("-b", branch_name)
            logger.info("Created branch: %s", branch_name)
        except GitCommandError as exc:
            raise ExecutorError(
                f"Failed to create branch {branch_name}: {exc}",
                details={"branch": branch_name},
            ) from exc

        return branch_name

    def commit(
        self,
        finding: Finding,
        plan: RefactoringPlan,
        author_name: str = "CodeCustodian",
        author_email: str = "bot@codecustodian.dev",
    ) -> str:
        """Stage all changes and commit with a detailed message.

        Returns the commit SHA.
        """
        self.repo.git.add("-A")

        # Check if there's anything to commit
        if not self.repo.is_dirty(index=True):
            logger.warning("Nothing to commit — working tree is clean")
            return self.repo.head.commit.hexsha

        summary = plan.summary[:50]
        body = (
            f"Finding: {finding.id}\n"
            f"Type: {finding.type.value}\n"
            f"Severity: {finding.severity.value}\n\n"
            f"Changes:\n"
            + "\n".join(f"- {c.file_path}" for c in plan.changes)
            + f"\n\nAI Reasoning:\n{plan.ai_reasoning[:500]}"
            f"\n\nConfidence: {plan.confidence_score}/10"
            f"\nRisk: {plan.risk_level.value}"
            f"\n\nCo-authored-by: {author_name} <{author_email}>"
        )

        commit_msg = f"refactor: {summary}\n\n{body}"

        try:
            self.repo.git.commit(
                "-m",
                commit_msg,
                author=f"{author_name} <{author_email}>",
            )
        except GitCommandError as exc:
            raise ExecutorError(
                f"Commit failed: {exc}",
                details={"summary": summary},
            ) from exc

        sha = self.repo.head.commit.hexsha
        logger.info("Committed %s: %s", sha[:8], summary)
        return sha

    def push(self, branch: str, remote: str = "origin") -> None:
        """Push branch to remote with auth error handling."""
        try:
            self.repo.git.push(remote, branch)
            logger.info("Pushed %s to %s", branch, remote)
        except GitCommandError as exc:
            error_str = str(exc).lower()
            if "authentication" in error_str or "permission" in error_str:
                raise ExecutorError(
                    f"Authentication failed when pushing to {remote}/{branch}. "
                    "Check your credentials or SSH key.",
                    details={"branch": branch, "remote": remote},
                ) from exc
            raise ExecutorError(
                f"Push failed for {branch}: {exc}",
                details={"branch": branch, "remote": remote},
            ) from exc

    def checkout(self, branch: str) -> None:
        """Checkout an existing branch."""
        try:
            self.repo.git.checkout(branch)
        except GitCommandError as exc:
            raise ExecutorError(
                f"Checkout failed for {branch}: {exc}",
                details={"branch": branch},
            ) from exc

    def cleanup(self, branch: str | None = None) -> None:
        """Switch back to original branch and optionally delete the feature branch.

        Args:
            branch: The feature branch to delete. If None, just switches back.
        """
        if self._original_branch:
            try:
                self.repo.git.checkout(self._original_branch)
                logger.info("Returned to branch: %s", self._original_branch)
            except GitCommandError as exc:
                logger.error("Failed to return to %s: %s", self._original_branch, exc)

        if branch:
            try:
                self.repo.git.branch("-D", branch)
                logger.info("Deleted local branch: %s", branch)
            except GitCommandError as exc:
                logger.warning("Failed to delete branch %s: %s", branch, exc)

        self._original_branch = None

    def stash(self) -> None:
        """Stash current changes."""
        self.repo.git.stash()

    def stash_pop(self) -> None:
        """Pop stashed changes."""
        self.repo.git.stash("pop")

    def get_repo_name(self, config_override: str = "") -> str:
        """Derive the GitHub ``owner/repo`` name.

        Resolution order:
        1. *config_override* (from ``GitHubConfig.repo_name``).
        2. Parse the ``origin`` remote URL (HTTPS or SSH).

        Returns:
            ``owner/repo`` string.

        Raises:
            ExecutorError: If the repo name cannot be determined.
        """
        if config_override:
            return config_override

        try:
            origin = self.repo.remote("origin")
            url = next(origin.urls, None)
        except (ValueError, StopIteration):
            url = None

        if url:
            for pattern in (_HTTPS_PATTERN, _SSH_PATTERN):
                m = pattern.search(url)
                if m:
                    return m.group(1)

        raise ExecutorError(
            "Cannot determine GitHub repo name — set github.repo_name in "
            ".codecustodian.yml or add a GitHub 'origin' remote.",
            details={"remote_url": url or "<none>"},
        )
