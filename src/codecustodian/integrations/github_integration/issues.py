"""GitHub Issues integration.

Creates issues for findings that can't be auto-fixed,
and links issues to related PRs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from codecustodian.logging import get_logger
from codecustodian.models import Finding

if TYPE_CHECKING:
    from github import Github

logger = get_logger("integrations.issues")


class IssueManager:
    """Create and manage GitHub issues for tech debt findings."""

    def __init__(self, token: str, repo_name: str) -> None:
        from github import Github

        self.gh: Github = Github(token)
        self.repo = self.gh.get_repo(repo_name)

    def create_issue(self, finding: Finding, reason: str = "auto") -> int:
        """Create an issue for a finding that can't be auto-fixed.

        Returns the issue number.
        """
        title = f"[Tech Debt] {finding.description[:80]}"
        body = f"""\
## Technical Debt Finding

**File:** `{finding.file}`
**Line:** {finding.line}
**Type:** {finding.type.value}
**Severity:** {finding.severity.value}

### Description

{finding.description}

### Suggested Fix

{finding.suggestion}

### Why This Wasn't Auto-Fixed

{reason}

---
*Reported by CodeCustodian*
"""

        labels = ["tech-debt", f"severity:{finding.severity.value}"]
        issue = self.repo.create_issue(
            title=title,
            body=body,
            labels=labels,
        )

        logger.info("Created issue #%d: %s", issue.number, title)
        return issue.number
