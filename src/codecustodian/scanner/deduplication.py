"""Finding de-duplication engine.

Prevents the same finding from being reported across multiple runs
by hashing key attributes and storing them in TinyDB.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from tinydb import TinyDB, Query

from codecustodian.logging import get_logger
from codecustodian.models import Finding

logger = get_logger("scanner.deduplication")


class DeduplicationEngine:
    """De-duplicate findings across pipeline runs using content hashing."""

    def __init__(self, db_path: str | Path = ".codecustodian-cache/dedup.json") -> None:
        db_file = Path(db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        self._db = TinyDB(str(db_file))
        self._table = self._db.table("seen_findings")

    def deduplicate(self, findings: list[Finding]) -> list[Finding]:
        """Filter findings that have already been seen."""
        unique: list[Finding] = []
        for finding in findings:
            fingerprint = self._hash(finding)
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

    def _hash(self, finding: Finding) -> str:
        """Generate a stable hash for a finding."""
        content = f"{finding.type.value}:{finding.file}:{finding.line}:{finding.description}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _is_seen(self, fingerprint: str) -> bool:
        q = Query()
        return bool(self._table.search(q.fingerprint == fingerprint))

    def _mark_seen(self, fingerprint: str, finding_id: str) -> None:
        self._table.insert({"fingerprint": fingerprint, "finding_id": finding_id})

    def clear(self) -> None:
        """Clear all de-duplication state."""
        self._table.truncate()
