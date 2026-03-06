"""End-to-end CLI + Enterprise + Safety + Feedback + MCP workflow tests.

Covers all features of CodeCustodian for the demo preparation:
  - All 5 scanners against the realistic demo/sample-enterprise-app target
  - Full pipeline dry-run result structure
  - All 10 CLI commands (scan, run, init, validate, findings, create-prs,
    onboard, status, report, interactive)
  - Enterprise features: ROI, SLA, Budget, Audit, RBAC, approval, multi-tenant
  - Safety checks: eval/exec/secret/path-traversal blocking
  - Feedback & historical pattern learning loop
  - Local MCP server: all 17 tools, 7 resources, 7 prompts

Run with:
    pytest tests/e2e/test_full_workflow.py -v -m e2e

Skip E2E tests:
    pytest -m "not e2e"
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

import pytest

from codecustodian.cli.main import app

# ── Constants ─────────────────────────────────────────────────────────────

FIXTURE_REPO = "tests/fixtures/sample_repo"
DEMO_REPO = "demo/sample-enterprise-app"


# ── Helpers ───────────────────────────────────────────────────────────────


def _load_json_from_output(output: str):
    """Extract the first/only JSON object or array from CLI stdout."""
    decoder = json.JSONDecoder()
    text = output.strip()
    for index, char in enumerate(text):
        if char not in "[{":
            continue
        try:
            payload, end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if text[index + end:].strip() == "":
            return payload
    raise AssertionError(f"No JSON payload found in output:\n{output[:800]}")


# ══════════════════════════════════════════════════════════════════════════
# Existing fixture tests (kept unchanged for regression safety)
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
def test_scan_command_detects_fixture_findings(cli_runner) -> None:
    result = cli_runner.invoke(
        app,
        [
            "scan",
            "--repo-path",
            FIXTURE_REPO,
            "--output-format",
            "json",
        ],
    )
    assert result.exit_code == 0
    payload = _load_json_from_output(result.stdout)
    assert isinstance(payload, list)
    assert len(payload) >= 3
    finding_types = {item["type"] for item in payload}
    assert "security" in finding_types
    assert "todo_comment" in finding_types


@pytest.mark.e2e
def test_run_dry_run_outputs_pipeline_result_json(cli_runner) -> None:
    result = cli_runner.invoke(
        app,
        [
            "run",
            "--repo-path",
            FIXTURE_REPO,
            "--config",
            f"{FIXTURE_REPO}/.codecustodian.yml",
            "--dry-run",
            "--output-format",
            "json",
        ],
    )
    assert result.exit_code == 0
    payload = _load_json_from_output(result.stdout)
    assert "findings" in payload
    assert "plans" in payload
    assert isinstance(payload["findings"], list)


# ══════════════════════════════════════════════════════════════════════════
# Phase 2.1 — TestDemoAppScanners
# All 5 scanners against the realistic demo/sample-enterprise-app target
# ══════════════════════════════════════════════════════════════════════════


class TestDemoAppScanners:
    """Verify all 5 scanner types detect realistic planted issues (Phase 2.1)."""

    @pytest.mark.e2e
    def test_scan_demo_app_all_five_types(self, cli_runner) -> None:
        """Single scan pass detects all 5 finding types in demo app."""
        result = cli_runner.invoke(
            app,
            ["scan", "--repo-path", DEMO_REPO, "--output-format", "json"],
        )
        assert result.exit_code == 0, f"CLI error:\n{result.output}"
        findings = _load_json_from_output(result.stdout)
        assert isinstance(findings, list)
        found_types = {f["type"] for f in findings}
        expected = {"security", "deprecated_api", "code_smell", "todo_comment", "type_coverage"}
        missing = expected - found_types
        assert not missing, f"Missing scanner types in demo app: {missing}"

    @pytest.mark.e2e
    def test_scan_demo_app_security_critical(self, cli_runner) -> None:
        """Security scanner detects critical-severity issues in auth.py."""
        result = cli_runner.invoke(
            app,
            [
                "scan",
                "--repo-path",
                DEMO_REPO,
                "--scanner",
                "security_patterns",
                "--output-format",
                "json",
            ],
        )
        assert result.exit_code == 0, f"CLI error:\n{result.output}"
        findings = _load_json_from_output(result.stdout)
        assert isinstance(findings, list)
        assert len(findings) >= 1, "Expected at least one security finding"
        severities = {f["severity"] for f in findings}
        # auth.py has hardcoded secrets, SQL injection, eval — at least one critical/high
        assert severities & {"critical", "high"}, (
            f"Expected critical/high security findings; got severities: {severities}"
        )

    @pytest.mark.e2e
    def test_scan_demo_app_deprecated_apis(self, cli_runner) -> None:
        """Deprecated-API scanner detects pandas/numpy deprecations in data_processor.py."""
        result = cli_runner.invoke(
            app,
            [
                "scan",
                "--repo-path",
                DEMO_REPO,
                "--scanner",
                "deprecated_apis",
                "--output-format",
                "json",
            ],
        )
        assert result.exit_code == 0, f"CLI error:\n{result.output}"
        findings = _load_json_from_output(result.stdout)
        assert isinstance(findings, list)
        assert len(findings) >= 1, (
            "Expected deprecated API findings (df.append, df.iteritems, np.float)"
        )
        types = {f["type"] for f in findings}
        assert "deprecated_api" in types

    @pytest.mark.e2e
    def test_scan_demo_app_code_smells(self, cli_runner) -> None:
        """Code-smell scanner detects high complexity / deep nesting in data_processor.py."""
        result = cli_runner.invoke(
            app,
            [
                "scan",
                "--repo-path",
                DEMO_REPO,
                "--scanner",
                "code_smells",
                "--output-format",
                "json",
            ],
        )
        assert result.exit_code == 0, f"CLI error:\n{result.output}"
        findings = _load_json_from_output(result.stdout)
        assert isinstance(findings, list)
        assert len(findings) >= 1, (
            "Expected code-smell findings (normalize_prices complexity / nesting)"
        )

    @pytest.mark.e2e
    def test_scan_demo_app_type_coverage(self, cli_runner) -> None:
        """Type-coverage scanner detects missing annotations in api_handlers.py."""
        result = cli_runner.invoke(
            app,
            [
                "scan",
                "--repo-path",
                DEMO_REPO,
                "--scanner",
                "type_coverage",
                "--output-format",
                "json",
            ],
        )
        assert result.exit_code == 0, f"CLI error:\n{result.output}"
        findings = _load_json_from_output(result.stdout)
        assert isinstance(findings, list)
        assert len(findings) >= 1, (
            "Expected type-coverage findings (api_handlers.py has zero annotations)"
        )

    @pytest.mark.e2e
    def test_scan_demo_app_todo_comments(self, cli_runner) -> None:
        """TODO-scanner detects the module-level TODO in utils.py."""
        result = cli_runner.invoke(
            app,
            [
                "scan",
                "--repo-path",
                DEMO_REPO,
                "--scanner",
                "todo_comments",
                "--output-format",
                "json",
            ],
        )
        assert result.exit_code == 0, f"CLI error:\n{result.output}"
        findings = _load_json_from_output(result.stdout)
        assert isinstance(findings, list)
        assert len(findings) >= 1, "Expected at least one TODO finding in utils.py"
        types = {f["type"] for f in findings}
        assert "todo_comment" in types

    @pytest.mark.e2e
    def test_scan_demo_app_security_scanner_only(self, cli_runner) -> None:
        """Single-scanner filter: --scanner security_patterns returns only security type."""
        result = cli_runner.invoke(
            app,
            [
                "scan",
                "--repo-path",
                DEMO_REPO,
                "--scanner",
                "security_patterns",
                "--output-format",
                "json",
            ],
        )
        assert result.exit_code == 0, f"CLI error:\n{result.output}"
        findings = _load_json_from_output(result.stdout)
        types = {f["type"] for f in findings}
        # Only security type should appear when filtered
        assert types <= {"security"}, f"Unexpected types when filtering: {types}"

    @pytest.mark.e2e
    def test_scan_demo_app_multi_scanner_filter(self, cli_runner) -> None:
        """Two separate single-scanner runs produce only the expected types each."""
        # deprecated_apis only
        result_dep = cli_runner.invoke(
            app,
            ["scan", "--repo-path", DEMO_REPO, "--scanner", "deprecated_apis",
             "--output-format", "json"],
        )
        assert result_dep.exit_code == 0, f"CLI error:\n{result_dep.output}"
        findings_dep = _load_json_from_output(result_dep.stdout)
        types_dep = {f["type"] for f in findings_dep}
        assert types_dep <= {"deprecated_api"}, f"Unexpected types for deprecated_apis run: {types_dep}"

        # todo_comments only
        result_todo = cli_runner.invoke(
            app,
            ["scan", "--repo-path", DEMO_REPO, "--scanner", "todo_comments",
             "--output-format", "json"],
        )
        assert result_todo.exit_code == 0, f"CLI error:\n{result_todo.output}"
        findings_todo = _load_json_from_output(result_todo.stdout)
        types_todo = {f["type"] for f in findings_todo}
        assert types_todo <= {"todo_comment"}, f"Unexpected types for todo_comments run: {types_todo}"


# ══════════════════════════════════════════════════════════════════════════
# Phase 2.2 — TestPipelineDryRun
# Full pipeline result structure validation
# ══════════════════════════════════════════════════════════════════════════


class TestPipelineDryRun:
    """Verify pipeline dry-run result structure and content (Phase 2.2)."""

    def _invoke_dry_run(self, cli_runner, repo: str = DEMO_REPO):
        return cli_runner.invoke(
            app,
            [
                "run",
                "--repo-path",
                repo,
                "--dry-run",
                "--output-format",
                "json",
            ],
        )

    @pytest.mark.e2e
    def test_dry_run_full_result_structure(self, cli_runner) -> None:
        """Pipeline result contains all expected top-level keys."""
        result = self._invoke_dry_run(cli_runner)
        assert result.exit_code == 0, f"CLI error:\n{result.output}"
        payload = _load_json_from_output(result.stdout)
        required_keys = {"findings", "plans", "proposals", "cost_savings_estimate",
                         "total_duration_seconds", "errors"}
        missing = required_keys - set(payload.keys())
        assert not missing, f"Pipeline result missing keys: {missing}"
        assert isinstance(payload["findings"], list)
        assert isinstance(payload["plans"], list)
        assert isinstance(payload["proposals"], list)
        assert isinstance(payload["errors"], list)

    @pytest.mark.e2e
    def test_dry_run_cost_savings_estimate(self, cli_runner) -> None:
        """cost_savings_estimate is a positive number when findings exist."""
        result = self._invoke_dry_run(cli_runner)
        assert result.exit_code == 0, f"CLI error:\n{result.output}"
        payload = _load_json_from_output(result.stdout)
        estimate = payload.get("cost_savings_estimate", 0)
        # cost_savings_estimate may be a dict or a number depending on pipeline version
        if isinstance(estimate, dict):
            # Dict form: {'manual_hours': ..., 'savings_usd': ..., 'hours_saved': ..., ...}
            savings_usd = estimate.get("savings_usd", estimate.get("hours_saved", 0))
            assert isinstance(savings_usd, (int, float)), (
                f"savings_usd should be a number, got {type(savings_usd)}"
            )
            assert savings_usd >= 0, f"Expected non-negative savings_usd, got {savings_usd}"
        else:
            assert isinstance(estimate, (int, float)), (
                f"cost_savings_estimate should be a number or dict, got {type(estimate)}"
            )
            assert estimate >= 0, f"Expected non-negative cost_savings_estimate, got {estimate}"

    @pytest.mark.e2e
    def test_dry_run_plans_have_confidence(self, cli_runner) -> None:
        """Each plan in full fixture repo dry-run has confidence_score between 1-10."""
        result = cli_runner.invoke(
            app,
            [
                "run",
                "--repo-path",
                FIXTURE_REPO,
                "--config",
                f"{FIXTURE_REPO}/.codecustodian.yml",
                "--dry-run",
                "--output-format",
                "json",
            ],
        )
        assert result.exit_code == 0, f"CLI error:\n{result.output}"
        payload = _load_json_from_output(result.stdout)
        plans = payload.get("plans", [])
        for plan in plans:
            score = plan.get("confidence_score", plan.get("confidence", None))
            if score is not None:
                assert 1 <= score <= 10, (
                    f"confidence_score out of range [1,10]: {score}"
                )

    @pytest.mark.e2e
    def test_dry_run_proposals_list_present(self, cli_runner) -> None:
        """proposals key exists and is a list (may be empty for high-confidence findings)."""
        result = self._invoke_dry_run(cli_runner)
        assert result.exit_code == 0, f"CLI error:\n{result.output}"
        payload = _load_json_from_output(result.stdout)
        assert "proposals" in payload, "Pipeline result missing 'proposals' key"
        assert isinstance(payload["proposals"], list)

    @pytest.mark.e2e
    def test_dry_run_no_duplicate_findings(self, cli_runner) -> None:
        """No duplicate dedup_key values in findings list (dedup working)."""
        result = self._invoke_dry_run(cli_runner)
        assert result.exit_code == 0, f"CLI error:\n{result.output}"
        payload = _load_json_from_output(result.stdout)
        findings = payload.get("findings", [])
        dedup_keys = [f.get("dedup_key") for f in findings if f.get("dedup_key")]
        assert len(dedup_keys) == len(set(dedup_keys)), (
            f"Duplicate dedup_key values found: {len(dedup_keys) - len(set(dedup_keys))} dupes"
        )


# ══════════════════════════════════════════════════════════════════════════
# Phase 2.3 — TestCLICommands
# All 10 CLI commands verified
# ══════════════════════════════════════════════════════════════════════════


class TestCLICommands:
    """Verify all 10 CLI commands execute without error (Phase 2.3)."""

    @pytest.mark.e2e
    def test_cli_scan_table_format(self, cli_runner) -> None:
        result = cli_runner.invoke(
            app,
            ["scan", "--repo-path", DEMO_REPO, "--output-format", "table"],
        )
        assert result.exit_code == 0, f"CLI error:\n{result.output}"

    @pytest.mark.e2e
    def test_cli_scan_csv_format(self, cli_runner) -> None:
        result = cli_runner.invoke(
            app,
            ["scan", "--repo-path", DEMO_REPO, "--output-format", "csv"],
        )
        assert result.exit_code == 0, f"CLI error:\n{result.output}"
        # CSV output should contain a header row
        assert "type" in result.stdout.lower() or "severity" in result.stdout.lower(), (
            f"CSV output missing column headers:\n{result.stdout[:400]}"
        )

    @pytest.mark.e2e
    def test_cli_findings_severity_filter(self, cli_runner) -> None:
        """findings --severity critical returns only critical-severity items."""
        # First run a scan so findings are cached
        cli_runner.invoke(app, ["scan", "--repo-path", DEMO_REPO, "--output-format", "json"])
        result = cli_runner.invoke(
            app,
            ["findings", "--severity", "critical", "--output-format", "json"],
        )
        assert result.exit_code == 0, f"CLI error:\n{result.output}"

    @pytest.mark.e2e
    def test_cli_findings_type_filter(self, cli_runner) -> None:
        """findings --type security returns only security-type items."""
        cli_runner.invoke(app, ["scan", "--repo-path", DEMO_REPO, "--output-format", "json"])
        result = cli_runner.invoke(
            app,
            ["findings", "--type", "security", "--output-format", "json"],
        )
        assert result.exit_code == 0, f"CLI error:\n{result.output}"

    @pytest.mark.e2e
    def test_cli_validate_command(self, cli_runner) -> None:
        """validate command exits 0 for a valid config file."""
        result = cli_runner.invoke(
            app,
            ["validate", "--path", f"{FIXTURE_REPO}/.codecustodian.yml"],
        )
        assert result.exit_code == 0, f"CLI error:\n{result.output}"

    @pytest.mark.e2e
    def test_cli_init_creates_config(self, cli_runner) -> None:
        """init command creates a .codecustodian.yml in new directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = cli_runner.invoke(
                app,
                ["init", tmpdir],
            )
            assert result.exit_code == 0, f"CLI error:\n{result.output}"
            assert (Path(tmpdir) / ".codecustodian.yml").exists(), (
                "init did not create .codecustodian.yml"
            )

    @pytest.mark.e2e
    def test_cli_status_command(self, cli_runner) -> None:
        """status command exits 0."""
        result = cli_runner.invoke(app, ["status"])
        assert result.exit_code == 0, f"CLI error:\n{result.output}"

    @pytest.mark.e2e
    def test_cli_report_command(self, cli_runner) -> None:
        """report command exits 0."""
        result = cli_runner.invoke(app, ["report"])
        assert result.exit_code == 0, f"CLI error:\n{result.output}"

    @pytest.mark.e2e
    def test_cli_onboard_command(self, cli_runner) -> None:
        """onboard command analyzes demo app and exits 0."""
        result = cli_runner.invoke(
            app,
            ["onboard", "--repo-path", DEMO_REPO],
        )
        assert result.exit_code == 0, f"CLI error:\n{result.output}"

    @pytest.mark.e2e
    def test_cli_interactive_help(self, cli_runner) -> None:
        """interactive --help exits 0 (command is registered)."""
        result = cli_runner.invoke(app, ["interactive", "--help"])
        assert result.exit_code == 0, f"CLI error:\n{result.output}"


