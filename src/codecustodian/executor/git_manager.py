"""Git workflow manager.

Handles branching, commits, and push operations for refactoring PRs.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from git import Repo

from codecustodian.logging import get_logger
from codecustodian.models import Finding, RefactoringPlan

if TYPE_CHECKING:
    pass

logger = get_logger("executor.git_manager")


class GitManager:
    """Manage git operations for the refactoring workflow."""

    def __init__(self, repo_path: str | Path) -> None:
        self.repo = Repo(str(repo_path))
        self.repo_path = Path(repo_path)

    @property
    def current_branch(self) -> str:
        return str(self.repo.active_branch)

    @property
    def is_clean(self) -> bool:
        return not self.repo.is_dirty(untracked_files=True)

    def create_branch(self, finding: Finding, prefix: str = "tech-debt") -> str:
        """Create and checkout a new branch for a refactoring.

        Returns the branch name.
        """
        category = finding.type.value.replace("_", "-")
        file_short = Path(finding.file).stem[:20]
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M")
        branch_name = f"{prefix}/{category}-{file_short}-{timestamp}"

        self.repo.git.checkout("-b", branch_name)
        logger.info("Created branch: %s", branch_name)
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
        self.repo.git.commit("-m", commit_msg, author=f"{author_name} <{author_email}>")

        sha = self.repo.head.commit.hexsha
        logger.info("Committed %s: %s", sha[:8], summary)
        return sha

    def push(self, branch: str, remote: str = "origin") -> None:
        """Push branch to remote."""
        self.repo.git.push(remote, branch)
        logger.info("Pushed %s to %s", branch, remote)

    def checkout(self, branch: str) -> None:
        """Checkout an existing branch."""
        self.repo.git.checkout(branch)

    def stash(self) -> None:
        """Stash current changes."""
        self.repo.git.stash()

    def stash_pop(self) -> None:
        """Pop stashed changes."""
        self.repo.git.stash("pop")
