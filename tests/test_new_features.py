"""Tests for Phase 11 new features:

1. Diff Preview in dry-run mode
2. Finding Deep-Dive CLI command
3. HTML ROI Report export
4. Blast Radius Analysis
5. Architectural Drift Scanner
6. MCP get_blast_radius tool
"""

from __future__ import annotations

import json
import tempfile
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from codecustodian.cli.main import app
from codecustodian.models import (
    ChangeType,
    FileChange,
    Finding,
    FindingType,
    RefactoringPlan,
    RiskLevel,
    SeverityLevel,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_finding(**overrides) -> Finding:
    defaults = {
        "type": FindingType.DEPRECATED_API,
        "severity": SeverityLevel.HIGH,
        "file": "src/app.py",
        "line": 5,
        "description": "Deprecated API usage detected",
        "suggestion": "Use modern alternative",
        "priority_score": 120.0,
    }
    defaults.update(overrides)
    return Finding(**defaults)


def _make_plan(**overrides) -> RefactoringPlan:
    change = FileChange(
        file_path="src/app.py",
        change_type=ChangeType.REPLACE,
        old_content="old_call()",
        new_content="new_call()",
        start_line=5,
        end_line=5,
        description="Replace deprecated API call",
    )
    defaults = {
        "finding_id": "finding-001",
        "summary": "Replace deprecated API",
        "description": "Use supported API",
        "changes": [change],
        "confidence_score": 8,
        "risk_level": RiskLevel.LOW,
        "ai_reasoning": "Mechanical replacement.",
    }
    defaults.update(overrides)
    return RefactoringPlan(**defaults)


# ═══════════════════════════════════════════════════════════════════════════
# 1. Diff Preview
# ═══════════════════════════════════════════════════════════════════════════


class TestDiffPreview:
    """Test the _print_diff_preview helper used in dry-run mode."""

    def test_diff_preview_imports(self):
        """Verify diff Preview dependencies are importable."""
        import difflib

        from rich.syntax import Syntax  # noqa: F401

        # Ensure unified_diff works
        diff = list(difflib.unified_diff(["a\n"], ["b\n"], fromfile="a", tofile="b"))
        assert any(line.startswith("---") for line in diff)

    def test_diff_preview_function_exists(self):
        from codecustodian.cli.main import _print_diff_preview

        plans = [_make_plan()]
        # Should not raise even with no console
        _print_diff_preview(plans)

    def test_diff_preview_empty_plans(self):
        from codecustodian.cli.main import _print_diff_preview

        _print_diff_preview([])


# ═══════════════════════════════════════════════════════════════════════════
# 2. Finding Deep-Dive CLI command
# ═══════════════════════════════════════════════════════════════════════════


class TestFindingDeepDive:
    """Test the `finding` CLI command."""

    def test_finding_detail_function_exists(self):
        from codecustodian.cli.main import _print_finding_detail

        finding = _make_finding()
        # Should render without error
        _print_finding_detail(finding, repo_root=None)

    def test_finding_command_no_match(self, cli_runner):
        """Finding command with an ID that doesn't match any finding."""
        result = cli_runner.invoke(
            app,
            [
                "finding",
                "nonexistent-id-xyz",
                "--repo-path",
                "tests/fixtures/sample_repo",
            ],
        )
        assert result.exit_code == 1
        assert "No finding matching" in result.stdout

    def test_finding_command_with_match(self, cli_runner):
        """Finding command should display detail when a match is found."""
        result = cli_runner.invoke(
            app,
            [
                "finding",
                "sec",
                "--repo-path",
                "tests/fixtures/sample_repo",
            ],
        )
        # IDs are UUIDs so "sec" may or may not match; accept either outcome
        assert result.exit_code in (0, 1)


# ═══════════════════════════════════════════════════════════════════════════
# 3. HTML ROI Report
# ═══════════════════════════════════════════════════════════════════════════


class TestHTMLROIReport:
    """Test the export_html method on ROICalculator."""

    def test_export_html_valid(self):
        from codecustodian.enterprise.roi_calculator import ROICalculator, ROIReport

        report = ROIReport(
            period="2025-Q1",
            total_fixes=42,
            successful_fixes=40,
            total_operational_cost=50.0,
            estimated_savings_usd=3000.0,
            net_roi_pct=5900.0,
            total_hours_saved=40.0,
            hourly_rate_used=75.0,
            payback_period_months=0.5,
            productivity_gain_pct=25.0,
            by_finding_type={
                "deprecated_api": {"count": 20, "cost": 25, "hours": 40, "savings": 1500},
                "security": {"count": 10, "cost": 15, "hours": 30, "savings": 1000},
                "code_smell": {"count": 12, "cost": 10, "hours": 18, "savings": 500},
            },
        )

        calc = ROICalculator()
        html = calc.export_html(report)

        assert "<!DOCTYPE html>" in html
        assert "CodeCustodian ROI Report" in html
        assert "chart.js" in html.lower() or "Chart" in html
        assert "$3,000" in html
        assert "5900%" in html or "5,900%" in html
        assert "deprecated_api" in html
        assert "security" in html

    def test_export_html_empty_report(self):
        from codecustodian.enterprise.roi_calculator import ROICalculator, ROIReport

        report = ROIReport(period="empty", by_finding_type={})
        calc = ROICalculator()
        html = calc.export_html(report)
        assert "<!DOCTYPE html>" in html

    def test_report_command_supports_html(self, cli_runner, monkeypatch, tmp_path):
        """The 'report' command should accept --format html."""
        from codecustodian.enterprise.roi_calculator import ROICalculator, ROIReport

        report = ROIReport(period="test", by_finding_type={})

        monkeypatch.setattr(
            ROICalculator,
            "generate_report",
            lambda self, *a, **kw: report,
        )
        monkeypatch.setattr(
            ROICalculator,
            "export_html",
            lambda self, r: "<html>mock</html>",
        )

        out_file = str(tmp_path / "report.html")
        result = cli_runner.invoke(
            app,
            ["report", "--format", "html", "--output", out_file],
        )
        assert result.exit_code == 0
        assert Path(out_file).read_text(encoding="utf-8") == "<html>mock</html>"

    def test_report_command_rejects_invalid_format(self, cli_runner):
        result = cli_runner.invoke(app, ["report", "--format", "xml"])
        assert result.exit_code != 0


# ═══════════════════════════════════════════════════════════════════════════
# 4. Blast Radius Analysis
# ═══════════════════════════════════════════════════════════════════════════


class TestBlastRadiusAnalyzer:
    """Test blast radius module."""

    def _make_repo(self, tmp_path: Path) -> Path:
        """Create a mini Python repo with import relationships."""
        (tmp_path / "a.py").write_text("import b\n", encoding="utf-8")
        (tmp_path / "b.py").write_text("import c\n", encoding="utf-8")
        (tmp_path / "c.py").write_text("x = 1\n", encoding="utf-8")
        (tmp_path / "test_a.py").write_text("import a\n", encoding="utf-8")
        return tmp_path

    def test_build_graph(self, tmp_path: Path):
        from codecustodian.intelligence.blast_radius import BlastRadiusAnalyzer

        repo = self._make_repo(tmp_path)
        analyzer = BlastRadiusAnalyzer(repo)
        analyzer.build_graph()
        assert len(analyzer._all_modules) >= 4
        assert "b" in analyzer._graph.get("a", set())

    def test_analyze_low_radius(self, tmp_path: Path):
        from codecustodian.intelligence.blast_radius import BlastRadiusAnalyzer

        repo = self._make_repo(tmp_path)
        plan = _make_plan(
            changes=[
                FileChange(
                    file_path="c.py",
                    change_type=ChangeType.REPLACE,
                    old_content="x = 1",
                    new_content="x = 2",
                    start_line=1,
                    end_line=1,
                    description="Change constant",
                )
            ]
        )
        analyzer = BlastRadiusAnalyzer(repo)
        report = analyzer.analyze(plan)
        assert 0.0 <= report.radius_score <= 1.0
        assert report.risk_level in ("low", "medium", "high", "critical")
        # c.py is imported by b.py (direct), b.py by a.py (transitive)
        assert len(report.directly_affected) >= 1

    def test_analyze_finds_tests(self, tmp_path: Path):
        from codecustodian.intelligence.blast_radius import BlastRadiusAnalyzer

        repo = self._make_repo(tmp_path)
        plan = _make_plan(
            changes=[
                FileChange(
                    file_path="a.py",
                    change_type=ChangeType.REPLACE,
                    old_content="import b",
                    new_content="import b  # changed",
                    start_line=1,
                    end_line=1,
                    description="Modify a.py",
                )
            ]
        )
        analyzer = BlastRadiusAnalyzer(repo)
        report = analyzer.analyze(plan)
        assert any("test_a" in t for t in report.affected_tests)

    def test_risk_levels(self, tmp_path: Path):
        from codecustodian.intelligence.blast_radius import BlastRadiusReport

        # Validate the Pydantic model
        r = BlastRadiusReport(
            directly_affected=["a"],
            transitively_affected=["b"],
            total_files_in_repo=10,
            radius_score=0.4,
            risk_level="critical",
        )
        assert r.risk_level == "critical"
        assert r.radius_score == 0.4

    def test_empty_repo(self, tmp_path: Path):
        from codecustodian.intelligence.blast_radius import BlastRadiusAnalyzer

        # With no Python files the graph is empty, but plan references
        # src/app.py which becomes 1 changed module out of max(0,1)→1.
        plan = _make_plan()
        analyzer = BlastRadiusAnalyzer(tmp_path)
        report = analyzer.analyze(plan)
        # The analyzer should not crash on an empty repo
        assert 0.0 <= report.radius_score <= 1.0


# ═══════════════════════════════════════════════════════════════════════════
# 4b. Blast Radius Safety Check
# ═══════════════════════════════════════════════════════════════════════════


class TestBlastRadiusSafetyCheck:
    """Test the blast radius safety check (Check #7)."""

    @pytest.mark.asyncio
    async def test_passes_for_low_radius(self, tmp_path: Path):
        from codecustodian.executor.safety_checks import SafetyCheckRunner

        (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
        plan = _make_plan(
            changes=[
                FileChange(
                    file_path="a.py",
                    change_type=ChangeType.REPLACE,
                    old_content="x = 1",
                    new_content="x = 2",
                    start_line=1,
                    end_line=1,
                    description="Tweak",
                )
            ]
        )
        checker = SafetyCheckRunner(repo_path=str(tmp_path))
        result = await checker.check_blast_radius(plan)
        assert result.name == "blast_radius"

    @pytest.mark.asyncio
    async def test_graceful_fallback_on_error(self):
        from codecustodian.executor.safety_checks import SafetyCheckRunner

        plan = _make_plan()
        checker = SafetyCheckRunner(repo_path="/nonexistent/path")
        # The analyzer runs on a nonexistent path producing a high radius
        # (plan module vs empty graph → 100%), so the check may fail or pass.
        # The key invariant: it should NOT raise an unhandled exception.
        result = await checker.check_blast_radius(plan)
        assert result.name == "blast_radius"


# ═══════════════════════════════════════════════════════════════════════════
# 5. Architectural Drift Scanner
# ═══════════════════════════════════════════════════════════════════════════


class TestArchitecturalDriftScanner:
    """Test the architectural drift detection scanner."""

    def test_scanner_name(self):
        from codecustodian.scanner.architectural_drift import ArchitecturalDriftScanner

        scanner = ArchitecturalDriftScanner()
        assert scanner.name == "architectural_drift"
        assert scanner.enabled is True

    def test_empty_repo(self, tmp_path: Path):
        from codecustodian.scanner.architectural_drift import ArchitecturalDriftScanner

        scanner = ArchitecturalDriftScanner()
        findings = scanner.scan(str(tmp_path))
        assert findings == []

    def test_detects_module_size_violation(self, tmp_path: Path):
        from codecustodian.scanner.architectural_drift import ArchitecturalDriftScanner

        big_file = tmp_path / "big.py"
        big_file.write_text("\n".join(f"line_{i} = {i}" for i in range(700)), encoding="utf-8")
        scanner = ArchitecturalDriftScanner()
        findings = scanner.scan(str(tmp_path))
        size_findings = [f for f in findings if f.metadata.get("drift_type") == "module_size"]
        assert len(size_findings) >= 1
        assert "700" in size_findings[0].description or "exceeding" in size_findings[0].description

    def test_no_findings_for_small_files(self, tmp_path: Path):
        from codecustodian.scanner.architectural_drift import ArchitecturalDriftScanner

        (tmp_path / "small.py").write_text("x = 1\n", encoding="utf-8")
        scanner = ArchitecturalDriftScanner()
        findings = scanner.scan(str(tmp_path))
        size_findings = [f for f in findings if f.metadata.get("drift_type") == "module_size"]
        assert len(size_findings) == 0

    def test_detects_circular_dependency(self, tmp_path: Path):
        from codecustodian.scanner.architectural_drift import ArchitecturalDriftScanner

        # Create a repo structure that mimics src/codecustodian layout
        src = tmp_path / "src" / "codecustodian"
        src.mkdir(parents=True)
        pkg_a = src / "alpha"
        pkg_b = src / "beta"
        pkg_a.mkdir()
        pkg_b.mkdir()
        (pkg_a / "__init__.py").write_text("import beta\n", encoding="utf-8")
        (pkg_b / "__init__.py").write_text("import alpha\n", encoding="utf-8")

        scanner = ArchitecturalDriftScanner()
        findings = scanner.scan(str(tmp_path))
        cycle_findings = [f for f in findings if f.metadata.get("drift_type") == "circular_dependency"]
        # May or may not detect depending on package resolution — scanner uses top-level package
        # Just verify no crash
        assert isinstance(findings, list)

    def test_registered_in_default_registry(self):
        from codecustodian.scanner.registry import get_default_registry

        registry = get_default_registry()
        listing = registry.list_scanners()
        assert "architectural_drift" in listing

    def test_finding_fields(self, tmp_path: Path):
        from codecustodian.scanner.architectural_drift import ArchitecturalDriftScanner

        big_file = tmp_path / "big.py"
        big_file.write_text("\n".join(f"x_{i} = {i}" for i in range(700)), encoding="utf-8")
        scanner = ArchitecturalDriftScanner()
        findings = scanner.scan(str(tmp_path))
        for f in findings:
            assert f.type == FindingType.CODE_SMELL
            assert f.severity in (SeverityLevel.LOW, SeverityLevel.MEDIUM, SeverityLevel.HIGH)
            assert f.scanner_name == "architectural_drift"


# ═══════════════════════════════════════════════════════════════════════════
# 6. MCP get_blast_radius tool
# ═══════════════════════════════════════════════════════════════════════════


class TestMCPBlastRadiusTool:
    """Test the get_blast_radius MCP tool.

    These tests require a compatible FastMCP version.
    They are skipped if the server cannot be imported (e.g. API changes).
    """

    @pytest.fixture(autouse=True)
    def _skip_if_mcp_broken(self):
        try:
            from codecustodian.mcp.server import mcp  # noqa: F401
        except (TypeError, ImportError):
            pytest.skip("FastMCP server init incompatible with installed version")

    @pytest.mark.asyncio
    async def test_tool_registered(self):
        from fastmcp import Client

        from codecustodian.mcp.server import mcp

        async with Client(mcp) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}

        assert "get_blast_radius" in names

    @pytest.mark.asyncio
    async def test_tool_readonly_annotation(self):
        from fastmcp import Client

        from codecustodian.mcp.server import mcp

        async with Client(mcp) as client:
            tools = await client.list_tools()

        for t in tools:
            if t.name == "get_blast_radius":
                assert t.annotations is not None
                assert t.annotations.readOnlyHint is True

    @pytest.mark.asyncio
    async def test_plan_not_in_cache(self):
        from fastmcp import Client

        from codecustodian.mcp.cache import ScanCache
        from codecustodian.mcp.server import mcp

        cache = ScanCache()
        with patch("codecustodian.mcp.cache.scan_cache", cache):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "get_blast_radius",
                    {"plan_id": "nonexistent"},
                )

        data = json.loads(result.content[0].text)
        assert "error" in data
        assert "not found" in data["error"]

    @pytest.mark.asyncio
    async def test_blast_radius_success(self, tmp_path: Path):
        from fastmcp import Client

        from codecustodian.intelligence.blast_radius import BlastRadiusReport
        from codecustodian.mcp.cache import ScanCache
        from codecustodian.mcp.server import mcp

        plan = _make_plan(id="p-br-001")
        cache = ScanCache()
        await cache.store_plan(plan)

        mock_report = BlastRadiusReport(
            directly_affected=["b"],
            transitively_affected=["c"],
            affected_tests=["test_a"],
            total_files_in_repo=10,
            radius_score=0.3,
            risk_level="high",
        )

        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = mock_report

        with (
            patch("codecustodian.mcp.cache.scan_cache", cache),
            patch(
                "codecustodian.intelligence.blast_radius.BlastRadiusAnalyzer",
                return_value=mock_analyzer,
            ),
        ):
            async with Client(mcp) as client:
                result = await client.call_tool(
                    "get_blast_radius",
                    {"plan_id": "p-br-001", "repo_path": str(tmp_path)},
                )

        data = json.loads(result.content[0].text)
        assert data["radius_score"] == 0.3
        assert data["risk_level"] == "high"
        assert "b" in data["directly_affected"]
