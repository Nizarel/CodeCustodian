"""Approval workflow engine (BR-GOV-001, BR-GOV-002).

Manages human-in-the-loop approval gates for refactoring plans and PRs.
Supports multiple approval states, auto-approval rules, and sensitive-path
detection.

Usage::

    wf = ApprovalWorkflowManager(config.approval)
    req = wf.request_approval(plan_id="p1", resource_type="plan", requester="bot")
    wf.approve(req.id, approver="alice@contoso.com")
    wf.is_approved("p1")  # True
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from codecustodian.logging import get_logger

logger = get_logger("enterprise.approvals")


# ── Models ─────────────────────────────────────────────────────────────────


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_APPROVED = "auto_approved"
    EXPIRED = "expired"


class ApprovalRequest(BaseModel):
    """A request for human approval."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    resource_id: str = ""
    resource_type: str = "plan"          # plan | pr | execution
    requester: str = "codecustodian"
    status: ApprovalStatus = ApprovalStatus.PENDING
    approver: str = ""
    approved_at: str = ""
    reason: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── Manager ────────────────────────────────────────────────────────────────


class ApprovalWorkflowManager:
    """Manage approval gates for plans and PRs (BR-GOV-001, BR-GOV-002).

    Persists approval state in JSONL for audit compliance.

    Args:
        require_plan_approval: Require approval before executing plans.
        require_pr_approval: Require approval before creating PRs.
        approved_repos: Repos exempt from approval (auto-approved).
        sensitive_paths: Glob patterns for paths that always need approval.
        data_dir: Directory for approval log persistence.
    """

    def __init__(
        self,
        require_plan_approval: bool = False,
        require_pr_approval: bool = True,
        approved_repos: list[str] | None = None,
        sensitive_paths: list[str] | None = None,
        approval_required_categories: list[str] | None = None,
        data_dir: str | Path = ".codecustodian-approvals",
    ) -> None:
        self.require_plan_approval = require_plan_approval
        self.require_pr_approval = require_pr_approval
        self.approved_repos = approved_repos or []
        self.sensitive_paths = sensitive_paths or [
            "**/auth/**",
            "**/payments/**",
            "**/security/**",
        ]
        self.approval_required_categories = approval_required_categories or []
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._log_file = self.data_dir / "approvals.jsonl"
        self._requests: dict[str, ApprovalRequest] = {}
        self._load()

    @classmethod
    def from_config(cls, config: Any) -> ApprovalWorkflowManager:
        """Create from an ``ApprovalConfig`` model."""
        return cls(
            require_plan_approval=config.require_plan_approval,
            require_pr_approval=config.require_pr_approval,
            approved_repos=list(config.approved_repos),
            sensitive_paths=list(config.sensitive_paths),
            approval_required_categories=list(
                getattr(config, "approval_required_categories", [])
            ),
        )

    # ── Request / Approve / Reject ─────────────────────────────────────

    def request_approval(
        self,
        resource_id: str,
        resource_type: str = "plan",
        requester: str = "codecustodian",
        *,
        metadata: dict[str, Any] | None = None,
    ) -> ApprovalRequest:
        """Create an approval request (BR-GOV-002)."""
        req = ApprovalRequest(
            resource_id=resource_id,
            resource_type=resource_type,
            requester=requester,
            metadata=metadata or {},
        )
        self._requests[req.id] = req
        self._persist(req)
        logger.info(
            "Approval requested: %s (%s) by %s",
            resource_id,
            resource_type,
            requester,
        )
        return req

    def approve(
        self,
        request_id: str,
        approver: str,
        reason: str = "",
    ) -> ApprovalRequest:
        """Approve a pending request."""
        req = self._requests.get(request_id)
        if not req:
            raise ValueError(f"Approval request {request_id} not found")
        req.status = ApprovalStatus.APPROVED
        req.approver = approver
        req.approved_at = datetime.now(timezone.utc).isoformat()
        req.reason = reason
        self._persist(req)
        logger.info("Approved %s by %s", request_id, approver)
        return req

    def reject(
        self,
        request_id: str,
        approver: str,
        reason: str = "",
    ) -> ApprovalRequest:
        """Reject a pending request."""
        req = self._requests.get(request_id)
        if not req:
            raise ValueError(f"Approval request {request_id} not found")
        req.status = ApprovalStatus.REJECTED
        req.approver = approver
        req.approved_at = datetime.now(timezone.utc).isoformat()
        req.reason = reason
        self._persist(req)
        logger.info("Rejected %s by %s: %s", request_id, approver, reason)
        return req

    # ── Query ──────────────────────────────────────────────────────────

    def is_approved(self, resource_id: str) -> bool:
        """Check if a resource has been approved."""
        for req in self._requests.values():
            if req.resource_id == resource_id and req.status in (
                ApprovalStatus.APPROVED,
                ApprovalStatus.AUTO_APPROVED,
            ):
                return True
        return False

    def needs_approval(
        self,
        resource_type: str,
        *,
        repo: str = "",
        file_path: str = "",
        finding_type: str = "",
    ) -> bool:
        """Determine if an action needs approval.

        Auto-approves if:
        - The resource type doesn't require approval per config.
        - The repo is in ``approved_repos``.

        Forces approval if:
        - The file matches a ``sensitive_paths`` glob.
        """
        # Sensitive-path override
        if file_path and self._is_sensitive(file_path):
            return True

        # Auto-approve for pre-approved repos
        if repo and repo in self.approved_repos:
            return False

        if finding_type and finding_type in self.approval_required_categories:
            return True

        if resource_type == "plan":
            return self.require_plan_approval
        if resource_type == "pr":
            return self.require_pr_approval
        return False

    async def request_plan_approval(
        self,
        plan: Any,
        repo: str,
        *,
        requester: str = "codecustodian",
        timeout: int = 3600,
    ) -> bool:
        """Request and await plan approval for sensitive categories/repos."""
        finding_type = str(getattr(plan, "finding_type", ""))
        metadata = {"repo": repo, "finding_type": finding_type}

        if not self.needs_approval("plan", repo=repo, finding_type=finding_type):
            return True

        req = self.request_approval(
            resource_id=str(getattr(plan, "id", "")),
            resource_type="plan",
            requester=requester,
            metadata=metadata,
        )
        await self._notify_approvers(req)
        return await self._wait_for_approval(req.id, timeout=timeout)

    async def _notify_approvers(self, req: ApprovalRequest) -> None:
        """Send approval notification to configured approvers."""
        logger.info(
            "Approval notification sent for %s (%s)",
            req.resource_id,
            req.id,
        )

    async def _wait_for_approval(self, request_id: str, timeout: int = 3600) -> bool:
        """Poll approval status until approved/rejected/expired or timeout."""
        start = datetime.now(timezone.utc)
        while (datetime.now(timezone.utc) - start).total_seconds() < timeout:
            req = self._requests.get(request_id)
            if not req:
                return False
            if req.status in (ApprovalStatus.APPROVED, ApprovalStatus.AUTO_APPROVED):
                return True
            if req.status in (ApprovalStatus.REJECTED, ApprovalStatus.EXPIRED):
                return False
            await asyncio.sleep(5)

        req = self._requests.get(request_id)
        if req and req.status == ApprovalStatus.PENDING:
            req.status = ApprovalStatus.EXPIRED
            req.reason = "Approval request timed out"
            req.approved_at = datetime.now(timezone.utc).isoformat()
            self._persist(req)
        return False

    def get_pending(self) -> list[ApprovalRequest]:
        """Return all pending approval requests."""
        return [
            r
            for r in self._requests.values()
            if r.status == ApprovalStatus.PENDING
        ]

    def auto_approve(
        self,
        resource_id: str,
        resource_type: str = "plan",
        reason: str = "Pre-approved repo",
    ) -> ApprovalRequest:
        """Create an auto-approved request for exempt repos."""
        req = ApprovalRequest(
            resource_id=resource_id,
            resource_type=resource_type,
            status=ApprovalStatus.AUTO_APPROVED,
            approver="system",
            approved_at=datetime.now(timezone.utc).isoformat(),
            reason=reason,
        )
        self._requests[req.id] = req
        self._persist(req)
        logger.info("Auto-approved %s: %s", resource_id, reason)
        return req

    def expire_stale(self, timeout_seconds: int = 3600) -> list[ApprovalRequest]:
        """Mark pending approval requests older than timeout as expired."""
        now = datetime.now(timezone.utc)
        expired: list[ApprovalRequest] = []
        for req in self._requests.values():
            if req.status != ApprovalStatus.PENDING:
                continue
            created = self._parse_timestamp(req.timestamp)
            if created is None:
                continue
            if (now - created).total_seconds() > timeout_seconds:
                req.status = ApprovalStatus.EXPIRED
                req.reason = "Approval request expired"
                req.approved_at = now.isoformat()
                self._persist(req)
                expired.append(req)
        return expired

    # ── Internal ───────────────────────────────────────────────────────

    def _is_sensitive(self, file_path: str) -> bool:
        """Check if a file path matches any sensitive-path glob."""
        for pattern in self.sensitive_paths:
            if fnmatch(file_path, pattern):
                return True
        return False

    def _persist(self, req: ApprovalRequest) -> None:
        """Append an approval request to the JSONL log."""
        with open(self._log_file, "a", encoding="utf-8") as f:
            f.write(req.model_dump_json() + "\n")

    @staticmethod
    def _parse_timestamp(value: str) -> datetime | None:
        """Parse ISO timestamp safely."""
        try:
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None

    def _load(self) -> None:
        """Load approval requests from the JSONL log."""
        if not self._log_file.exists():
            return
        for line in self._log_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                req = ApprovalRequest(**json.loads(line))
                self._requests[req.id] = req
            except (json.JSONDecodeError, Exception):
                continue
