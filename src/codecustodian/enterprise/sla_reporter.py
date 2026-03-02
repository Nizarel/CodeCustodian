"""SLA & Reliability Reporting (BR-ENT-002).

Tracks pipeline run success rates, average time-to-PR, failure reasons,
and failure trend analysis.  Exports reports in CSV and Markdown and
forwards metrics to Azure Monitor via ``ObservabilityProvider``.

Storage: TinyDB-backed local database for lightweight persistence.
"""

from __future__ import annotations

import csv
import io
import statistics
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from codecustodian.logging import get_logger

logger = get_logger("enterprise.sla_reporter")


# ── Models ─────────────────────────────────────────────────────────────────


class SLARecord(BaseModel):
    """A single pipeline run tracked for SLA purposes."""

    run_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    success: bool
    duration_seconds: float = 0.0
    findings_count: int = 0
    prs_created: int = 0
    failure_reason: str = ""
    team: str = ""


class SLAReport(BaseModel):
    """Aggregated SLA metrics over a time window."""

    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    success_rate: float = 0.0
    avg_duration_seconds: float = 0.0
    p95_duration_seconds: float = 0.0
    avg_time_to_pr_seconds: float = 0.0
    total_findings: int = 0
    total_prs: int = 0
    top_failure_reasons: list[dict[str, Any]] = Field(default_factory=list)
    failure_trend: str = "stable"  # improving | stable | degrading
    period_start: str = ""
    period_end: str = ""
    alert: str = ""


# ── Reporter ───────────────────────────────────────────────────────────────


