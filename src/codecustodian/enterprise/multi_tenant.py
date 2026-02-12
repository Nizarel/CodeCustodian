"""Multi-tenant isolation for enterprise deployments (FR-SEC-102).

Ensures that each Azure AD tenant's data (findings, PRs, audit logs,
cost records) is isolated.  Uses a tenant-scoped directory layout:

    .codecustodian-data/<tenant_id>/audit/
    .codecustodian-data/<tenant_id>/costs/
    .codecustodian-data/<tenant_id>/roi/

Usage::

    mgr = MultiTenantManager(data_root=".codecustodian-data")
    tenant_cfg = mgr.get_tenant_config("contoso-tenant-id")
    dirs = mgr.get_tenant_dirs("contoso-tenant-id")
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from codecustodian.logging import get_logger

logger = get_logger("enterprise.multi_tenant")


# ── Models ─────────────────────────────────────────────────────────────────


class TenantConfig(BaseModel):
    """Per-tenant configuration overrides."""

    tenant_id: str
    display_name: str = ""
    enabled: bool = True
    allowed_repos: list[str] = Field(default_factory=list)
    monthly_budget: float = 500.0
    max_prs_per_run: int = 5
    require_approval: bool = True
    custom_settings: dict[str, Any] = Field(default_factory=dict)


class TenantDirs(BaseModel):
    """Resolved directory paths for a tenant's isolated data."""

    root: str
    audit: str
    costs: str
    roi: str
    feedback: str


# ── Manager ────────────────────────────────────────────────────────────────


class MultiTenantManager:
    """Manage tenant isolation for enterprise deployments (FR-SEC-102).

    Each tenant gets isolated data directories and optional config
    overrides.  The manager does NOT handle authentication — that is
    handled by ``RBACManager.user_from_claims()``.

    Args:
        data_root: Base directory for all tenant data.
        tenants: Pre-loaded tenant configs (optional; can be added later).
    """

    def __init__(
        self,
        data_root: str | Path = ".codecustodian-data",
        tenants: list[TenantConfig] | None = None,
    ) -> None:
        self.data_root = Path(data_root)
        self._tenants: dict[str, TenantConfig] = {}
        for t in tenants or []:
            self._tenants[t.tenant_id] = t

    # ── Tenant registration ────────────────────────────────────────────

    def register_tenant(self, config: TenantConfig) -> None:
        """Register or update a tenant configuration."""
        self._tenants[config.tenant_id] = config
        self._ensure_dirs(config.tenant_id)
        logger.info("Tenant registered: %s (%s)", config.tenant_id, config.display_name)

    def get_tenant_config(self, tenant_id: str) -> TenantConfig:
        """Return the config for a tenant, creating a default if needed."""
        if tenant_id not in self._tenants:
            self._tenants[tenant_id] = TenantConfig(tenant_id=tenant_id)
        return self._tenants[tenant_id]

    def list_tenants(self) -> list[TenantConfig]:
        """Return all registered tenants."""
        return list(self._tenants.values())

    # ── Directory isolation ────────────────────────────────────────────

    def get_tenant_dirs(self, tenant_id: str) -> TenantDirs:
        """Return isolated directory paths for a tenant.

        Creates directories on disk if they don't exist.
        """
        self._ensure_dirs(tenant_id)
        root = self.data_root / tenant_id
        return TenantDirs(
            root=str(root),
            audit=str(root / "audit"),
            costs=str(root / "costs"),
            roi=str(root / "roi"),
            feedback=str(root / "feedback"),
        )

    def is_tenant_enabled(self, tenant_id: str) -> bool:
        """Check if a tenant is enabled."""
        cfg = self._tenants.get(tenant_id)
        return cfg.enabled if cfg else True  # Default to enabled for unknown

    # ── Internal ───────────────────────────────────────────────────────

    def _ensure_dirs(self, tenant_id: str) -> None:
        """Create tenant data directories if they don't exist."""
        root = self.data_root / tenant_id
        for sub in ("audit", "costs", "roi", "feedback"):
            (root / sub).mkdir(parents=True, exist_ok=True)
