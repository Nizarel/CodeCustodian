"""Enterprise audit logging.

Logs all CodeCustodian operations for compliance and traceability.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator

from codecustodian.logging import get_logger

logger = get_logger("enterprise.audit")


class AuditEntry(BaseModel):
    """A single audit log entry."""

    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    event_type: str = "refactoring_action"
    action: str
    finding_id: str = ""
    file_path: str = ""
    actor: str = "codecustodian"
    target: str = ""
    changes: dict[str, int] = Field(
        default_factory=lambda: {
            "files_modified": 1,
            "lines_added": 0,
            "lines_removed": 0,
        }
    )
    ai_reasoning: str = ""
    confidence_score: float | None = None
    verification: dict[str, bool | None] = Field(
        default_factory=lambda: {
            "tests_passed": None,
            "linting_passed": None,
            "security_passed": None,
        }
    )
    pr_number: int | None = None
    approver: str | None = None
    merge_date: str | None = None
    details: dict = Field(default_factory=dict)
    status: str = "success"
    entry_hash: str = ""

    def compute_hash(self) -> str:
        """Create deterministic SHA-256 hash for tamper-evident entries."""
        payload = self.model_dump(exclude={"entry_hash"}, mode="json")
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @model_validator(mode="after")
    def _ensure_hash(self) -> AuditEntry:
        if not self.entry_hash:
            self.entry_hash = self.compute_hash()
        return self


class AuditLogger:
    """Append-only audit logger for enterprise compliance."""

    def __init__(
        self,
        log_dir: str | Path = ".codecustodian-audit",
        monitor_sink: Callable[[dict[str, Any]], None] | None = None,
        blob_sink: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        self.log_file = self.log_dir / f"audit-{today}.jsonl"
        self.monitor_sink = monitor_sink
        self.blob_sink = blob_sink

    def log(self, action: str, target: str = "", **details: object) -> None:
        """Record an audit entry."""
        files_modified = int(details.pop("files_modified", 1) or 1)
        lines_added = int(details.pop("lines_added", 0) or 0)
        lines_removed = int(details.pop("lines_removed", 0) or 0)
        tests_passed = details.pop("tests_passed", None)
        linting_passed = details.pop("linting_passed", None)
        security_passed = details.pop("security_passed", None)

        entry = AuditEntry(
            event_type=str(details.pop("event_type", action)),
            action=action,
            finding_id=str(details.pop("finding_id", "")),
            file_path=str(details.pop("file_path", target)),
            target=target,
            actor=str(details.pop("actor", "codecustodian")),
            changes={
                "files_modified": files_modified,
                "lines_added": lines_added,
                "lines_removed": lines_removed,
            },
            ai_reasoning=str(details.pop("ai_reasoning", "")),
            confidence_score=details.pop("confidence_score", None),
            verification={
                "tests_passed": bool(tests_passed) if tests_passed is not None else None,
                "linting_passed": bool(linting_passed) if linting_passed is not None else None,
                "security_passed": bool(security_passed) if security_passed is not None else None,
            },
            pr_number=details.pop("pr_number", None),
            approver=details.pop("approver", None),
            merge_date=details.pop("merge_date", None),
            details=details,
        )

        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(entry.model_dump_json() + "\n")

        payload = entry.model_dump(mode="json")
        self._emit_to_optional_sinks(payload)
        logger.debug("Audit: %s → %s", action, target)

    def _emit_to_optional_sinks(self, payload: dict[str, Any]) -> None:
        """Emit to external sinks (e.g., Azure Monitor / Blob) on best effort."""
        for sink_name, sink in (
            ("monitor", self.monitor_sink),
            ("blob", self.blob_sink),
        ):
            if sink is None:
                continue
            try:
                sink(payload)
            except Exception as exc:
                logger.warning("Audit %s sink emission failed: %s", sink_name, exc)

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
