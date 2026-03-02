"""Historical pattern recognition for cross-org learning (FR-LEARN-101).

Queries past refactorings across the organisation to find similar
patterns and their outcomes.  This enables CodeCustodian to suggest
approaches that worked before and avoid approaches that were rejected.

Storage: TinyDB-backed for lightweight persistence.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from codecustodian.logging import get_logger
from codecustodian.models import Finding

logger = get_logger("feedback.history")


# ── Models ─────────────────────────────────────────────────────────────────


class HistoricalRefactoring(BaseModel):
    """A record of a past refactoring and its outcome."""

    finding_type: str
    library: str = ""
    pattern: str = ""
    file_pattern: str = ""
    team: str = ""
    repo: str = ""
    success: bool = True
    outcome: str = "merged"  # merged | rejected | modified
    success_rate: float = 1.0
    modifications: list[str] = Field(default_factory=list)
    learned_recommendation: str = ""
    confidence_was: int = 5
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class SimilarPattern(BaseModel):
    """A similar historical pattern found for a given finding."""

    team: str = ""
    repo: str = ""
    success_rate: float = 1.0
    common_modifications: list[str] = Field(default_factory=list)
    recommendation: str = ""
    match_score: float = 0.0


# ── Recognizer ─────────────────────────────────────────────────────────────


class HistoricalPatternRecognizer:
    """Query historical refactorings across org for similar patterns (FR-LEARN-101).

    Stores refactoring outcomes and searches by finding type, library,
    and file pattern to find precedents.

    Args:
        db_path: Path to the TinyDB JSON file.
    """

    def __init__(
        self, db_path: str = ".codecustodian-cache/history.json"
    ) -> None:
        from tinydb import TinyDB

        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = TinyDB(str(path))
        self._table = self.db.table("historical_refactorings")

    def close(self) -> None:
        """Close the underlying TinyDB to release file locks."""
        self.db.close()

    # ── Recording ──────────────────────────────────────────────────────

    def record_refactoring(self, entry: HistoricalRefactoring) -> None:
        """Record a completed refactoring for future pattern matching."""
        self._table.insert(entry.model_dump())
        logger.info(
            "Historical refactoring recorded: type=%s lib=%s outcome=%s",
            entry.finding_type,
            entry.library or "n/a",
            entry.outcome,
        )

    def record_from_outcome(
        self,
        finding: Finding,
        outcome: str,
        *,
        team: str = "",
        repo: str = "",
        modifications: list[str] | None = None,
        confidence_was: int = 5,
    ) -> None:
        """Convenience: record from a Finding + outcome string."""
        entry = HistoricalRefactoring(
            finding_type=finding.type.value,
            library=finding.metadata.get("library", ""),
            pattern=finding.metadata.get("pattern", ""),
            file_pattern=str(Path(finding.file).parent),
            team=team,
            repo=repo,
            success=outcome == "merged",
            outcome=outcome,
            success_rate=1.0 if outcome == "merged" else 0.0,
            modifications=modifications or [],
            learned_recommendation=self._derive_recommendation(outcome, modifications),
            confidence_was=confidence_was,
        )
        self.record_refactoring(entry)

    # ── Pattern matching ───────────────────────────────────────────────

    async def find_similar(
        self,
        finding: Finding,
        *,
        max_results: int = 5,
    ) -> list[SimilarPattern]:
        """Find similar past refactorings and their outcomes.

        Searches by finding type + library + pattern; ranks by
        match quality.

        Args:
            finding: The finding to search for precedents.
            max_results: Maximum similar patterns to return.

        Returns:
            List of ``SimilarPattern`` sorted by match score.
        """
        from tinydb import where

        finding_type = finding.type.value
        library = finding.metadata.get("library", "")
        pattern = finding.metadata.get("pattern", "")

        # Start with type match (required)
        candidates = self._table.search(where("finding_type") == finding_type)

        if not candidates:
            return []

        # Score each candidate
        scored: list[tuple[dict, float]] = []
        for record in candidates:
            score = 1.0  # Base score for type match

            # Library match bonus
            rec_lib = record.get("library", "")
            if library and rec_lib and library.lower() == rec_lib.lower():
                score += 2.0

            # Pattern match bonus
            rec_pattern = record.get("pattern", "")
            if pattern and rec_pattern and pattern.lower() in rec_pattern.lower():
                score += 1.5

            # File path similarity bonus
            rec_file = record.get("file_pattern", "")
            finding_dir = str(Path(finding.file).parent)
            if rec_file and finding_dir and rec_file in finding_dir:
                score += 0.5

            scored.append((record, score))

        # Sort by score, take top N
        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:max_results]

        results: list[SimilarPattern] = []
        for record, match_score in top:
            results.append(SimilarPattern(
                team=record.get("team", ""),
                repo=record.get("repo", ""),
                success_rate=record.get("success_rate", 0.0),
                common_modifications=record.get("modifications", []),
                recommendation=record.get("learned_recommendation", ""),
                match_score=round(match_score, 2),
            ))

        return results

    def get_context_for_prompt(
        self,
        finding: Finding,
        similar: list[SimilarPattern] | None = None,
    ) -> str:
        """Format historical context as a prompt section for Copilot SDK.

        Designed to be appended to the system or user prompt so the AI
        can learn from past outcomes.

        Returns an empty string if no similar patterns exist.
        """
        if similar is None:
            import asyncio
            try:
                asyncio.get_running_loop()
                # If we're in an async context, create a task
                # But for simplicity, return empty and let caller use async
                return ""
            except RuntimeError:
                similar = asyncio.run(self.find_similar(finding))

        if not similar:
            return ""

        lines = [
            "Historical Context (similar past refactorings and their outcomes):",
        ]
        for i, pat in enumerate(similar[:3], 1):
            lines.append(f"  {i}. Team '{pat.team or 'unknown'}' — "
                         f"success rate: {pat.success_rate:.0%}")
            if pat.recommendation:
                lines.append(f"     Recommendation: {pat.recommendation}")
            if pat.common_modifications:
                mods = ", ".join(pat.common_modifications[:3])
                lines.append(f"     Common modifications: {mods}")

        return "\n".join(lines)

    # ── Aggregates ─────────────────────────────────────────────────────

    def get_success_rate_by_type(self) -> dict[str, float]:
        """Return per-finding-type success rates across all history."""
        all_records = self._table.all()
        type_stats: dict[str, dict[str, int]] = {}

        for r in all_records:
            ft = r.get("finding_type", "unknown")
            if ft not in type_stats:
                type_stats[ft] = {"total": 0, "success": 0}
            type_stats[ft]["total"] += 1
            if r.get("success", False):
                type_stats[ft]["success"] += 1

        return {
            ft: stats["success"] / stats["total"]
            for ft, stats in type_stats.items()
            if stats["total"] > 0
        }

    def get_summary(self) -> dict[str, Any]:
        """Return overall history summary."""
        all_records = self._table.all()
        total = len(all_records)
        if total == 0:
            return {"total": 0, "success_rate_by_type": {}}

        success = sum(1 for r in all_records if r.get("success", False))
        return {
            "total": total,
            "overall_success_rate": round(success / total, 3),
            "success_rate_by_type": self.get_success_rate_by_type(),
        }

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _derive_recommendation(
        outcome: str,
        modifications: list[str] | None,
    ) -> str:
        """Derive a recommendation from the outcome."""
        if outcome == "merged" and not modifications:
            return "Approach was accepted without changes — use same strategy"
        if outcome == "merged" and modifications:
            return f"Accepted with modifications: {', '.join(modifications[:3])}"
        if outcome == "rejected":
            return "Approach was rejected — try alternative strategy"
        if outcome == "modified":
            return f"Required changes: {', '.join(modifications[:3]) if modifications else 'style adjustments'}"
        return ""
