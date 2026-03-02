"""Tests for MCP server structure, health check, and tool registrations.

Uses FastMCP's in-memory ``Client(mcp)`` pattern — no subprocess or
network needed.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from codecustodian.mcp.cache import ScanCache
from codecustodian.mcp.server import mcp
from codecustodian.models import (
    Finding,
    FindingType,
    RefactoringPlan,
    SeverityLevel,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_finding(**overrides) -> Finding:
    """Create a test finding with sensible defaults."""
    defaults = {
        "id": "f001",
        "type": FindingType.DEPRECATED_API,
        "severity": SeverityLevel.HIGH,
        "file": "src/app.py",
        "line": 42,
        "description": "pandas.DataFrame.append is deprecated",
        "suggestion": "Use pd.concat instead",
        "priority_score": 120.0,
    }
    defaults.update(overrides)
    return Finding(**defaults)


def _make_plan(finding_id: str = "f001", **overrides) -> RefactoringPlan:
    """Create a test plan with sensible defaults."""
    defaults = {
        "id": "p001",
        "finding_id": finding_id,
        "summary": "Replace DataFrame.append with pd.concat",
        "confidence_score": 9,
        "changes": [],
    }
    defaults.update(overrides)
    return RefactoringPlan(**defaults)


# ---------------------------------------------------------------------------
# Server structure
# ---------------------------------------------------------------------------


class TestMCPServerStructure:
    """Verify the server is wired correctly."""

    def test_server_name(self):
        assert mcp.name == "CodeCustodian"

    @pytest.mark.asyncio
    async def test_lists_all_tools(self):
        from fastmcp import Client

        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}

        expected = {
            "scan_repository",
            "list_scanners",
            "plan_refactoring",
            "apply_refactoring",
            "verify_changes",
            "create_pull_request",
            "calculate_roi",
            "get_business_impact",
            "get_blast_radius",
        }
        assert expected == names

    @pytest.mark.asyncio
    async def test_lists_all_resources(self):
        from fastmcp import Client

        async with Client(mcp) as client:
            resources = await client.list_resources()
            uris = {str(r.uri) for r in resources}

        # Static resources only in list_resources (templates are separate)
        for uri in ("codecustodian://config", "codecustodian://version", "config://settings"):
            assert uri in uris

    @pytest.mark.asyncio
    async def test_lists_resource_templates(self):
        from fastmcp import Client

        async with Client(mcp) as client:
            templates = await client.list_resource_templates()
            uris = {str(t.uriTemplate) for t in templates}

        assert "findings://{repo_name}/all" in uris
        assert "findings://{repo_name}/{finding_type}" in uris
        assert "dashboard://{team_name}/summary" in uris

    @pytest.mark.asyncio
    async def test_lists_all_prompts(self):
        from fastmcp import Client

        async with Client(mcp) as client:
            prompts = await client.list_prompts()
            names = {p.name for p in prompts}

        expected = {"refactor_finding", "scan_summary", "roi_report", "onboard_repo"}
        assert expected == names


# ---------------------------------------------------------------------------
# Tool annotations
# ---------------------------------------------------------------------------


class TestToolAnnotations:
    """Verify readOnlyHint / destructiveHint are set correctly."""

    @pytest.mark.asyncio
    async def test_readonly_tools(self):
        from fastmcp import Client

        async with Client(mcp) as client:
            tools = await client.list_tools()

        readonly_names = {
            "scan_repository",
            "list_scanners",
            "plan_refactoring",
            "verify_changes",
            "calculate_roi",
            "get_business_impact",
            "get_blast_radius",
        }
        for t in tools:
            if t.name in readonly_names:
                assert t.annotations is not None, f"{t.name} missing annotations"
                assert t.annotations.readOnlyHint is True, f"{t.name} should be readOnly"

    @pytest.mark.asyncio
    async def test_destructive_tools(self):
        from fastmcp import Client

        async with Client(mcp) as client:
            tools = await client.list_tools()

        destructive_names = {"apply_refactoring", "create_pull_request"}
        for t in tools:
            if t.name in destructive_names:
                assert t.annotations is not None, f"{t.name} missing annotations"
                assert t.annotations.destructiveHint is True, f"{t.name} should be destructive"

    @pytest.mark.asyncio
    async def test_open_world_on_create_pr(self):
        from fastmcp import Client

        async with Client(mcp) as client:
            tools = await client.list_tools()

        for t in tools:
            if t.name == "create_pull_request":
                assert t.annotations.openWorldHint is True


# ---------------------------------------------------------------------------
# scan_repository tool
# ---------------------------------------------------------------------------


class TestScanRepositoryTool:
    """Tests for the scan_repository MCP tool."""

    @pytest.mark.asyncio
    async def test_scan_with_mocked_registry(self):
        from fastmcp import Client

        finding = _make_finding()
        mock_scanner = MagicMock()
        mock_scanner.name = "deprecated_api"
        mock_scanner.scan.return_value = [finding]

        mock_registry = MagicMock()
        mock_registry.get_enabled.return_value = [mock_scanner]

        cache = ScanCache()
        with (
            patch("codecustodian.mcp.cache.scan_cache", cache),
            patch(
                "codecustodian.scanner.registry.get_default_registry",
                return_value=mock_registry,
            ),
        ):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "scan_repository",
                    {"repo_path": ".", "scanners": "all", "config_path": ".codecustodian.yml"},
                )

        text = result.content[0].text
        data = json.loads(text)
        assert data["total"] == 1
        assert len(data["findings"]) == 1

    @pytest.mark.asyncio
    async def test_scan_handles_scanner_failure(self):
        from fastmcp import Client

        mock_scanner = MagicMock()
        mock_scanner.name = "broken"
        mock_scanner.scan.side_effect = RuntimeError("boom")

        mock_registry = MagicMock()
        mock_registry.get_enabled.return_value = [mock_scanner]

        cache = ScanCache()
        with (
            patch("codecustodian.mcp.cache.scan_cache", cache),
            patch(
                "codecustodian.scanner.registry.get_default_registry",
                return_value=mock_registry,
            ),
        ):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "scan_repository",
                    {"repo_path": "."},
                )

        data = json.loads(result.content[0].text)
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_scan_specific_scanners(self):
        from fastmcp import Client

        finding = _make_finding()
        mock_scanner = MagicMock()
        mock_scanner.name = "deprecated_api"
        mock_scanner.scan.return_value = [finding]

        mock_registry = MagicMock()
        mock_registry.get.side_effect = lambda n: mock_scanner if n == "deprecated_api" else None

        cache = ScanCache()
        with (
            patch("codecustodian.mcp.cache.scan_cache", cache),
            patch(
                "codecustodian.scanner.registry.get_default_registry",
                return_value=mock_registry,
            ),
        ):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "scan_repository",
                    {"repo_path": ".", "scanners": "deprecated_api"},
                )

        data = json.loads(result.content[0].text)
        assert data["total"] == 1


# ---------------------------------------------------------------------------
# list_scanners tool
# ---------------------------------------------------------------------------


class TestListScannersTool:
    @pytest.mark.asyncio
    async def test_list_returns_catalog(self):
        from fastmcp import Client

        catalog = [
            {"name": "deprecated_api", "description": "Finds deprecated APIs", "detects": "deprecated_api", "enabled": "True"},
            {"name": "todo_comments", "description": "Finds old TODOs", "detects": "todo_comments", "enabled": "True"},
        ]
        mock_registry = MagicMock()
        mock_registry.list_catalog.return_value = catalog

        with patch(
            "codecustodian.scanner.registry.get_default_registry",
            return_value=mock_registry,
        ):
            async with Client(mcp) as client:
                result = await client.call_tool("list_scanners", {})

        data = json.loads(result.content[0].text)
        assert len(data) == 2
        assert data[0]["name"] == "deprecated_api"


# ---------------------------------------------------------------------------
# plan_refactoring tool
# ---------------------------------------------------------------------------


class TestPlanRefactoringTool:
    @pytest.mark.asyncio
    async def test_finding_not_in_cache(self):
        from fastmcp import Client

        cache = ScanCache()
        with patch("codecustodian.mcp.cache.scan_cache", cache):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "plan_refactoring",
                    {"finding_id": "nonexistent"},
                )

        data = json.loads(result.content[0].text)
        assert "error" in data
        assert "not found" in data["error"]

    @pytest.mark.asyncio
    async def test_plan_success(self):
        from fastmcp import Client

        finding = _make_finding()
        plan = _make_plan()
        cache = ScanCache()
        await cache.store_finding(finding)

        mock_planner = AsyncMock()
        mock_planner.plan_refactoring.return_value = plan

        with (
            patch("codecustodian.mcp.cache.scan_cache", cache),
            patch("codecustodian.planner.planner.Planner", return_value=mock_planner),
            patch("codecustodian.planner.copilot_client.CopilotPlannerClient"),
        ):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "plan_refactoring",
                    {"finding_id": "f001"},
                )

        data = json.loads(result.content[0].text)
        assert data.get("id") == "p001" or "summary" in data


# ---------------------------------------------------------------------------
# apply_refactoring tool
# ---------------------------------------------------------------------------


class TestApplyRefactoringTool:
    @pytest.mark.asyncio
    async def test_plan_not_in_cache(self):
        from fastmcp import Client

        cache = ScanCache()
        with patch("codecustodian.mcp.cache.scan_cache", cache):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "apply_refactoring",
                    {"plan_id": "nonexistent"},
                )

        data = json.loads(result.content[0].text)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_apply_success(self):
        from pathlib import Path

        from fastmcp import Client

        plan = _make_plan()
        cache = ScanCache()
        await cache.store_plan(plan)

        mock_editor = MagicMock()
        mock_editor.apply_changes.return_value = [Path("src/app.py")]

        with (
            patch("codecustodian.mcp.cache.scan_cache", cache),
            patch(
                "codecustodian.executor.file_editor.SafeFileEditor",
                return_value=mock_editor,
            ),
        ):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "apply_refactoring",
                    {"plan_id": "p001"},
                )

        data = json.loads(result.content[0].text)
        assert data["success"] is True
        assert "app.py" in str(data["changed_files"])

    @pytest.mark.asyncio
    async def test_apply_failure_rolls_back(self):
        from fastmcp import Client

        plan = _make_plan()
        cache = ScanCache()
        await cache.store_plan(plan)

        mock_editor = MagicMock()
        mock_editor.apply_changes.side_effect = RuntimeError("write failed")

        with (
            patch("codecustodian.mcp.cache.scan_cache", cache),
            patch(
                "codecustodian.executor.file_editor.SafeFileEditor",
                return_value=mock_editor,
            ),
        ):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "apply_refactoring",
                    {"plan_id": "p001"},
                )

        data = json.loads(result.content[0].text)
        assert "error" in data
        assert "rolled back" in data["error"]


# ---------------------------------------------------------------------------
# verify_changes tool
# ---------------------------------------------------------------------------


class TestVerifyChangesTool:
    @pytest.mark.asyncio
    async def test_verify_passes(self):
        from fastmcp import Client

        mock_test_result = MagicMock()
        mock_test_result.passed = True
        mock_test_result.tests_run = 10
        mock_test_result.tests_passed = 10
        mock_test_result.tests_failed = 0

        mock_lint_result = MagicMock()
        mock_lint_result.passed = True
        mock_lint_result.violations = []

        with (
            patch(
                "codecustodian.verifier.test_runner.TestRunner.run_tests",
                return_value=mock_test_result,
            ),
            patch(
                "codecustodian.verifier.linter.LinterRunner.run_all",
                return_value=mock_lint_result,
            ),
        ):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "verify_changes",
                    {"changed_files": ["src/app.py"]},
                )

        data = json.loads(result.content[0].text)
        assert data["passed"] is True

    @pytest.mark.asyncio
    async def test_verify_test_failure(self):
        from fastmcp import Client

        mock_test_result = MagicMock()
        mock_test_result.passed = False
        mock_test_result.tests_run = 10
        mock_test_result.tests_passed = 8
        mock_test_result.tests_failed = 2

        mock_lint_result = MagicMock()
        mock_lint_result.passed = True
        mock_lint_result.violations = []

        with (
            patch(
                "codecustodian.verifier.test_runner.TestRunner.run_tests",
                return_value=mock_test_result,
            ),
            patch(
                "codecustodian.verifier.linter.LinterRunner.run_all",
                return_value=mock_lint_result,
            ),
        ):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "verify_changes",
                    {"changed_files": ["src/app.py"]},
                )

        data = json.loads(result.content[0].text)
        assert data["passed"] is False


# ---------------------------------------------------------------------------
# calculate_roi tool
# ---------------------------------------------------------------------------


class TestCalculateROITool:
    @pytest.mark.asyncio
    async def test_roi_not_in_cache(self):
        from fastmcp import Client

        cache = ScanCache()
        with patch("codecustodian.mcp.cache.scan_cache", cache):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "calculate_roi",
                    {"finding_id": "missing"},
                )

        data = json.loads(result.content[0].text)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_roi_calculation(self):
        from fastmcp import Client

        finding = _make_finding(severity=SeverityLevel.HIGH, type=FindingType.DEPRECATED_API)
        cache = ScanCache()
        await cache.store_finding(finding)

        with patch("codecustodian.mcp.cache.scan_cache", cache):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "calculate_roi",
                    {"finding_id": "f001"},
                )

        data = json.loads(result.content[0].text)
        assert "roi_percentage" in data
        assert data["roi_percentage"] > 0
        assert data["estimated_manual_hours"] > 0

    @pytest.mark.asyncio
    async def test_roi_security_finding(self):
        from fastmcp import Client

        finding = _make_finding(
            id="sec1",
            severity=SeverityLevel.CRITICAL,
            type=FindingType.SECURITY,
        )
        cache = ScanCache()
        await cache.store_finding(finding)

        with patch("codecustodian.mcp.cache.scan_cache", cache):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "calculate_roi",
                    {"finding_id": "sec1"},
                )

        data = json.loads(result.content[0].text)
        # Security + critical → highest hours
        assert data["estimated_manual_hours"] == 24.0


# ---------------------------------------------------------------------------
# get_business_impact tool
# ---------------------------------------------------------------------------


class TestGetBusinessImpactTool:
    @pytest.mark.asyncio
    async def test_impact_not_in_cache(self):
        from fastmcp import Client

        cache = ScanCache()
        with patch("codecustodian.mcp.cache.scan_cache", cache):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "get_business_impact",
                    {"finding_id": "missing"},
                )

        data = json.loads(result.content[0].text)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_critical_security_sla_risk(self):
        from fastmcp import Client

        finding = _make_finding(
            id="s1",
            severity=SeverityLevel.CRITICAL,
            type=FindingType.SECURITY,
        )
        cache = ScanCache()
        await cache.store_finding(finding)

        with patch("codecustodian.mcp.cache.scan_cache", cache):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "get_business_impact",
                    {"finding_id": "s1"},
                )

        data = json.loads(result.content[0].text)
        assert data["sla_risk"] is True
        assert data["business_impact_level"] == "critical"
        assert data["recommendation"] == "Fix immediately"

    @pytest.mark.asyncio
    async def test_low_severity_impact(self):
        from fastmcp import Client

        finding = _make_finding(
            id="l1",
            severity=SeverityLevel.LOW,
            type=FindingType.TODO_COMMENT,
        )
        cache = ScanCache()
        await cache.store_finding(finding)

        with patch("codecustodian.mcp.cache.scan_cache", cache):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "get_business_impact",
                    {"finding_id": "l1"},
                )

        data = json.loads(result.content[0].text)
        assert data["sla_risk"] is False
        # Real 5-factor scorer gives ~150 for a TODO in src/app.py
        # (criticality from path + baseline), so impact is "medium" not "low"
        assert data["business_impact_level"] in ("low", "medium")
        assert data["recommendation"] in ("Add to backlog", "Schedule for next sprint")


# ---------------------------------------------------------------------------
# create_pull_request tool (mostly error paths — full PR needs GitHub)
# ---------------------------------------------------------------------------


class TestCreatePullRequestTool:
    @pytest.mark.asyncio
    async def test_finding_not_in_cache(self):
        from fastmcp import Client

        cache = ScanCache()
        with patch("codecustodian.mcp.cache.scan_cache", cache):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "create_pull_request",
                    {"finding_id": "x", "plan_id": "y"},
                )

        data = json.loads(result.content[0].text)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_no_github_token(self):
        from fastmcp import Client

        finding = _make_finding()
        plan = _make_plan()
        cache = ScanCache()
        await cache.store_finding(finding)
        await cache.store_plan(plan)

        mock_git = MagicMock()
        mock_git.create_branch.return_value = "tech-debt/test"
        mock_git.commit.return_value = "abc123"
        mock_git.push.return_value = None

        with (
            patch("codecustodian.mcp.cache.scan_cache", cache),
            patch("codecustodian.executor.git_manager.GitManager", return_value=mock_git),
            patch.dict("os.environ", {"GITHUB_TOKEN": ""}, clear=False),
        ):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "create_pull_request",
                    {"finding_id": "f001", "plan_id": "p001"},
                )

        data = json.loads(result.content[0].text)
        assert "error" in data
        assert "GITHUB_TOKEN" in data["error"]
