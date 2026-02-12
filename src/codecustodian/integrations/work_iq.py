"""Work item intelligence integration.

Maps findings to project management concepts — sprints,
backlogs, and priority queues.
"""

from __future__ import annotations

from codecustodian.logging import get_logger
from codecustodian.models import Finding, SeverityLevel

logger = get_logger("integrations.work_iq")


class WorkItemIntelligence:
    """Intelligent work-item routing and prioritization."""

    def prioritize_findings(self, findings: list[Finding]) -> list[Finding]:
        """Sort findings by business priority.

        Priority factors:
        1. Severity (critical > high > medium > low > info)
        2. Security findings first
        3. Deprecated APIs with known deadlines
        4. Code smells by complexity impact
        """
        severity_order = {
            SeverityLevel.CRITICAL: 0,
            SeverityLevel.HIGH: 1,
            SeverityLevel.MEDIUM: 2,
            SeverityLevel.LOW: 3,
            SeverityLevel.INFO: 4,
        }

        type_bonus = {
            "security": -1,
            "deprecated_api": 0,
            "code_smell": 1,
            "todo_comment": 2,
            "missing_type_hints": 3,
        }

        def sort_key(f: Finding) -> tuple:
            sev = severity_order.get(f.severity, 5)
            bonus = type_bonus.get(f.type.value, 5)
            return (sev + bonus, f.file, f.line)

        sorted_findings = sorted(findings, key=sort_key)
        logger.info("Prioritized %d findings", len(sorted_findings))
        return sorted_findings

    def estimate_effort(self, finding: Finding) -> str:
        """Estimate effort for fixing a finding.

        Returns: "trivial" | "small" | "medium" | "large"
        """
        if finding.type.value in ("todo_comment", "missing_type_hints"):
            return "trivial"
        elif finding.type.value == "deprecated_api":
            return "small"
        elif finding.type.value == "code_smell":
            return "medium"
        elif finding.type.value == "security":
            return "medium"
        return "small"
