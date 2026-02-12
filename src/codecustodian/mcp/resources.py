"""MCP resource definitions for the CodeCustodian server.

Exposes CodeCustodian state as MCP resources that AI assistants can
read for context.  Uses URI-template resources for dynamic data
(e.g. ``findings://{repo_name}/all``).
"""

from __future__ import annotations

import json

from fastmcp import Context, FastMCP

from codecustodian.logging import get_logger

logger = get_logger("mcp.resources")


def register_resources(mcp: FastMCP) -> None:
    """Register all MCP resources on the server instance."""

    # ── Static resources ───────────────────────────────────────────────

    @mcp.resource("codecustodian://config")
    async def get_config() -> str:
        """Return the current CodeCustodian configuration as YAML."""
        from codecustodian.config.defaults import DEFAULT_YAML

        return DEFAULT_YAML

    @mcp.resource("codecustodian://version")
    async def get_version() -> str:
        """Return the current CodeCustodian version."""
        from codecustodian import __version__

        return __version__

    # ── Dynamic resources (URI templates) ──────────────────────────────

    @mcp.resource("findings://{repo_name}/all")
    async def get_all_findings(repo_name: str) -> str:
        """Return all cached findings for a repository as JSON.

        Findings are populated by calling the ``scan_repository`` tool.
        """
        from codecustodian.mcp.cache import scan_cache

        findings = await scan_cache.list_findings()
        data = [f.model_dump(mode="json") for f in findings]
        return json.dumps({"repo": repo_name, "total": len(data), "findings": data}, indent=2)

    @mcp.resource("findings://{repo_name}/{finding_type}")
    async def get_findings_by_type(repo_name: str, finding_type: str) -> str:
        """Return cached findings filtered by type.

        Valid types: ``deprecated_api``, ``todo_comment``, ``code_smell``,
        ``security``, ``type_coverage``.
        """
        from codecustodian.mcp.cache import scan_cache

        findings = await scan_cache.list_findings()
        filtered = [
            f.model_dump(mode="json")
            for f in findings
            if (f.type.value if hasattr(f.type, "value") else str(f.type)) == finding_type
        ]
        return json.dumps(
            {"repo": repo_name, "type": finding_type, "total": len(filtered), "findings": filtered},
            indent=2,
        )

    @mcp.resource("config://settings")
    async def get_settings() -> str:
        """Return the active configuration as a JSON summary."""
        from codecustodian.config.schema import CodeCustodianConfig

        try:
            config = CodeCustodianConfig.from_file(".codecustodian.yml")
        except Exception:
            config = CodeCustodianConfig()
        return json.dumps(config.model_dump(exclude_defaults=True), indent=2, default=str)

    @mcp.resource("dashboard://{team_name}/summary")
    async def get_dashboard(team_name: str) -> str:
        """Return a dashboard summary with finding counts and trends.

        Useful for team-level visibility into technical debt status.
        """
        from codecustodian.mcp.cache import scan_cache

        findings = await scan_cache.list_findings()
        by_severity: dict[str, int] = {}
        by_type: dict[str, int] = {}
        for f in findings:
            s = f.severity.value if hasattr(f.severity, "value") else str(f.severity)
            t = f.type.value if hasattr(f.type, "value") else str(f.type)
            by_severity[s] = by_severity.get(s, 0) + 1
            by_type[t] = by_type.get(t, 0) + 1

        cache_stats = await scan_cache.stats()

        dashboard = {
            "team": team_name,
            "total_findings": len(findings),
            "by_severity": by_severity,
            "by_type": by_type,
            "plans_cached": cache_stats.get("plans", 0),
        }
        return json.dumps(dashboard, indent=2)

    @mcp.resource("codecustodian://scanners")
    async def get_scanners() -> str:
        """List available scanners and their status."""
        from codecustodian.scanner.registry import get_default_registry

        registry = get_default_registry()
        catalog = registry.list_catalog()
        lines = [f"- {entry['name']}: {entry['description']}" for entry in catalog]
        return "\n".join(lines) if lines else "No scanners registered."
