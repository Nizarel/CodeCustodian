"""Tests for Phase 8: Business Intelligence, Feedback & Learning.

Covers BusinessImpactScorer, DynamicReprioritizer, FeedbackCollector,
PreferenceStore, HistoricalPatternRecognizer, and SLAReporter.
"""

from __future__ import annotations

import tempfile

import pytest

from codecustodian.models import Finding, FindingType, SeverityLevel

# ── Helpers ────────────────────────────────────────────────────────────────


def _make_finding(
    *,
    file: str = "src/main.py",
    severity: SeverityLevel = SeverityLevel.MEDIUM,
    finding_type: FindingType = FindingType.CODE_SMELL,
    description: str = "test finding",
    metadata: dict | None = None,
) -> Finding:
    return Finding(
        type=finding_type,
        severity=severity,
        file=file,
        line=10,
        description=description,
        metadata=metadata or {},
    )


# ═══════════════════════════════════════════════════════════════════════════
# BusinessImpactScorer
# ═══════════════════════════════════════════════════════════════════════════


class TestBusinessImpactScorer:
    """Tests for intelligence/business_impact.py."""

    def test_criticality_critical_path(self):
        from codecustodian.intelligence.business_impact import BusinessImpactScorer

        scorer = BusinessImpactScorer()
        finding = _make_finding(file="src/auth/login.py")
        assert scorer._get_criticality(finding) >= 7.0

    def test_criticality_normal_path(self):
        from codecustodian.intelligence.business_impact import BusinessImpactScorer

        scorer = BusinessImpactScorer()
        finding = _make_finding(file="src/utils/helpers.py")
        assert scorer._get_criticality(finding) == 3.0

    def test_criticality_metadata_override(self):
        from codecustodian.intelligence.business_impact import BusinessImpactScorer

        scorer = BusinessImpactScorer()
        finding = _make_finding(
            file="src/utils.py",
            metadata={"criticality_level": "critical"},
        )
        assert scorer._get_criticality(finding) == 10.0

    def test_regulatory_risk_detected(self):
        from codecustodian.intelligence.business_impact import BusinessImpactScorer

        scorer = BusinessImpactScorer()
        finding = _make_finding(
            file="src/pii_handler.py",
            description="Processes credit_card data",
        )
        assert scorer._get_regulatory_risk(finding) >= 5.0

    def test_regulatory_risk_none(self):
        from codecustodian.intelligence.business_impact import BusinessImpactScorer

        scorer = BusinessImpactScorer()
        finding = _make_finding(file="src/hello.py")
        assert scorer._get_regulatory_risk(finding) == 0.0

    @pytest.mark.asyncio
    async def test_usage_frequency_normalised(self):
        from codecustodian.intelligence.business_impact import BusinessImpactScorer

        scorer = BusinessImpactScorer()
        finding = _make_finding(metadata={"usage_frequency": 100})
        result = await scorer._get_usage_frequency(finding)
        assert 5.0 <= result <= 8.0

    @pytest.mark.asyncio
    async def test_usage_frequency_zero(self):
        from codecustodian.intelligence.business_impact import BusinessImpactScorer

        scorer = BusinessImpactScorer()
        finding = _make_finding()
        result = await scorer._get_usage_frequency(finding)
        assert result == 0.0

    @pytest.mark.asyncio
    async def test_score_composite(self):
        from codecustodian.intelligence.business_impact import BusinessImpactScorer

        scorer = BusinessImpactScorer()
        finding = _make_finding(
            file="src/auth/payment.py",
            metadata={"usage_frequency": 50},
        )
        score = await scorer.score(finding, ".")
        # Should be > 0 because of criticality at minimum
        assert score > 0

    @pytest.mark.asyncio
    async def test_score_detailed_breakdown(self):
        from codecustodian.intelligence.business_impact import BusinessImpactScorer

        scorer = BusinessImpactScorer()
        finding = _make_finding(
            file="src/billing/invoice.py",
            metadata={"compliance": ["pci", "gdpr"]},
        )
        breakdown = await scorer.score_detailed(finding, ".")
        assert breakdown.total > 0
        assert breakdown.criticality >= 7.0
        assert breakdown.regulatory_risk >= 5.0
        assert len(breakdown.factors) > 0

    @pytest.mark.asyncio
    async def test_score_batch(self):
        from codecustodian.intelligence.business_impact import BusinessImpactScorer

        scorer = BusinessImpactScorer()
        findings = [
            _make_finding(file="src/auth.py"),
            _make_finding(file="src/utils.py"),
        ]
        results = await scorer.score_batch(findings, ".")
        assert len(results) == 2
        # First result should have higher score (auth is critical)
        assert results[0][1].total >= results[1][1].total

    def test_impact_breakdown_model(self):
        from codecustodian.intelligence.business_impact import ImpactBreakdown

        breakdown = ImpactBreakdown(
            usage=5.0,
            criticality=10.0,
            change_frequency=3.0,
            velocity_impact=0.0,
            regulatory_risk=8.0,
            total=1280.0,
            factors=["critical_path=10.0", "regulatory=8.0"],
        )
        assert breakdown.total == 1280.0
        assert len(breakdown.factors) == 2

    def test_scoring_weights_custom(self):
        from codecustodian.intelligence.business_impact import (
            BusinessImpactScorer,
            ScoringWeights,
        )

        weights = ScoringWeights(usage=200.0, criticality=100.0)
        scorer = BusinessImpactScorer(weights=weights)
        assert scorer.weights.usage == 200.0
        assert scorer.weights.criticality == 100.0


