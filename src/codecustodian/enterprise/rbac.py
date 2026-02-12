"""Enterprise RBAC (Role-Based Access Control).

Controls access to CodeCustodian features based on
team roles and organizational policies.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel

from codecustodian.logging import get_logger

logger = get_logger("enterprise.rbac")


class Role(str, Enum):
    ADMIN = "admin"
    TEAM_LEAD = "team_lead"
    DEVELOPER = "developer"
    VIEWER = "viewer"


class Permission(str, Enum):
    SCAN = "scan"
    PLAN = "plan"
    EXECUTE = "execute"
    CREATE_PR = "create_pr"
    CONFIGURE = "configure"
    VIEW_REPORTS = "view_reports"


class RBACPolicy(BaseModel):
    """Maps roles to permissions."""

    role: Role
    permissions: list[Permission]


# Default role → permission mapping
DEFAULT_POLICIES: list[RBACPolicy] = [
    RBACPolicy(
        role=Role.ADMIN,
        permissions=list(Permission),
    ),
    RBACPolicy(
        role=Role.TEAM_LEAD,
        permissions=[
            Permission.SCAN,
            Permission.PLAN,
            Permission.EXECUTE,
            Permission.CREATE_PR,
            Permission.VIEW_REPORTS,
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
