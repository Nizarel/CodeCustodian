"""Enterprise audit logging.

Logs all CodeCustodian operations for compliance and traceability.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from codecustodian.logging import get_logger

logger = get_logger("enterprise.audit")


class AuditEntry(BaseModel):
    """A single audit log entry."""

    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    action: str
    actor: str = "codecustodian"
    target: str = ""
    details: dict = Field(default_factory=dict)
    status: str = "success"


class AuditLogger:
    """Append-only audit logger for enterprise compliance."""

    def __init__(self, log_dir: str | Path = ".codecustodian-audit") -> None:
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.log_file = self.log_dir / f"audit-{today}.jsonl"

    def log(self, action: str, target: str = "", **details: object) -> None:
        """Record an audit entry."""
        entry = AuditEntry(
            action=action,
            target=target,
            details=details,  # type: ignore[arg-type]
        )
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(entry.model_dump_json() + "\n")
        logger.debug("Audit: %s → %s", action, target)

    def query(
        self,
        action: str | None = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        """Query audit entries from today's log."""
        entries: list[AuditEntry] = []
        if not self.log_file.exists():
            return entries

        for line in self.log_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            entry = AuditEntry(**json.loads(line))
            if action and entry.action != action:
                continue
            entries.append(entry)
            if len(entries) >= limit:
                break

        return entries
