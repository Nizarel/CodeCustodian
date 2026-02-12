"""GitHub PR creation and management.

Creates pull requests with structured descriptions, labels,
and metadata for tech debt refactorings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from codecustodian.logging import get_logger
from codecustodian.models import (
    Finding,
    PullRequestInfo,
    RefactoringPlan,
    VerificationResult,
)

if TYPE_CHECKING:
    from github import Github

logger = get_logger("integrations.pr_creator")


class PullRequestCreator:
    """Create and manage pull requests via PyGithub."""

    def __init__(self, token: str, repo_name: str) -> None:
        from github import Github

        self.gh: Github = Github(token)
        self.repo = self.gh.get_repo(repo_name)
        self.token = token

    def create_pr(
        self,
        finding: Finding,
        plan: RefactoringPlan,
        verification: VerificationResult,
        branch: str,
        base: str = "main",
    ) -> PullRequestInfo:
        """Create a PR with structured description and labels."""
        title = f"refactor: {plan.summary[:80]}"
        body = self._build_body(finding, plan, verification)

        pr = self.repo.create_pull(
            title=title,
            body=body,
            head=branch,
            base=base,
        )

        # Add labels
        labels = self._select_labels(finding, plan)
        for label in labels:
            try:
                pr.add_to_labels(label)
            except Exception:
                logger.debug("Label '%s' not found, skipping", label)

        logger.info("Created PR #%d: %s", pr.number, title)
        return PullRequestInfo(
            number=pr.number,
            url=pr.html_url,
            title=title,
            branch=branch,
        )

    def _build_body(
        self,
        finding: Finding,
        plan: RefactoringPlan,
        verification: VerificationResult,
    ) -> str:
        """Build a structured PR description."""
        changes_table = "\n".join(
            f"| `{c.file_path}` | {c.description or 'Updated'} |"
            for c in plan.changes
        )

        return f"""\
## 🤖 Automated Tech Debt Refactoring

**Finding:** {finding.description}
**Severity:** {finding.severity.value}
**Type:** {finding.type.value}
**Confidence:** {plan.confidence_score}/10
**Risk:** {plan.risk_level.value}

### Changes

| File | Description |
|------|-------------|
{changes_table}

### AI Reasoning

{plan.ai_reasoning}

### Verification

- Tests run: {verification.tests_run}
- Tests passed: {verification.tests_passed}
- Coverage: {verification.coverage_overall:.1f}%
- Lint clean: {'✅' if not verification.lint_violations else '❌'}

### Alternatives Considered

{chr(10).join(f'- {a}' for a in plan.alternatives) if plan.alternatives else 'None'}

---
*Created by [CodeCustodian](https://github.com/nizarel/CodeCustodian) — AI-powered technical debt management*
"""

    @staticmethod
    def _select_labels(finding: Finding, plan: RefactoringPlan) -> list[str]:
        """Select labels based on finding and plan."""
        labels = ["tech-debt", "automated", f"severity:{finding.severity.value}"]

        if finding.type.value == "deprecated_api":
            labels.append("deprecation")
        elif finding.type.value == "security":
            labels.append("security")

        if plan.confidence_score >= 8:
            labels.append("high-confidence")
        elif plan.confidence_score <= 4:
            labels.append("needs-review")

        return labels
