"""Enterprise reporting and dashboards.

Generates tech debt reports, trend analysis, and executive summaries.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from codecustodian.logging import get_logger
from codecustodian.models import PipelineResult

logger = get_logger("enterprise.reporting")


class ReportGenerator:
    """Generate tech debt reports."""

    def __init__(self, output_dir: str | Path = "reports") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_markdown(self, result: PipelineResult) -> Path:
        """Generate a Markdown report from a pipeline result."""
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d_%H%M")
        report_path = self.output_dir / f"tech-debt-report-{timestamp}.md"

        content = f"""\
# Tech Debt Report

**Generated:** {datetime.now(UTC).isoformat()}
**Duration:** {result.duration_seconds:.1f}s

## Summary

| Metric | Value |
|--------|-------|
| Total findings | {result.total_findings} |
| Fixed | {result.findings_fixed} |
| PRs created | {result.prs_created} |
| Success rate | {result.success_rate:.1f}% |

## Findings

"""
        for finding in result.findings:
            content += (
                f"### {finding.type.value}: {finding.description[:80]}\n\n"
                f"- **File:** `{finding.file}`\n"
                f"- **Line:** {finding.line}\n"
                f"- **Severity:** {finding.severity.value}\n\n"
            )

        report_path.write_text(content, encoding="utf-8")
        logger.info("Report generated: %s", report_path)
        return report_path
