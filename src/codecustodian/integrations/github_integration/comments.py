"""PR review comments manager.

Handles inline code review comments, thread management,
and audit trail summaries.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from codecustodian.logging import get_logger
from codecustodian.models import (
    ExecutionResult,
    Finding,
    RefactoringPlan,
    VerificationResult,
)

if TYPE_CHECKING:
    from github import Github
    from github.Repository import Repository

logger = get_logger("integrations.comments")


class CommentManager:
    """Manage PR review and inline comments."""

    def __init__(self, token: str, repo_name: str) -> None:
        from github import Github

        self.gh: Github = Github(token)
        self.repo: Repository = self.gh.get_repo(repo_name)

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
            pr_number,
            file_path,
            line,
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

    def post_audit_summary(
        self,
        pr_number: int,
        finding: Finding,
        plan: RefactoringPlan,
        execution: ExecutionResult,
        verification: VerificationResult,
    ) -> int:
        """Post a collapsible audit trail comment on the PR.

        Includes: pipeline metadata, safety check details, transaction
        log, and verification breakdown.

        Returns the comment ID.
        """
        # Safety checks
        safety_md = ""
        if execution.safety_result:
            checks_rows = "\n".join(
                f"| {c.name} | {'✅' if c.passed else '❌'} | {c.message} |"
                for c in execution.safety_result.checks
            )
            safety_md = (
                f"| Check | Status | Details |\n|-------|--------|---------|\n{checks_rows}\n"
            )
        else:
            safety_md = "_No safety checks recorded._"

        # Transaction log
        if execution.transaction_log:
            tx_rows = "\n".join(
                f"| {e.timestamp:%H:%M:%S} | {e.action} | "
                f"`{e.file_path}` | {'✅' if e.success else '❌'} |"
                for e in execution.transaction_log
            )
            tx_md = f"| Time | Action | File | OK |\n|------|--------|------|----|\n{tx_rows}\n"
        else:
            tx_md = "_No transaction log entries._"

        # Lint violations
        lint_md = ""
        if verification.lint_violations:
            lint_rows = "\n".join(
                f"| `{v.file}` | {v.line} | {v.code} | {v.message} |"
                for v in verification.lint_violations[:10]
            )
            lint_md = (
                f"| File | Line | Code | Message |\n|------|------|------|---------|\n{lint_rows}\n"
            )
            if len(verification.lint_violations) > 10:
                lint_md += f"\n_… and {len(verification.lint_violations) - 10} more_\n"
        else:
            lint_md = "✅ No lint violations."

        # Security issues
        sec_md = ""
        if verification.security_issues:
            sec_rows = "\n".join(
                f"| `{s.file}` | {s.line} | {s.severity} | {s.description} |"
                for s in verification.security_issues[:10]
            )
            sec_md = (
                "| File | Line | Severity | Description |\n"
                "|------|------|----------|-------------|\n"
                f"{sec_rows}\n"
            )
        else:
            sec_md = "✅ No security issues."

        body = (
            "## 📋 Audit Trail\n"
            "\n"
            f"**Finding:** {finding.id} — {finding.description[:60]}\n"
            f"**Plan:** {plan.id} | **Commit:** `{execution.commit_sha[:8]}`\n"
            f"**Branch:** `{execution.branch_name}`\n"
            f"**Execution duration:** {execution.duration_seconds:.1f}s\n"
            "\n"
            "<details>\n"
            "<summary>🛡️ Safety Checks</summary>\n"
            "\n"
            f"{safety_md}\n"
            "</details>\n"
            "\n"
            "<details>\n"
            "<summary>📜 Transaction Log</summary>\n"
            "\n"
            f"{tx_md}\n"
            "</details>\n"
            "\n"
            "<details>\n"
            "<summary>🔍 Lint Results</summary>\n"
            "\n"
            f"{lint_md}\n"
            "</details>\n"
            "\n"
            "<details>\n"
            "<summary>🔒 Security Scan</summary>\n"
            "\n"
            f"{sec_md}\n"
            "</details>\n"
            "\n"
            "---\n"
            "*Audit trail generated by CodeCustodian*\n"
        )

        return self.post_pr_comment(pr_number, body)