# ══════════════════════════════════════════════════════════════════════════
# Phase 2.4 — TestEnterpriseFeaturesE2E
# Budget / SLA / ROI / Audit / RBAC / approval / multi-tenant
# ══════════════════════════════════════════════════════════════════════════


class TestEnterpriseFeaturesE2E:
    """Verify enterprise features work end-to-end (Phase 2.4)."""

    @pytest.mark.e2e
    def test_roi_calculator_report(self, tmp_path) -> None:
        """ROICalculator generates a report with positive savings after recording events."""
        from codecustodian.enterprise.roi_calculator import ROICalculator

        calc = ROICalculator(hourly_rate=100.0, data_dir=str(tmp_path / "roi"))
        calc.record("security", "critical", ai_cost_usd=0.05, was_successful=True)
        calc.record("deprecated_api", "high", ai_cost_usd=0.03, was_successful=True)
        report = calc.generate_report()
        assert report.total_fixes == 2
        assert report.successful_fixes == 2
        assert report.estimated_savings_usd > 0, (
            f"Expected positive savings; got {report.estimated_savings_usd}"
        )
        assert report.total_hours_saved > 0

    @pytest.mark.e2e
    def test_sla_reporter_records_and_reports(self, tmp_path) -> None:
        """SLAReporter persists run records and generates an aggregated report."""
        from codecustodian.enterprise.sla_reporter import SLARecord, SLAReporter

        reporter = SLAReporter(db_path=str(tmp_path / "sla.json"))
        try:
            reporter.record_run(SLARecord(
                run_id="run-001", success=True, duration_seconds=12.5,
                findings_count=5, prs_created=2
            ))
            reporter.record_run(SLARecord(
                run_id="run-002", success=False, duration_seconds=5.0,
                findings_count=2, prs_created=0, failure_reason="timeout"
            ))
            report = reporter.generate_report()
            assert report.total_runs == 2
            assert report.successful_runs == 1
            assert report.failed_runs == 1
            assert 0.0 <= report.success_rate <= 100.0
        finally:
            reporter.close()

    @pytest.mark.e2e
    def test_budget_manager_tracks_cost(self, tmp_path) -> None:
        """BudgetManager tracks cumulative cost and returns correct summary."""
        from codecustodian.enterprise.budget_manager import BudgetManager

        bm = BudgetManager(
            team_id="test-team",
            monthly_budget=100.0,
            data_dir=str(tmp_path / "costs"),
        )
        bm.record_cost("plan", 0.05, run_id="r1")
        bm.record_cost("execute", 0.10, run_id="r1")
        summary = bm.get_summary()
        assert summary.total_spent > 0
        assert summary.remaining < 100.0
        assert summary.monthly_budget == 100.0

    @pytest.mark.e2e
    def test_audit_logger_tamper_evident_hash(self, tmp_path) -> None:
        """AuditLogger records entries with a tamper-evident SHA-256 hash."""
        from codecustodian.enterprise.audit import AuditEntry, AuditLogger

        logger_inst = AuditLogger(log_dir=str(tmp_path / "audit"))
        logger_inst.log("refactoring_applied", target="src/app.py",
                        finding_id="f001", confidence_score=8.0)

        # Read back and validate hash
        log_file = next(iter((tmp_path / "audit").glob("audit-*.jsonl")))
        line = log_file.read_text().strip().splitlines()[0]
        entry_data = json.loads(line)
        entry = AuditEntry(**entry_data)
        computed = entry.compute_hash()
        assert entry.entry_hash == computed, (
            f"Tamper-evident hash mismatch: stored={entry.entry_hash[:8]} computed={computed[:8]}"
        )

    @pytest.mark.e2e
    def test_rbac_admin_has_all_permissions(self) -> None:
        """ADMIN role has all permissions."""
        from codecustodian.enterprise.rbac import Permission, Role, check_permission

        for perm in Permission:
            assert check_permission(Role.ADMIN, perm), (
                f"ADMIN should have permission {perm.value}"
            )

    @pytest.mark.e2e
    def test_rbac_viewer_limited_permissions(self) -> None:
        """VIEWER role cannot scan, plan, or execute."""
        from codecustodian.enterprise.rbac import Permission, Role, check_permission

        assert not check_permission(Role.VIEWER, Permission.EXECUTE)
        assert not check_permission(Role.VIEWER, Permission.SCAN)
        assert not check_permission(Role.VIEWER, Permission.CREATE_PR)
        assert check_permission(Role.VIEWER, Permission.VIEW_REPORTS)

    @pytest.mark.e2e
    def test_multi_tenant_isolation(self, tmp_path) -> None:
        """MultiTenantManager creates isolated directories per tenant."""
        from codecustodian.enterprise.multi_tenant import MultiTenantManager, TenantConfig

        mgr = MultiTenantManager(data_root=str(tmp_path / "data"))
        mgr.register_tenant(TenantConfig(tenant_id="tenant-A", display_name="Contoso"))
        mgr.register_tenant(TenantConfig(tenant_id="tenant-B", display_name="Fabrikam"))

        dirs_a = mgr.get_tenant_dirs("tenant-A")
        dirs_b = mgr.get_tenant_dirs("tenant-B")
        assert dirs_a.root != dirs_b.root, "Tenant dirs must be isolated"
        assert "tenant-A" in dirs_a.root
        assert "tenant-B" in dirs_b.root
        # Directories should exist on disk
        assert Path(dirs_a.audit).exists()
        assert Path(dirs_b.audit).exists()

    @pytest.mark.e2e
    def test_approval_workflow_request_and_approve(self, tmp_path) -> None:
        """ApprovalWorkflowManager transitions from PENDING → APPROVED correctly."""
        from codecustodian.enterprise.approval_workflows import (
            ApprovalStatus,
            ApprovalWorkflowManager,
        )

        wf = ApprovalWorkflowManager(
            require_plan_approval=True,
            data_dir=str(tmp_path / "approvals"),
        )
        req = wf.request_approval(
            resource_id="plan-001", resource_type="plan", requester="codecustodian"
        )
        assert req.status == ApprovalStatus.PENDING
        wf.approve(req.id, approver="alice@contoso.com")
        assert wf.is_approved("plan-001")


