"""Phase 7 tests — Azure integrations & enterprise features.

Covers:
- Work IQ context provider (with mocked MCP client)
- Budget manager (cost recording, thresholds, enforcement)
- ROI calculator (recording, report generation)
- Enhanced RBAC (new roles, RBACManager, user_from_claims)
- Multi-tenant isolation
- Approval workflows (request, approve, reject, auto-approve)
- Secrets manager (env fallback, Key Vault mock)
- Notification engine (GitHub, Teams mocks)
"""

from __future__ import annotations

from datetime import UTC
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from codecustodian.models import Finding, FindingType, SeverityLevel

# ═══════════════════════════════════════════════════════════════════════════
# Work IQ Context Provider
# ═══════════════════════════════════════════════════════════════════════════


class TestWorkIQContextProvider:
    @pytest.fixture
    def finding(self) -> Finding:
        return Finding(
            type=FindingType.SECURITY,
            severity=SeverityLevel.HIGH,
            file="src/auth.py",
            line=42,
            description="Hardcoded secret",
        )

    @pytest.fixture
    def provider(self):
        from codecustodian.integrations.work_iq import WorkIQContextProvider

        return WorkIQContextProvider(timeout=5.0)

    async def test_get_expert_fallback(self, provider, finding):
        """When MCP is unreachable, returns empty ExpertResult."""
        result = await provider.get_expert_for_finding(finding)
        assert result.name == ""
        assert result.relevance_score == 0.0

    async def test_get_sprint_context_fallback(self, provider):
        result = await provider.get_sprint_context()
        assert result.sprint_name == ""
        assert result.is_code_freeze is False

    async def test_should_create_pr_now_default(self, provider, finding):
        """Without Work IQ, defaults to True."""
        result = await provider.should_create_pr_now(finding)
        assert result is True

    async def test_get_organizational_context_fallback(self, provider):
        result = await provider.get_organizational_context("auth module")
        assert result.related_documents == []
        assert result.recent_discussions == []

    async def test_get_expert_with_mocked_client(self, provider, finding):
        """Mock the _call_tool method to simulate Work IQ response."""
        provider._call_tool = AsyncMock(
            return_value={
                "name": "Alice Eng",
                "email": "alice@contoso.com",
                "relevance": 0.95,
                "recent_files": ["src/auth.py"],
                "teams": ["Security Team"],
                "available": True,
            }
        )
        result = await provider.get_expert_for_finding(finding)
        assert result.name == "Alice Eng"
        assert result.email == "alice@contoso.com"
        assert result.relevance_score == 0.95
        assert "src/auth.py" in result.recent_files

    async def test_sprint_code_freeze_defers_pr(self, provider, finding):
        """During code freeze, non-critical findings are deferred."""
        provider.get_sprint_context = AsyncMock(
            return_value=MagicMock(
                is_code_freeze=True,
                capacity_pct=50.0,
            )
        )
        # LOW severity code smell should be deferred
        finding.severity = SeverityLevel.LOW
        finding.type = FindingType.CODE_SMELL
        result = await provider.should_create_pr_now(finding)
        assert result is False

    async def test_sprint_freeze_allows_critical_security(self, provider, finding):
        """Critical security findings go through even during freeze."""
        provider.get_sprint_context = AsyncMock(
            return_value=MagicMock(
                is_code_freeze=True,
                capacity_pct=50.0,
            )
        )
        finding.severity = SeverityLevel.CRITICAL
        finding.type = FindingType.SECURITY
        result = await provider.should_create_pr_now(finding)
        assert result is True

    async def test_over_capacity_defers_pr(self, provider, finding):
        """Over 90% capacity defers all PRs."""
        provider.get_sprint_context = AsyncMock(
            return_value=MagicMock(
                is_code_freeze=False,
                capacity_pct=95.0,
            )
        )
        result = await provider.should_create_pr_now(finding)
        assert result is False

    def test_is_available_initially_none(self, provider):
        assert provider.is_available is None

    def test_get_work_iq_mcp_config(self):
        from codecustodian.integrations.work_iq import get_work_iq_mcp_config

        cfg = get_work_iq_mcp_config()
        assert cfg["type"] == "stdio"
        assert cfg["command"] == "npx"
        assert "@microsoft/workiq" in cfg["args"]


