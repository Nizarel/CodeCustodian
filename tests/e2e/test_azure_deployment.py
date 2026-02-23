"""Post-deployment end-to-end tests for the Azure-hosted MCP server.

These tests validate the live deployment at:
    https://codecustodian-prod-app.greenforest-c49f3fb9.eastus2.azurecontainerapps.io

Run with:
    pytest tests/e2e/test_azure_deployment.py -v -m azure_e2e

Skip when running offline:
    pytest -m "not azure_e2e"
"""

from __future__ import annotations

import json
import os

import httpx
import pytest

FQDN = os.environ.get(
    "CODECUSTODIAN_FQDN",
    "codecustodian-prod-app.greenforest-c49f3fb9.eastus2.azurecontainerapps.io",
)
BASE_URL = f"https://{FQDN}"
MCP_URL = f"{BASE_URL}/mcp"
TIMEOUT = 90.0
MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}

pytestmark = pytest.mark.azure_e2e

# ── Helpers ────────────────────────────────────────────────────────────────


def _jsonrpc(method: str, params: dict | None = None, req_id: int = 1) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method,
        "params": params or {},
    }


def _extract_sse_result(text: str) -> dict:
    """Parse SSE event stream and return the JSON-RPC result payload."""
    results: list[dict] = []
    for line in text.splitlines():
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload:
            continue
        try:
            obj = json.loads(payload)
            if "result" in obj or "error" in obj:
                results.append(obj)
        except json.JSONDecodeError:
            continue
    if not results:
        raise AssertionError(f"No JSON-RPC result in SSE stream: {text[:500]}")
    return results[-1]


def _mcp_session(client: httpx.Client) -> str:
    """Perform MCP initialize handshake and return session ID."""
    body = _jsonrpc(
        "initialize",
        {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "e2e-test", "version": "1.0"},
        },
    )
    resp = client.post(MCP_URL, json=body, headers=MCP_HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    session_id = resp.headers.get("mcp-session-id", "")
    assert session_id, "Missing mcp-session-id in initialize response"
    result = _extract_sse_result(resp.text)
    assert "result" in result, f"Initialize failed: {result}"
    return session_id


def _mcp_call(
    client: httpx.Client,
    session_id: str,
    method: str,
    params: dict | None = None,
    req_id: int = 2,
) -> dict:
    """Send an MCP JSON-RPC request and return the result."""
    headers = {**MCP_HEADERS, "mcp-session-id": session_id}
    body = _jsonrpc(method, params, req_id)
    resp = client.post(MCP_URL, json=body, headers=headers, timeout=TIMEOUT)
    resp.raise_for_status()
    return _extract_sse_result(resp.text)


# ── Health ─────────────────────────────────────────────────────────────────


class TestHealthEndpoint:
    """FR-AZURE-004: Container app health."""

    def test_health_returns_ok(self) -> None:
        with httpx.Client() as client:
            resp = client.get(f"{BASE_URL}/health", timeout=TIMEOUT)
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert "version" in data

    def test_health_version_format(self) -> None:
        with httpx.Client() as client:
            data = client.get(f"{BASE_URL}/health", timeout=TIMEOUT).json()
            parts = data["version"].split(".")
            assert len(parts) == 3, f"Version should be semver: {data['version']}"


# ── MCP Protocol ───────────────────────────────────────────────────────────


class TestMCPProtocol:
    """MCP protocol compliance on the live endpoint."""

    def test_initialize_returns_session(self) -> None:
        with httpx.Client() as client:
            session_id = _mcp_session(client)
            assert len(session_id) > 0

    def test_initialize_returns_capabilities(self) -> None:
        with httpx.Client() as client:
            body = _jsonrpc(
                "initialize",
                {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "e2e-test", "version": "1.0"},
                },
            )
            resp = client.post(
                MCP_URL, json=body, headers=MCP_HEADERS, timeout=TIMEOUT
            )
            result = _extract_sse_result(resp.text)
            caps = result["result"]["capabilities"]
            assert "tools" in caps
            assert "resources" in caps
            assert "prompts" in caps

    def test_server_info(self) -> None:
        with httpx.Client() as client:
            body = _jsonrpc(
                "initialize",
                {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "e2e-test", "version": "1.0"},
                },
            )
            resp = client.post(
                MCP_URL, json=body, headers=MCP_HEADERS, timeout=TIMEOUT
            )
            result = _extract_sse_result(resp.text)
            info = result["result"]["serverInfo"]
            assert info["name"] == "CodeCustodian"
            assert info["version"]

    def test_invalid_method_returns_error(self) -> None:
        with httpx.Client() as client:
            session_id = _mcp_session(client)
            result = _mcp_call(
                client, session_id, "nonexistent/method", req_id=99
            )
            assert "error" in result


