"""MCP prompt definitions.

Pre-built prompts that AI assistants can use for common
CodeCustodian workflows.
"""

from __future__ import annotations

from fastmcp import FastMCP


def register_prompts(mcp: FastMCP) -> None:
    """Register all MCP prompts on the server instance."""

    @mcp.prompt()
    def analyze_finding(
        finding_type: str,
        description: str,
        file_path: str,
        line: int,
    ) -> str:
        """Generate a prompt for analyzing a specific finding."""
        return f"""\
Analyze this tech debt finding and suggest a refactoring plan:

Type: {finding_type}
File: {file_path}
Line: {line}
Description: {description}

Please provide:
1. Root cause analysis
2. Recommended fix with code changes
3. Risk assessment
4. Testing recommendations
"""

    @mcp.prompt()
    def prioritize_findings(total_count: int) -> str:
        """Generate a prompt for prioritizing findings."""
        return f"""\
I have {total_count} tech debt findings. Please help prioritize them by:

1. Business impact (what breaks if not fixed)
2. Effort required (trivial/small/medium/large)
3. Risk of the fix (low/medium/high)
4. Dependencies between findings

Suggest an optimal order for addressing them.
"""

    @mcp.prompt()
    def review_plan(plan_summary: str, confidence: int) -> str:
        """Generate a prompt for reviewing a refactoring plan."""
        return f"""\
Please review this refactoring plan:

Summary: {plan_summary}
AI Confidence: {confidence}/10

Evaluate:
1. Is the proposed change safe?
2. Are there edge cases not covered?
3. Will existing tests still pass?
4. Are there better alternatives?
"""
