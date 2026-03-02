"""Tests for MCP resources, prompts, and the scan cache.

Uses FastMCP's in-memory ``Client(mcp)`` pattern.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from codecustodian.mcp.cache import ScanCache, _Entry
from codecustodian.mcp.server import mcp
from codecustodian.models import Finding, FindingType, RefactoringPlan, SeverityLevel

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_finding(**overrides) -> Finding:
    defaults = {
        "id": "f100",
        "type": FindingType.CODE_SMELL,
        "severity": SeverityLevel.MEDIUM,
        "file": "src/utils.py",
        "line": 10,
        "description": "High cyclomatic complexity",
    }
    defaults.update(overrides)
    return Finding(**defaults)


def _make_plan(**overrides) -> RefactoringPlan:
    defaults = {
        "id": "plan100",
        "finding_id": "f100",
        "summary": "Simplify complex function",
        "confidence_score": 8,
    }
    defaults.update(overrides)
    return RefactoringPlan(**defaults)


# ═══════════════════════════════════════════════════════════════════════════
# ScanCache unit tests
# ═══════════════════════════════════════════════════════════════════════════


class TestScanCache:
    @pytest.mark.asyncio
    async def test_store_and_get_finding(self):
        cache = ScanCache()
        finding = _make_finding()
        await cache.store_finding(finding)
        result = await cache.get_finding("f100")
        assert result is not None
        assert result.id == "f100"

    @pytest.mark.asyncio
    async def test_get_missing_finding(self):
        cache = ScanCache()
        result = await cache.get_finding("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_store_findings_bulk(self):
        cache = ScanCache()
        findings = [_make_finding(id=f"f{i}") for i in range(5)]
        await cache.store_findings(findings)
        listed = await cache.list_findings()
        assert len(listed) == 5

    @pytest.mark.asyncio
    async def test_store_and_get_plan(self):
        cache = ScanCache()
        plan = _make_plan()
        await cache.store_plan(plan)
        result = await cache.get_plan("plan100")
        assert result is not None
        assert result.id == "plan100"

    @pytest.mark.asyncio
    async def test_get_missing_plan(self):
        cache = ScanCache()
        result = await cache.get_plan("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_plans(self):
        cache = ScanCache()
        plans = [_make_plan(id=f"p{i}", finding_id=f"f{i}") for i in range(3)]
        for p in plans:
            await cache.store_plan(p)
        listed = await cache.list_plans()
        assert len(listed) == 3

    @pytest.mark.asyncio
    async def test_clear(self):
        cache = ScanCache()
        await cache.store_finding(_make_finding())
        await cache.store_plan(_make_plan())
        await cache.clear()
        assert await cache.list_findings() == []
        assert await cache.list_plans() == []

    @pytest.mark.asyncio
    async def test_stats(self):
        cache = ScanCache()
        await cache.store_finding(_make_finding())
        await cache.store_plan(_make_plan())
        stats = await cache.stats()
        assert stats["findings"] == 1
        assert stats["plans"] == 1

    @pytest.mark.asyncio
    async def test_expired_entries_purged(self):
        cache = ScanCache(ttl_seconds=0)  # immediate expiry
        await cache.store_finding(_make_finding())
        # Entry should be expired
        result = await cache.get_finding("f100")
        assert result is None

    def test_entry_expiry(self):
        entry = _Entry("value")
        assert not entry.expired(9999)
        assert entry.expired(0)


# ═══════════════════════════════════════════════════════════════════════════
# MCP Resources
# ═══════════════════════════════════════════════════════════════════════════


class TestMCPResources:
    @pytest.mark.asyncio
    async def test_read_version_resource(self):
        from fastmcp import Client

        from codecustodian import __version__

        async with Client(mcp) as client:
            result = await client.read_resource("codecustodian://version")

        assert __version__ in str(result)

    @pytest.mark.asyncio
    async def test_read_config_resource(self):
        from fastmcp import Client

        async with Client(mcp) as client:
            result = await client.read_resource("codecustodian://config")

        text = str(result)
        assert "scanners" in text
        assert "behavior" in text

    @pytest.mark.asyncio
    async def test_read_settings_resource(self):
        from fastmcp import Client

        async with Client(mcp) as client:
            result = await client.read_resource("config://settings")

        # Should be valid JSON
        text = result[0].text
        data = json.loads(text)
        assert isinstance(data, dict)

    @pytest.mark.asyncio
    async def test_read_scanners_resource(self):
        from fastmcp import Client

        async with Client(mcp) as client:
            result = await client.read_resource("codecustodian://scanners")

        text = str(result)
        # Should contain scanner names
        assert isinstance(text, str)

    @pytest.mark.asyncio
    async def test_findings_all_resource_empty(self):
        from fastmcp import Client

        cache = ScanCache()
        with patch("codecustodian.mcp.cache.scan_cache", cache):
            async with Client(mcp) as client:
                result = await client.read_resource("findings://test-repo/all")

        text = result[0].text
        data = json.loads(text)
        assert data["repo"] == "test-repo"
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_findings_all_with_data(self):
        from fastmcp import Client

        cache = ScanCache()
        await cache.store_findings([
            _make_finding(id="f1"),
            _make_finding(id="f2"),
        ])
        with patch("codecustodian.mcp.cache.scan_cache", cache):
            async with Client(mcp) as client:
                result = await client.read_resource("findings://myrepo/all")

        data = json.loads(result[0].text)
        assert data["total"] == 2
        assert data["repo"] == "myrepo"

    @pytest.mark.asyncio
    async def test_findings_by_type(self):
        from fastmcp import Client

        cache = ScanCache()
        await cache.store_findings([
            _make_finding(id="f1", type=FindingType.CODE_SMELL),
            _make_finding(id="f2", type=FindingType.SECURITY),
            _make_finding(id="f3", type=FindingType.CODE_SMELL),
        ])
        with patch("codecustodian.mcp.cache.scan_cache", cache):
            async with Client(mcp) as client:
                result = await client.read_resource("findings://repo/code_smell")

        data = json.loads(result[0].text)
        assert data["type"] == "code_smell"
        assert data["total"] == 2

    @pytest.mark.asyncio
    async def test_dashboard_resource(self):
        from fastmcp import Client

        cache = ScanCache()
        await cache.store_findings([
            _make_finding(id="f1", severity=SeverityLevel.HIGH),
            _make_finding(id="f2", severity=SeverityLevel.LOW),
        ])
        with patch("codecustodian.mcp.cache.scan_cache", cache):
            async with Client(mcp) as client:
                result = await client.read_resource("dashboard://my-team/summary")

        data = json.loads(result[0].text)
        assert data["team"] == "my-team"
        assert data["total_findings"] == 2
        assert "by_severity" in data
        assert "by_type" in data


# ═══════════════════════════════════════════════════════════════════════════
# MCP Prompts
# ═══════════════════════════════════════════════════════════════════════════


class TestMCPPrompts:
    @pytest.mark.asyncio
    async def test_refactor_finding_prompt(self):
        from fastmcp import Client

        async with Client(mcp) as client:
            result = await client.get_prompt(
                "refactor_finding",
                {
                    "finding_type": "deprecated_api",
                    "file_path": "src/app.py",
                    "line": 42,
                    "description": "DataFrame.append is deprecated",
                },
            )

        text = result.messages[0].content.text
        assert "deprecated_api" in text
        assert "src/app.py" in text
        assert "42" in text
        assert "Root cause" in text

    @pytest.mark.asyncio
    async def test_scan_summary_prompt(self):
        from fastmcp import Client

        async with Client(mcp) as client:
            result = await client.get_prompt(
                "scan_summary",
                {"total_findings": 25, "repo_name": "my-project"},
            )

        text = result.messages[0].content.text
        assert "25" in text
        assert "my-project" in text
        assert "prioriti" in text.lower()

    @pytest.mark.asyncio
    async def test_roi_report_prompt(self):
        from fastmcp import Client

        async with Client(mcp) as client:
            result = await client.get_prompt(
                "roi_report",
                {"team_name": "platform", "period": "quarterly"},
            )

        text = result.messages[0].content.text
        assert "platform" in text
        assert "quarterly" in text
        assert "ROI" in text

    @pytest.mark.asyncio
    async def test_onboard_repo_prompt(self):
        from fastmcp import Client

        async with Client(mcp) as client:
            result = await client.get_prompt(
                "onboard_repo",
                {"repo_url": "https://github.com/org/repo", "language": "python"},
            )

        text = result.messages[0].content.text
        assert "https://github.com/org/repo" in text
        assert "python" in text
        assert "codecustodian.yml" in text.lower() or ".codecustodian" in text.lower()

    @pytest.mark.asyncio
    async def test_refactor_finding_prompt_default_description(self):
        from fastmcp import Client

        async with Client(mcp) as client:
            result = await client.get_prompt(
                "refactor_finding",
                {"finding_type": "code_smell", "file_path": "x.py", "line": 1},
            )

        text = result.messages[0].content.text
        assert "code_smell" in text

    @pytest.mark.asyncio
    async def test_scan_summary_default_repo_name(self):
        from fastmcp import Client

        async with Client(mcp) as client:
            result = await client.get_prompt(
                "scan_summary",
                {"total_findings": 5},
            )

        text = result.messages[0].content.text
        assert "this repository" in text
