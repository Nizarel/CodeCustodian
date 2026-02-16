"""ROI calculator for automated refactoring (BR-ENT-001, BR-RPT-003).

Quantifies the return-on-investment of CodeCustodian runs by comparing
the cost of AI operations against the estimated developer time saved.

Key metrics:
- Cost per finding fixed  (AI spend / fixes applied)
- Hours saved             (fixes × avg manual effort)
- Net ROI %               ((savings − cost) / cost × 100)

Persistence is JSONL (same pattern as ``AuditLogger`` and ``FeedbackStore``).
"""

from __future__ import annotations

import json
from csv import DictWriter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from codecustodian.logging import get_logger

logger = get_logger("enterprise.roi")


# ── Models ─────────────────────────────────────────────────────────────────


class ROIEntry(BaseModel):
    """A single refactoring event used for ROI tracking."""

    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    run_id: str = ""
    finding_type: str = ""
    severity: str = ""
    ai_cost_usd: float = 0.0
    infra_cost_usd: float = 0.0
    setup_cost_usd: float = 0.0
    estimated_manual_hours: float = 0.0
    automation_rate: float = 1.0
    was_successful: bool = True
    pr_number: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ROIReport(BaseModel):
    """Aggregated ROI summary for a period."""

    period: str = ""
    total_ai_cost: float = 0.0
    total_infra_cost: float = 0.0
    total_setup_cost: float = 0.0
    total_operational_cost: float = 0.0
    total_hours_saved: float = 0.0
    total_fixes: int = 0
    successful_fixes: int = 0
    cost_per_fix: float = 0.0
    hourly_rate_used: float = 0.0
    automation_rate: float = 1.0
    estimated_savings_usd: float = 0.0
    net_roi_pct: float = 0.0
    annual_roi_pct: float = 0.0
    payback_period_months: float = 0.0
    productivity_gain_pct: float = 0.0
    by_finding_type: dict[str, dict[str, float]] = Field(default_factory=dict)


# ── Default effort estimates (hours) ───────────────────────────────────────

DEFAULT_EFFORT_HOURS: dict[str, float] = {
    "deprecated_api": 2.0,
    "todo_comment": 0.5,
    "code_smell": 1.5,
    "security": 3.0,
    "missing_type_hints": 0.25,
}


# ── Calculator ─────────────────────────────────────────────────────────────