class SLAReporter:
    """Track SLA metrics and generate reliability reports (BR-ENT-002).

    Uses TinyDB for persistence and ``ObservabilityProvider`` for
    Azure Monitor metric forwarding.

    Args:
        db_path: Path to the TinyDB JSON file.
        observability: Optional ``ObservabilityProvider`` for metric emission.
        failure_spike_threshold: Percentage above which an alert is raised.
    """

    def __init__(
        self,
        db_path: str | Path = ".codecustodian-cache/sla.json",
        *,
        observability: Any | None = None,
        failure_spike_threshold: float = 10.0,
    ) -> None:
        from tinydb import TinyDB

        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = TinyDB(str(path))
        self._table = self.db.table("sla_records")
        self._observability = observability
        self._failure_spike_threshold = failure_spike_threshold

    def close(self) -> None:
        """Close the underlying TinyDB to release file locks."""
        self.db.close()

    # ── Recording ──────────────────────────────────────────────────────

    def record_run(self, record: SLARecord) -> None:
        """Persist a pipeline run result and emit to Azure Monitor."""
        self._table.insert(record.model_dump())
        logger.info(
            "SLA record: run=%s success=%s duration=%.1fs",
            record.run_id,
            record.success,
            record.duration_seconds,
        )

        # Forward to Azure Monitor if available
        if self._observability is not None:
            try:
                self._observability.record_sla_metrics(
                    run_id=record.run_id,
                    success=record.success,
                    duration_seconds=record.duration_seconds,
                    failure_reason=record.failure_reason,
                )
            except Exception as exc:
                logger.warning("Azure Monitor SLA emission failed: %s", exc)

    def record_from_pipeline_result(self, result: Any, team: str = "") -> None:
        """Convenience: build an ``SLARecord`` from a ``PipelineResult``."""
        record = SLARecord(
            run_id=result.run_id,
            success=len(result.errors) == 0,
            duration_seconds=result.total_duration_seconds,
            findings_count=result.total_findings,
            prs_created=result.prs_created,
            failure_reason=result.errors[0] if result.errors else "",
            team=team,
        )
        self.record_run(record)

    # ── Reporting ──────────────────────────────────────────────────────

    def generate_report(
        self,
        *,
        team: str = "",
        last_n: int = 0,
    ) -> SLAReport:
        """Generate an aggregated SLA report.

        Args:
            team: Filter by team name (empty = all teams).
            last_n: Limit to the N most recent runs (0 = all).

        Returns:
            ``SLAReport`` with aggregated metrics.
        """
        from tinydb import where

        records = self._table.search(where("team") == team) if team else self._table.all()

        if last_n > 0:
            records = sorted(records, key=lambda r: r.get("timestamp", ""), reverse=True)
            records = records[:last_n]

        if not records:
            return SLAReport()

        total = len(records)
        successful = sum(1 for r in records if r.get("success", False))
        failed = total - successful
        success_rate = (successful / total * 100) if total > 0 else 0.0

        durations = [r.get("duration_seconds", 0.0) for r in records]
        avg_duration = statistics.mean(durations) if durations else 0.0

        sorted_durations = sorted(durations)
        p95_idx = int(len(sorted_durations) * 0.95)
        p95_duration = sorted_durations[min(p95_idx, len(sorted_durations) - 1)]

        # Time-to-PR: duration of runs that created PRs
        pr_durations = [
            r.get("duration_seconds", 0.0)
            for r in records
            if r.get("prs_created", 0) > 0
        ]
        avg_time_to_pr = statistics.mean(pr_durations) if pr_durations else 0.0

        total_findings = sum(r.get("findings_count", 0) for r in records)
        total_prs = sum(r.get("prs_created", 0) for r in records)

        # Failure reasons breakdown
        failure_reasons: dict[str, int] = {}
        for r in records:
            reason = r.get("failure_reason", "")
            if reason:
                key = reason[:80]  # Truncate long reasons
                failure_reasons[key] = failure_reasons.get(key, 0) + 1

        top_failures = [
            {"reason": reason, "count": count}
            for reason, count in sorted(
                failure_reasons.items(), key=lambda x: x[1], reverse=True
            )[:5]
        ]

        # Failure trend (compare recent half vs older half)
        trend = self._compute_failure_trend(records)

        # Alert on spike
        alert = ""
        if failed > 0:
            failure_pct = (failed / total) * 100
            if failure_pct > self._failure_spike_threshold:
                alert = (
                    f"ALERT: Failure rate {failure_pct:.1f}% exceeds "
                    f"threshold {self._failure_spike_threshold:.1f}%"
                )

        timestamps = [r.get("timestamp", "") for r in records if r.get("timestamp")]
        period_start = min(timestamps) if timestamps else ""
        period_end = max(timestamps) if timestamps else ""

        return SLAReport(
            total_runs=total,
            successful_runs=successful,
            failed_runs=failed,
            success_rate=round(success_rate, 2),
            avg_duration_seconds=round(avg_duration, 2),
            p95_duration_seconds=round(p95_duration, 2),
            avg_time_to_pr_seconds=round(avg_time_to_pr, 2),
            total_findings=total_findings,
            total_prs=total_prs,
            top_failure_reasons=top_failures,
            failure_trend=trend,
            period_start=period_start,
            period_end=period_end,
            alert=alert,
        )

    # ── Export ──────────────────────────────────────────────────────────

    def export_csv(self, *, team: str = "", last_n: int = 0) -> str:
        """Export SLA records as CSV string."""
        from tinydb import where

        records = self._table.search(where("team") == team) if team else self._table.all()

        if last_n > 0:
            records = sorted(records, key=lambda r: r.get("timestamp", ""), reverse=True)
            records = records[:last_n]

        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "run_id", "timestamp", "success", "duration_seconds",
                "findings_count", "prs_created", "failure_reason", "team",
            ],
        )
        writer.writeheader()
        for r in records:
            writer.writerow({
                "run_id": r.get("run_id", ""),
                "timestamp": r.get("timestamp", ""),
                "success": r.get("success", False),
                "duration_seconds": r.get("duration_seconds", 0),
                "findings_count": r.get("findings_count", 0),
                "prs_created": r.get("prs_created", 0),
                "failure_reason": r.get("failure_reason", ""),
                "team": r.get("team", ""),
            })
        return output.getvalue()

    def export_markdown(self, *, team: str = "", last_n: int = 0) -> str:
        """Export an SLA report as a Markdown document."""
        report = self.generate_report(team=team, last_n=last_n)
        lines = [
            "# SLA & Reliability Report",
            "",
            f"**Period:** {report.period_start or 'N/A'} → {report.period_end or 'N/A'}",
            f"**Team:** {team or 'All'}",
            "",
            "## Summary",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total Runs | {report.total_runs} |",
            f"| Successful | {report.successful_runs} |",
            f"| Failed | {report.failed_runs} |",
            f"| Success Rate | {report.success_rate:.1f}% |",
            f"| Avg Duration | {report.avg_duration_seconds:.1f}s |",
            f"| P95 Duration | {report.p95_duration_seconds:.1f}s |",
            f"| Avg Time-to-PR | {report.avg_time_to_pr_seconds:.1f}s |",
            f"| Total Findings | {report.total_findings} |",
            f"| Total PRs | {report.total_prs} |",
            f"| Failure Trend | {report.failure_trend} |",
            "",
        ]

        if report.alert:
            lines.extend([f"> **{report.alert}**", ""])

        if report.top_failure_reasons:
            lines.extend([
                "## Top Failure Reasons",
                "",
                "| Reason | Count |",
                "|--------|-------|",
            ])
            for fr in report.top_failure_reasons:
                lines.append(f"| {fr['reason']} | {fr['count']} |")
            lines.append("")

        return "\n".join(lines)

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _compute_failure_trend(records: list[dict]) -> str:
        """Compare failure rates: recent half vs older half."""
        if len(records) < 4:
            return "stable"

        sorted_recs = sorted(records, key=lambda r: r.get("timestamp", ""))
        mid = len(sorted_recs) // 2
        older = sorted_recs[:mid]
        recent = sorted_recs[mid:]

        older_fail = sum(1 for r in older if not r.get("success", True))
        recent_fail = sum(1 for r in recent if not r.get("success", True))

        older_rate = older_fail / len(older)
        recent_rate = recent_fail / len(recent)

        if recent_rate > older_rate + 0.1:
            return "degrading"
        if recent_rate < older_rate - 0.1:
            return "improving"
        return "stable"