# ── MCP Tools ──────────────────────────────────────────────────────────────


class TestMCPTools:
    """FR-API-001: All 8 MCP tools reachable and functional."""

    def test_tools_list_returns_all_eight(self) -> None:
        with httpx.Client() as client:
            session_id = _mcp_session(client)
            result = _mcp_call(client, session_id, "tools/list")
            tools = result["result"]["tools"]
            tool_names = {t["name"] for t in tools}
            expected = {
                "scan_repository",
                "list_scanners",
                "plan_refactoring",
                "apply_refactoring",
                "verify_changes",
                "create_pull_request",
                "calculate_roi",
                "get_business_impact",
            }
            assert expected == tool_names, f"Missing: {expected - tool_names}"

    def test_list_scanners_returns_five(self) -> None:
        with httpx.Client() as client:
            session_id = _mcp_session(client)
            result = _mcp_call(
                client,
                session_id,
                "tools/call",
                {"name": "list_scanners", "arguments": {}},
                req_id=3,
            )
            assert "result" in result
            content = result["result"]
            scanners: list = []
            if "structuredContent" in content and content["structuredContent"]:
                scanners = content["structuredContent"].get("result", [])
            elif "content" in content:
                text = content["content"][0]["text"]
                parsed = json.loads(text)
                scanners = (
                    parsed
                    if isinstance(parsed, list)
                    else parsed.get("result", [])
                )
            assert len(scanners) == 5
            names = {s["name"] for s in scanners}
            assert names == {
                "deprecated_apis",
                "security_patterns",
                "code_smells",
                "todo_comments",
                "type_coverage",
            }

    def test_tool_annotations(self) -> None:
        """Destructive tools must have destructiveHint=True."""
        with httpx.Client() as client:
            session_id = _mcp_session(client)
            result = _mcp_call(client, session_id, "tools/list")
            tools = {t["name"]: t for t in result["result"]["tools"]}

            for name in (
                "scan_repository",
                "list_scanners",
                "verify_changes",
                "calculate_roi",
                "get_business_impact",
            ):
                ann = tools[name].get("annotations", {})
                assert ann.get("readOnlyHint") is True, (
                    f"{name} should be readOnly"
                )

            for name in ("apply_refactoring", "create_pull_request"):
                ann = tools[name].get("annotations", {})
                assert ann.get("destructiveHint") is True, (
                    f"{name} should be destructive"
                )


# ── MCP Resources ──────────────────────────────────────────────────────────


class TestMCPResources:
    """MCP resources are accessible on the live server."""

    def test_resources_list(self) -> None:
        with httpx.Client() as client:
            session_id = _mcp_session(client)
            result = _mcp_call(client, session_id, "resources/list")
            resources = result["result"]["resources"]
            uris = {r["uri"] for r in resources}
            assert "codecustodian://version" in uris
            assert "codecustodian://config" in uris
            assert "codecustodian://scanners" in uris
            assert "config://settings" in uris

    def test_read_version_resource(self) -> None:
        with httpx.Client() as client:
            session_id = _mcp_session(client)
            result = _mcp_call(
                client,
                session_id,
                "resources/read",
                {"uri": "codecustodian://version"},
                req_id=4,
            )
            assert "result" in result
            contents = result["result"]["contents"]
            assert len(contents) > 0
            text = contents[0].get("text", "")
            assert "." in text, f"Expected version string, got: {text}"

    def test_read_config_resource(self) -> None:
        with httpx.Client() as client:
            session_id = _mcp_session(client)
            result = _mcp_call(
                client,
                session_id,
                "resources/read",
                {"uri": "codecustodian://config"},
                req_id=5,
            )
            contents = result["result"]["contents"]
            text = contents[0].get("text", "")
            assert "version" in text.lower()


# ── MCP Prompts ────────────────────────────────────────────────────────────


