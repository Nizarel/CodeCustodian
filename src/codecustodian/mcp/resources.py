"""MCP resource definitions.

Exposes CodeCustodian state as MCP resources that AI assistants
can read for context.
"""

from __future__ import annotations

from fastmcp import FastMCP


def register_resources(mcp: FastMCP) -> None:
    """Register all MCP resources on the server instance."""

    @mcp.resource("codecustodian://config")
    async def get_config() -> str:
        """Return the current CodeCustodian configuration."""
        from codecustodian.config.schema import CodeCustodianConfig

        try:
            config = CodeCustodianConfig.from_file(".codecustodian.yml")
            return config.to_yaml()
        except Exception:
            from codecustodian.config.defaults import DEFAULT_YAML
            return DEFAULT_YAML

    @mcp.resource("codecustodian://version")
    async def get_version() -> str:
        """Return the current CodeCustodian version."""
        from codecustodian import __version__
        return __version__

    @mcp.resource("codecustodian://scanners")
    async def get_scanners() -> str:
        """List available scanners and their status."""
        from codecustodian.scanner.registry import get_default_registry

        registry = get_default_registry()
        scanners = registry.list_scanners()
        lines = [f"- {name}: {desc}" for name, desc in scanners.items()]
        return "\n".join(lines)