# ═══════════════════════════════════════════════════════════════════════════
# Budget Manager
# ═══════════════════════════════════════════════════════════════════════════


class TestBudgetManager:
    @pytest.fixture
    def manager(self, tmp_path: Path):
        from codecustodian.enterprise.budget_manager import BudgetManager

        return BudgetManager(
            monthly_budget=100.0,
            alert_thresholds=[50, 80, 100],
            hard_limit=True,
            data_dir=tmp_path / "costs",
        )

    def test_record_cost(self, manager):
        entry = manager.record_cost("plan", 1.50, run_id="r1")
        assert entry.operation == "plan"
        assert entry.cost_usd == 1.50

    def test_total_tracking(self, manager):
        manager.record_cost("plan", 10.0)
        manager.record_cost("execute", 20.0)
        summary = manager.get_summary()
        assert summary.total_spent == 30.0
        assert summary.remaining == 70.0

    def test_usage_pct(self, manager):
        manager.record_cost("plan", 50.0)
        summary = manager.get_summary()
        assert summary.usage_pct == 50.0

    def test_hard_limit_enforcement(self, manager):
        from codecustodian.exceptions import BudgetExceededError

        manager.record_cost("plan", 95.0)
        with pytest.raises(BudgetExceededError) as exc_info:
            manager.check_budget(estimated_cost=10.0)
        assert exc_info.value.current_cost == 95.0
        assert exc_info.value.budget_limit == 100.0

    def test_within_budget(self, manager):
        manager.record_cost("plan", 10.0)
        assert manager.check_budget(estimated_cost=5.0) is True

    def test_threshold_alerts(self, manager):
        manager.record_cost("plan", 55.0)
        alerts = manager.get_alerts()
        assert any(a.threshold_pct == 50 for a in alerts)

    def test_persistence_reload(self, tmp_path: Path):
        from codecustodian.enterprise.budget_manager import BudgetManager

        data_dir = tmp_path / "costs"
        mgr1 = BudgetManager(monthly_budget=100.0, data_dir=data_dir)
        mgr1.record_cost("plan", 42.0)

        # New instance should reload the total
        mgr2 = BudgetManager(monthly_budget=100.0, data_dir=data_dir)
        assert mgr2._total_spent == 42.0

    def test_from_config(self):
        from codecustodian.config.schema import BudgetConfig
        from codecustodian.enterprise.budget_manager import BudgetManager

        cfg = BudgetConfig(monthly_budget=200.0, alert_thresholds=[25, 75])
        mgr = BudgetManager.from_config(cfg)
        assert mgr.monthly_budget == 200.0
        assert mgr.alert_thresholds == [25, 75]

    def test_entries_count(self, manager):
        manager.record_cost("plan", 1.0)
        manager.record_cost("execute", 2.0)
        manager.record_cost("verify", 0.5)
        summary = manager.get_summary()
        assert summary.entries_count == 3


# ═══════════════════════════════════════════════════════════════════════════
# ROI Calculator
# ═══════════════════════════════════════════════════════════════════════════


class TestROICalculator:
    @pytest.fixture
    def calculator(self, tmp_path: Path):
        from codecustodian.enterprise.roi_calculator import ROICalculator

        return ROICalculator(
            hourly_rate=100.0,
            data_dir=tmp_path / "roi",
        )

    def test_record_entry(self, calculator):
        entry = calculator.record(
            finding_type="security",
            severity="high",
            ai_cost_usd=0.05,
            run_id="run1",
        )
        assert entry.finding_type == "security"
        assert entry.ai_cost_usd == 0.05
        assert entry.estimated_manual_hours == 3.0  # default for security

    def test_report_single_fix(self, calculator):
        calculator.record("deprecated_api", "high", 0.10)
        report = calculator.generate_report()
        assert report.total_fixes == 1
        assert report.successful_fixes == 1
        assert report.total_ai_cost == 0.10
        assert report.total_hours_saved == 2.0  # deprecated_api default
        assert report.estimated_savings_usd == 200.0  # 2h * $100
        assert report.net_roi_pct > 0

    def test_report_by_type_breakdown(self, calculator):
        calculator.record("security", "high", 0.05)
        calculator.record("security", "critical", 0.08)
        calculator.record("todo_comment", "low", 0.01)
        report = calculator.generate_report()
        assert "security" in report.by_finding_type
        assert "todo_comment" in report.by_finding_type
        assert report.by_finding_type["security"]["count"] == 2

    def test_failed_fix_excluded_from_hours(self, calculator):
        calculator.record("security", "high", 0.05, was_successful=False)
        report = calculator.generate_report()
        assert report.total_hours_saved == 0.0
        assert report.successful_fixes == 0

    def test_empty_report(self, calculator):
        report = calculator.generate_report()
        assert report.total_fixes == 0
        assert report.net_roi_pct == 0.0