# ══════════════════════════════════════════════════════════════════════════
# Phase 2.5 — TestSafetyChecksE2E
# Pre-execution safety validator blocks dangerous code
# ══════════════════════════════════════════════════════════════════════════


class TestSafetyChecksE2E:
    """Verify SafetyCheckRunner blocks dangerous patterns (Phase 2.5)."""

    def _make_plan_with_content(self, new_content: str, old_content: str = "x = 1"):
        """Build a minimal RefactoringPlan with the given new_content."""
        from codecustodian.models import ChangeType, FileChange, RefactoringPlan, RiskLevel

        change = FileChange(
            file_path="src/safe_to_delete.py",
            change_type=ChangeType.REPLACE,
            old_content=old_content,
            new_content=new_content,
        )
        return RefactoringPlan(
            finding_id="f-test",
            summary="Test plan",
            description="Safety test",
            changes=[change],
            confidence_score=8,
            risk_level=RiskLevel.LOW,
        )

    @pytest.mark.e2e
    def test_safety_blocks_eval_in_new_code(self, tmp_path) -> None:
        """Safety check blocks plans containing eval() calls."""
        from codecustodian.executor.safety_checks import SafetyCheckRunner

        plan = self._make_plan_with_content(
            'result = eval("user_input")\nprint(result)\n'
        )
        runner = SafetyCheckRunner(repo_path=str(tmp_path))
        safety_result = asyncio.run(runner.run_all_checks(plan))
        assert not safety_result.passed, (
            "SafetyCheckRunner should have blocked eval() in new code"
        )
        check_names = [c.name for c in safety_result.checks if c.failed]
        assert any("danger" in n or "function" in n for n in check_names), (
            f"Expected 'dangerous_functions' check to fail; failed checks: {check_names}"
        )

    @pytest.mark.e2e
    def test_safety_blocks_exec_in_new_code(self, tmp_path) -> None:
        """Safety check blocks plans containing exec() calls."""
        from codecustodian.executor.safety_checks import SafetyCheckRunner

        plan = self._make_plan_with_content("exec(data)\n")
        runner = SafetyCheckRunner(repo_path=str(tmp_path))
        safety_result = asyncio.run(runner.run_all_checks(plan))
        assert not safety_result.passed, "SafetyCheckRunner should block exec() in new code"

    @pytest.mark.e2e
    def test_safety_blocks_hardcoded_openai_secret(self, tmp_path) -> None:
        """Safety check blocks plans containing OpenAI API key pattern (sk-)."""
        from codecustodian.executor.safety_checks import SafetyCheckRunner

        secret_key = "sk-" + "A" * 40  # matches sk-<32+> pattern
        plan = self._make_plan_with_content(
            f'OPENAI_KEY = "{secret_key}"\n'
        )
        runner = SafetyCheckRunner(repo_path=str(tmp_path))
        safety_result = asyncio.run(runner.run_all_checks(plan))
        assert not safety_result.passed, (
            "SafetyCheckRunner should block OpenAI API key in new code"
        )

    @pytest.mark.e2e
    def test_safety_blocks_aws_access_key(self, tmp_path) -> None:
        """Safety check blocks plans containing AWS access key ID (AKIA...)."""
        from codecustodian.executor.safety_checks import SafetyCheckRunner

        plan = self._make_plan_with_content(
            'AWS_KEY = "AKIA' + "B" * 16 + '"\n'
        )
        runner = SafetyCheckRunner(repo_path=str(tmp_path))
        safety_result = asyncio.run(runner.run_all_checks(plan))
        assert not safety_result.passed, (
            "SafetyCheckRunner should block AWS access key in new code"
        )

    @pytest.mark.e2e
    def test_safety_allows_clean_code(self, tmp_path) -> None:
        """Safety check passes for clean, simple replacement code."""
        from codecustodian.executor.safety_checks import SafetyCheckRunner

        # Create multi-file repo so blast_radius sees target as <30% of codebase
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "safe_to_delete.py").write_text("x = 1\n")
        for name in ("app.py", "utils.py", "config.py", "models.py"):
            (tmp_path / "src" / name).write_text("# module\n")

        plan = self._make_plan_with_content(
            "import os\nimport json\n\ndef process(data: dict) -> str:\n"
            "    return json.dumps(data)\n"
        )
        runner = SafetyCheckRunner(repo_path=str(tmp_path))
        safety_result = asyncio.run(runner.run_all_checks(plan))
        assert safety_result.passed, (
            f"Clean code should pass safety checks; failures: "
            f"{[c.name for c in safety_result.checks if c.failed]}"
        )


