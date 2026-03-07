"""Enterprise RBAC (Role-Based Access Control) — FR-SEC-101, FR-SEC-102.

Controls access to CodeCustodian features based on team roles,
organizational policies, and optional Azure AD JWT validation.

Roles: ADMIN, SECURITY_ADMIN, TEAM_LEAD, CONTRIBUTOR, DEVELOPER, VIEWER
Scoped permissions support per-repo and per-path enforcement.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from codecustodian.logging import get_logger

logger = get_logger("enterprise.rbac")


class Role(StrEnum):
    ADMIN = "admin"
    SECURITY_ADMIN = "security_admin"
    TEAM_LEAD = "team_lead"
    CONTRIBUTOR = "contributor"
    DEVELOPER = "developer"
    VIEWER = "viewer"


class Permission(StrEnum):
    SCAN = "scan"
    PLAN = "plan"
    EXECUTE = "execute"
    CREATE_PR = "create_pr"
    CONFIGURE = "configure"
    VIEW_REPORTS = "view_reports"
    OVERRIDE_SECURITY = "override_security"
    VIEW_AUDIT_LOGS = "view_audit_logs"
    APPROVE_PLANS = "approve_plans"
    APPROVE_PRS = "approve_prs"


class RBACPolicy(BaseModel):
    """Maps roles to permissions."""

    role: Role
    permissions: list[Permission]


class UserContext(BaseModel):
    """Authenticated user context with role and scope (FR-SEC-102).

    Created from Azure AD JWT claims or static config.
    """

    user_id: str
    email: str = ""
    display_name: str = ""
    role: Role = Role.VIEWER
    tenant_id: str = ""
    scoped_repos: list[str] = Field(
        default_factory=list,
        description="Repos this user can access; empty = all",
    )
    authenticated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    claims: dict[str, Any] = Field(default_factory=dict)


# Default role → permission mapping
DEFAULT_POLICIES: list[RBACPolicy] = [
    RBACPolicy(
        role=Role.ADMIN,
        permissions=list(Permission),
    ),
    RBACPolicy(
        role=Role.SECURITY_ADMIN,
        permissions=[
            Permission.SCAN,
            Permission.PLAN,
            Permission.VIEW_REPORTS,
            Permission.VIEW_AUDIT_LOGS,
            Permission.OVERRIDE_SECURITY,
            Permission.APPROVE_PLANS,
            Permission.APPROVE_PRS,
        ],
    ),
    RBACPolicy(
        role=Role.TEAM_LEAD,
        permissions=[
            Permission.SCAN,
            Permission.PLAN,
            Permission.EXECUTE,
            Permission.CREATE_PR,
            Permission.VIEW_REPORTS,
            Permission.VIEW_AUDIT_LOGS,
            Permission.APPROVE_PLANS,
            Permission.APPROVE_PRS,
        ],
    ),
    RBACPolicy(
        role=Role.CONTRIBUTOR,
        permissions=[
            Permission.SCAN,
            Permission.PLAN,
            Permission.EXECUTE,
            Permission.CREATE_PR,
            Permission.VIEW_REPORTS,
            Permission.APPROVE_PRS,
        ],
    ),
    RBACPolicy(
        role=Role.DEVELOPER,
        permissions=[
            Permission.SCAN,
            Permission.PLAN,
            Permission.VIEW_REPORTS,
        ],
    ),
    RBACPolicy(
        role=Role.VIEWER,
        permissions=[Permission.VIEW_REPORTS],
    ),
]


def check_permission(role: Role, permission: Permission) -> bool:
    """Check if a role has a specific permission."""
    for policy in DEFAULT_POLICIES:
        if policy.role == role:
            return permission in policy.permissions
    return False


class RBACManager:
    """Centralized RBAC enforcement with optional Azure AD (FR-SEC-101).

    Supports:
    - Static role lookup from ``DEFAULT_POLICIES``
    - Azure AD JWT claim decoding (when ``azure-identity`` is installed)
    - Per-repo scope enforcement
    - Audit-log integration
    """

    def __init__(
        self,
        policies: list[RBACPolicy] | None = None,
        *,
        tenant_id: str = "",
    ) -> None:
        self.policies = {p.role: p for p in (policies or DEFAULT_POLICIES)}
        self.tenant_id = tenant_id

    def has_permission(
        self,
        user: UserContext,
        permission: Permission,
        *,
        repo: str = "",
    ) -> bool:
        """Check if ``user`` has ``permission``, optionally scoped to ``repo``.

        Args:
            user: Authenticated user context.
            permission: The permission to check.
            repo: Optional repo scope (``owner/name``).

        Returns:
            ``True`` if permitted.
        """
        # Scope check
        if repo and user.scoped_repos and repo not in user.scoped_repos:
            logger.warning(
                "User %s denied access to repo %s (not in scoped_repos)",
                user.user_id,
                repo,
            )
            return False

        policy = self.policies.get(user.role)
        if not policy:
            return False
        allowed = permission in policy.permissions
        if not allowed:
            logger.info(
                "User %s (%s) denied permission %s",
                user.user_id,
                user.role.value,
                permission.value,
            )
        return allowed

    def require_permission(
        self,
        user: UserContext,
        permission: Permission,
        *,
        repo: str = "",
    ) -> None:
        """Raise ``PermissionError`` if the user lacks the permission."""
        if not self.has_permission(user, permission, repo=repo):
            raise PermissionError(
                f"User {user.user_id} ({user.role.value}) lacks "
                f"permission '{permission.value}'" + (f" on repo {repo}" if repo else "")
            )

    def user_from_claims(self, claims: dict[str, Any]) -> UserContext:
        """Build a ``UserContext`` from Azure AD JWT claims (FR-SEC-102).

        Expected claims:
        - ``oid`` / ``sub`` → user_id
        - ``preferred_username`` / ``email`` → email
        - ``name`` → display_name
        - ``roles`` → list of role strings (first match wins)
        - ``tid`` → tenant_id
        """
        user_id = claims.get("oid") or claims.get("sub", "unknown")
        email = claims.get("preferred_username") or claims.get("email", "")
        display_name = claims.get("name", "")
        tenant_id = claims.get("tid", "")

        # Map Azure AD roles claim to CodeCustodian Role
        role = Role.VIEWER
        ad_roles = claims.get("roles", [])
        role_map = {r.value: r for r in Role}
        for ad_role in ad_roles:
            normalized = ad_role.lower().replace("-", "_").replace(" ", "_")
            if normalized in role_map:
                role = role_map[normalized]
                break

        return UserContext(
            user_id=user_id,
            email=email,
            display_name=display_name,
            role=role,
            tenant_id=tenant_id,
            claims=claims,
        )