# ═══════════════════════════════════════════════════════════════════════════
# Enhanced RBAC
# ═══════════════════════════════════════════════════════════════════════════


class TestEnhancedRBAC:
    def test_new_roles_exist(self):
        from codecustodian.enterprise.rbac import Role

        assert Role.SECURITY_ADMIN.value == "security_admin"
        assert Role.CONTRIBUTOR.value == "contributor"

    def test_new_permissions_exist(self):
        from codecustodian.enterprise.rbac import Permission

        assert Permission.OVERRIDE_SECURITY.value == "override_security"
        assert Permission.VIEW_AUDIT_LOGS.value == "view_audit_logs"
        assert Permission.APPROVE_PLANS.value == "approve_plans"
        assert Permission.APPROVE_PRS.value == "approve_prs"

    def test_security_admin_permissions(self):
        from codecustodian.enterprise.rbac import Permission, Role, check_permission

        assert check_permission(Role.SECURITY_ADMIN, Permission.OVERRIDE_SECURITY)
        assert check_permission(Role.SECURITY_ADMIN, Permission.VIEW_AUDIT_LOGS)
        assert check_permission(Role.SECURITY_ADMIN, Permission.APPROVE_PLANS)
        assert not check_permission(Role.SECURITY_ADMIN, Permission.EXECUTE)

    def test_contributor_permissions(self):
        from codecustodian.enterprise.rbac import Permission, Role, check_permission

        assert check_permission(Role.CONTRIBUTOR, Permission.SCAN)
        assert check_permission(Role.CONTRIBUTOR, Permission.EXECUTE)
        assert check_permission(Role.CONTRIBUTOR, Permission.CREATE_PR)
        assert not check_permission(Role.CONTRIBUTOR, Permission.APPROVE_PLANS)

    def test_admin_has_all_new_permissions(self):
        from codecustodian.enterprise.rbac import Permission, Role, check_permission

        for perm in Permission:
            assert check_permission(Role.ADMIN, perm), f"Admin missing {perm}"

    def test_rbac_manager_has_permission(self):
        from codecustodian.enterprise.rbac import Permission, RBACManager, Role, UserContext

        mgr = RBACManager()
        user = UserContext(user_id="u1", role=Role.DEVELOPER)
        assert mgr.has_permission(user, Permission.SCAN)
        assert not mgr.has_permission(user, Permission.EXECUTE)

    def test_rbac_manager_require_permission_raises(self):
        from codecustodian.enterprise.rbac import Permission, RBACManager, Role, UserContext

        mgr = RBACManager()
        user = UserContext(user_id="u1", role=Role.VIEWER)
        with pytest.raises(PermissionError, match="lacks permission"):
            mgr.require_permission(user, Permission.EXECUTE)

    def test_rbac_manager_scoped_repos(self):
        from codecustodian.enterprise.rbac import Permission, RBACManager, Role, UserContext

        mgr = RBACManager()
        user = UserContext(
            user_id="u1",
            role=Role.ADMIN,
            scoped_repos=["owner/repo1"],
        )
        assert mgr.has_permission(user, Permission.EXECUTE, repo="owner/repo1")
        assert not mgr.has_permission(user, Permission.EXECUTE, repo="owner/repo2")

    def test_user_from_claims(self):
        from codecustodian.enterprise.rbac import RBACManager, Role

        mgr = RBACManager()
        claims = {
            "oid": "user-123",
            "preferred_username": "alice@contoso.com",
            "name": "Alice",
            "tid": "tenant-abc",
            "roles": ["team_lead"],
        }
        user = mgr.user_from_claims(claims)
        assert user.user_id == "user-123"
        assert user.email == "alice@contoso.com"
        assert user.role == Role.TEAM_LEAD
        assert user.tenant_id == "tenant-abc"

    def test_user_from_claims_unknown_role(self):
        from codecustodian.enterprise.rbac import RBACManager, Role

        mgr = RBACManager()
        claims = {"oid": "u2", "roles": ["unknown_role"]}
        user = mgr.user_from_claims(claims)
        assert user.role == Role.VIEWER  # fallback