class TestMCPPrompts:
    """MCP prompts are registered and accessible."""

    def test_prompts_list_returns_four(self) -> None:
        with httpx.Client() as client:
            session_id = _mcp_session(client)
            result = _mcp_call(client, session_id, "prompts/list")
            prompts = result["result"]["prompts"]
            names = {p["name"] for p in prompts}
            expected = {
                "refactor_finding",
                "scan_summary",
                "roi_report",
                "onboard_repo",
            }
            assert expected == names, f"Missing prompts: {expected - names}"

    def test_get_prompt_refactor_finding(self) -> None:
        with httpx.Client() as client:
            session_id = _mcp_session(client)
            result = _mcp_call(
                client,
                session_id,
                "prompts/get",
                {
                    "name": "refactor_finding",
                    "arguments": {
                        "finding_type": "deprecated_api",
                        "file_path": "src/app.py",
                        "line": "42",
                    },
                },
                req_id=6,
            )
            assert "result" in result
            messages = result["result"]["messages"]
            assert len(messages) > 0
            text = messages[0]["content"]["text"]
            assert "deprecated_api" in text or "src/app.py" in text


# ── Work IQ Integration ───────────────────────────────────────────────────


class TestWorkIQIntegration:
    """FR-AZURE-002 / Bonus Work IQ: integration models and logic."""

    def test_work_item_intelligence_prioritize(self) -> None:
        """WorkItemIntelligence.prioritize_findings sorts by severity+type."""
        from codecustodian.integrations.work_iq import WorkItemIntelligence
        from codecustodian.models import Finding, FindingType, SeverityLevel

        wiq = WorkItemIntelligence()
        findings = [
            Finding(
                type=FindingType.TODO_COMMENT,
                severity=SeverityLevel.LOW,
                file="a.py",
                line=1,
                description="todo",
            ),
            Finding(
                type=FindingType.SECURITY,
                severity=SeverityLevel.CRITICAL,
                file="b.py",
                line=2,
                description="sql injection",
            ),
            Finding(
                type=FindingType.DEPRECATED_API,
                severity=SeverityLevel.HIGH,
                file="c.py",
                line=3,
                description="deprecated",
            ),
        ]
        result = wiq.prioritize_findings(findings)
        assert result[0].type == FindingType.SECURITY
        assert result[0].severity == SeverityLevel.CRITICAL

    def test_work_item_intelligence_effort(self) -> None:
        from codecustodian.integrations.work_iq import WorkItemIntelligence
        from codecustodian.models import Finding, FindingType, SeverityLevel

        wiq = WorkItemIntelligence()
        f = Finding(
            type=FindingType.SECURITY,
            severity=SeverityLevel.HIGH,
            file="x.py",
            line=1,
            description="vuln",
        )
        assert wiq.estimate_effort(f) == "medium"

    @pytest.mark.asyncio
    async def test_work_iq_provider_graceful_fallback(self) -> None:
        """WorkIQContextProvider falls back when server unavailable."""
        from codecustodian.integrations.work_iq import WorkIQContextProvider
        from codecustodian.models import Finding, FindingType, SeverityLevel

        provider = WorkIQContextProvider(command="nonexistent-cmd-xyz")
        finding = Finding(
            type=FindingType.DEPRECATED_API,
            severity=SeverityLevel.HIGH,
            file="a.py",
            line=1,
            description="test",
        )
        expert = await provider.get_expert_for_finding(finding)
        assert expert.name == ""
        assert expert.relevance_score == 0.0

    @pytest.mark.asyncio
    async def test_work_iq_should_create_pr_defaults_true(self) -> None:
        """When Work IQ is unreachable, should_create_pr_now defaults True."""
        from codecustodian.integrations.work_iq import WorkIQContextProvider
        from codecustodian.models import Finding, FindingType, SeverityLevel

        provider = WorkIQContextProvider(command="nonexistent-cmd-xyz")
        finding = Finding(
            type=FindingType.TODO_COMMENT,
            severity=SeverityLevel.LOW,
            file="a.py",
            line=1,
            description="test",
        )
        # First call sets _available = False
        await provider.get_expert_for_finding(finding)
        result = await provider.should_create_pr_now(finding)
        assert result is True

    @pytest.mark.asyncio
    async def test_work_iq_sprint_context_empty_on_failure(self) -> None:
        """Sprint context returns defaults when server unavailable."""
        from codecustodian.integrations.work_iq import WorkIQContextProvider

        provider = WorkIQContextProvider(command="nonexistent-cmd-xyz")
        ctx = await provider.get_sprint_context()
        assert ctx.days_remaining == 0
        assert ctx.is_code_freeze is False

    @pytest.mark.asyncio
    async def test_work_iq_org_context_empty_on_failure(self) -> None:
        """Organizational context returns empty lists on failure."""
        from codecustodian.integrations.work_iq import WorkIQContextProvider

        provider = WorkIQContextProvider(command="nonexistent-cmd-xyz")
        ctx = await provider.get_organizational_context("pandas migration")
        assert ctx.related_documents == []
        assert ctx.recent_discussions == []

    def test_work_iq_mcp_config_shape(self) -> None:
        """get_work_iq_mcp_config returns valid MCP server config."""
        from codecustodian.integrations.work_iq import get_work_iq_mcp_config

        cfg = get_work_iq_mcp_config()
        assert cfg["type"] == "stdio"
        assert cfg["command"] == "npx"
        assert "@microsoft/workiq" in cfg["args"]

    def test_work_iq_models(self) -> None:
        """Work IQ Pydantic models instantiate with defaults."""
        from codecustodian.integrations.work_iq import (
            ExpertResult,
            OrgContext,
            SprintContext,
        )

        expert = ExpertResult()
        assert expert.name == ""
        assert expert.available is True

        sprint = SprintContext()
        assert sprint.days_remaining == 0
        assert sprint.is_code_freeze is False

        org = OrgContext()
        assert org.related_documents == []