# ═══════════════════════════════════════════════════════════════════════════
# DynamicReprioritizer
# ═══════════════════════════════════════════════════════════════════════════


class TestDynamicReprioritizer:
    """Tests for intelligence/reprioritization.py."""

    @pytest.mark.asyncio
    async def test_production_incident_boost(self):
        from codecustodian.intelligence.reprioritization import DynamicReprioritizer

        reprioritizer = DynamicReprioritizer()
        findings = [
            _make_finding(file="src/api/handler.py"),
            _make_finding(file="src/utils.py"),
        ]
        original_score = findings[0].priority_score
        result = await reprioritizer.handle_event(
            "production_incident",
            {"file_path": "src/api/handler.py"},
            findings,
        )
        assert result.elevated == 1
        assert findings[0].priority_score > original_score

    @pytest.mark.asyncio
    async def test_cve_announced_boost(self):
        from codecustodian.intelligence.reprioritization import DynamicReprioritizer

        reprioritizer = DynamicReprioritizer()
        findings = [
            _make_finding(metadata={"library": "requests", "cve": "CVE-2026-1234"}),
            _make_finding(metadata={}),
        ]
        result = await reprioritizer.handle_event(
            "cve_announced",
            {"cve_id": "CVE-2026-1234", "library": "requests"},
            findings,
        )
        assert result.elevated >= 1

    @pytest.mark.asyncio
    async def test_budget_exceeded_pauses_noncritical(self):
        from codecustodian.intelligence.reprioritization import DynamicReprioritizer

        reprioritizer = DynamicReprioritizer()
        findings = [
            _make_finding(file="src/low.py"),
            _make_finding(file="src/high.py"),
        ]
        findings[1].priority_score = 200  # High priority
        result = await reprioritizer.handle_event(
            "budget_exceeded",
            {},
            findings,
        )
        assert result.paused >= 1
        # Low-priority finding should be paused
        assert findings[0].metadata.get("paused") is True

    @pytest.mark.asyncio
    async def test_deadline_approaching(self):
        from codecustodian.intelligence.reprioritization import DynamicReprioritizer

        reprioritizer = DynamicReprioritizer()
        findings = [
            _make_finding(metadata={"library": "pandas"}),
            _make_finding(metadata={}),
        ]
        result = await reprioritizer.handle_event(
            "deadline_approaching",
            {"library": "pandas"},
            findings,
        )
        assert result.elevated == 1

    @pytest.mark.asyncio
    async def test_team_capacity_low(self):
        from codecustodian.intelligence.reprioritization import DynamicReprioritizer

        reprioritizer = DynamicReprioritizer()
        findings = [
            _make_finding(),
        ]
        findings[0].priority_score = 10  # Low priority
        result = await reprioritizer.handle_event(
            "team_capacity_change",
            {"team_id": "team-alpha", "capacity_ratio": 0.3},
            findings,
        )
        assert result.paused >= 1

    @pytest.mark.asyncio
    async def test_filter_active(self):
        from codecustodian.intelligence.reprioritization import DynamicReprioritizer

        findings = [
            _make_finding(file="a.py"),
            _make_finding(file="b.py"),
        ]
        findings[1].metadata["paused"] = True
        active = DynamicReprioritizer.filter_active(findings)
        assert len(active) == 1

    @pytest.mark.asyncio
    async def test_event_log(self):
        from codecustodian.intelligence.reprioritization import DynamicReprioritizer

        reprioritizer = DynamicReprioritizer()
        await reprioritizer.handle_event("production_incident", {"file_path": "x"}, [])
        assert len(reprioritizer.get_event_log()) == 1

    @pytest.mark.asyncio
    async def test_custom_event(self):
        from codecustodian.intelligence.reprioritization import DynamicReprioritizer

        reprioritizer = DynamicReprioritizer()
        findings = [_make_finding(file="src/custom/path.py")]
        result = await reprioritizer.handle_event(
            "unknown_event",
            {"file_pattern": "custom", "boost": 100},
            findings,
        )
        assert result.elevated == 1


