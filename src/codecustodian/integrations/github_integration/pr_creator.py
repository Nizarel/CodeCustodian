"""GitHub PR creation and management.

Creates pull requests with structured descriptions, labels,
and metadata for tech debt refactorings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from codecustodian.exceptions import GitHubAPIError
from codecustodian.logging import get_logger
from codecustodian.models import (
    ExecutionResult,
    Finding,
    PullRequestInfo,
    RefactoringPlan,
    VerificationResult,
)

if TYPE_CHECKING:
    from github import Github
    from github.Repository import Repository

logger = get_logger("integrations.pr_creator")

# ── Label colour palette ───────────────────────────────────────────────────

_LABEL_COLORS: dict[str, str] = {
    "tech-debt": "d4c5f9",
    "automated": "0075ca",
    "codecustodian": "7057ff",
    # Priority
    "P1-critical": "b60205",
    "P2-high": "d93f0b",
    "P3-medium": "fbca04",
    "P4-low": "0e8a16",
    # Status
    "ready-to-merge": "0e8a16",
    "needs-review": "e4e669",
    "draft": "c5def5",
    # Risk
    "risk:low": "0e8a16",
    "risk:medium": "fbca04",
    "risk:high": "d93f0b",
    # Effort
    "effort:low": "0e8a16",
    "effort:medium": "fbca04",
    "effort:high": "d93f0b",
    # Confidence
    "high-confidence": "0e8a16",
    "low-confidence": "d93f0b",
    # Category
    "deprecation": "ff9f1c",
    "security": "b60205",
    "code-smell": "c5def5",
    "todo": "fbca04",
    "type-coverage": "0075ca",
}


class PullRequestCreator:
    """Create and manage pull requests via PyGithub."""

    def __init__(self, token: str, repo_name: str) -> None:
        from github import Github

        self.gh: Github = Github(token)
        self.repo: Repository = self.gh.get_repo(repo_name)
        self.token = token

    # ── Public API ─────────────────────────────────────────────────────

    def create_pr(
        self,
        finding: Finding,
        plan: RefactoringPlan,
        execution: ExecutionResult,
        verification: VerificationResult,
        branch: str,
        base: str = "main",
        *,
        draft_threshold: int = 7,
        reviewers: list[str] | None = None,
        team_reviewers: list[str] | None = None,
    ) -> PullRequestInfo:
        """Create a PR with structured description, labels, and reviewers.

        Args:
            finding: The tech-debt finding being addressed.
            plan: The AI-generated refactoring plan.
            execution: Result from the safe executor.
            verification: Result from the verification stage.
            branch: Head branch name.
            base: Target branch (default ``main``).
            draft_threshold: Confidence below this → draft PR.
            reviewers: Individual GitHub usernames to request review from.
            team_reviewers: GitHub team slugs to request review from.

        Returns:
            Populated ``PullRequestInfo``.

        Raises:
            GitHubAPIError: On any GitHub API failure.
        """
        title = f"refactor: {plan.summary[:80]}"
        body = self._build_body(finding, plan, execution, verification)
        is_draft = plan.confidence_score < draft_threshold

        try:
            pr = self.repo.create_pull(
                title=title,
                body=body,
                head=branch,
                base=base,
                draft=is_draft,
            )
        except Exception as exc:
            raise GitHubAPIError(
                f"Failed to create PR for finding {finding.id}: {exc}",
                status_code=getattr(exc, "status", None),
                response_body=str(getattr(exc, "data", "")),
                details={"finding_id": finding.id, "branch": branch},
            ) from exc

        # ── Labels ─────────────────────────────────────────────────
        labels = self._select_labels(finding, plan)
        if is_draft:
            labels.append("draft")
        self._ensure_labels_exist(labels)
        try:
            pr.set_labels(*labels)
        except Exception:
            logger.warning("Failed to set labels on PR #%d", pr.number)

        # ── Reviewers ──────────────────────────────────────────────
        assigned_reviewers: list[str] = []
        try:
            user_rev = reviewers or []
            team_rev = team_reviewers or []
            if user_rev or team_rev:
                pr.create_review_request(
                    reviewers=user_rev, team_reviewers=team_rev,
                )
                assigned_reviewers = list(user_rev)
        except Exception:
            logger.warning("Failed to request reviewers on PR #%d", pr.number)

        logger.info(
            "Created %sPR #%d: %s",
            "draft " if is_draft else "",
            pr.number,
            title,
        )

        return PullRequestInfo(
            number=pr.number,
            url=pr.html_url,
            title=title,
            body=body,
            labels=labels,
            reviewers=assigned_reviewers,
            branch=branch,
            base_branch=base,
            draft=is_draft,
        )

    # ── Body builder ───────────────────────────────────────────────────

    def _build_body(
        self,
        finding: Finding,
        plan: RefactoringPlan,
        execution: ExecutionResult,
        verification: VerificationResult,
    ) -> str:
        """Build a structured PR description (BR-PR-001).

        Sections: executive summary, changes table, AI reasoning
        (collapsible), confidence factors, reviewer effort, verification
        results, alternatives (collapsible), and risks.
        """
        changes_table = "\n".join(
            f"| `{c.file_path}` | {c.change_type.value} | "
            f"{c.description or 'Updated'} |"
            for c in plan.changes
        )

        # Confidence factors
        factors_md = (
            "\n".join(f"- {f}" for f in plan.confidence_factors)
            if plan.confidence_factors
            else "- No explicit factors recorded"
        )

        # Alternatives
        if plan.alternatives:
            alt_items: list[str] = []
            for alt in plan.alternatives:
                rec = " ⭐ **recommended**" if alt.recommended else ""
                pros = ", ".join(alt.pros) if alt.pros else "—"
                cons = ", ".join(alt.cons) if alt.cons else "—"
                alt_items.append(
                    f"#### {alt.name}{rec}\n"
                    f"{alt.description}\n"
                    f"- **Pros:** {pros}\n"
                    f"- **Cons:** {cons}\n"
                    f"- **Confidence:** {alt.confidence_score}/10"
                )
            alts_md = "\n\n".join(alt_items)
        else:
            alts_md = "No alternatives were considered."

        # Verification summary
        lint_status = (
            "✅ Clean" if verification.lint_passed
            else f"❌ {len(verification.lint_violations)} violation(s)"
        )
        sec_status = (
            "✅ Clean" if verification.security_passed
            else f"❌ {len(verification.security_issues)} issue(s)"
        )
        coverage_delta = verification.coverage_delta
        delta_icon = "📈" if coverage_delta >= 0 else "📉"

        # Risks
        risks_md = ""
        if plan.risk_level.value != "low":
            risks_md += f"- ⚠️ Risk level: **{plan.risk_level.value}**\n"
        if plan.changes_signature:
            risks_md += "- ⚠️ Public API signature changed\n"
        if plan.requires_manual_verification:
            risks_md += "- ⚠️ Manual verification recommended\n"
        if not risks_md:
            risks_md = "- ✅ No significant risks identified"

        return (
            "## 🤖 Automated Tech Debt Refactoring\n"
            "\n"
            f"> **Finding:** {finding.description}\n"
            f"> **Severity:** {finding.severity.value} "
            f"| **Type:** {finding.type.value}\n"
            f"> **File:** `{finding.file}` (line {finding.line})\n"
            "\n"
            "| Metric | Value |\n"
            "|--------|-------|\n"
            f"| Confidence | **{plan.confidence_score}/10** |\n"
            f"| Risk | {plan.risk_level.value} |\n"
            f"| Reviewer effort | {plan.reviewer_effort} |\n"
            f"| Duration | {execution.duration_seconds:.1f}s |\n"
            "\n"
            "---\n"
            "\n"
            "### 📝 Changes\n"
            "\n"
            "| File | Type | Description |\n"
            "|------|------|-------------|\n"
            f"{changes_table}\n"
            "\n"
            "<details>\n"
            "<summary>🧠 AI Reasoning</summary>\n"
            "\n"
            f"{plan.ai_reasoning or '_No reasoning recorded._'}\n"
            "\n"
            "</details>\n"
            "\n"
            "### 🎯 Confidence Factors\n"
            "\n"
            f"{factors_md}\n"
            "\n"
            "### ✅ Verification Results\n"
            "\n"
            "| Check | Result |\n"
            "|-------|--------|\n"
            f"| Tests | {verification.tests_passed}/{verification.tests_run}"
            f" passed ({verification.tests_failed} failed,"
            f" {verification.tests_skipped} skipped) |\n"
            f"| Coverage | {verification.coverage_overall:.1f}%"
            f" ({delta_icon} {coverage_delta:+.1f}%) |\n"
            f"| Lint | {lint_status} |\n"
            f"| Security | {sec_status} |\n"
            "\n"
            "<details>\n"
            "<summary>🔄 Alternatives Considered</summary>\n"
            "\n"
            f"{alts_md}\n"
            "\n"
            "</details>\n"
            "\n"
            "### ⚠️ Risks\n"
            "\n"
            f"{risks_md}\n"
            "\n"
            "---\n"
            "*Created by [CodeCustodian]"
            "(https://github.com/nizarel/CodeCustodian) — "
            "AI-powered technical debt management*\n"
        )

    # ── Labels ─────────────────────────────────────────────────────────

    @staticmethod
    def _select_labels(finding: Finding, plan: RefactoringPlan) -> list[str]:
        """Select labels based on finding attributes and plan metrics.

        Categories:
        - Base: tech-debt, automated, codecustodian
        - Priority: P1–P4 from severity
        - Category: deprecation | security | code-smell | todo | type-coverage
        - Risk: risk:low | risk:medium | risk:high
        - Effort: effort:low | effort:medium | effort:high
        - Confidence: high-confidence (≥8) | low-confidence (≤4)
        """
        labels: list[str] = ["tech-debt", "automated", "codecustodian"]

        # Priority from severity
        _severity_to_priority = {
            "critical": "P1-critical",
            "high": "P2-high",
            "medium": "P3-medium",
            "low": "P4-low",
            "info": "P4-low",
        }
        labels.append(
            _severity_to_priority.get(finding.severity.value, "P3-medium"),
        )

        # Category from finding type
        _type_to_label = {
            "deprecated_api": "deprecation",
            "security": "security",
            "code_smell": "code-smell",
            "todo_comment": "todo",
            "type_coverage": "type-coverage",
        }
        cat_label = _type_to_label.get(finding.type.value)
        if cat_label:
            labels.append(cat_label)

        # Risk
        labels.append(f"risk:{plan.risk_level.value}")

        # Reviewer effort
        labels.append(f"effort:{plan.reviewer_effort}")

        # Confidence bucket
        if plan.confidence_score >= 8:
            labels.append("high-confidence")
        elif plan.confidence_score <= 4:
            labels.append("low-confidence")

        return labels

    def _ensure_labels_exist(self, labels: list[str]) -> None:
        """Create labels on the repo if they don't already exist.

        Silently ignores 422 (label already exists) errors.
        """
        for label_name in labels:
            colour = _LABEL_COLORS.get(label_name, "ededed")
            try:
                self.repo.create_label(name=label_name, color=colour)
            except Exception as exc:
                # 422 = already exists — expected for most runs
                if getattr(exc, "status", None) != 422:
                    logger.debug(
                        "Could not create label '%s': %s",
                        label_name,
                        exc,
                    )
