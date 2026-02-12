"""PR interaction handler.

Monitors PR comments, review requests, and feedback loops
for CodeCustodian-created pull requests.

Supported commands (prefixed with ``@codecustodian`` or ``/``):
  approve, reject, explain, retry, why, alternatives,
  modify, feedback, smaller, propose.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from codecustodian.feedback.store import FeedbackEntry, FeedbackStore
from codecustodian.logging import get_logger

if TYPE_CHECKING:
    from github import Github
    from github.PullRequest import PullRequest
    from github.Repository import Repository

logger = get_logger("integrations.pr_interaction")

# Pattern: @codecustodian <command> [args]  or  /command [args]
_CMD_PATTERN = re.compile(
    r"(?:@codecustodian\s+|/)(\w+)(?:\s+(.*))?",
    re.IGNORECASE | re.DOTALL,
)


class PRInteractionHandler:
    """Handle interactions on CodeCustodian PRs."""

    def __init__(
        self,
        token: str,
        repo_name: str,
        *,
        feedback_dir: str = ".codecustodian-cache",
    ) -> None:
        from github import Github

        self.gh: Github = Github(token)
        self.repo: Repository = self.gh.get_repo(repo_name)
        self.feedback_store = FeedbackStore(storage_dir=feedback_dir)

        # Dispatch table — keys are canonical command names
        self._handlers: dict[str, str] = {
            "approve": "_handle_approval",
            "lgtm": "_handle_approval",
            "reject": "_handle_rejection",
            "close": "_handle_rejection",
            "explain": "_handle_explain",
            "retry": "_handle_retry",
            "why": "_handle_why",
            "alternatives": "_handle_alternatives",
            "modify": "_handle_modify",
            "feedback": "_handle_feedback",
            "smaller": "_handle_smaller",
            "propose": "_handle_propose",
        }

    # ── Public dispatcher ──────────────────────────────────────────────

    def handle_comment(
        self, pr_number: int, comment_body: str,
    ) -> str | None:
        """Process a review comment and generate a response.

        Parses ``@codecustodian <command>`` or ``/<command>`` from the
        comment body.  Also recognises bare keywords like ``lgtm`` and
        ``looks good`` for approval.

        Returns:
            A reply message, or ``None`` when the comment is not a command.
        """
        pr = self.repo.get_pull(pr_number)

        # 1. Try structured command parsing
        m = _CMD_PATTERN.search(comment_body)
        if m:
            cmd = m.group(1).lower()
            args = (m.group(2) or "").strip()
            handler_name = self._handlers.get(cmd)
            if handler_name:
                handler = getattr(self, handler_name)
                return handler(pr, args)

        # 2. Try legacy bare-keyword matching
        body_lower = comment_body.strip().lower()
        if body_lower in {"lgtm", "looks good", "👍"}:
            return self._handle_approval(pr)
        if body_lower in {"won't fix", "wontfix"}:
            return self._handle_rejection(pr)

        return None

    # ── Command handlers ───────────────────────────────────────────────

    def _handle_approval(
        self, pr: PullRequest, args: str = "",
    ) -> str:
        """Handle PR approval — record positive feedback."""
        self._record_feedback(pr, "approved", args)
        logger.info("PR #%d approved", pr.number)
        return (
            "✅ Thanks for reviewing! Merging will proceed according to "
            "your branch protection rules."
        )

    def _handle_rejection(
        self, pr: PullRequest, args: str = "",
    ) -> str:
        """Handle PR rejection — close PR and record negative feedback."""
        pr.edit(state="closed")
        self._record_feedback(pr, "rejected", args)
        logger.info("PR #%d closed by reviewer", pr.number)
        return (
            "❌ Understood. I've closed this PR and recorded the feedback "
            "to improve future suggestions."
        )

    def _handle_explain(
        self, pr: PullRequest, args: str = "",
    ) -> str:
        """Provide a detailed explanation by extracting the AI reasoning."""
        body = pr.body or ""
        # Extract AI Reasoning from the collapsible section
        reasoning_match = re.search(
            r"<summary>🧠 AI Reasoning</summary>\s*\n(.*?)\n</details>",
            body,
            re.DOTALL,
        )
        if reasoning_match:
            reasoning = reasoning_match.group(1).strip()
            return (
                "### 🧠 Explanation\n\n"
                f"{reasoning}\n\n"
                "Check the PR description for more details including "
                "confidence factors and alternatives."
            )
        return (
            "I'll provide a detailed explanation of the changes — "
            "check the PR description for the AI reasoning section."
        )

    def _handle_retry(
        self, pr: PullRequest, args: str = "",
    ) -> str:
        """Signal a retry request — recorded for future pipeline integration."""
        self._record_feedback(pr, "retry_requested", args)
        logger.info("Retry requested for PR #%d", pr.number)
        return (
            "🔄 Retry requested — the pipeline will re-plan this finding "
            "with updated context. This will be executed on the next run."
        )

    def _handle_why(
        self, pr: PullRequest, args: str = "",
    ) -> str:
        """Explain *why* this finding was flagged."""
        body = pr.body or ""
        # Extract Finding line from body
        finding_match = re.search(r"> \*\*Finding:\*\*\s*(.+)", body)
        severity_match = re.search(r"> \*\*Severity:\*\*\s*(\w+)", body)
        finding_desc = finding_match.group(1) if finding_match else "Unknown"
        severity = severity_match.group(1) if severity_match else "unknown"

        return (
            f"### 🔍 Why This Was Flagged\n\n"
            f"**Finding:** {finding_desc}\n"
            f"**Severity:** {severity}\n\n"
            "This issue was detected by CodeCustodian's automated scanners. "
            "The severity and priority were determined by combining the "
            "finding type, impact analysis, and business-impact scoring."
        )

    def _handle_alternatives(
        self, pr: PullRequest, args: str = "",
    ) -> str:
        """List the alternative solutions considered."""
        body = pr.body or ""
        alt_match = re.search(
            r"<summary>🔄 Alternatives Considered</summary>\s*\n(.*?)\n</details>",
            body,
            re.DOTALL,
        )
        if alt_match:
            alts = alt_match.group(1).strip()
            return f"### 🔄 Alternatives\n\n{alts}"
        return "No alternatives were recorded for this refactoring."

    def _handle_modify(
        self, pr: PullRequest, args: str = "",
    ) -> str:
        """Acknowledge a modify request with reviewer instructions."""
        self._record_feedback(pr, "modified", args)
        logger.info("Modify requested on PR #%d: %s", pr.number, args[:80])
        return (
            "📝 Modification request recorded.\n\n"
            f"**Your request:** {args or '(no details provided)'}\n\n"
            "The pipeline will incorporate this feedback on the next retry. "
            "Use `@codecustodian retry` to re-plan with this context."
        )

    def _handle_feedback(
        self, pr: PullRequest, args: str = "",
    ) -> str:
        """Record freeform reviewer feedback."""
        self._record_feedback(pr, "feedback", args)
        logger.info("Feedback recorded for PR #%d", pr.number)
        stats = self.feedback_store.get_accuracy_stats()
        return (
            "📊 Feedback recorded — thank you!\n\n"
            f"**Historical accuracy:** {stats['accuracy']}% "
            f"({stats['approved']}/{stats['total']} approved)"
        )

    def _handle_smaller(
        self, pr: PullRequest, args: str = "",
    ) -> str:
        """Request a smaller scope for the PR."""
        self._record_feedback(pr, "smaller_requested", args)
        logger.info("Smaller PR requested for PR #%d", pr.number)
        return (
            "✂️ Understood — you'd like a smaller change scope.\n\n"
            "The pipeline will attempt to break this refactoring into "
            "smaller, more focused PRs on the next run. "
            "Use `@codecustodian retry` to trigger re-planning."
        )

    def _handle_propose(
        self, pr: PullRequest, args: str = "",
    ) -> str:
        """Close the PR and create a proposal issue instead."""
        pr.edit(state="closed")
        self._record_feedback(pr, "downgraded_to_proposal", args)
        logger.info(
            "PR #%d closed → downgraded to proposal", pr.number,
        )
        return (
            "📋 PR closed and downgraded to a proposal.\n\n"
            "A proposal issue will be created with the recommended steps "
            "for manual implementation. Use the IssueManager to create "
            "the proposal issue separately."
        )

    # ── Helpers ────────────────────────────────────────────────────────

    def _record_feedback(
        self, pr: PullRequest, action: str, comment: str = "",
    ) -> None:
        """Record reviewer feedback to the FeedbackStore."""
        # Extract finding metadata from PR body
        body = pr.body or ""
        finding_id = ""
        finding_type = ""
        confidence = 0

        id_match = re.search(r"finding\.id[\"']?\s*[:=]\s*[\"']?(\w+)", body)
        if id_match:
            finding_id = id_match.group(1)

        type_match = re.search(r"\*\*Type:\*\*\s*(\w+)", body)
        if type_match:
            finding_type = type_match.group(1)

        conf_match = re.search(r"Confidence\s*\|\s*\*\*(\d+)/10\*\*", body)
        if conf_match:
            confidence = int(conf_match.group(1))

        entry = FeedbackEntry(
            finding_id=finding_id or f"pr-{pr.number}",
            finding_type=finding_type,
            action=action,
            confidence_was=confidence,
            reviewer_comment=comment[:500],
            pr_number=pr.number,
        )
        self.feedback_store.record(entry)