class ROICalculator:
    """Calculate and persist ROI metrics (BR-ENT-001).

    Args:
        hourly_rate: Developer hourly cost in USD for savings estimates.
        effort_hours: Mapping of finding type → estimated manual hours.
        data_dir: Directory for JSONL ROI logs.
    """

    def __init__(
        self,
        hourly_rate: float = 75.0,
        automation_rate: float = 1.0,
        effort_hours: dict[str, float] | None = None,
        data_dir: str | Path = ".codecustodian-roi",
    ) -> None:
        self.hourly_rate = hourly_rate
        self.automation_rate = max(0.0, min(automation_rate, 1.0))
        self.effort_hours = effort_hours or dict(DEFAULT_EFFORT_HOURS)
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._period = datetime.now(timezone.utc).strftime("%Y-%m")
        self._log_file = self.data_dir / f"roi-{self._period}.jsonl"

    # ── Record ─────────────────────────────────────────────────────────

    def record(
        self,
        finding_type: str,
        severity: str,
        ai_cost_usd: float,
        *,
        run_id: str = "",
        infra_cost_usd: float = 0.0,
        setup_cost_usd: float = 0.0,
        automation_rate: float | None = None,
        was_successful: bool = True,
        pr_number: int | None = None,
        **details: Any,
    ) -> ROIEntry:
        """Record a refactoring event for ROI tracking."""
        manual_hours = self.effort_hours.get(finding_type, 1.0)
        effective_automation = (
            max(0.0, min(automation_rate, 1.0))
            if automation_rate is not None
            else self.automation_rate
        )
        entry = ROIEntry(
            run_id=run_id,
            finding_type=finding_type,
            severity=severity,
            ai_cost_usd=ai_cost_usd,
            infra_cost_usd=infra_cost_usd,
            setup_cost_usd=setup_cost_usd,
            estimated_manual_hours=manual_hours,
            automation_rate=effective_automation,
            was_successful=was_successful,
            pr_number=pr_number,
            details=details,
        )
        with open(self._log_file, "a", encoding="utf-8") as f:
            f.write(entry.model_dump_json() + "\n")
        logger.debug(
            "ROI entry recorded: %s cost=$%.4f hours_saved=%.1f",
            finding_type,
            ai_cost_usd,
            manual_hours,
        )
        return entry

    # ── Report ─────────────────────────────────────────────────────────

    def generate_report(self, period: str | None = None) -> ROIReport:
        """Generate an aggregated ROI report (BR-RPT-003).

        Args:
            period: YYYY-MM string. Defaults to current month.
        """
        period = period or self._period
        log_file = self.data_dir / f"roi-{period}.jsonl"
        entries = self._load_entries(log_file)

        total_ai_cost = sum(e.ai_cost_usd for e in entries)
        total_infra_cost = sum(e.infra_cost_usd for e in entries)
        total_setup_cost = sum(e.setup_cost_usd for e in entries)
        total_cost = total_ai_cost + total_infra_cost + total_setup_cost
        total_hours = sum(
            e.estimated_manual_hours * e.automation_rate
            for e in entries
            if e.was_successful
        )
        successful = sum(1 for e in entries if e.was_successful)
        cost_per_fix = total_cost / successful if successful > 0 else 0.0
        savings = total_hours * self.hourly_rate
        net_roi = ((savings - total_cost) / total_cost * 100) if total_cost > 0 else 0.0
        annual_roi = net_roi
        payback_period_months = (
            total_cost / max(savings - total_cost, 0.0001)
            if savings > total_cost and total_cost > 0
            else 0.0
        )
        avg_automation = (
            sum(e.automation_rate for e in entries) / len(entries)
            if entries
            else self.automation_rate
        )
        productivity_gain = avg_automation * 100

        # Break down by finding type
        by_type: dict[str, dict[str, float]] = {}
        for entry in entries:
            ft = entry.finding_type or "unknown"
            bucket = by_type.setdefault(
                ft,
                {
                    "cost": 0.0,
                    "hours": 0.0,
                    "count": 0,
                    "savings": 0.0,
                },
            )
            entry_cost = entry.ai_cost_usd + entry.infra_cost_usd + entry.setup_cost_usd
            hours_saved = entry.estimated_manual_hours * entry.automation_rate
            bucket["cost"] += entry_cost
            bucket["hours"] += hours_saved
            bucket["count"] += 1
            bucket["savings"] += hours_saved * self.hourly_rate

        return ROIReport(
            period=period,
            total_ai_cost=round(total_ai_cost, 4),
            total_infra_cost=round(total_infra_cost, 4),
            total_setup_cost=round(total_setup_cost, 4),
            total_operational_cost=round(total_cost, 4),
            total_hours_saved=round(total_hours, 2),
            total_fixes=len(entries),
            successful_fixes=successful,
            cost_per_fix=round(cost_per_fix, 4),
            hourly_rate_used=self.hourly_rate,
            automation_rate=round(avg_automation, 4),
            estimated_savings_usd=round(savings, 2),
            net_roi_pct=round(net_roi, 2),
            annual_roi_pct=round(annual_roi, 2),
            payback_period_months=round(payback_period_months, 2),
            productivity_gain_pct=round(productivity_gain, 2),
            by_finding_type=by_type,
        )

    def export_csv(self, report: ROIReport, output_path: str | Path) -> Path:
        """Export monthly ROI report to CSV."""
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        summary_rows = [
            {"metric": "period", "value": report.period},
            {"metric": "total_operational_cost", "value": report.total_operational_cost},
            {"metric": "estimated_savings_usd", "value": report.estimated_savings_usd},
            {"metric": "net_roi_pct", "value": report.net_roi_pct},
            {"metric": "annual_roi_pct", "value": report.annual_roi_pct},
            {"metric": "payback_period_months", "value": report.payback_period_months},
            {"metric": "productivity_gain_pct", "value": report.productivity_gain_pct},
        ]

        with open(output, "w", newline="", encoding="utf-8") as csv_file:
            writer = DictWriter(csv_file, fieldnames=["section", "key", "value"])
            writer.writeheader()
            for row in summary_rows:
                writer.writerow(
                    {"section": "summary", "key": row["metric"], "value": row["value"]}
                )
            for finding_type, metrics in report.by_finding_type.items():
                for key, value in metrics.items():
                    writer.writerow(
                        {
                            "section": f"finding_type:{finding_type}",
                            "key": key,
                            "value": value,
                        }
                    )

        return output

    def export_markdown(self, report: ROIReport) -> str:
        """Render monthly ROI report as Markdown."""
        lines = [
            f"# ROI Report ({report.period})",
            "",
            "## Summary",
            f"- Total operational cost: ${report.total_operational_cost:.2f}",
            f"- Estimated savings: ${report.estimated_savings_usd:.2f}",
            f"- Net ROI: {report.net_roi_pct:.2f}%",
            f"- Annual ROI: {report.annual_roi_pct:.2f}%",
            f"- Payback period: {report.payback_period_months:.2f} months",
            f"- Productivity gain: {report.productivity_gain_pct:.2f}%",
            "",
            "## By Finding Type",
            "| Finding Type | Count | Cost | Hours | Savings |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]

        for finding_type, metrics in sorted(report.by_finding_type.items()):
            lines.append(
                "| "
                f"{finding_type} | "
                f"{int(metrics.get('count', 0))} | "
                f"${metrics.get('cost', 0.0):.2f} | "
                f"{metrics.get('hours', 0.0):.2f} | "
                f"${metrics.get('savings', 0.0):.2f} |"
            )

        return "\n".join(lines)

    def compare_periods(self, period_before: str, period_after: str) -> dict[str, Any]:
        """Return before/after ROI comparison summary."""
        before = self.generate_report(period_before)
        after = self.generate_report(period_after)

        return {
            "before": before.model_dump(),
            "after": after.model_dump(),
            "delta": {
                "cost": round(after.total_operational_cost - before.total_operational_cost, 4),
                "savings": round(after.estimated_savings_usd - before.estimated_savings_usd, 2),
                "net_roi_pct": round(after.net_roi_pct - before.net_roi_pct, 2),
                "annual_roi_pct": round(after.annual_roi_pct - before.annual_roi_pct, 2),
                "productivity_gain_pct": round(
                    after.productivity_gain_pct - before.productivity_gain_pct,
                    2,
                ),
            },
        }

    # ── Helpers ────────────────────────────────────────────────────────

    def _load_entries(self, log_file: Path) -> list[ROIEntry]:
        """Load ROI entries from a JSONL file."""
        if not log_file.exists():
            return []
        entries: list[ROIEntry] = []
        for line in log_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                entries.append(ROIEntry(**json.loads(line)))
            except (json.JSONDecodeError, Exception):
                continue
        return entries
