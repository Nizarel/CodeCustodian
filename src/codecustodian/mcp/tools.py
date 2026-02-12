"""MCP tool definitions.

Individual MCP tools exposed by the CodeCustodian server.
"""

from __future__ import annotations

from fastmcp import FastMCP


def register_tools(mcp: FastMCP) -> None:
    """Register all MCP tools on the server instance."""

    @mcp.tool()
    async def scan_repository(
        path: str = ".",
        scanners: str = "all",
    ) -> dict:
        """Scan a repository for tech debt issues.

        Args:
            path: Path to the repository root
            scanners: Comma-separated scanner names or 'all'
        """
        from codecustodian.scanner.registry import get_default_registry
        from codecustodian.models import FindingType

        registry = get_default_registry()
        scanner_names = (
            list(registry.list_scanners().keys())
            if scanners == "all"
            else [s.strip() for s in scanners.split(",")]
        )

        all_findings: list[dict] = []
        for name in scanner_names:
            scanner = registry.get(name)
            if scanner:
                findings = scanner.scan(path)
                all_findings.extend(f.model_dump() for f in findings)

        return {
            "total": len(all_findings),
            "findings": all_findings[:50],  # Limit for MCP response
        }

    @mcp.tool()
    async def get_finding_details(finding_id: str) -> dict:
        """Get detailed information about a specific finding."""
        return {
            "finding_id": finding_id,
            "status": "lookup not yet implemented — requires scan cache",
        }

    @mcp.tool()
    async def validate_config(path: str = ".codecustodian.yml") -> dict:
        """Validate a CodeCustodian configuration file."""
        from codecustodian.config.schema import CodeCustodianConfig

        try:
            config = CodeCustodianConfig.from_file(path)
            return {"valid": True, "summary": str(config)}
        except Exception as e:
            return {"valid": False, "error": str(e)}
