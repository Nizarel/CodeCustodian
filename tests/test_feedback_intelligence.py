"""Tests for feedback and intelligence modules."""

from __future__ import annotations

import tempfile

from codecustodian.feedback.store import FeedbackEntry, FeedbackStore
from codecustodian.intelligence.trends import TrendAnalyzer
from codecustodian.models import Finding, FindingType, SeverityLevel


class TestFeedbackStore:
    def test_record_and_stats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FeedbackStore(storage_dir=tmpdir)
            store.record(
                FeedbackEntry(
                    finding_id="f1",
                    finding_type="code_smell",
                    action="approved",
                    confidence_was=8,
                )
            )
            store.record(
                FeedbackEntry(
                    finding_id="f2",
                    finding_type="deprecated_api",
                    action="rejected",
                    confidence_was=5,
                )
            )

            stats = store.get_accuracy_stats()
            assert stats["total"] == 2
            assert stats["approved"] == 1
            assert stats["rejected"] == 1
            assert stats["accuracy"] == 50.0

    def test_empty_stats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FeedbackStore(storage_dir=tmpdir)
            stats = store.get_accuracy_stats()
            assert stats["total"] == 0
            assert stats["accuracy"] == 0.0


class TestTrendAnalyzer:
    def test_analyze_findings(self):
        analyzer = TrendAnalyzer()

        findings = [
            Finding(
                type=FindingType.CODE_SMELL,
                severity=SeverityLevel.MEDIUM,
                file="src/main.py",
                line=1,
                description="test1",
            ),
            Finding(
                type=FindingType.CODE_SMELL,
                severity=SeverityLevel.HIGH,
                file="src/main.py",
                line=20,
                description="test2",
            ),
            Finding(
                type=FindingType.SECURITY,
                severity=SeverityLevel.CRITICAL,
                file="src/utils.py",
                line=5,
                description="test3",
            ),
        ]

        result = analyzer.analyze_findings(findings)
        assert result["total_findings"] == 3
        assert result["type_distribution"]["code_smell"] == 2
        assert result["type_distribution"]["security"] == 1
        assert result["hotspots"][0]["file"] == "src/main.py"
        assert result["hotspots"][0]["count"] == 2

    def test_empty_findings(self):
        analyzer = TrendAnalyzer()
        result = analyzer.analyze_findings([])
        assert result["hotspots"] == []
        assert result["type_distribution"] == {}
        assert result["severity_distribution"] == {}
