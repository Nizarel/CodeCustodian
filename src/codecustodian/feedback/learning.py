"""Feedback collection and learning from PR outcomes (FR-LEARN-100).

Tracks whether PRs were merged, rejected, or modified before merge.
Builds per-scanner success rates and auto-adjusts confidence thresholds
so CodeCustodian gets smarter over time.

Storage: TinyDB-backed for lightweight persistence, compatible
with the existing JSONL-based ``FeedbackStore``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from codecustodian.logging import get_logger

logger = get_logger("feedback.learning")


# ── Models ─────────────────────────────────────────────────────────────────


class PROutcome(BaseModel):
    """Outcome of a PR created by CodeCustodian."""

    pr_number: int
    status: str = "pending"  # merged | rejected | modified | pending
    confidence_was: int = 5
    scanner_type: str = ""
    finding_type: str = ""
    modifications: list[str] = Field(default_factory=list)
    reviewer: str = ""
    review_time_hours: float = 0.0
    team: str = ""
    repo: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


# ── Collector ──────────────────────────────────────────────────────────────


class FeedbackCollector:
    """Track PR outcomes to learn and improve over time (FR-LEARN-100).

    Uses TinyDB for persistence.  Provides success rate calculations
    per scanner type and per team for trend analysis and automatic
    confidence threshold adjustment.

    Args:
        db_path: Path to the TinyDB JSON file.
    """

    def __init__(self, db_path: str = ".codecustodian-cache/learning.json") -> None:
        from pathlib import Path

        from tinydb import TinyDB

        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = TinyDB(str(path))
        self._table = self.db.table("pr_outcomes")

    def close(self) -> None:
        """Close the underlying TinyDB to release file locks."""
        self.db.close()

    # ── Recording ──────────────────────────────────────────────────────

    def record_outcome(self, outcome: PROutcome) -> None:
        """Persist a PR outcome for learning.

        Args:
            outcome: The PR outcome details.
        """
        self._table.insert(outcome.model_dump())
        logger.info(
            "PR outcome recorded: PR #%d → %s (confidence was %d, scanner=%s)",
            outcome.pr_number,
            outcome.status,
            outcome.confidence_was,
            outcome.scanner_type or "unknown",
        )

    def record_dict(self, pr_number: int, outcome: dict[str, Any]) -> None:
        """Convenience: record from a dict payload.

        Expected keys: ``status``, ``confidence``, ``scanner_type``,
        ``modifications``, ``reviewer``, ``review_time``.
        """
        entry = PROutcome(
            pr_number=pr_number,
            status=outcome.get("status", "pending"),
            confidence_was=outcome.get("confidence", 5),
            scanner_type=outcome.get("scanner_type", ""),
            finding_type=outcome.get("finding_type", ""),
            modifications=outcome.get("modifications", []),
            reviewer=outcome.get("reviewer", ""),
            review_time_hours=outcome.get("review_time", 0.0),
            team=outcome.get("team", ""),
            repo=outcome.get("repo", ""),
        )
        self.record_outcome(entry)

    # ── Scanner success rates ──────────────────────────────────────────

    def get_scanner_success_rate(self, scanner_type: str) -> float:
        """Calculate merge rate for a specific scanner type.

        Returns:
            Float 0.0-1.0 representing the merged/total ratio.
            If < 0.9, the caller should increase confidence thresholds.
        """
        from tinydb import where

        records = self._table.search(where("scanner_type") == scanner_type)
        if not records:
            return 1.0  # No data = assume good

        completed = [r for r in records if r.get("status") != "pending"]
        if not completed:
            return 1.0

        merged = sum(1 for r in completed if r.get("status") == "merged")
        return merged / len(completed)

    def get_all_scanner_rates(self) -> dict[str, float]:
        """Return success rates for all scanner types."""
        all_records = self._table.all()
        scanner_types: set[str] = set()
        for r in all_records:
            st = r.get("scanner_type", "")
            if st:
                scanner_types.add(st)

        return {st: self.get_scanner_success_rate(st) for st in scanner_types}

    # ── Team success rates ─────────────────────────────────────────────

    def get_team_success_rate(self, team: str) -> float:
        """Calculate merge rate for a specific team.

        Returns:
            Float 0.0-1.0 representing the merged/total ratio.
        """
        from tinydb import where

        records = self._table.search(where("team") == team)
        if not records:
            return 1.0

        completed = [r for r in records if r.get("status") != "pending"]
        if not completed:
            return 1.0

        merged = sum(1 for r in completed if r.get("status") == "merged")
        return merged / len(completed)

    # ── Confidence adjustment ──────────────────────────────────────────

    def suggest_confidence_adjustment(
        self,
        scanner_type: str,
        *,
        target_success_rate: float = 0.9,
    ) -> int:
        """Suggest a confidence score adjustment based on historical data.

        Returns:
            Positive int = increase threshold, negative = decrease.
            Zero = no change needed.
        """
        rate = self.get_scanner_success_rate(scanner_type)

        if rate >= target_success_rate:
            return 0  # Scanner is performing well

        # How far below target? Each 10% gap = +1 to threshold
        gap = target_success_rate - rate
        adjustment = max(1, int(gap * 10))

        logger.info(
            "Scanner %s success rate %.1f%% < target %.1f%% → suggest +%d confidence threshold",
            scanner_type,
            rate * 100,
            target_success_rate * 100,
            adjustment,
        )
        return adjustment

    # ── Summary stats ──────────────────────────────────────────────────

    def get_summary(self) -> dict[str, Any]:
        """Return overall learning summary."""
        all_records = self._table.all()
        total = len(all_records)
        if total == 0:
            return {"total": 0, "merged": 0, "rejected": 0, "modified": 0, "accuracy": 0.0}

        merged = sum(1 for r in all_records if r.get("status") == "merged")
        rejected = sum(1 for r in all_records if r.get("status") == "rejected")
        modified = sum(1 for r in all_records if r.get("status") == "modified")
        completed = merged + rejected + modified

        accuracy = (merged / completed * 100) if completed > 0 else 0.0

        return {
            "total": total,
            "merged": merged,
            "rejected": rejected,
            "modified": modified,
            "pending": total - completed,
            "accuracy": round(accuracy, 1),
            "scanner_rates": self.get_all_scanner_rates(),
        }