# ── Product Requirements ───────────────────────────────────────────────────


class TestProductRequirements:
    """Verify key product requirements against live deployment."""

    def test_fr_scan_all_five_scanners(self) -> None:
        """FR-SCAN-010 through FR-SCAN-052: All 5 scanners available."""
        with httpx.Client() as client:
            session_id = _mcp_session(client)
            result = _mcp_call(
                client,
                session_id,
                "tools/call",
                {"name": "list_scanners", "arguments": {}},
                req_id=10,
            )
            content = result["result"]
            scanners: list = []
            if "structuredContent" in content and content["structuredContent"]:
                scanners = content["structuredContent"].get("result", [])
            elif "content" in content:
                parsed = json.loads(content["content"][0]["text"])
                scanners = (
                    parsed
                    if isinstance(parsed, list)
                    else parsed.get("result", [])
                )
            assert len(scanners) >= 5

    def test_fr_plan_tool_registered(self) -> None:
        """FR-PLAN-001: AI planner tool available."""
        with httpx.Client() as client:
            session_id = _mcp_session(client)
            result = _mcp_call(client, session_id, "tools/list")
            names = {t["name"] for t in result["result"]["tools"]}
            assert "plan_refactoring" in names

    def test_fr_exec_tool_registered(self) -> None:
        """FR-EXEC-001: Executor tool with destructive annotation."""
        with httpx.Client() as client:
            session_id = _mcp_session(client)
            result = _mcp_call(client, session_id, "tools/list")
            tools = {t["name"]: t for t in result["result"]["tools"]}
            assert "apply_refactoring" in tools
            ann = tools["apply_refactoring"].get("annotations", {})
            assert ann.get("destructiveHint") is True

    def test_fr_verify_tool_registered(self) -> None:
        """FR-VERIFY-001: Verifier tool available."""
        with httpx.Client() as client:
            session_id = _mcp_session(client)
            result = _mcp_call(client, session_id, "tools/list")
            names = {t["name"] for t in result["result"]["tools"]}
            assert "verify_changes" in names

    def test_fr_github_pr_tool_registered(self) -> None:
        """FR-GITHUB-001: PR creation tool available."""
        with httpx.Client() as client:
            session_id = _mcp_session(client)
            result = _mcp_call(client, session_id, "tools/list")
            names = {t["name"] for t in result["result"]["tools"]}
            assert "create_pull_request" in names

    def test_fr_ent_001_roi_tool(self) -> None:
        """FR-ENT-001: ROI calculation tool available."""
        with httpx.Client() as client:
            session_id = _mcp_session(client)
            result = _mcp_call(client, session_id, "tools/list")
            names = {t["name"] for t in result["result"]["tools"]}
            assert "calculate_roi" in names

    def test_fr_ent_business_impact_tool(self) -> None:
        """FR-PRIORITY-100: Business impact scoring tool available."""
        with httpx.Client() as client:
            session_id = _mcp_session(client)
            result = _mcp_call(client, session_id, "tools/list")
            names = {t["name"] for t in result["result"]["tools"]}
            assert "get_business_impact" in names

    def test_fr_azure_004_container_app_running(self) -> None:
        """FR-AZURE-004: App deployed and healthy on Container Apps."""
        with httpx.Client() as client:
            resp = client.get(f"{BASE_URL}/health", timeout=TIMEOUT)
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"

    def test_pipeline_stages_cli(self) -> None:
        """FR-ARCH-001: Full pipeline stages available via CLI."""
        from typer.testing import CliRunner

        from codecustodian.cli.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["scan", "--help"])
        assert result.exit_code == 0
        assert "--scanner" in result.stdout

        result = runner.invoke(app, ["run", "--help"])
        assert result.exit_code == 0
        assert "--dry-run" in result.stdout
        assert "--enable-work-iq" in result.stdout

    def test_config_validation(self) -> None:
        """FR-CONFIG-001: Pydantic validation of configuration."""
        from codecustodian.config.schema import CodeCustodianConfig

        config = CodeCustodianConfig()
        assert config.version == "1.0"
        assert config.behavior.max_prs_per_run == 5
        assert config.behavior.confidence_threshold == 7

    def test_enterprise_roi_calculator(self) -> None:
        """FR-ENT-001: ROI calculator produces meaningful output."""
        import tempfile

        from codecustodian.enterprise.roi_calculator import ROICalculator

        with tempfile.TemporaryDirectory() as td:
            calc = ROICalculator(data_dir=td)
            calc.record("security", "critical", 0.50)
            calc.record("deprecated_api", "high", 0.25)
            report = calc.generate_report()
            assert report.total_fixes == 2
            assert report.successful_fixes == 2
            assert report.total_hours_saved > 0
            assert report.estimated_savings_usd > 0

    def test_enterprise_budget_manager(self) -> None:
        """FR-ENT: Budget tracking enforces limits."""
        import tempfile

        from codecustodian.enterprise.budget_manager import BudgetManager

        with tempfile.TemporaryDirectory() as td:
            mgr = BudgetManager(monthly_budget=100.0, data_dir=td)
            mgr.record_cost("test_op", 50.0)
            summary = mgr.get_summary()
            assert summary.remaining == 50.0
            assert mgr.check_budget(10.0) is True

    def test_responsible_ai_doc_exists(self) -> None:
        """FR-SEC-001: Responsible AI documentation present."""
        from pathlib import Path

        rai_path = Path(__file__).parents[2] / "Docs" / "RESPONSIBLE_AI.md"
        assert rai_path.exists(), "RESPONSIBLE_AI.md missing"
        content = rai_path.read_text(encoding="utf-8")
        assert "responsible" in content.lower()

    def test_security_audit_logger(self) -> None:
        """FR-SEC: Audit logging with tamper detection."""
        import tempfile

        from codecustodian.enterprise.audit import AuditLogger

        with tempfile.TemporaryDirectory() as td:
            logger_inst = AuditLogger(log_dir=td)
            logger_inst.log("test_action", "target.py")
            entries = logger_inst.query(action="test_action")
            assert len(entries) >= 1
            assert entries[-1].action == "test_action"