# ═══════════════════════════════════════════════════════════════════════════
# Multi-Tenant
# ═══════════════════════════════════════════════════════════════════════════


class TestMultiTenant:
    @pytest.fixture
    def manager(self, tmp_path: Path):
        from codecustodian.enterprise.multi_tenant import MultiTenantManager

        return MultiTenantManager(data_root=tmp_path / "tenants")

    def test_register_tenant(self, manager):
        from codecustodian.enterprise.multi_tenant import TenantConfig

        cfg = TenantConfig(tenant_id="t1", display_name="Contoso")
        manager.register_tenant(cfg)
        assert manager.get_tenant_config("t1").display_name == "Contoso"

    def test_get_tenant_dirs(self, manager):
        dirs = manager.get_tenant_dirs("t2")
        assert Path(dirs.audit).exists()
        assert Path(dirs.costs).exists()
        assert Path(dirs.roi).exists()
        assert Path(dirs.feedback).exists()

    def test_tenant_isolation(self, manager):
        dirs1 = manager.get_tenant_dirs("t1")
        dirs2 = manager.get_tenant_dirs("t2")
        assert dirs1.root != dirs2.root
        assert "t1" in dirs1.root
        assert "t2" in dirs2.root

    def test_list_tenants(self, manager):
        from codecustodian.enterprise.multi_tenant import TenantConfig

        manager.register_tenant(TenantConfig(tenant_id="a"))
        manager.register_tenant(TenantConfig(tenant_id="b"))
        tenants = manager.list_tenants()
        ids = {t.tenant_id for t in tenants}
        assert ids == {"a", "b"}

    def test_default_config_for_unknown_tenant(self, manager):
        cfg = manager.get_tenant_config("unknown")
        assert cfg.tenant_id == "unknown"
        assert cfg.enabled is True

    def test_is_tenant_enabled(self, manager):
        from codecustodian.enterprise.multi_tenant import TenantConfig

        manager.register_tenant(TenantConfig(tenant_id="disabled", enabled=False))
        assert manager.is_tenant_enabled("disabled") is False
        assert manager.is_tenant_enabled("unknown") is True


# ═══════════════════════════════════════════════════════════════════════════
# Approval Workflows
# ═══════════════════════════════════════════════════════════════════════════


