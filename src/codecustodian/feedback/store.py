"""Feedback loop — capture and learn from PR review outcomes.

Stores review decisions (approve/reject/modify) and uses them
to improve future planning accuracy and confidence scoring.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from codecustodian.logging import get_logger

logger = get_logger("feedback")


class FeedbackEntry(BaseModel):
    """A single feedback entry from a PR review."""

    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    finding_id: str
    finding_type: str
    action: str  # approved | rejected | modified
    confidence_was: int
    reviewer_comment: str = ""
    pr_number: int = 0


class FeedbackStore:
    """Persistent feedback storage for learning."""

    def __init__(self, storage_dir: str | Path = ".codecustodian-cache") -> None:
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.file = self.storage_dir / "feedback.jsonl"

    def record(self, entry: FeedbackEntry) -> None:
        """Record a feedback entry."""
        with open(self.file, "a", encoding="utf-8") as f:
            f.write(entry.model_dump_json() + "\n")
        logger.info(
            "Feedback recorded: %s → %s (confidence was %d)",
            entry.finding_id,
            entry.action,
            entry.confidence_was,
        )

    def get_accuracy_stats(self) -> dict:
        """Calculate accuracy from historical feedback."""
        if not self.file.exists():
            return {"total": 0, "approved": 0, "rejected": 0, "accuracy": 0.0}

        total = approved = rejected = 0
        for line in self.file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            total += 1
            if entry.get("action") == "approved":
                approved += 1
            elif entry.get("action") == "rejected":
                rejected += 1

        accuracy = (approved / total * 100) if total > 0 else 0.0
        return {
            "total": total,
            "approved": approved,
            "rejected": rejected,
            "accuracy": round(accuracy, 1),
        }
