"""Intelligence module — trend analysis and pattern detection.

Analyzes historical scan data to detect tech debt trends,
predict problem areas, and generate actionable insights.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from codecustodian.logging import get_logger
from codecustodian.models import Finding

logger = get_logger("intelligence")


class TrendAnalyzer:
    """Analyze tech debt trends over time."""

    def analyze_findings(self, findings: list[Finding]) -> dict:
        """Analyze current findings for patterns and hotspots."""
        if not findings:
            return {"hotspots": [], "type_distribution": {}, "severity_distribution": {}}

        # File hotspots — most findings per file
        file_counts = Counter(f.file for f in findings)
        hotspots = [
            {"file": file, "count": count}
            for file, count in file_counts.most_common(10)
        ]

        # Type distribution
        type_dist = Counter(f.type.value for f in findings)

        # Severity distribution
        sev_dist = Counter(f.severity.value for f in findings)

        # Directory-level analysis
        dir_counts = Counter(
            str(Path(f.file).parent) for f in findings
        )
        hotspot_dirs = [
            {"directory": d, "count": c}
            for d, c in dir_counts.most_common(5)
        ]

        return {
            "total_findings": len(findings),
            "hotspots": hotspots,
            "hotspot_directories": hotspot_dirs,
            "type_distribution": dict(type_dist),
            "severity_distribution": dict(sev_dist),
            "avg_severity": self._avg_severity(findings),
        }

    @staticmethod
    def _avg_severity(findings: list[Finding]) -> float:
        """Calculate average severity as a numeric score."""
        severity_scores = {
            "critical": 5,
            "high": 4,
            "medium": 3,
            "low": 2,
            "info": 1,
        }
        if not findings:
            return 0.0
        total = sum(severity_scores.get(f.severity.value, 0) for f in findings)
        return round(total / len(findings), 2)
