"""GitHub Issues integration.

Creates issues for findings that can't be auto-fixed,
and links issues to related PRs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from codecustodian.exceptions import GitHubAPIError
from codecustodian.logging import get_logger
from codecustodian.models import Finding, ProposalResult

if TYPE_CHECKING:
    from github import Github
    from github.Repository import Repository

logger = get_logger("integrations.issues")


class IssueManager:
    """Create and manage GitHub issues for tech debt findings."""

    def __init__(self, token: str, repo_name: str) -> None:
        from github import Github

        self.gh: Github = Github(token)
        self.repo: Repository = self.gh.get_repo(repo_name)

    def create_issue(self, finding: Finding, reason: str = "auto") -> int:
        """Create an issue for a finding that can't be auto-fixed.

        Returns the issue number.
        """
        title = f"[Tech Debt] {finding.description[:80]}"
        body = (
            "## Technical Debt Finding\n"
            "\n"
            f"**File:** `{finding.file}`\n"
            f"**Line:** {finding.line}\n"
            f"**Type:** {finding.type.value}\n"
            f"**Severity:** {finding.severity.value}\n"
            "\n"
            "### Description\n"
            "\n"
            f"{finding.description}\n"
            "\n"
            "### Suggested Fix\n"
            "\n"
            f"{finding.suggestion}\n"
            "\n"
            "### Why This Wasn't Auto-Fixed\n"
            "\n"
            f"{reason}\n"
            "\n"
            "---\n"
            "*Reported by CodeCustodian*\n"
        )

        labels = ["tech-debt", f"severity:{finding.severity.value}"]
        try:
            issue = self.repo.create_issue(
                title=title,
                body=body,
                labels=labels,
            )
        except Exception as exc:
            raise GitHubAPIError(
                f"Failed to create issue for finding: {exc}",
                status_code=getattr(exc, "status", None),
                response_body=str(getattr(exc, "data", "")),
                details={"finding_id": finding.id},
            ) from exc

        logger.info("Created issue #%d: %s", issue.number, title)
        return issue.number

    def create_proposal_issue(self, proposal: ProposalResult) -> int:
        """Create a GitHub issue for a low-confidence proposal (BR-PR-003).

        Returns the issue number.

        Raises:
            GitHubAPIError: On GitHub API failure.
        """
        finding = proposal.finding

        # Check for duplicate open issues
        dup = self._check_duplicate(finding)
        if dup is not None:
            logger.info(
                "Duplicate proposal issue #%d already exists for %s",
                dup,
                finding.id,
            )
            return dup

        steps_md = "\n".join(
            f"{i}. {step}" for i, step in enumerate(proposal.recommended_steps, 1)
        )
        risks_md = (
            "\n".join(f"- ⚠️ {r}" for r in proposal.risks)
            if proposal.risks
            else "- No significant risks identified"
        )

        title = f"[Proposal] {finding.description[:72]}"
        body = (
            "## 📋 Tech Debt Proposal\n"
            "\n"
            "> CodeCustodian identified this tech debt but the confidence was "
            "too low for an automated fix. Please review and consider a "
            "manual refactoring.\n"
            "\n"
            f"**File:** `{finding.file}` (line {finding.line})\n"
            f"**Type:** {finding.type.value}\n"
            f"**Severity:** {finding.severity.value}\n"
            f"**Estimated effort:** {proposal.estimated_effort}\n"
            "\n"
            "### Description\n"
            "\n"
            f"{finding.description}\n"
            "\n"
            f"{finding.suggestion}\n"
            "\n"
            "### Recommended Steps\n"
            "\n"
            f"{steps_md}\n"
            "\n"
            "### Risks\n"
            "\n"
            f"{risks_md}\n"
            "\n"
            "---\n"
            "*Reported by CodeCustodian — proposal mode*\n"
        )

        labels = [
            "tech-debt",
            "proposal",
            f"severity:{finding.severity.value}",
            f"effort:{proposal.estimated_effort}",
        ]

        try:
            issue = self.repo.create_issue(
                title=title,
                body=body,
                labels=labels,
            )
        except Exception as exc:
            raise GitHubAPIError(
                f"Failed to create proposal issue: {exc}",
                status_code=getattr(exc, "status", None),
                response_body=str(getattr(exc, "data", "")),
                details={"finding_id": finding.id},
            ) from exc

        logger.info("Created proposal issue #%d: %s", issue.number, title)
        return issue.number

    def _check_duplicate(self, finding: Finding) -> int | None:
        """Return the number of an existing open issue for this finding.

        Searches for issues whose title contains the finding description
        prefix and the ``[Proposal]`` tag.  Returns ``None`` if no
        duplicate is found.
        """
        search_title = finding.description[:40]
        try:
            open_issues = self.repo.get_issues(state="open")
            for issue in open_issues:
                if (
                    issue.title.startswith("[Proposal]")
                    and search_title in issue.title
                ):
                    return issue.number
        except Exception:
            logger.debug("Duplicate check failed — proceeding with creation")
        return None
