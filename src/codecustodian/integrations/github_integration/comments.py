"""PR review comments manager.

Handles inline code review comments and thread management.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from codecustodian.logging import get_logger

if TYPE_CHECKING:
    from github import Github

logger = get_logger("integrations.comments")


class CommentManager:
    """Manage PR review and inline comments."""

    def __init__(self, token: str, repo_name: str) -> None:
        from github import Github

        self.gh: Github = Github(token)
        self.repo = self.gh.get_repo(repo_name)

    def post_review_comment(
        self,
        pr_number: int,
        body: str,
        file_path: str,
        line: int,
        commit_sha: str,
    ) -> int:
        """Post an inline review comment on a PR.

        Returns the comment ID.
        """
        pr = self.repo.get_pull(pr_number)
        commit = self.repo.get_commit(commit_sha)

        comment = pr.create_review_comment(
            body=body,
            commit=commit,
            path=file_path,
            line=line,
        )

        logger.debug(
            "Posted review comment on PR #%d at %s:%d",
            pr_number, file_path, line,
        )
        return comment.id

    def post_pr_comment(self, pr_number: int, body: str) -> int:
        """Post a general comment on a PR.

        Returns the comment ID.
        """
        pr = self.repo.get_pull(pr_number)
        comment = pr.create_issue_comment(body)
        logger.debug("Posted comment on PR #%d", pr_number)
        return comment.id