# ═══════════════════════════════════════════════════════════════════════════
# FeedbackCollector
# ═══════════════════════════════════════════════════════════════════════════


class TestFeedbackCollector:
    """Tests for feedback/learning.py."""

    def test_record_and_summary(self):
        from codecustodian.feedback.learning import FeedbackCollector, PROutcome

        with tempfile.TemporaryDirectory() as tmpdir:
            collector = FeedbackCollector(
                db_path=f"{tmpdir}/learning.json"
            )
            collector.record_outcome(PROutcome(
                pr_number=1,
                status="merged",
                confidence_was=8,
                scanner_type="deprecated_api",
            ))
            collector.record_outcome(PROutcome(
                pr_number=2,
                status="rejected",
                confidence_was=5,
                scanner_type="deprecated_api",
            ))

            summary = collector.get_summary()
            assert summary["total"] == 2
            assert summary["merged"] == 1
            assert summary["rejected"] == 1
            collector.close()

    def test_scanner_success_rate(self):
        from codecustodian.feedback.learning import FeedbackCollector, PROutcome

        with tempfile.TemporaryDirectory() as tmpdir:
            collector = FeedbackCollector(
                db_path=f"{tmpdir}/learning.json"
            )
            for i in range(8):
                collector.record_outcome(PROutcome(
                    pr_number=i,
                    status="merged",
                    scanner_type="code_smell",
                ))
            for i in range(2):
                collector.record_outcome(PROutcome(
                    pr_number=10 + i,
                    status="rejected",
                    scanner_type="code_smell",
                ))

            rate = collector.get_scanner_success_rate("code_smell")
            assert rate == 0.8
            collector.close()

    def test_scanner_rate_no_data(self):
        from codecustodian.feedback.learning import FeedbackCollector

        with tempfile.TemporaryDirectory() as tmpdir:
            collector = FeedbackCollector(
                db_path=f"{tmpdir}/learning.json"
            )
            rate = collector.get_scanner_success_rate("unknown")
            assert rate == 1.0
            collector.close()

    def test_confidence_adjustment_needed(self):
        from codecustodian.feedback.learning import FeedbackCollector, PROutcome

        with tempfile.TemporaryDirectory() as tmpdir:
            collector = FeedbackCollector(
                db_path=f"{tmpdir}/learning.json"
            )
            # 70% success rate → below 90% target
            for i in range(7):
                collector.record_outcome(PROutcome(
                    pr_number=i, status="merged", scanner_type="security"
                ))
            for i in range(3):
                collector.record_outcome(PROutcome(
                    pr_number=10 + i, status="rejected", scanner_type="security"
                ))

            adj = collector.suggest_confidence_adjustment("security")
            assert adj >= 1
            collector.close()

    def test_confidence_no_adjustment(self):
        from codecustodian.feedback.learning import FeedbackCollector, PROutcome

        with tempfile.TemporaryDirectory() as tmpdir:
            collector = FeedbackCollector(
                db_path=f"{tmpdir}/learning.json"
            )
            for i in range(10):
                collector.record_outcome(PROutcome(
                    pr_number=i, status="merged", scanner_type="todo"
                ))
            adj = collector.suggest_confidence_adjustment("todo")
            assert adj == 0
            collector.close()

    def test_record_dict(self):
        from codecustodian.feedback.learning import FeedbackCollector

        with tempfile.TemporaryDirectory() as tmpdir:
            collector = FeedbackCollector(
                db_path=f"{tmpdir}/learning.json"
            )
            collector.record_dict(42, {
                "status": "modified",
                "confidence": 7,
                "scanner_type": "code_smell",
            })
            summary = collector.get_summary()
            assert summary["total"] == 1
            assert summary["modified"] == 1
            collector.close()

    def test_all_scanner_rates(self):
        from codecustodian.feedback.learning import FeedbackCollector, PROutcome

        with tempfile.TemporaryDirectory() as tmpdir:
            collector = FeedbackCollector(
                db_path=f"{tmpdir}/learning.json"
            )
            collector.record_outcome(PROutcome(
                pr_number=1, status="merged", scanner_type="a"
            ))
            collector.record_outcome(PROutcome(
                pr_number=2, status="rejected", scanner_type="b"
            ))
            rates = collector.get_all_scanner_rates()
            assert "a" in rates
            assert "b" in rates
            assert rates["a"] == 1.0
            assert rates["b"] == 0.0
            collector.close()