class TestApprovalWorkflows:
    @pytest.fixture
    def manager(self, tmp_path: Path):
        from codecustodian.enterprise.approval_workflows import ApprovalWorkflowManager

        return ApprovalWorkflowManager(
            require_plan_approval=True,
            require_pr_approval=True,
            approved_repos=["owner/safe-repo"],
            sensitive_paths=["**/auth/**", "**/payments/**"],
            data_dir=tmp_path / "approvals",
        )

    def test_request_approval(self, manager):
        req = manager.request_approval("plan-1", "plan")
        assert req.resource_id == "plan-1"
        assert req.status.value == "pending"

    def test_approve(self, manager):
        req = manager.request_approval("plan-1", "plan")
        approved = manager.approve(req.id, "alice@contoso.com")
        assert approved.status.value == "approved"
        assert approved.approver == "alice@contoso.com"

    def test_reject(self, manager):
        req = manager.request_approval("plan-2", "plan")
        rejected = manager.reject(req.id, "bob@contoso.com", reason="Too risky")
        assert rejected.status.value == "rejected"
        assert rejected.reason == "Too risky"

    def test_is_approved(self, manager):
        req = manager.request_approval("plan-3", "plan")
        assert not manager.is_approved("plan-3")
        manager.approve(req.id, "admin")
        assert manager.is_approved("plan-3")

    def test_needs_approval_plan(self, manager):
        assert manager.needs_approval("plan") is True

    def test_needs_approval_auto_approved_repo(self, manager):
        assert manager.needs_approval("plan", repo="owner/safe-repo") is False

    def test_needs_approval_sensitive_path(self, manager):
        assert (
            manager.needs_approval("plan", repo="owner/safe-repo", file_path="src/auth/login.py")
            is True
        )

    def test_get_pending(self, manager):
        manager.request_approval("a", "plan")
        manager.request_approval("b", "pr")
        req_c = manager.request_approval("c", "plan")
        manager.approve(req_c.id, "admin")
        pending = manager.get_pending()
        assert len(pending) == 2

    def test_auto_approve(self, manager):
        req = manager.auto_approve("plan-x", "plan", reason="Pre-approved repo")
        assert req.status.value == "auto_approved"
        assert manager.is_approved("plan-x")

    def test_persistence(self, tmp_path: Path):
        from codecustodian.enterprise.approval_workflows import ApprovalWorkflowManager

        data_dir = tmp_path / "approvals"
        mgr1 = ApprovalWorkflowManager(data_dir=data_dir)
        req = mgr1.request_approval("p1", "plan")
        mgr1.approve(req.id, "admin")

        # New instance should reload
        mgr2 = ApprovalWorkflowManager(data_dir=data_dir)
        assert mgr2.is_approved("p1")

    def test_approve_nonexistent_raises(self, manager):
        with pytest.raises(ValueError, match="not found"):
            manager.approve("nonexistent", "admin")

    def test_from_config(self):
        from codecustodian.config.schema import ApprovalConfig
        from codecustodian.enterprise.approval_workflows import ApprovalWorkflowManager

        cfg = ApprovalConfig(
            require_plan_approval=True,
            approved_repos=["owner/repo1"],
        )
        mgr = ApprovalWorkflowManager.from_config(cfg)
        assert mgr.require_plan_approval is True
        assert "owner/repo1" in mgr.approved_repos


# ═══════════════════════════════════════════════════════════════════════════
# Secrets Manager
# ═══════════════════════════════════════════════════════════════════════════


class TestSecretsManager:
    @pytest.fixture
    def manager(self):
        from codecustodian.enterprise.secrets_manager import SecretsManager

        return SecretsManager()  # no vault_name — pure env fallback

    async def test_get_secret_from_env(self, manager, monkeypatch):
        monkeypatch.setenv("MY_SECRET", "s3cret")
        value = await manager.get_secret("MY_SECRET")
        assert value == "s3cret"

    async def test_get_secret_missing(self, manager, monkeypatch):
        monkeypatch.delenv("NONEXISTENT", raising=False)
        value = await manager.get_secret("NONEXISTENT")
        assert value == ""

    async def test_set_secret_without_vault_returns_env_source(self, manager):
        info = await manager.set_secret("test", "value")
        assert info.source == "env"

    async def test_list_secrets_without_vault(self, manager):
        result = await manager.list_secrets()
        assert result == []

    async def test_check_rotation_without_vault(self, manager):
        result = await manager.check_rotation_status()
        assert result == []

    async def test_keyvault_client_mock(self):
        from codecustodian.enterprise.secrets_manager import SecretsManager

        sm = SecretsManager()
        mock_secret = MagicMock()
        mock_secret.value = "vault-value"
        mock_secret.properties.updated_on = None

        sm._client = MagicMock()
        sm._client.get_secret.return_value = mock_secret

        value = await sm.get_secret("KV_SECRET")
        assert value == "vault-value"
        sm._client.get_secret.assert_called_once_with("KV_SECRET")

    def test_days_since_update(self):
        from datetime import datetime

        from codecustodian.enterprise.secrets_manager import SecretsManager

        days = SecretsManager._days_since_update(None)
        assert days == -1

        now = datetime.now(UTC)
        days = SecretsManager._days_since_update(now)
        assert days == 0


