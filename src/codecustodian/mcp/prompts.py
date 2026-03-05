"""MCP prompt definitions for the CodeCustodian server.

Pre-built prompts that AI assistants can use for common
CodeCustodian workflows — analysis, prioritisation, ROI reporting,
and repository onboarding.
"""

from __future__ import annotations

from fastmcp import FastMCP

from codecustodian.logging import get_logger

logger = get_logger("mcp.prompts")


def register_prompts(mcp: FastMCP) -> None:
    """Register all MCP prompts on the server instance."""

    # ── 1. refactor_finding ────────────────────────────────────────────

    @mcp.prompt()
    def refactor_finding(
        finding_type: str,
        file_path: str,
        line: int,
        description: str = "",
    ) -> str:
        """Generate a prompt for analysing and fixing a specific finding.

        Args:
            finding_type: Category (deprecated_api, code_smell, …).
            file_path: Source file containing the issue.
            line: Line number of the finding.
            description: Human-readable description of the issue.
        """
        return (
            "Analyse the following technical debt finding and produce a "
            "refactoring plan:\n\n"
            f"**Type:** {finding_type}\n"
            f"**File:** {file_path}\n"
            f"**Line:** {line}\n"
            f"**Description:** {description}\n\n"
            "Please provide:\n"
            "1. Root cause analysis\n"
            "2. Recommended fix with complete code changes\n"
            "3. Risk assessment (low / medium / high)\n"
            "4. Confidence score (1-10)\n"
            "5. Any alternative approaches\n"
            "6. Testing recommendations"
        )

    # ── 2. scan_summary ────────────────────────────────────────────────

    @mcp.prompt()
    def scan_summary(total_findings: int, repo_name: str = "this repository") -> str:
        """Generate a prompt for prioritising scan findings.

        Args:
            total_findings: Number of findings from the scan.
            repo_name: Human-readable repository name.
        """
        return (
            f"I have **{total_findings}** technical debt findings in "
            f"**{repo_name}**. Please help prioritise them by:\n\n"
            "1. **Business impact** — what breaks if not fixed?\n"
            "2. **Effort required** — trivial / small / medium / large\n"
            "3. **Risk of the fix** — low / medium / high\n"
            "4. **Dependencies** between findings\n\n"
            "Suggest an optimal order for addressing them and group "
            "related findings that can be fixed together."
        )

    # ── 3. roi_report ──────────────────────────────────────────────────

    @mcp.prompt()
    def roi_report(team_name: str, period: str = "monthly") -> str:
        """Generate a prompt for producing an ROI report.

        Args:
            team_name: Team or project to report on.
            period: Reporting period (weekly / monthly / quarterly).
        """
        return (
            f"Generate a **{period}** ROI report for team **{team_name}** "
            "covering technical debt remediation.\n\n"
            "Include:\n"
            "1. Total findings fixed vs remaining\n"
            "2. Estimated developer hours saved\n"
            "3. Cost savings (automated fix cost vs manual effort)\n"
            "4. Risk reduction across severity levels\n"
            "5. Trend analysis — is debt growing or shrinking?\n"
            "6. Recommendations for next period"
        )

    # ── 4. onboard_repo ────────────────────────────────────────────────

    @mcp.prompt()
    def onboard_repo(repo_url: str, language: str = "python") -> str:
        """Generate a prompt for onboarding a new repository.

        Args:
            repo_url: Git clone URL or GitHub URL.
            language: Primary language of the repository.
        """
        return (
            f"Help me on-board the repository at **{repo_url}** "
            f"(primary language: **{language}**) into CodeCustodian.\n\n"
            "Walk me through:\n"
            "1. Recommended `.codecustodian.yml` configuration\n"
            "2. Which scanners to enable and why\n"
            "3. Suggested thresholds (complexity, TODO age, coverage)\n"
            "4. Paths to exclude\n"
            "5. CI/CD integration steps (GitHub Actions)\n"
            "6. Expected initial scan results and how to interpret them"
        )

    # ── 5. forecast_report ─────────────────────────────────────────────

    @mcp.prompt()
    def forecast_report(repo_name: str, period: str = "quarterly") -> str:
        """Generate a prompt for interpreting debt forecasts.

        Args:
            repo_name: Repository or project name.
            period: Time horizon (monthly / quarterly / yearly).
        """
        return (
            f"Analyse the **{period}** technical debt forecast for "
            f"**{repo_name}** and produce an executive summary.\n\n"
            "Include:\n"
            "1. Current trend (improving / stable / worsening) with slope data\n"
            "2. Predicted findings at the end of the period\n"
            "3. Confidence interval and data quality assessment\n"
            "4. Top hotspot directories with growing debt\n"
            "5. Recommended sprint-level remediation priorities\n"
            "6. ROI projection if top hotspots are addressed\n"
            "7. Comparison with previous forecast (if available)"
        )
