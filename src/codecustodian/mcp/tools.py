"""MCP tool definitions for the CodeCustodian server.

Nine tools exposed via FastMCP covering the full pipeline:
scan → plan → apply → verify → PR, plus read-only analytics
and blast-radius impact analysis.

All tools use ``Context`` for progress reporting and logging, and carry
``ToolAnnotations`` to communicate intent to MCP clients.
"""

from __future__ import annotations

from mcp.types import ToolAnnotations

from fastmcp import Context, FastMCP

from codecustodian.logging import get_logger

logger = get_logger("mcp.tools")


# ── Helpers ────────────────────────────────────────────────────────────────


def _summarize_findings(findings: list) -> dict:
    """Group findings by type and severity."""
    by_type: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for f in findings:
        t = f.type.value if hasattr(f.type, "value") else str(f.type)
        s = f.severity.value if hasattr(f.severity, "value") else str(f.severity)
        by_type[t] = by_type.get(t, 0) + 1
        by_severity[s] = by_severity.get(s, 0) + 1
    return {"by_type": by_type, "by_severity": by_severity}


# ── Registration ───────────────────────────────────────────────────────────


def register_tools(mcp: FastMCP) -> None:  # noqa: C901 — intentionally long
    """Register all MCP tools on the server instance."""

    # ── 1. scan_repository ─────────────────────────────────────────────

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def scan_repository(
        repo_path: str = ".",
        scanners: str = "all",
        config_path: str = ".codecustodian.yml",
        ctx: Context = None,  # type: ignore[assignment]
    ) -> dict:
        """Scan a repository for technical debt issues.

        Returns findings grouped by type and severity.  Results are
        cached so downstream tools (``plan_refactoring``, etc.) can
        reference them by ID.

        Args:
            repo_path: Path to repository root.
            scanners: Comma-separated scanner names, or ``'all'``.
            config_path: Path to configuration YAML.
        """
        from codecustodian.config.schema import CodeCustodianConfig
        from codecustodian.mcp.cache import scan_cache
        from codecustodian.scanner.registry import get_default_registry

        if ctx:
            await ctx.info("Loading configuration…")

        try:
            config = CodeCustodianConfig.from_file(config_path)
        except Exception:
            config = None

        registry = get_default_registry(config)

        if scanners == "all":
            enabled = registry.get_enabled()
        else:
            names = [s.strip() for s in scanners.split(",")]
            enabled = [s for n in names if (s := registry.get(n)) is not None]

        all_findings = []
        total = len(enabled)
        for idx, scanner in enumerate(enabled):
            if ctx:
                await ctx.report_progress(idx, total, f"Running {scanner.name}…")
            try:
                results = scanner.scan(repo_path)
                all_findings.extend(results)
            except Exception as exc:
                if ctx:
                    await ctx.warning(f"Scanner {scanner.name} failed: {exc}")

        # Cache findings for inter-tool use
        await scan_cache.store_findings(all_findings)

        if ctx:
            await ctx.report_progress(total, total, "Scan complete")

        return {
            "total": len(all_findings),
            "findings": [f.model_dump(mode="json") for f in all_findings[:50]],
            "summary": _summarize_findings(all_findings),
        }

    # ── 2. list_scanners ───────────────────────────────────────────────

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def list_scanners(
        ctx: Context = None,  # type: ignore[assignment]
    ) -> list[dict]:
        """List all available scanners with marketplace-style metadata.

        Returns name, description, enabled status, and finding type for
        each registered scanner.
        """
        from codecustodian.scanner.registry import get_default_registry

        registry = get_default_registry()
        catalog = registry.list_catalog()

        if ctx:
            await ctx.info(f"Found {len(catalog)} registered scanners")

        return catalog

    # ── 3. plan_refactoring ────────────────────────────────────────────

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def plan_refactoring(
        finding_id: str,
        repo_path: str = ".",
        ctx: Context = None,  # type: ignore[assignment]
    ) -> dict:
        """Generate an AI-powered refactoring plan for a finding.

        The finding must have been cached by a prior ``scan_repository``
        call.  The resulting plan is cached for ``apply_refactoring``.

        Args:
            finding_id: ID of the finding from a scan result.
            repo_path: Path to repository root.
        """
        from codecustodian.mcp.cache import scan_cache
        from codecustodian.models import CodeContext

        finding = await scan_cache.get_finding(finding_id)
        if finding is None:
            return {"error": f"Finding '{finding_id}' not found in cache. Run scan_repository first."}

        if ctx:
            await ctx.info(f"Planning refactoring for {finding.type.value} in {finding.file}")
            await ctx.report_progress(0, 3, "Building code context…")

        # Build minimal code context
        context = CodeContext(
            file_path=finding.file,
            source_code="",
            start_line=max(1, finding.line - 10),
            end_line=finding.line + 10,
        )

        try:
            from pathlib import Path

            file_path = Path(repo_path) / finding.file
            if file_path.exists():
                lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
                start = max(0, finding.line - 11)
                end = min(len(lines), finding.line + 10)
                context.source_code = "\n".join(lines[start:end])
                context.start_line = start + 1
                context.end_line = end
        except Exception:
            pass

        if ctx:
            await ctx.report_progress(1, 3, "Generating plan via Copilot SDK…")

        try:
            from codecustodian.config.schema import CodeCustodianConfig
            from codecustodian.planner.copilot_client import CopilotPlannerClient
            from codecustodian.planner.planner import Planner

            config = CodeCustodianConfig()
            copilot = CopilotPlannerClient(config.advanced.copilot)
            planner = Planner(config=config, copilot_client=copilot)
            plan = await planner.plan_refactoring(finding, context)
        except Exception as exc:
            return {"error": f"Planning failed: {exc}", "finding_id": finding_id}

        if ctx:
            await ctx.report_progress(3, 3, "Plan ready")

        # Cache plan for apply_refactoring
        if hasattr(plan, "id"):
            await scan_cache.store_plan(plan)

        return plan.model_dump(mode="json") if hasattr(plan, "model_dump") else {"plan": str(plan)}

    # ── 4. apply_refactoring ───────────────────────────────────────────

    @mcp.tool(
        annotations=ToolAnnotations(destructiveHint=True, idempotentHint=False),
    )
    async def apply_refactoring(
        plan_id: str,
        repo_path: str = ".",
        ctx: Context = None,  # type: ignore[assignment]
    ) -> dict:
        """Apply a cached refactoring plan to the codebase.

        **Destructive** — creates file backups before modifying code.
        The plan must have been cached by ``plan_refactoring``.

        Args:
            plan_id: ID of the plan from ``plan_refactoring``.
            repo_path: Path to repository root.
        """
        from pathlib import Path as _Path

        from codecustodian.executor.file_editor import SafeFileEditor
        from codecustodian.mcp.cache import scan_cache

        plan = await scan_cache.get_plan(plan_id)
        if plan is None:
            return {"error": f"Plan '{plan_id}' not found in cache. Run plan_refactoring first."}

        if ctx:
            await ctx.warning("Applying destructive file changes — backups will be created")

        editor = SafeFileEditor(backup_dir=_Path(repo_path) / ".codecustodian-backups")

        try:
            changed_files = editor.apply_changes(plan.changes)
            changed = [str(p) for p in changed_files]
        except Exception as exc:
            return {"error": f"Apply failed (changes rolled back): {exc}", "plan_id": plan_id}

        if ctx:
            await ctx.info(f"Applied {len(changed)} file changes")

        return {
            "plan_id": plan_id,
            "success": True,
            "changed_files": changed,
        }

    # ── 5. verify_changes ──────────────────────────────────────────────

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def verify_changes(
        changed_files: list[str],
        repo_path: str = ".",
        ctx: Context = None,  # type: ignore[assignment]
    ) -> dict:
        """Run tests and linters on changed files.

        Returns pass/fail, coverage delta, and any new violations.

        Args:
            changed_files: List of file paths that were modified.
            repo_path: Path to repository root.
        """
        from pathlib import Path as _Path

        if ctx:
            await ctx.info(f"Verifying {len(changed_files)} changed files…")
            await ctx.report_progress(0, 2, "Running tests…")

        result: dict = {"passed": True, "stages": {}}

        try:
            from codecustodian.verifier.test_runner import TestRunner

            runner = TestRunner()
            paths = [_Path(f) for f in changed_files]
            test_result = runner.run_tests(paths, repo_path=repo_path)
            result["stages"]["tests"] = {
                "passed": test_result.passed,
                "tests_run": test_result.tests_run,
                "tests_passed": test_result.tests_passed,
                "tests_failed": test_result.tests_failed,
            }
            if not test_result.passed:
                result["passed"] = False
        except Exception as exc:
            result["stages"]["tests"] = {"error": str(exc)}

        if ctx:
            await ctx.report_progress(1, 2, "Running linters…")

        try:
            from codecustodian.verifier.linter import LinterRunner

            linter = LinterRunner()
            paths = [_Path(f) for f in changed_files]
            lint_result = linter.run_all(paths)
            result["stages"]["lint"] = {
                "passed": lint_result.passed,
                "violations": len(lint_result.violations) if hasattr(lint_result, "violations") else 0,
            }
            if not lint_result.passed:
                result["passed"] = False
        except Exception as exc:
            result["stages"]["lint"] = {"error": str(exc)}

        if ctx:
            await ctx.report_progress(2, 2, "Verification complete")

        return result

    # ── 6. create_pull_request ─────────────────────────────────────────

    @mcp.tool(
        annotations=ToolAnnotations(destructiveHint=True, openWorldHint=True),
    )
    async def create_pull_request(
        finding_id: str,
        plan_id: str,
        repo_path: str = ".",
        ctx: Context = None,  # type: ignore[assignment]
    ) -> dict:
        """Create a GitHub pull request for a completed refactoring.

        Branches, commits, pushes, and opens a PR on GitHub.

        Args:
            finding_id: ID of the original finding.
            plan_id: ID of the applied plan.
            repo_path: Path to repository root.
        """
        import os

        from codecustodian.executor.git_manager import GitManager
        from codecustodian.integrations.github_integration.pr_creator import PullRequestCreator
        from codecustodian.mcp.cache import scan_cache
        from codecustodian.models import ExecutionResult, VerificationResult

        finding = await scan_cache.get_finding(finding_id)
        plan = await scan_cache.get_plan(plan_id)

        if finding is None:
            return {"error": f"Finding '{finding_id}' not in cache"}
        if plan is None:
            return {"error": f"Plan '{plan_id}' not in cache"}

        if ctx:
            await ctx.info("Creating branch and committing changes…")

        try:
            git = GitManager(repo_path)
            branch = git.create_branch(finding)
            commit_sha = git.commit(finding, plan)
            git.push(branch)
        except Exception as exc:
            return {"error": f"Git operations failed: {exc}"}

        if ctx:
            await ctx.info("Opening pull request on GitHub…")

        token = os.environ.get("GITHUB_TOKEN", "")
        if not token:
            return {"error": "GITHUB_TOKEN environment variable not set"}

        try:
            repo_name = git.get_repo_name()
            creator = PullRequestCreator(token=token, repo_name=repo_name)
            execution = ExecutionResult(plan_id=plan.id, success=True)
            verification = VerificationResult(passed=True)
            pr_info = creator.create_pr(
                finding=finding,
                plan=plan,
                execution=execution,
                verification=verification,
                branch=branch,
            )
        except Exception as exc:
            return {"error": f"PR creation failed: {exc}"}

        if ctx:
            await ctx.info(f"PR #{pr_info.number} created: {pr_info.url}")

        return pr_info.model_dump(mode="json")

    # ── 7. calculate_roi ───────────────────────────────────────────────

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def calculate_roi(
        finding_id: str,
        ctx: Context = None,  # type: ignore[assignment]
    ) -> dict:
        """Calculate return-on-investment metrics for fixing a finding.

        Estimates hours saved, risk reduction, and cost based on
        finding severity and type.

        Args:
            finding_id: ID of a cached finding.
        """
        from codecustodian.mcp.cache import scan_cache

        finding = await scan_cache.get_finding(finding_id)
        if finding is None:
            return {"error": f"Finding '{finding_id}' not in cache"}

        severity_hours = {"critical": 8.0, "high": 4.0, "medium": 2.0, "low": 1.0, "info": 0.5}
        type_multiplier = {
            "deprecated_api": 1.5,
            "security": 3.0,
            "code_smell": 1.0,
            "todo_comment": 0.5,
            "type_coverage": 0.8,
        }

        sev = finding.severity.value if hasattr(finding.severity, "value") else str(finding.severity)
        typ = finding.type.value if hasattr(finding.type, "value") else str(finding.type)
        hours = severity_hours.get(sev, 1.0) * type_multiplier.get(typ, 1.0)

        hourly_rate = 75.0  # USD, configurable
        cost_of_inaction = hours * hourly_rate
        fix_cost = 0.50  # average AI cost per fix
        roi = ((cost_of_inaction - fix_cost) / fix_cost) * 100 if fix_cost > 0 else 0

        result = {
            "finding_id": finding_id,
            "estimated_manual_hours": round(hours, 1),
            "cost_of_inaction_usd": round(cost_of_inaction, 2),
            "automated_fix_cost_usd": fix_cost,
            "roi_percentage": round(roi, 1),
            "risk_reduction": sev,
        }

        if ctx:
            await ctx.info(f"ROI: {roi:.0f}% — saves ~{hours:.1f}h manual effort")

        return result

    # ── 8. get_business_impact ─────────────────────────────────────────

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def get_business_impact(
        finding_id: str,
        repo_path: str = ".",
        ctx: Context = None,  # type: ignore[assignment]
    ) -> dict:
        """Analyse business impact of a technical debt finding.

        Uses the 5-factor ``BusinessImpactScorer`` (FR-PRIORITY-100)
        to compute usage frequency, criticality, change frequency,
        velocity impact, and regulatory risk scores.

        Args:
            finding_id: ID of a cached finding.
            repo_path: Path to repository root (for git history analysis).
        """
        from codecustodian.intelligence.business_impact import BusinessImpactScorer
        from codecustodian.mcp.cache import scan_cache

        finding = await scan_cache.get_finding(finding_id)
        if finding is None:
            return {"error": f"Finding '{finding_id}' not in cache"}

        if ctx:
            await ctx.info(f"Scoring business impact for {finding.file}")

        scorer = BusinessImpactScorer()
        breakdown = await scorer.score_detailed(finding, repo_path)

        sev = finding.severity.value if hasattr(finding.severity, "value") else str(finding.severity)

        # Map score to business impact level for backward compatibility
        if breakdown.total > 500 or sev == "critical":
            biz_level = "critical"
        elif breakdown.total > 200 or sev == "high":
            biz_level = "high"
        elif breakdown.total > 100 or sev == "medium":
            biz_level = "medium"
        else:
            biz_level = "low"

        result = {
            "finding_id": finding_id,
            "total_score": breakdown.total,
            "factors": {
                "usage_frequency": breakdown.usage,
                "criticality": breakdown.criticality,
                "change_frequency": breakdown.change_frequency,
                "velocity_impact": breakdown.velocity_impact,
                "regulatory_risk": breakdown.regulatory_risk,
            },
            "factor_descriptions": breakdown.factors,
            "affected_file": finding.file,
            "finding_type": finding.type.value if hasattr(finding.type, "value") else str(finding.type),
            "severity": sev,
            # Backward-compatible keys
            "business_impact_level": biz_level,
            "sla_risk": biz_level in ("critical", "high"),
            "recommendation": (
                "Fix immediately" if biz_level == "critical"
                else "Schedule for next sprint" if biz_level in ("high", "medium")
                else "Add to backlog"
            ),
        }

        if ctx:
            await ctx.info(
                f"Business impact: {breakdown.total:.0f} — "
                f"{', '.join(breakdown.factors) or 'baseline'}"
            )

        return result

    # ── 9. get_blast_radius ────────────────────────────────────────────

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def get_blast_radius(
        plan_id: str,
        repo_path: str = ".",
        ctx: Context = None,  # type: ignore[assignment]
    ) -> dict:
        """Analyse the blast radius of a cached refactoring plan.

        Builds an import-based dependency graph, then uses BFS to
        determine which modules are directly and transitively affected.
        Returns a risk score (0–1) and risk level.

        Args:
            plan_id: ID of a cached plan from ``plan_refactoring``.
            repo_path: Path to repository root.
        """
        from codecustodian.intelligence.blast_radius import BlastRadiusAnalyzer
        from codecustodian.mcp.cache import scan_cache

        plan = await scan_cache.get_plan(plan_id)
        if plan is None:
            return {"error": f"Plan '{plan_id}' not found in cache. Run plan_refactoring first."}

        if ctx:
            await ctx.info("Building dependency graph…")

        try:
            analyzer = BlastRadiusAnalyzer(repo_path)
            report = analyzer.analyze(plan)
        except Exception as exc:
            return {"error": f"Blast radius analysis failed: {exc}"}

        if ctx:
            await ctx.info(
                f"Blast radius: {report.radius_score:.0%} — risk {report.risk_level}"
            )

        return report.model_dump(mode="json")
