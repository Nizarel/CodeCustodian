"""Tests for enterprise modules."""

from __future__ import annotations

import tempfile
from pathlib import Path

from codecustodian.enterprise.audit import AuditLogger
from codecustodian.enterprise.rbac import Permission, Role, check_permission
from codecustodian.enterprise.reporting import ReportGenerator
from codecustodian.models import PipelineResult


class TestRBAC:
    def test_admin_has_all_permissions(self):
        for perm in Permission:
            assert check_permission(Role.ADMIN, perm)

    def test_viewer_can_only_view(self):
        assert check_permission(Role.VIEWER, Permission.VIEW_REPORTS)
        assert not check_permission(Role.VIEWER, Permission.EXECUTE)
        assert not check_permission(Role.VIEWER, Permission.CREATE_PR)

    def test_developer_can_scan(self):
        assert check_permission(Role.DEVELOPER, Permission.SCAN)
        assert check_permission(Role.DEVELOPER, Permission.PLAN)
        assert not check_permission(Role.DEVELOPER, Permission.EXECUTE)


class TestAuditLogger:
    def test_log_and_query(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(log_dir=tmpdir)
            logger.log("scan", target="repo/test", findings=5)
            logger.log("execute", target="repo/test", plan_id="p1")

            entries = logger.query()
            assert len(entries) == 2
            assert entries[0].action == "scan"
            assert entries[1].action == "execute"

    def test_query_filter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            logger = AuditLogger(log_dir=tmpdir)
            logger.log("scan", target="repo1")
            logger.log("execute", target="repo2")

            entries = logger.query(action="scan")
            assert len(entries) == 1
            assert entries[0].action == "scan"


class TestReportGenerator:
    def test_generate_markdown(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = ReportGenerator(output_dir=tmpdir)
            result = PipelineResult(total_duration_seconds=5.0)
            report_path = generator.generate_markdown(result)

            assert report_path.exists()
            content = report_path.read_text()
            assert "Tech Debt Report" in content
            assert "Total findings" in content
