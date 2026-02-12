"""Custom exception hierarchy for CodeCustodian.

All exceptions inherit from ``CodeCustodianError`` so callers can catch
the base class for generic error handling or specific subclasses for
targeted recovery.
"""

from __future__ import annotations

from typing import Any


class CodeCustodianError(Exception):
    """Base exception for all CodeCustodian errors.

    Args:
        message: Human-readable error description.
        details: Optional structured context for logging / telemetry.
    """

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


# ── Pipeline stage errors ──────────────────────────────────────────────────


class ScannerError(CodeCustodianError):
    """Raised when a scanner fails during the scan stage."""


class PlannerError(CodeCustodianError):
    """Raised when AI planning fails (Copilot SDK call, tool execution)."""


class ExecutorError(CodeCustodianError):
    """Raised when safe file-editing or git operations fail."""


class VerifierError(CodeCustodianError):
    """Raised when test/lint/security verification fails unrecoverably."""


# ── Integration errors ─────────────────────────────────────────────────────


class GitHubAPIError(CodeCustodianError):
    """Raised on GitHub API failures (PR creation, issue posting, etc.).

    Args:
        message: Error description.
        status_code: HTTP status code from the GitHub API.
        response_body: Raw response body for debugging.
        details: Additional context.
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)
        self.status_code = status_code
        self.response_body = response_body


class AzureIntegrationError(CodeCustodianError):
    """Raised on Azure DevOps / Azure Monitor integration failures."""


# ── Governance errors ──────────────────────────────────────────────────────


class BudgetExceededError(CodeCustodianError):
    """Raised when a pipeline run would exceed the configured budget.

    Args:
        message: Error description.
        current_cost: Accumulated cost so far (USD).
        budget_limit: Configured budget ceiling (USD).
        details: Additional context.
    """

    def __init__(
        self,
        message: str,
        current_cost: float = 0.0,
        budget_limit: float = 0.0,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)
        self.current_cost = current_cost
        self.budget_limit = budget_limit


class ApprovalRequiredError(CodeCustodianError):
    """Raised when an action requires human approval before proceeding.

    Args:
        message: Error description.
        resource_id: ID of the plan/PR/finding that needs approval.
        approval_type: The kind of approval required (``"plan"`` | ``"pr"``).
        details: Additional context.
    """

    def __init__(
        self,
        message: str,
        resource_id: str = "",
        approval_type: str = "plan",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details)
        self.resource_id = resource_id
        self.approval_type = approval_type
