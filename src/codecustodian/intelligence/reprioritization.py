"""Dynamic re-prioritization engine (FR-PRIORITY-101).

Reacts to real-time events (production incidents, CVEs, deadlines,
budget changes, team capacity) and adjusts finding priorities on
the fly so the pipeline always works on what matters most *right now*.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from codecustodian.logging import get_logger
from codecustodian.models import Finding

logger = get_logger("intelligence.reprioritization")


# ── Event types ────────────────────────────────────────────────────────────


class EventType(StrEnum):
    """Supported re-prioritization event types."""

    PRODUCTION_INCIDENT = "production_incident"
    CVE_ANNOUNCED = "cve_announced"
    DEADLINE_APPROACHING = "deadline_approaching"
    BUDGET_EXCEEDED = "budget_exceeded"
    TEAM_CAPACITY_CHANGE = "team_capacity_change"
    CUSTOM = "custom"


class PriorityEvent(BaseModel):
    """An event that triggers re-prioritization."""

    event_type: EventType
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: str = ""


class ReprioritizationResult(BaseModel):
    """Outcome of a re-prioritization pass."""

    event_type: str
    findings_affected: int = 0
    elevated: int = 0
    paused: int = 0
    details: str = ""


# ── Reprioritizer ──────────────────────────────────────────────────────────


class DynamicReprioritizer:
    """Re-evaluate priorities based on changing context (FR-PRIORITY-101).

    Operates on passed-in finding lists — does **not** own persistence.
    The caller (typically ``Pipeline._prioritize()``) is responsible for
    feeding findings in and collecting the adjusted list back.
    """

    # Default priority boost amounts
    INCIDENT_BOOST = 200
    CVE_BOOST = 300
    DEADLINE_BOOST = 150
    CRITICAL_THRESHOLD = 100.0

    def __init__(
        self,
        *,
        budget_manager: Any | None = None,
        work_iq_provider: Any | None = None,
    ) -> None:
        self._budget_manager = budget_manager
        self._work_iq = work_iq_provider
        self._event_log: list[PriorityEvent] = []

    # ── Public API ─────────────────────────────────────────────────────

    async def handle_event(
        self,
        event_type: str | EventType,
        payload: dict[str, Any],
        findings: list[Finding],
    ) -> ReprioritizationResult:
        """Dispatch an event and apply priority adjustments to *findings*.

        Args:
            event_type: One of :class:`EventType` values or a custom string.
            payload: Event-specific data (file_path, cve_id, library, etc.).
            findings: The mutable list of findings to adjust.

        Returns:
            Summary of what changed.
        """
        if isinstance(event_type, str):
            try:
                event_type = EventType(event_type)
            except ValueError:
                event_type = EventType.CUSTOM

        event = PriorityEvent(event_type=event_type, payload=payload)
        self._event_log.append(event)

        dispatchers = {
            EventType.PRODUCTION_INCIDENT: self._handle_production_incident,
            EventType.CVE_ANNOUNCED: self._handle_cve_announced,
            EventType.DEADLINE_APPROACHING: self._handle_deadline_approaching,
            EventType.BUDGET_EXCEEDED: self._handle_budget_exceeded,
            EventType.TEAM_CAPACITY_CHANGE: self._handle_team_capacity_change,
        }

        handler = dispatchers.get(event_type, self._handle_custom)
        result = await handler(payload, findings)

        logger.info(
            "Reprioritization event=%s affected=%d elevated=%d paused=%d",
            event_type.value if isinstance(event_type, EventType) else event_type,
            result.findings_affected,
            result.elevated,
            result.paused,
        )
        return result

    def get_event_log(self) -> list[PriorityEvent]:
        """Return the history of handled events."""
        return list(self._event_log)

    # ── Event handlers ─────────────────────────────────────────────────

    async def _handle_production_incident(
        self,
        payload: dict[str, Any],
        findings: list[Finding],
    ) -> ReprioritizationResult:
        """Elevate all findings in the affected file."""
        file_path = payload.get("file_path", "")
        boost = payload.get("boost", self.INCIDENT_BOOST)
        elevated = 0

        for f in findings:
            if self._file_matches(f.file, file_path):
                f.priority_score += boost
                f.metadata["priority_boost"] = f"production_incident:+{boost}"
                elevated += 1

        return ReprioritizationResult(
            event_type=EventType.PRODUCTION_INCIDENT.value,
            findings_affected=elevated,
            elevated=elevated,
            details=f"Boosted {elevated} findings in {file_path} by +{boost}",
        )

    async def _handle_cve_announced(
        self,
        payload: dict[str, Any],
        findings: list[Finding],
    ) -> ReprioritizationResult:
        """Elevate findings related to the announced CVE."""
        cve_id = payload.get("cve_id", "")
        library = payload.get("library", "")
        boost = payload.get("boost", self.CVE_BOOST)
        elevated = 0

        for f in findings:
            if self._matches_cve(f, cve_id, library):
                f.priority_score += boost
                f.metadata["priority_boost"] = f"cve:{cve_id}:+{boost}"
                elevated += 1

        return ReprioritizationResult(
            event_type=EventType.CVE_ANNOUNCED.value,
            findings_affected=elevated,
            elevated=elevated,
            details=f"CVE {cve_id}: boosted {elevated} findings by +{boost}",
        )

    async def _handle_deadline_approaching(
        self,
        payload: dict[str, Any],
        findings: list[Finding],
    ) -> ReprioritizationResult:
        """Elevate deprecation warnings for an upcoming library upgrade."""
        library = payload.get("library", "")
        boost = payload.get("boost", self.DEADLINE_BOOST)
        elevated = 0

        for f in findings:
            lib_meta = f.metadata.get("library", "")
            if library and library.lower() in lib_meta.lower():
                f.priority_score += boost
                f.metadata["priority_boost"] = f"deadline:{library}:+{boost}"
                elevated += 1

        return ReprioritizationResult(
            event_type=EventType.DEADLINE_APPROACHING.value,
            findings_affected=elevated,
            elevated=elevated,
            details=f"Deadline for {library}: boosted {elevated} findings by +{boost}",
        )

    async def _handle_budget_exceeded(
        self,
        payload: dict[str, Any],
        findings: list[Finding],
    ) -> ReprioritizationResult:
        """Pause non-critical findings, continue only high-priority ones."""
        paused = 0
        for f in findings:
            combined = f.priority_score + f.business_impact_score
            if combined < self.CRITICAL_THRESHOLD:
                f.metadata["paused"] = True
                f.metadata["pause_reason"] = "budget_exceeded"
                paused += 1

        active = len(findings) - paused
        return ReprioritizationResult(
            event_type=EventType.BUDGET_EXCEEDED.value,
            findings_affected=len(findings),
            paused=paused,
            details=f"Budget exceeded: paused {paused} non-critical, {active} remain active",
        )

    async def _handle_team_capacity_change(
        self,
        payload: dict[str, Any],
        findings: list[Finding],
    ) -> ReprioritizationResult:
        """Adjust based on team capacity from Work IQ or payload."""
        capacity_ratio = payload.get("capacity_ratio", 1.0)
        team_id = payload.get("team_id", "unknown")

        if capacity_ratio < 0.5:
            # Team at <50% capacity — pause low-priority
            paused = 0
            for f in findings:
                if f.priority_score < 50:
                    f.metadata["paused"] = True
                    f.metadata["pause_reason"] = f"team_capacity:{team_id}"
                    paused += 1
            return ReprioritizationResult(
                event_type=EventType.TEAM_CAPACITY_CHANGE.value,
                findings_affected=len(findings),
                paused=paused,
                details=f"Team {team_id} at {capacity_ratio:.0%} — paused {paused} low-priority",
            )

        return ReprioritizationResult(
            event_type=EventType.TEAM_CAPACITY_CHANGE.value,
            findings_affected=0,
            details=f"Team {team_id} at {capacity_ratio:.0%} — no adjustments needed",
        )

    async def _handle_custom(
        self,
        payload: dict[str, Any],
        findings: list[Finding],
    ) -> ReprioritizationResult:
        """Handle custom events with a generic boost."""
        boost = payload.get("boost", 0)
        pattern = payload.get("file_pattern", "")
        elevated = 0

        if boost and pattern:
            for f in findings:
                if pattern.lower() in f.file.lower():
                    f.priority_score += boost
                    elevated += 1

        return ReprioritizationResult(
            event_type=EventType.CUSTOM.value,
            findings_affected=elevated,
            elevated=elevated,
            details=f"Custom event: elevated {elevated} findings matching '{pattern}'",
        )

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def filter_active(findings: list[Finding]) -> list[Finding]:
        """Return only findings that are not paused."""
        return [f for f in findings if not f.metadata.get("paused", False)]

    @staticmethod
    def _file_matches(finding_file: str, target: str) -> bool:
        """Check if a finding's file matches the target path."""
        if not target:
            return False
        # Normalise separators
        a = finding_file.replace("\\", "/").lower()
        b = target.replace("\\", "/").lower()
        return a == b or a.endswith(b) or b.endswith(a)

    @staticmethod
    def _matches_cve(
        finding: Finding,
        cve_id: str,
        library: str,
    ) -> bool:
        """Check if a finding is related to the announced CVE."""
        # Check metadata for CVE reference
        meta_cve = finding.metadata.get("cve", "")
        if cve_id and cve_id.lower() in meta_cve.lower():
            return True

        # Check library match + security type
        if library:
            lib_meta = finding.metadata.get("library", "")
            desc_lower = finding.description.lower()
            if library.lower() in lib_meta.lower() or library.lower() in desc_lower:
                return True

        return False