# ═══════════════════════════════════════════════════════════════════════════
# PreferenceStore
# ═══════════════════════════════════════════════════════════════════════════


class TestPreferenceStore:
    """Tests for feedback/preferences.py."""

    def test_record_and_retrieve(self):
        from codecustodian.feedback.preferences import PreferenceStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = PreferenceStore(db_path=f"{tmpdir}/prefs.json")
            store.record_preference(
                "team-alpha",
                "prefer async/await over callbacks",
                category="pattern",
            )
            prefs = store.get_preferences(team="team-alpha")
            assert len(prefs) == 1
            assert "async/await" in prefs[0]
            store.close()

    def test_duplicate_prevention(self):
        from codecustodian.feedback.preferences import PreferenceStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = PreferenceStore(db_path=f"{tmpdir}/prefs.json")
            store.record_preference("t1", "use dataclasses")
            store.record_preference("t1", "use dataclasses")
            prefs = store.get_preferences(team="t1")
            assert len(prefs) == 1
            store.close()

    def test_user_overrides_team(self):
        from codecustodian.feedback.preferences import PreferenceStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = PreferenceStore(db_path=f"{tmpdir}/prefs.json")
            store.record_preference("team", "use tabs")
            store.record_preference("alice", "use spaces", is_user=True)
            # Both should appear
            prefs = store.get_preferences(team="team", user="alice")
            assert len(prefs) == 2
            store.close()

    def test_preferences_for_prompt(self):
        from codecustodian.feedback.preferences import PreferenceStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = PreferenceStore(db_path=f"{tmpdir}/prefs.json")
            store.record_preference("t", "use type hints everywhere")
            prompt = store.get_preferences_for_prompt(team="t")
            assert "type hints" in prompt
            assert "Preferences" in prompt
            store.close()

    def test_empty_prompt(self):
        from codecustodian.feedback.preferences import PreferenceStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = PreferenceStore(db_path=f"{tmpdir}/prefs.json")
            prompt = store.get_preferences_for_prompt(team="nonexistent")
            assert prompt == ""
            store.close()

    def test_remove_preference(self):
        from codecustodian.feedback.preferences import PreferenceStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = PreferenceStore(db_path=f"{tmpdir}/prefs.json")
            store.record_preference("t", "use pytest")
            assert store.remove_preference("t", "use pytest")
            prefs = store.get_preferences(team="t")
            assert len(prefs) == 0
            store.close()

    def test_get_summary(self):
        from codecustodian.feedback.preferences import PreferenceStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = PreferenceStore(db_path=f"{tmpdir}/prefs.json")
            store.record_preference("t1", "pref1", category="style")
            store.record_preference("t2", "pref2", category="pattern")
            summary = store.get_summary()
            assert summary["total"] == 2
            assert summary["teams"] == 2
            store.close()