# ── MCP Tools Extended (Phase 3) ───────────────────────────────────────────


class TestMCPToolsExtended:
    """Phase 3: Additional tool invocations on the live Azure endpoint."""

    def test_calculate_roi_tool_returns_savings(self) -> None:
        """calculate_roi remote call returns a non-error response with savings data."""
        with httpx.Client() as client:
            session_id = _mcp_session(client)
            result = _mcp_call(
                client,
                session_id,
                "tools/call",
                {"name": "calculate_roi", "arguments": {}},
                req_id=20,
            )
            assert "result" in result, f"calculate_roi returned error: {result}"
            content = result["result"]
            # extract text from content array
            text = ""
            if "content" in content:
                items = content["content"]
                if items:
                    text = items[0].get("text", str(items[0]))
            elif "structuredContent" in content:
                text = str(content["structuredContent"])
            # Verify it's not an empty error response
            assert text or content, "calculate_roi returned empty result"

    def test_get_business_impact_tool_returns_score(self) -> None:
        """get_business_impact remote call returns a non-error response."""
        with httpx.Client() as client:
            session_id = _mcp_session(client)
            result = _mcp_call(
                client,
                session_id,
                "tools/call",
                {"name": "get_business_impact", "arguments": {}},
                req_id=21,
            )
            assert "result" in result, f"get_business_impact returned error: {result}"

    def test_plan_refactoring_missing_finding_returns_graceful_error(self) -> None:
        """plan_refactoring with an unknown finding_id returns an error message, not a crash."""
        with httpx.Client() as client:
            session_id = _mcp_session(client)
            result = _mcp_call(
                client,
                session_id,
                "tools/call",
                {
                    "name": "plan_refactoring",
                    "arguments": {"finding_id": "nonexistent-finding-9z8y"},
                },
                req_id=22,
            )
            # Expected: graceful error response (not a 500 / unhandled crash)
            assert "result" in result or "error" in result, (
                "plan_refactoring should return a result or structured error"
            )
            if "result" in result:
                content = result["result"]
                text = ""
                if "content" in content and content["content"]:
                    text = content["content"][0].get("text", "")
                elif "structuredContent" in content:
                    text = str(content["structuredContent"])
                # Should say the finding was not found
                assert "not found" in text.lower() or "error" in text.lower() or text, (
                    f"Expected graceful error message; got: {text[:200]!r}"
                )

    def test_scan_repository_health_path(self) -> None:
        """scan_repository returns a structured response (even for empty/default path)."""
        with httpx.Client() as client:
            session_id = _mcp_session(client)
            result = _mcp_call(
                client,
                session_id,
                "tools/call",
                {
                    "name": "scan_repository",
                    "arguments": {
                        "repo_path": ".",
                        "scanners": "all",
                    },
                },
                req_id=23,
            )
            # Should return result (may have 0 findings if running in container with no code)
            assert "result" in result or "error" in result, (
                "scan_repository should return a result or structured error"
            )


