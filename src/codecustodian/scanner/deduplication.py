"""Finding de-duplication engine.

Prevents the same finding from being reported across multiple runs
by hashing key attributes and storing them in TinyDB.  Tracks
``first_seen`` timestamps and supports ``mark_resolved`` for
trend analysis (BR-SCN-001).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from tinydb import TinyDB, Query

from codecustodian.logging import get_logger
from codecustodian.models import Finding

logger = get_logger("scanner.deduplication")


class DeduplicationEngine:
    """De-duplicate findings across pipeline runs using content hashing.

    Uses the ``Finding.dedup_key`` computed field as the stable
    fingerprint, avoiding logic duplication.
    """

    def __init__(self, db_path: str | Path = ".codecustodian-cache/dedup.json") -> None:
        db_file = Path(db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        self._db = TinyDB(str(db_file))
        self._table = self._db.table("seen_findings")

    # ── Core API ──────────────────────────────────────────────────────

    def deduplicate(self, findings: list[Finding]) -> list[Finding]:
        """Return only findings not seen in previous runs.

        Newly-seen findings are persisted with a ``first_seen`` timestamp.
        """
        unique: list[Finding] = []
        for finding in findings:
            fingerprint = finding.dedup_key
            if not self._is_seen(fingerprint):
                unique.append(finding)
                self._mark_seen(fingerprint, finding.id)
        logger.info(
            "De-dup: %d → %d findings (%d duplicates removed)",
            len(findings),
            len(unique),
            len(findings) - len(unique),
        )
        return unique

    def mark_resolved(self, finding_id: str) -> bool:
        """Mark a finding as resolved for trend tracking.

        Returns ``True`` if the record was found and updated.
        """
        q = Query()
        updated = self._table.update(
            {"resolved_at": datetime.now(UTC).isoformat()},
            q.finding_id == finding_id,
        )
        if updated:
            logger.debug("Marked finding %s as resolved", finding_id)
            return True
        logger.debug("Finding %s not found in dedup store", finding_id)
        return False

    def get_trends(self) -> dict[str, int]:
        """Return trend counts: ``new``, ``recurring``, ``resolved``."""
        q = Query()
        all_records = self._table.all()
        resolved = sum(1 for r in all_records if "resolved_at" in r)
        total = len(all_records)
        return {
            "total": total,
            "resolved": resolved,
            "active": total - resolved,
        }

    def clear(self) -> None:
        """Clear all de-duplication state."""
        self._table.truncate()

    # ── Internal helpers ──────────────────────────────────────────────

    def _is_seen(self, fingerprint: str) -> bool:
        q = Query()
        return bool(self._table.search(q.fingerprint == fingerprint))

    def _mark_seen(self, fingerprint: str, finding_id: str) -> None:
        self._table.insert({
            "fingerprint": fingerprint,
            "finding_id": finding_id,
            "first_seen": datetime.now(UTC).isoformat(),
        })
