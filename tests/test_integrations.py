"""Tests for integration modules."""

from __future__ import annotations

from codecustodian.integrations.work_iq import WorkItemIntelligence
from codecustodian.models import Finding, FindingType, SeverityLevel


class TestWorkItemIntelligence:
    def _make_finding(self, severity: SeverityLevel, ftype: FindingType) -> Finding:
        return Finding(
            type=ftype,
            severity=severity,
            file="a.py",
            line=1,
            description="test",
        )

    def test_prioritize_by_severity(self):
        wiq = WorkItemIntelligence()
        findings = [
            self._make_finding(SeverityLevel.LOW, FindingType.CODE_SMELL),
            self._make_finding(SeverityLevel.CRITICAL, FindingType.SECURITY),
            self._make_finding(SeverityLevel.MEDIUM, FindingType.DEPRECATED_API),
        ]
        sorted_f = wiq.prioritize_findings(findings)
        assert sorted_f[0].severity == SeverityLevel.CRITICAL

    def test_estimate_effort(self):
        wiq = WorkItemIntelligence()
        todo = self._make_finding(SeverityLevel.LOW, FindingType.TODO_COMMENT)
        assert wiq.estimate_effort(todo) == "trivial"

        security = self._make_finding(SeverityLevel.HIGH, FindingType.SECURITY)
        assert wiq.estimate_effort(security) == "medium"