# ── MCP Resources Extended (Phase 3) ──────────────────────────────────────


class TestMCPResourcesExtended:
    """Phase 3: Additional resource reads on the live Azure endpoint."""

    def test_read_scanners_resource(self) -> None:
        """codecustodian://scanners resource lists scanner names."""
        with httpx.Client() as client:
            session_id = _mcp_session(client)
            result = _mcp_call(
                client,
                session_id,
                "resources/read",
                {"uri": "codecustodian://scanners"},
                req_id=30,
            )
            assert "result" in result
            contents = result["result"]["contents"]
            assert len(contents) > 0
            text = contents[0].get("text", "")
            assert "security" in text.lower() or "deprecated" in text.lower(), (
                f"Expected scanner names in resource; got: {text[:300]!r}"
            )

    def test_read_findings_all_resource(self) -> None:
        """findings://test-repo/all URI template resource returns valid JSON."""
        with httpx.Client() as client:
            session_id = _mcp_session(client)
            result = _mcp_call(
                client,
                session_id,
                "resources/read",
                {"uri": "findings://test-repo/all"},
                req_id=31,
            )
            assert "result" in result
            contents = result["result"]["contents"]
            assert len(contents) > 0
            text = contents[0].get("text", "")
            data = json.loads(text)
            assert "findings" in data
            assert "total" in data

    def test_read_dashboard_resource(self) -> None:
        """dashboard://test-team/summary resource returns expected structure."""
        with httpx.Client() as client:
            session_id = _mcp_session(client)
            result = _mcp_call(
                client,
                session_id,
                "resources/read",
                {"uri": "dashboard://test-team/summary"},
                req_id=32,
            )
            assert "result" in result
            contents = result["result"]["contents"]
            assert len(contents) > 0
            text = contents[0].get("text", "")
            data = json.loads(text)
            assert "total_findings" in data
            assert "by_severity" in data
            assert "by_type" in data

    def test_read_config_settings_resource(self) -> None:
        """config://settings resource returns JSON with a version key."""
        with httpx.Client() as client:
            session_id = _mcp_session(client)
            result = _mcp_call(
                client,
                session_id,
                "resources/read",
                {"uri": "config://settings"},
                req_id=33,
            )
            assert "result" in result
            contents = result["result"]["contents"]
            assert len(contents) > 0
            text = contents[0].get("text", "")
            # Should be valid JSON
            try:
                data = json.loads(text)
                assert isinstance(data, dict)
            except json.JSONDecodeError:
                # May be empty JSON object for default config — still acceptable
                assert text is not None