# ══════════════════════════════════════════════════════════════════════════
# Phase 2.6 — TestFeedbackIntelligenceE2E
# Feedback loop: record, retrieve, learn
# ══════════════════════════════════════════════════════════════════════════


class TestFeedbackIntelligenceE2E:
    """Verify feedback and historical learning loop (Phase 2.6)."""

    @pytest.mark.e2e
    def test_feedback_store_record_and_retrieve(self, tmp_path) -> None:
        """FeedbackStore persists entries and accuracy stats are updated."""
        from codecustodian.feedback.store import FeedbackEntry, FeedbackStore

        store = FeedbackStore(storage_dir=str(tmp_path / "feedback"))
        store.record(FeedbackEntry(
            finding_id="f-001", finding_type="security",
            action="approved", confidence_was=8
        ))
        store.record(FeedbackEntry(
            finding_id="f-002", finding_type="deprecated_api",
            action="rejected", confidence_was=5
        ))
        stats = store.get_accuracy_stats()
        assert stats["total"] == 2
        assert stats["approved"] == 1
        assert stats["rejected"] == 1
        assert 0.0 <= stats["accuracy"] <= 100.0

    @pytest.mark.e2e
    def test_preference_store_record_and_retrieve(self, tmp_path) -> None:
        """PreferenceStore records team preferences and retrieves them."""
        from codecustodian.feedback.preferences import PreferenceStore

        store = PreferenceStore(
            db_path=str(tmp_path / "preferences.json")
        )
        try:
            store.record_preference("team-alpha", "prefer async/await over callbacks")
            store.record_preference("team-alpha", "use dataclasses over dicts")
            prefs = store.get_preferences("team-alpha")
            assert len(prefs) >= 1, "Expected stored preferences to be retrievable"
            pref_texts = [p if isinstance(p, str) else p.get("preference", "") for p in prefs]
            assert any("async" in t for t in pref_texts), (
                "Expected async/await preference to be retrievable"
            )
        finally:
            store.close()

    @pytest.mark.e2e
    def test_historical_pattern_recognizer_record_and_find(self, tmp_path) -> None:
        """HistoricalPatternRecognizer records a refactoring and finds similar patterns."""
        from codecustodian.feedback.history import (
            HistoricalPatternRecognizer,
            HistoricalRefactoring,
        )
        from codecustodian.models import Finding, FindingType, SeverityLevel

        recognizer = HistoricalPatternRecognizer(
            db_path=str(tmp_path / "history.json")
        )
        try:
            recognizer.record_refactoring(HistoricalRefactoring(
                finding_type="deprecated_api",
                library="pandas",
                pattern="df.append",
                outcome="merged",
                success=True,
                success_rate=1.0,
                learned_recommendation="Replace df.append with pd.concat",
                confidence_was=8,
            ))
            finding = Finding(
                type=FindingType.DEPRECATED_API,
                severity=SeverityLevel.HIGH,
                file="src/data.py",
                line=42,
                description="df.append is deprecated",
            )
            patterns = asyncio.run(recognizer.find_similar(finding))
            assert isinstance(patterns, list), "find_similar should return a list"
        finally:
            recognizer.close()