# ═══════════════════════════════════════════════════════════════════════════
# Notification Engine
# ═══════════════════════════════════════════════════════════════════════════


class TestNotificationEngine:
    @pytest.fixture
    def engine(self):
        from codecustodian.intelligence.notifications import NotificationEngine

        return NotificationEngine(
            github_token="ghp_test",
            teams_webhook_url="https://outlook.office.com/webhook/test",
            severity_threshold="medium",
            enabled_events=["pr_created", "pipeline_failed", "budget_alert"],
        )

    async def test_severity_filter_skips_low(self, engine):
        result = await engine.notify(event="pr_created", severity="info", title="Low priority")
        assert result.channels_attempted == []

    async def test_event_filter_skips_unknown(self, engine):
        result = await engine.notify(event="unknown_event", severity="high", title="Test")
        assert result.channels_attempted == []

    async def test_teams_notification_mock(self, engine):
        """Mock httpx to verify Teams Adaptive Card is sent."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as MockClient:  # noqa: N806
            mock_client_instance = AsyncMock()
            mock_client_instance.post = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client_instance

            result = await engine.notify(
                event="pipeline_failed",
                severity="high",
                title="Pipeline Failed",
                body="Error in scan stage",
            )
            assert "teams" in result.channels_succeeded
            mock_client_instance.post.assert_called_once()

    async def test_github_notification_mock(self, engine):
        """Mock PyGithub to verify comment is posted."""
        mock_pr = MagicMock()
        mock_repo = MagicMock()
        mock_repo.get_pull.return_value = mock_pr
        mock_gh = MagicMock()
        mock_gh.get_repo.return_value = mock_repo

        with patch("github.Github", return_value=mock_gh):
            result = await engine.notify(
                event="pr_created",
                severity="high",
                title="PR Created",
                body="New PR for auth fix",
                metadata={"pr_number": 42, "repo": "owner/repo"},
            )
            assert "github" in result.channels_succeeded
            mock_pr.create_issue_comment.assert_called_once()

    async def test_github_skipped_without_pr_metadata(self):
        from codecustodian.intelligence.notifications import NotificationEngine

        engine = NotificationEngine(
            github_token="ghp_test",
            severity_threshold="low",
        )
        # No teams_webhook_url, no pr_number in metadata
        result = await engine.notify(
            event="budget_alert",
            severity="high",
            title="Budget Warning",
        )
        assert "github" not in result.channels_attempted

    def test_severity_ordering(self):
        from codecustodian.intelligence.notifications import NotificationEngine

        engine = NotificationEngine(severity_threshold="high")
        assert engine._passes_severity("critical") is True
        assert engine._passes_severity("high") is True
        assert engine._passes_severity("medium") is False
        assert engine._passes_severity("low") is False

    def test_get_history(self):
        from codecustodian.intelligence.notifications import NotificationEngine

        engine = NotificationEngine()
        assert engine.get_history() == []

    def test_adaptive_card_structure(self):
        from codecustodian.intelligence.notifications import (
            NotificationEngine,
            NotificationEvent,
        )

        engine = NotificationEngine()
        evt = NotificationEvent(
            event="test",
            severity="high",
            title="Test Card",
            body="Test body",
        )
        card = engine._build_adaptive_card(evt)
        assert card["type"] == "AdaptiveCard"
        assert card["version"] == "1.4"
        assert len(card["body"]) == 3


# ═══════════════════════════════════════════════════════════════════════════
# Integration: __init__ exports
# ═══════════════════════════════════════════════════════════════════════════


class TestPackageExports:
    def test_enterprise_exports(self):
        from codecustodian.enterprise import (
            Role,
        )

        # Just verify they're all importable
        assert Role.ADMIN.value == "admin"

    def test_intelligence_exports(self):
        from codecustodian.intelligence import (
            NotificationEngine,
        )

        assert NotificationEngine is not None

    def test_integrations_exports(self):
        from codecustodian.integrations import (
            WorkIQContextProvider,
        )

        assert WorkIQContextProvider is not None
