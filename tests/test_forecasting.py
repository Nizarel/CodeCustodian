"""Tests for the predictive debt forecasting module."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from codecustodian.intelligence.forecasting import PredictiveDebtForecaster
from codecustodian.models import (
    DebtForecast,
    DebtSnapshot,
    Finding,
    FindingType,
    SeverityLevel,
)


def _make_finding(**overrides: object) -> Finding:
    defaults: dict[str, object] = {
        "type": FindingType.DEPRECATED_API,
        "severity": SeverityLevel.HIGH,
        "file": "src/example.py",
        "line": 10,
        "description": "Deprecated API usage",
        "suggestion": "Use modern alternative",
        "priority_score": 120.0,
    }
    defaults.update(overrides)
    return Finding(**defaults)


class TestPredictiveDebtForecaster:
    """Unit tests for PredictiveDebtForecaster."""

    def _make_forecaster(self, tmp_path: Path) -> PredictiveDebtForecaster:
        return PredictiveDebtForecaster(snapshot_dir=tmp_path / "snapshots")

    # ── Snapshot I/O ───────────────────────────────────────────────────

    def test_record_snapshot_creates_json(self, tmp_path: Path) -> None:
        fc = self._make_forecaster(tmp_path)
        findings = [_make_finding() for _ in range(5)]
        fc.record_snapshot(findings, str(tmp_path))

        snapshots = list((tmp_path / "snapshots").glob("*.json"))
        assert len(snapshots) == 1

        data = json.loads(snapshots[0].read_text())
        assert data["total_findings"] == 5
        assert data["repo_path"] == str(tmp_path)

    def test_load_snapshots_returns_sorted(self, tmp_path: Path) -> None:
        fc = self._make_forecaster(tmp_path)
        snap_dir = tmp_path / "snapshots"
        snap_dir.mkdir(parents=True)

        repo_hash = fc._repo_hash(str(tmp_path))
        for i in range(3):
            d = date.today() - timedelta(days=30 * (2 - i))
            data = DebtSnapshot(
                date=d,
                repo_path=str(tmp_path),
                total_findings=10 + i * 5,
                by_type={"deprecated_api": 10 + i * 5},
                by_severity={"high": 10 + i * 5},
            ).model_dump(mode="json")
            (snap_dir / f"{repo_hash}_{d.isoformat()}.json").write_text(json.dumps(data))

        snapshots = fc.load_snapshots(str(tmp_path))
        assert len(snapshots) == 3
        assert snapshots[0].total_findings <= snapshots[2].total_findings

    def test_load_snapshots_empty_repo(self, tmp_path: Path) -> None:
        fc = self._make_forecaster(tmp_path)
        assert fc.load_snapshots(str(tmp_path)) == []

    # ── Forecasting ────────────────────────────────────────────────────

    def test_forecast_requires_min_snapshots(self, tmp_path: Path) -> None:
        fc = self._make_forecaster(tmp_path)
        # Record only 1 snapshot — need at least 3
        fc.record_snapshot([_make_finding()], str(tmp_path))

        forecast = fc.forecast(str(tmp_path))
        # With insufficient data, returns a best-effort stable forecast
        assert forecast.trend == "stable"
        assert forecast.snapshots_used == 1
        assert any("snapshots" in a.lower() for a in forecast.recommended_actions)

    def test_forecast_with_enough_snapshots(self, tmp_path: Path) -> None:
        fc = self._make_forecaster(tmp_path)
        snap_dir = tmp_path / "snapshots"
        snap_dir.mkdir(parents=True)

        repo_hash = fc._repo_hash(str(tmp_path))
        for i in range(4):
            d = date.today() - timedelta(days=30 * (3 - i))
            data = DebtSnapshot(
                date=d,
                repo_path=str(tmp_path),
                total_findings=20 + i * 10,
                by_type={"deprecated_api": 20 + i * 10},
                by_severity={"high": 20 + i * 10},
            ).model_dump(mode="json")
            (snap_dir / f"{repo_hash}_{d.isoformat()}.json").write_text(json.dumps(data))

        forecast = fc.forecast(str(tmp_path), horizon_days=90)
        assert isinstance(forecast, DebtForecast)
        assert forecast.predicted_findings >= 0
        assert forecast.trend in ("improving", "stable", "worsening")
        assert forecast.snapshots_used == 4
        assert isinstance(forecast.confidence_interval, tuple)

    def test_forecast_worsening_trend(self, tmp_path: Path) -> None:
        fc = self._make_forecaster(tmp_path)
        snap_dir = tmp_path / "snapshots"
        snap_dir.mkdir(parents=True)

        repo_hash = fc._repo_hash(str(tmp_path))
        for i in range(5):
            d = date.today() - timedelta(days=30 * (4 - i))
            data = DebtSnapshot(
                date=d,
                repo_path=str(tmp_path),
                total_findings=10 + i * 20,  # strongly increasing
                by_type={"deprecated_api": 10 + i * 20},
                by_severity={"high": 10 + i * 20},
            ).model_dump(mode="json")
            (snap_dir / f"{repo_hash}_{d.isoformat()}.json").write_text(json.dumps(data))

        forecast = fc.forecast(str(tmp_path))
        assert forecast.trend == "worsening"
        assert forecast.slope > 0

    def test_forecast_improving_trend(self, tmp_path: Path) -> None:
        fc = self._make_forecaster(tmp_path)
        snap_dir = tmp_path / "snapshots"
        snap_dir.mkdir(parents=True)

        repo_hash = fc._repo_hash(str(tmp_path))
        for i in range(5):
            d = date.today() - timedelta(days=30 * (4 - i))
            data = DebtSnapshot(
                date=d,
                repo_path=str(tmp_path),
                total_findings=100 - i * 20,  # strongly decreasing
                by_type={"deprecated_api": 100 - i * 20},
                by_severity={"high": 100 - i * 20},
            ).model_dump(mode="json")
            (snap_dir / f"{repo_hash}_{d.isoformat()}.json").write_text(json.dumps(data))

        forecast = fc.forecast(str(tmp_path))
        assert forecast.trend == "improving"
        assert forecast.slope < 0

    # ── Helpers ────────────────────────────────────────────────────────

    def test_linear_regression_basic(self, tmp_path: Path) -> None:
        fc = self._make_forecaster(tmp_path)
        slope, intercept = fc._linear_regression([0, 1, 2, 3], [0, 2, 4, 6])
        assert abs(slope - 2.0) < 0.01
        assert abs(intercept) < 0.01

    def test_repo_hash_deterministic(self, tmp_path: Path) -> None:
        fc = self._make_forecaster(tmp_path)
        h1 = fc._repo_hash("/some/path")
        h2 = fc._repo_hash("/some/path")
        assert h1 == h2
        assert len(h1) == 12

    def test_determine_trend_thresholds(self, tmp_path: Path) -> None:
        fc = self._make_forecaster(tmp_path)
        assert fc._determine_trend(-0.1) == "improving"
        assert fc._determine_trend(0.0) == "stable"
        assert fc._determine_trend(0.1) == "worsening"

    def test_forecast_has_recommended_actions(self, tmp_path: Path) -> None:
        fc = self._make_forecaster(tmp_path)
        snap_dir = tmp_path / "snapshots"
        snap_dir.mkdir(parents=True)

        repo_hash = fc._repo_hash(str(tmp_path))
        for i in range(3):
            d = date.today() - timedelta(days=30 * (2 - i))
            data = DebtSnapshot(
                date=d,
                repo_path=str(tmp_path),
                total_findings=50 + i * 10,
                by_type={"deprecated_api": 30, "security": 20 + i * 10},
                by_severity={"high": 50 + i * 10},
            ).model_dump(mode="json")
            (snap_dir / f"{repo_hash}_{d.isoformat()}.json").write_text(json.dumps(data))

        forecast = fc.forecast(str(tmp_path))
        assert isinstance(forecast.recommended_actions, list)
        assert len(forecast.recommended_actions) >= 1

    def test_forecast_identifies_hotspots(self, tmp_path: Path) -> None:
        fc = self._make_forecaster(tmp_path)
        snap_dir = tmp_path / "snapshots"
        snap_dir.mkdir(parents=True)

        repo_hash = fc._repo_hash(str(tmp_path))
        # First snapshot: only deprecated_api
        d1 = date.today() - timedelta(days=60)
        data1 = DebtSnapshot(
            date=d1,
            repo_path=str(tmp_path),
            total_findings=10,
            by_type={"deprecated_api": 10},
            by_severity={"high": 10},
        ).model_dump(mode="json")
        (snap_dir / f"{repo_hash}_{d1.isoformat()}.json").write_text(json.dumps(data1))

        # Subsequent snapshots: security grows
        for i in range(1, 3):
            d = date.today() - timedelta(days=60 - i * 30)
            data = DebtSnapshot(
                date=d,
                repo_path=str(tmp_path),
                total_findings=10 + i * 5,
                by_type={"deprecated_api": 10, "security": i * 5},
                by_severity={"high": 10 + i * 5},
            ).model_dump(mode="json")
            (snap_dir / f"{repo_hash}_{d.isoformat()}.json").write_text(json.dumps(data))

        forecast = fc.forecast(str(tmp_path))
        assert any("security" in h for h in forecast.hotspot_directories)