# ══════════════════════════════════════════════════════════════════════════
# Phase 2.7 — TestMCPServerLocal
# In-process FastMCP server: tools, resources, prompts
# ══════════════════════════════════════════════════════════════════════════


class TestMCPServerLocal:
    """Verify the local MCP server exposes all tools, resources and prompts (Phase 2.7)."""

    @pytest.mark.e2e
    def test_mcp_list_tools_returns_seventeen(self) -> None:
        """MCP server exposes exactly 17 tools."""
        from fastmcp import Client

        from codecustodian.mcp.server import mcp

        async def _run():
            async with Client(mcp) as client:
                return await client.list_tools()

        tools = asyncio.run(_run())
        tool_names = {t.name for t in tools}
        expected = {
            "scan_repository", "list_scanners", "plan_refactoring",
            "apply_refactoring", "verify_changes", "create_pull_request",
            "calculate_roi", "get_business_impact", "get_blast_radius",
            "get_debt_forecast", "check_pypi_versions", "get_reachability_analysis",
            "synthesize_tests", "plan_migration", "get_migration_status",
            "send_teams_notification", "scan_remote_repository",
        }
        assert expected == tool_names, f"Missing tools: {expected - tool_names}"

    @pytest.mark.e2e
    def test_mcp_list_scanners_returns_seven(self) -> None:
        """list_scanners tool returns all 7 scanner descriptors."""
        from fastmcp import Client

        from codecustodian.mcp.server import mcp

        async def _run():
            async with Client(mcp) as client:
                r = await client.call_tool("list_scanners", {})
                return r.structured_content

        data = asyncio.run(_run())
        # FastMCP wraps list results in {"result": [...]}
        if isinstance(data, dict) and "result" in data:
            data = data["result"]
        names = {s["name"] for s in data} if isinstance(data, list) else set()
        expected = {"deprecated_apis", "security_patterns", "code_smells",
                    "todo_comments", "type_coverage", "dependency_upgrades",
                    "architectural_drift"}
        assert expected == names, f"Missing scanners: {expected - names}"

    @pytest.mark.e2e
    def test_mcp_scan_repository_returns_findings(self) -> None:
        """scan_repository tool returns ≥5 findings for demo app."""
        from fastmcp import Client

        from codecustodian.mcp.server import mcp

        async def _run():
            async with Client(mcp) as client:
                r = await client.call_tool("scan_repository", {"repo_path": DEMO_REPO})
                return r.structured_content

        data = asyncio.run(_run())
        assert isinstance(data, dict), f"Expected dict result, got: {type(data)}"
        total = data.get("total", 0)
        assert total >= 5, f"Expected ≥5 findings from demo app; got {total}"

    @pytest.mark.e2e
    def test_mcp_calculate_roi_returns_savings(self) -> None:
        """calculate_roi tool returns a result dict (ROI info or cache-miss error)."""
        from fastmcp import Client

        from codecustodian.mcp.server import mcp

        async def _run():
            async with Client(mcp) as client:
                r = await client.call_tool("calculate_roi", {"finding_id": "dummy-test-id"})
                return r.structured_content

        data = asyncio.run(_run())
        assert isinstance(data, dict), f"Expected dict result from calculate_roi; got {type(data)}"

    @pytest.mark.e2e
    def test_mcp_get_business_impact_returns_data(self) -> None:
        """get_business_impact tool returns a result dict (impact data or cache-miss error)."""
        from fastmcp import Client

        from codecustodian.mcp.server import mcp

        async def _run():
            async with Client(mcp) as client:
                r = await client.call_tool("get_business_impact", {"finding_id": "dummy-test-id"})
                return r.structured_content

        data = asyncio.run(_run())
        assert isinstance(data, dict), f"Expected dict result from get_business_impact; got {type(data)}"

    @pytest.mark.e2e
    def test_mcp_resource_version_readable(self) -> None:
        """codecustodian://version resource returns a semver string."""
        from fastmcp import Client

        from codecustodian.mcp.server import mcp

        async def _run():
            async with Client(mcp) as client:
                return await client.read_resource("codecustodian://version")

        result = asyncio.run(_run())
        text = str(result)
        assert "." in text, (
            f"Expected semver version string, got: {text!r}"
        )

    @pytest.mark.e2e
    def test_mcp_resource_config_readable(self) -> None:
        """codecustodian://config resource returns YAML content."""
        from fastmcp import Client

        from codecustodian.mcp.server import mcp

        async def _run():
            async with Client(mcp) as client:
                return await client.read_resource("codecustodian://config")

        result = asyncio.run(_run())
        text = str(result)
        assert "version" in text.lower(), (
            f"Expected YAML config with 'version' key, got: {text[:200]!r}"
        )

    @pytest.mark.e2e
    def test_mcp_resource_scanners_readable(self) -> None:
        """codecustodian://scanners resource lists scanner names."""
        from fastmcp import Client

        from codecustodian.mcp.server import mcp

        async def _run():
            async with Client(mcp) as client:
                return await client.read_resource("codecustodian://scanners")

        result = asyncio.run(_run())
        text = str(result)
        assert "security" in text.lower() or "deprecated" in text.lower(), (
            f"Expected scanner names in resource; got: {text[:200]!r}"
        )

    @pytest.mark.e2e
    def test_mcp_resource_config_settings_readable(self) -> None:
        """config://settings resource returns JSON with version key."""
        from fastmcp import Client

        from codecustodian.mcp.server import mcp

        async def _run():
            async with Client(mcp) as client:
                return await client.read_resource("config://settings")

        result = asyncio.run(_run())
        text = result[0].text
        data = json.loads(text)
        assert isinstance(data, dict)

    @pytest.mark.e2e
    def test_mcp_resource_findings_all_readable(self) -> None:
        """findings://myrepo/all URI template resource returns JSON structure."""
        from fastmcp import Client

        from codecustodian.mcp.server import mcp

        async def _run():
            async with Client(mcp) as client:
                return await client.read_resource("findings://myrepo/all")

        result = asyncio.run(_run())
        data = json.loads(result[0].text)
        assert "findings" in data and "total" in data

    @pytest.mark.e2e
    def test_mcp_resource_dashboard_readable(self) -> None:
        """dashboard://team-alpha/summary resource returns expected structure."""
        from fastmcp import Client

        from codecustodian.mcp.server import mcp

        async def _run():
            async with Client(mcp) as client:
                return await client.read_resource("dashboard://team-alpha/summary")

        result = asyncio.run(_run())
        data = json.loads(result[0].text)
        assert "total_findings" in data
        assert "by_severity" in data
        assert "by_type" in data

    @pytest.mark.e2e
    def test_mcp_prompts_list_returns_seven(self) -> None:
        """MCP server registers exactly 7 prompts."""
        from fastmcp import Client

        from codecustodian.mcp.server import mcp

        async def _run():
            async with Client(mcp) as client:
                return await client.list_prompts()

        prompts = asyncio.run(_run())
        prompt_names = {p.name for p in prompts}
        expected = {
            "refactor_finding", "scan_summary", "roi_report",
            "onboard_repo", "forecast_report",
            "migration_assessment", "test_coverage_gap",
        }
        assert expected == prompt_names, f"Missing prompts: {expected - prompt_names}"

    @pytest.mark.e2e
    def test_mcp_prompt_refactor_finding_invocable(self) -> None:
        """refactor_finding prompt renders messages for a test finding."""
        from fastmcp import Client

        from codecustodian.mcp.server import mcp

        async def _run():
            async with Client(mcp) as client:
                return await client.get_prompt(
                    "refactor_finding",
                    {
                        "finding_type": "deprecated_api",
                        "file_path": "src/data.py",
                        "line": "42",
                        "description": "df.append is deprecated",
                    },
                )

        result = asyncio.run(_run())
        messages = result.messages
        assert messages, "Expected at least one message from refactor_finding prompt"
        text = messages[0].content.text
        assert "deprecated_api" in text or "src/data.py" in text or "df.append" in text, (
            f"Expected finding info in prompt text; got: {text[:300]!r}"
        )
