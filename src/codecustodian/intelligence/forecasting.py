"""Predictive debt forecasting using historical snapshots (v0.14.0).

Records point-in-time ``DebtSnapshot`` objects and uses simple linear
regression to forecast future technical debt levels.  No external ML
dependencies — uses pure Python math.

Usage::

    forecaster = PredictiveDebtForecaster(snapshot_dir)
    forecaster.record_snapshot(findings, repo_path=".")
    forecast = forecaster.forecast(repo_path=".", horizon_days=90)
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from codecustodian.logging import get_logger
from codecustodian.models import DebtForecast, DebtSnapshot, Finding

logger = get_logger("intelligence.forecasting")


class PredictiveDebtForecaster:
    """Forecast technical debt growth from historical snapshots.

    Snapshots are stored as JSON files in *snapshot_dir* with names
    ``{repo_hash}_{iso_date}.json``.  When enough history exists
    (``min_snapshots`` or more data points), a linear regression
    projects future finding counts.
    """

    def __init__(
        self,
        snapshot_dir: str | Path = ".codecustodian-cache/snapshots",
        min_snapshots: int = 3,
    ) -> None:
        self.snapshot_dir = Path(snapshot_dir)
        self.min_snapshots = max(2, min_snapshots)

    # ── Snapshot I/O ───────────────────────────────────────────────────

    def record_snapshot(
        self,
        findings: list[Finding],
        repo_path: str = ".",
    ) -> DebtSnapshot:
        """Create and persist a snapshot of the current debt state."""
        by_type = dict(Counter(f.type.value for f in findings))
        by_severity = dict(Counter(f.severity.value for f in findings))

        snapshot = DebtSnapshot(
            date=datetime.now(UTC),
            repo_path=repo_path,
            total_findings=len(findings),
            by_type=by_type,
            by_severity=by_severity,
        )

        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        repo_hash = self._repo_hash(repo_path)
        iso = snapshot.date.strftime("%Y%m%dT%H%M%S")
        path = self.snapshot_dir / f"{repo_hash}_{iso}.json"
        path.write_text(
            json.dumps(snapshot.model_dump(mode="json"), indent=2, default=str),
            encoding="utf-8",
        )
        logger.info("Recorded snapshot: %d findings → %s", len(findings), path)
        return snapshot

    def load_snapshots(self, repo_path: str = ".") -> list[DebtSnapshot]:
        """Load all snapshots for a repository, sorted by date ascending."""
        if not self.snapshot_dir.is_dir():
            return []

        repo_hash = self._repo_hash(repo_path)
        snapshots: list[DebtSnapshot] = []

        for path in sorted(self.snapshot_dir.glob(f"{repo_hash}_*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                snapshots.append(DebtSnapshot.model_validate(data))
            except Exception as exc:
                logger.warning("Skipping corrupt snapshot %s: %s", path, exc)

        return snapshots

    # ── Forecasting ────────────────────────────────────────────────────

    def forecast(
        self,
        repo_path: str = ".",
        horizon_days: int = 90,
    ) -> DebtForecast:
        """Produce a debt forecast from historical snapshots.

        Returns a ``DebtForecast`` with predicted finding count,
        trend classification, hotspot directories, and recommended
        actions.  When insufficient data exists, returns a best-effort
        forecast with ``trend="stable"``.
        """
        snapshots = self.load_snapshots(repo_path)

        if len(snapshots) < self.min_snapshots:
            current = snapshots[-1].total_findings if snapshots else 0
            return DebtForecast(
                predicted_findings=current,
                confidence_interval=(current, current),
                trend="stable",
                snapshots_used=len(snapshots),
                recommended_actions=[
                    f"Need at least {self.min_snapshots} snapshots for forecasting "
                    f"(have {len(snapshots)}). Run more scans to build history."
                ],
            )

        # Build time series: x = days since first snapshot, y = total findings
        epoch = snapshots[0].date
        x_vals = [
            (s.date - epoch).total_seconds() / 86400.0
            for s in snapshots
        ]
        y_vals = [float(s.total_findings) for s in snapshots]

        slope, intercept = self._linear_regression(x_vals, y_vals)
        trend = self._determine_trend(slope)

        # Project forward
        last_day = x_vals[-1]
        forecast_day = last_day + horizon_days
        predicted_raw = slope * forecast_day + intercept
        predicted = max(0, round(predicted_raw))

        # Confidence interval (±1 std error of estimate)
        residuals = [
            y - (slope * x + intercept)
            for x, y in zip(x_vals, y_vals, strict=True)
        ]
        n = len(residuals)
        std_err = math.sqrt(sum(r ** 2 for r in residuals) / max(n - 2, 1))
        margin = round(1.96 * std_err)  # ~95% CI
        ci_low = max(0, predicted - margin)
        ci_high = predicted + margin

        # Severity projection (proportional to current distribution)
        latest = snapshots[-1]
        predicted_by_severity: dict[str, int] = {}
        if latest.total_findings > 0:
            for sev, count in latest.by_severity.items():
                ratio = count / latest.total_findings
                predicted_by_severity[sev] = max(0, round(predicted * ratio))

        hotspots = self._identify_hotspots(snapshots)
        actions = self._generate_actions(trend, hotspots, slope, predicted)

        forecast = DebtForecast(
            predicted_findings=predicted,
            predicted_by_severity=predicted_by_severity,
            confidence_interval=(ci_low, ci_high),
            trend=trend,
            hotspot_directories=hotspots,
            recommended_actions=actions,
            snapshots_used=len(snapshots),
            slope=round(slope, 4),
        )

        logger.info(
            "Forecast: %s trend, %d predicted findings in %d days (slope=%.3f/day)",
            trend, predicted, horizon_days, slope,
        )
        return forecast

    # ── Pure-Python linear regression ──────────────────────────────────

    @staticmethod
    def _linear_regression(
        x: list[float], y: list[float],
    ) -> tuple[float, float]:
        """Ordinary least squares: y = slope * x + intercept.

        Returns ``(slope, intercept)``.  No external dependencies.
        """
        n = len(x)
        if n < 2:
            return 0.0, y[0] if y else 0.0

        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y, strict=True))
        sum_x2 = sum(xi ** 2 for xi in x)

        denom = n * sum_x2 - sum_x ** 2
        if abs(denom) < 1e-10:
            return 0.0, sum_y / n

        slope = (n * sum_xy - sum_x * sum_y) / denom
        intercept = (sum_y - slope * sum_x) / n
        return slope, intercept

    @staticmethod
    def _determine_trend(slope: float) -> str:
        """Classify the trend based on the regression slope (findings/day)."""
        if slope < -0.05:
            return "improving"
        elif slope > 0.05:
            return "worsening"
        return "stable"

    @staticmethod
    def _identify_hotspots(snapshots: list[DebtSnapshot]) -> list[str]:
        """Find finding types with growing counts across snapshots."""
        if len(snapshots) < 2:
            return []

        first = snapshots[0].by_type
        last = snapshots[-1].by_type

        growing: list[tuple[str, int]] = []
        for ftype, count in last.items():
            prev = first.get(ftype, 0)
            if count > prev:
                growing.append((ftype, count - prev))

        growing.sort(key=lambda t: t[1], reverse=True)
        return [f"{ftype} (+{delta})" for ftype, delta in growing[:5]]

    @staticmethod
    def _generate_actions(
        trend: str,
        hotspots: list[str],
        slope: float,
        predicted: int,
    ) -> list[str]:
        """Generate recommended actions based on forecast analysis."""
        actions: list[str] = []

        if trend == "worsening":
            actions.append(
                f"Debt is growing at ~{abs(slope):.2f} findings/day. "
                "Allocate dedicated remediation sprints."
            )
            if predicted > 100:
                actions.append(
                    "Predicted findings exceed 100 — consider raising "
                    "confidence thresholds to auto-fix more issues."
                )
        elif trend == "improving":
            actions.append(
                f"Debt is decreasing at ~{abs(slope):.2f} findings/day. "
                "Current remediation velocity is effective."
            )
        else:
            actions.append(
                "Debt is stable. Review scan thresholds to catch "
                "more issues or focus on high-severity backlog."
            )

        if hotspots:
            top = hotspots[0].split(" (")[0] if hotspots else ""
            actions.append(f"Fastest-growing category: {top}. Prioritize this area.")

        return actions

    # ── Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _repo_hash(repo_path: str) -> str:
        """Deterministic short hash of the repo path for filename safety."""
        return hashlib.sha256(repo_path.encode()).hexdigest()[:12]