# ═══════════════════════════════════════════════════════════════════════════
# HistoricalPatternRecognizer
# ═══════════════════════════════════════════════════════════════════════════


class TestHistoricalPatternRecognizer:
    """Tests for feedback/history.py."""

    @pytest.mark.asyncio
    async def test_record_and_find_similar(self):
        from codecustodian.feedback.history import (
            HistoricalPatternRecognizer,
            HistoricalRefactoring,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            recognizer = HistoricalPatternRecognizer(
                db_path=f"{tmpdir}/history.json"
            )
            recognizer.record_refactoring(HistoricalRefactoring(
                finding_type="deprecated_api",
                library="requests",
                team="team-alpha",
                outcome="merged",
                success=True,
                learned_recommendation="Use httpx instead",
            ))

            finding = _make_finding(
                finding_type=FindingType.DEPRECATED_API,
                metadata={"library": "requests"},
            )
            similar = await recognizer.find_similar(finding)
            assert len(similar) == 1
            assert similar[0].team == "team-alpha"
            recognizer.close()

    @pytest.mark.asyncio
    async def test_find_similar_no_matches(self):
        from codecustodian.feedback.history import HistoricalPatternRecognizer

        with tempfile.TemporaryDirectory() as tmpdir:
            recognizer = HistoricalPatternRecognizer(
                db_path=f"{tmpdir}/history.json"
            )
            finding = _make_finding(finding_type=FindingType.SECURITY)
            similar = await recognizer.find_similar(finding)
            assert len(similar) == 0
            recognizer.close()

    def test_record_from_outcome(self):
        from codecustodian.feedback.history import HistoricalPatternRecognizer

        with tempfile.TemporaryDirectory() as tmpdir:
            recognizer = HistoricalPatternRecognizer(
                db_path=f"{tmpdir}/history.json"
            )
            finding = _make_finding(
                finding_type=FindingType.CODE_SMELL,
                metadata={"library": "flask"},
            )
            recognizer.record_from_outcome(
                finding,
                "merged",
                team="backend",
                modifications=["simplified logic"],
            )
            summary = recognizer.get_summary()
            assert summary["total"] == 1
            assert summary["overall_success_rate"] == 1.0
            recognizer.close()

    def test_context_for_prompt(self):
        from codecustodian.feedback.history import (
            HistoricalPatternRecognizer,
            SimilarPattern,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            recognizer = HistoricalPatternRecognizer(
                db_path=f"{tmpdir}/history.json"
            )
            patterns = [
                SimilarPattern(
                    team="t1",
                    success_rate=0.9,
                    recommendation="Use pattern X",
                    match_score=3.0,
                ),
            ]
            context = recognizer.get_context_for_prompt(
                _make_finding(),
                similar=patterns,
            )
            assert "Historical Context" in context
            assert "pattern X" in context
            recognizer.close()

    def test_success_rate_by_type(self):
        from codecustodian.feedback.history import (
            HistoricalPatternRecognizer,
            HistoricalRefactoring,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            recognizer = HistoricalPatternRecognizer(
                db_path=f"{tmpdir}/history.json"
            )
            recognizer.record_refactoring(HistoricalRefactoring(
                finding_type="code_smell", success=True, outcome="merged",
            ))
            recognizer.record_refactoring(HistoricalRefactoring(
                finding_type="code_smell", success=False, outcome="rejected",
            ))
            rates = recognizer.get_success_rate_by_type()
            assert rates["code_smell"] == 0.5
            recognizer.close()


# ═══════════════════════════════════════════════════════════════════════════
# SLAReporter
# ═══════════════════════════════════════════════════════════════════════════


class TestSLAReporter:
    """Tests for enterprise/sla_reporter.py."""

    def test_record_and_report(self):
        from codecustodian.enterprise.sla_reporter import SLARecord, SLAReporter

        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = SLAReporter(db_path=f"{tmpdir}/sla.json")
            reporter.record_run(SLARecord(
                run_id="r1",
                success=True,
                duration_seconds=10.5,
                findings_count=5,
                prs_created=2,
            ))
            reporter.record_run(SLARecord(
                run_id="r2",
                success=False,
                duration_seconds=5.0,
                failure_reason="timeout",
            ))

            report = reporter.generate_report()
            assert report.total_runs == 2
            assert report.successful_runs == 1
            assert report.failed_runs == 1
            assert report.success_rate == 50.0
            reporter.close()

    def test_empty_report(self):
        from codecustodian.enterprise.sla_reporter import SLAReporter

        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = SLAReporter(db_path=f"{tmpdir}/sla.json")
            report = reporter.generate_report()
            assert report.total_runs == 0
            reporter.close()

    def test_failure_trend_degrading(self):
        from codecustodian.enterprise.sla_reporter import SLARecord, SLAReporter

        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = SLAReporter(db_path=f"{tmpdir}/sla.json")
            # Older runs: mostly success
            for i in range(5):
                reporter.record_run(SLARecord(
                    run_id=f"old-{i}",
                    success=True,
                    duration_seconds=10.0,
                    timestamp=f"2026-01-0{i + 1}T00:00:00Z",
                ))
            # Recent runs: mostly failures
            for i in range(5):
                reporter.record_run(SLARecord(
                    run_id=f"new-{i}",
                    success=False,
                    duration_seconds=5.0,
                    failure_reason="error",
                    timestamp=f"2026-02-0{i + 1}T00:00:00Z",
                ))

            report = reporter.generate_report()
            assert report.failure_trend == "degrading"
            reporter.close()

    def test_failure_spike_alert(self):
        from codecustodian.enterprise.sla_reporter import SLARecord, SLAReporter

        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = SLAReporter(
                db_path=f"{tmpdir}/sla.json",
                failure_spike_threshold=10.0,
            )
            # 50% failure rate → should alert
            reporter.record_run(SLARecord(
                run_id="r1", success=True, duration_seconds=10.0,
            ))
            reporter.record_run(SLARecord(
                run_id="r2", success=False, failure_reason="crash",
                duration_seconds=5.0,
            ))

            report = reporter.generate_report()
            assert report.alert != ""
            assert "ALERT" in report.alert
            reporter.close()

    def test_export_csv(self):
        from codecustodian.enterprise.sla_reporter import SLARecord, SLAReporter

        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = SLAReporter(db_path=f"{tmpdir}/sla.json")
            reporter.record_run(SLARecord(
                run_id="r1", success=True, duration_seconds=10.0,
            ))
            csv_str = reporter.export_csv()
            assert "run_id" in csv_str
            assert "r1" in csv_str
            reporter.close()

    def test_export_markdown(self):
        from codecustodian.enterprise.sla_reporter import SLARecord, SLAReporter

        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = SLAReporter(db_path=f"{tmpdir}/sla.json")
            reporter.record_run(SLARecord(
                run_id="r1", success=True, duration_seconds=10.0,
                findings_count=3, prs_created=1,
            ))
            md = reporter.export_markdown()
            assert "# SLA & Reliability Report" in md
            assert "Success Rate" in md
            reporter.close()

    def test_team_filter(self):
        from codecustodian.enterprise.sla_reporter import SLARecord, SLAReporter

        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = SLAReporter(db_path=f"{tmpdir}/sla.json")
            reporter.record_run(SLARecord(
                run_id="r1", success=True, duration_seconds=10.0, team="alpha",
            ))
            reporter.record_run(SLARecord(
                run_id="r2", success=False, duration_seconds=5.0, team="beta",
            ))

            alpha_report = reporter.generate_report(team="alpha")
            assert alpha_report.total_runs == 1
            assert alpha_report.success_rate == 100.0
            reporter.close()

    def test_top_failure_reasons(self):
        from codecustodian.enterprise.sla_reporter import SLARecord, SLAReporter

        with tempfile.TemporaryDirectory() as tmpdir:
            reporter = SLAReporter(db_path=f"{tmpdir}/sla.json")
            for i in range(3):
                reporter.record_run(SLARecord(
                    run_id=f"r{i}",
                    success=False,
                    failure_reason="timeout",
                    duration_seconds=5.0,
                ))
            reporter.record_run(SLARecord(
                run_id="r9",
                success=False,
                failure_reason="auth_error",
                duration_seconds=1.0,
            ))

            report = reporter.generate_report()
            assert len(report.top_failure_reasons) >= 1
            assert report.top_failure_reasons[0]["reason"] == "timeout"
            assert report.top_failure_reasons[0]["count"] == 3
            reporter.close()


# ═══════════════════════════════════════════════════════════════════════════
# Config schema Phase 8
# ═══════════════════════════════════════════════════════════════════════════


class TestPhase8Config:
    """Tests for new config schema models."""

    def test_sla_config_defaults(self):
        from codecustodian.config.schema import SLAConfig

        cfg = SLAConfig()
        assert cfg.enabled is True
        assert cfg.failure_spike_threshold == 10.0

    def test_learning_config_defaults(self):
        from codecustodian.config.schema import LearningConfig

        cfg = LearningConfig()
        assert cfg.enabled is True
        assert cfg.target_success_rate == 0.9
        assert cfg.auto_adjust_confidence is True

    def test_business_impact_config_defaults(self):
        from codecustodian.config.schema import BusinessImpactConfig

        cfg = BusinessImpactConfig()
        assert cfg.enabled is True
        assert cfg.usage_weight == 100.0
        assert cfg.regulatory_risk_weight == 80.0

    def test_full_config_includes_phase8(self):
        from codecustodian.config.schema import CodeCustodianConfig

        cfg = CodeCustodianConfig()
        assert hasattr(cfg, "sla")
        assert hasattr(cfg, "learning")
        assert hasattr(cfg, "business_impact")
        assert cfg.sla.enabled is True
        assert cfg.learning.enabled is True
        assert cfg.business_impact.enabled is True


# ═══════════════════════════════════════════════════════════════════════════
# Prompt injection
# ═══════════════════════════════════════════════════════════════════════════


class TestPromptInjection:
    """Tests for preference/history injection into prompts."""

    def test_build_finding_prompt_with_preferences(self):
        from codecustodian.models import CodeContext
        from codecustodian.planner.prompts import build_finding_prompt

        finding = _make_finding()
        context = CodeContext(
            file_path="src/main.py",
            source_code="def foo(): pass",
            start_line=1,
            end_line=1,
        )
        prompt = build_finding_prompt(
            finding,
            context,
            preferences="Team Preferences:\n  1. Use type hints",
            historical_context="Historical: pattern X worked before",
        )
        assert "type hints" in prompt
        assert "pattern X" in prompt

    def test_build_finding_prompt_without_extras(self):
        from codecustodian.models import CodeContext
        from codecustodian.planner.prompts import build_finding_prompt

        finding = _make_finding()
        context = CodeContext(
            file_path="src/main.py",
            source_code="def foo(): pass",
            start_line=1,
            end_line=1,
        )
        prompt = build_finding_prompt(finding, context)
        assert "Minimize changes" in prompt


# ═══════════════════════════════════════════════════════════════════════════
# Confidence scoring with scanner adjustment
# ═══════════════════════════════════════════════════════════════════════════


class TestConfidenceWithLearning:
    """Tests for scanner_adjustment in confidence scoring."""

    def test_scanner_adjustment_deduction(self):
        from codecustodian.models import CodeContext, RefactoringPlan
        from codecustodian.planner.confidence import calculate_confidence

        plan = RefactoringPlan(
            finding_id="f1",
            summary="test",
            confidence_score=8,
        )
        context = CodeContext(
            file_path="src/main.py",
            source_code="",
            start_line=1,
            end_line=1,
            has_tests=True,
        )
        score_base, _ = calculate_confidence(plan, context)
        score_adj, factors = calculate_confidence(
            plan, context, scanner_adjustment=2
        )
        assert score_adj < score_base
        assert any("scanner_history" in f for f in factors)

    def test_scanner_adjustment_zero(self):
        from codecustodian.models import CodeContext, RefactoringPlan
        from codecustodian.planner.confidence import calculate_confidence

        plan = RefactoringPlan(
            finding_id="f1",
            summary="test",
            confidence_score=8,
        )
        context = CodeContext(
            file_path="src/main.py",
            source_code="",
            start_line=1,
            end_line=1,
            has_tests=True,
        )
        score_base, _factors_base = calculate_confidence(plan, context)
        score_zero, _factors_zero = calculate_confidence(
            plan, context, scanner_adjustment=0
        )
        assert score_base == score_zero
