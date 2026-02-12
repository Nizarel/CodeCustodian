"""FastMCP server for CodeCustodian.

Exposes scanning, planning, and configuration as MCP tools and resources
consumable by Copilot Chat, VS Code, and other MCP clients.
"""

from __future__ import annotations

from fastmcp import FastMCP

from codecustodian import __version__

mcp = FastMCP(
    name="CodeCustodian",
    version=__version__,
    description="Autonomous AI agent for technical debt management",
)


# ── Tools ──────────────────────────────────────────────────────────────────


@mcp.tool()
def scan_repository(repo_path: str = ".", config_path: str = ".codecustodian.yml") -> dict:
    """Scan a repository for technical debt issues.

    Returns a summary of findings grouped by type and severity.
    """
    from codecustodian.config.schema import CodeCustodianConfig
    from codecustodian.scanner.registry import get_default_registry

    config = CodeCustodianConfig.from_file(config_path)
    registry = get_default_registry(config)

    all_findings = []
    for scanner in registry.get_enabled():
        findings = scanner.scan(repo_path)
        all_findings.extend(findings)

    return {
        "total": len(all_findings),
        "findings": [f.model_dump() for f in all_findings[:20]],
        "summary": _summarize_findings(all_findings),
    }


@mcp.tool()
def validate_config(config_path: str = ".codecustodian.yml") -> dict:
    """Validate a CodeCustodian configuration file."""
    from codecustodian.config.schema import CodeCustodianConfig

    try:
        config = CodeCustodianConfig.from_file(config_path)
        return {"valid": True, "config": config.model_dump(exclude_defaults=True)}
    except Exception as exc:
        return {"valid": False, "error": str(exc)}


@mcp.tool()
def list_scanners() -> list[dict]:
    """List all available scanners and their status."""
    from codecustodian.scanner.registry import get_default_registry

    registry = get_default_registry()
    return [
        {"name": name, "available": registry.get(name) is not None}
        for name in registry.list_scanners()
    ]


# ── Resources ──────────────────────────────────────────────────────────────


@mcp.resource("codecustodian://config")
def get_config() -> str:
    """Return the current CodeCustodian configuration as YAML."""
    from codecustodian.config.defaults import DEFAULT_YAML

    return DEFAULT_YAML


@mcp.resource("codecustodian://version")
def get_version() -> str:
    """Return the CodeCustodian version."""
    return __version__


# ── Prompts ────────────────────────────────────────────────────────────────


@mcp.prompt()
def analyze_finding(finding_type: str, file_path: str, line: int) -> str:
    """Generate a prompt to analyze a specific finding."""
    return (
        f"Analyze the following technical debt finding:\n"
        f"Type: {finding_type}\n"
        f"File: {file_path}\n"
        f"Line: {line}\n\n"
        f"Provide:\n"
        f"1. Root cause analysis\n"
        f"2. Recommended fix with code\n"
        f"3. Risk assessment (low/medium/high)\n"
        f"4. Confidence score (1-10)"
    )


# ── Helpers ────────────────────────────────────────────────────────────────


def _summarize_findings(findings: list) -> dict:
    """Group findings by type and severity."""
    by_type: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for f in findings:
        by_type[f.type.value] = by_type.get(f.type.value, 0) + 1
        by_severity[f.severity.value] = by_severity.get(f.severity.value, 0) + 1
    return {"by_type": by_type, "by_severity": by_severity}


def main() -> None:
    """Entry point for ``codecustodian-mcp`` command."""
    mcp.run()


if __name__ == "__main__":
    main()
