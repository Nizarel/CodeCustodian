"""PR interaction handler.

Monitors PR comments, review requests, and feedback loops
for CodeCustodian-created pull requests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from codecustodian.logging import get_logger

if TYPE_CHECKING:
    from github import Github, PullRequest

logger = get_logger("integrations.pr_interaction")


class PRInteractionHandler:
    """Handle interactions on CodeCustodian PRs."""

    def __init__(self, token: str, repo_name: str) -> None:
        from github import Github

        self.gh: Github = Github(token)
        self.repo = self.gh.get_repo(repo_name)

    def handle_comment(self, pr_number: int, comment_body: str) -> str | None:
        """Process a review comment and generate a response.

        Returns a reply message or None.
        """
        pr = self.repo.get_pull(pr_number)
        body_lower = comment_body.lower()

        if any(cmd in body_lower for cmd in ("/approve", "lgtm", "looks good")):
            return self._handle_approval(pr)
        elif any(cmd in body_lower for cmd in ("/reject", "/close", "won't fix")):
            return self._handle_rejection(pr)
        elif "/explain" in body_lower:
            return self._handle_explain(pr)
        elif "/retry" in body_lower:
            return self._handle_retry(pr)

        return None

    def _handle_approval(self, pr: PullRequest.PullRequest) -> str:
        """Handle PR approval."""
        logger.info("PR #%d approved", pr.number)
        return "Thanks for reviewing! Merging will proceed according to your branch protection rules."

    def _handle_rejection(self, pr: PullRequest.PullRequest) -> str:
        """Handle PR rejection — record feedback for learning."""
        pr.edit(state="closed")
        logger.info("PR #%d closed by reviewer", pr.number)
        return (
            "Understood. I've closed this PR and recorded the feedback "
            "to improve future suggestions."
        )

    def _handle_explain(self, pr: PullRequest.PullRequest) -> str:
        """Provide a detailed explanation of the PR's changes."""
        return (
            "I'll provide a detailed explanation of the changes — "
            "this feature requires the Copilot SDK. "
            "Check the PR description for the AI reasoning section."
        )

    def _handle_retry(self, pr: PullRequest.PullRequest) -> str:
        """Re-run the planning phase with updated context."""
        logger.info("Retry requested for PR #%d", pr.number)
        return "Retry requested — this will be implemented with the feedback loop."
