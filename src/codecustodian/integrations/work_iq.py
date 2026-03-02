"""Work item intelligence integration (FR-WORKIQ-100, FR-WORKIQ-101, FR-WORKIQ-102).

Maps findings to project management concepts — sprints, backlogs, and
priority queues.  Provides ``WorkIQContextProvider`` to query the
Microsoft Work IQ MCP server for organizational context: expert lookup,
sprint status, and PR-scheduling intelligence.

The Work IQ server is a proprietary ``@microsoft/workiq`` npm package
running as an MCP stdio server (``npx -y @microsoft/workiq mcp``).
"""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel, Field

from codecustodian.logging import get_logger
from codecustodian.models import Finding, SeverityLevel

logger = get_logger("integrations.work_iq")


# ── Result models ──────────────────────────────────────────────────────────


class ExpertResult(BaseModel):
    """Result of an expert-lookup query against Work IQ."""

    name: str = ""
    email: str = ""
    relevance_score: float = 0.0
    recent_files: list[str] = Field(default_factory=list)
    teams: list[str] = Field(default_factory=list)
    alternatives: list[dict[str, Any]] = Field(default_factory=list)
    available: bool = True


class SprintContext(BaseModel):
    """Current sprint status from Work IQ."""

    sprint_name: str = ""
    days_remaining: int = 0
    velocity: float = 0.0
    capacity_pct: float = 100.0
    active_incidents: int = 0
    active_work_items: int = 0
    committed_work_at_risk: bool = False
    is_code_freeze: bool = False


class OrgContext(BaseModel):
    """Organizational context from Work IQ (meetings, docs, messages)."""

    related_documents: list[str] = Field(default_factory=list)
    recent_discussions: list[str] = Field(default_factory=list)
    upcoming_meetings: list[str] = Field(default_factory=list)
    related_teams: list[str] = Field(default_factory=list)


# ── Original work-item intelligence ────────────────────────────────────────


class WorkItemIntelligence:
    """Intelligent work-item routing and prioritization."""

    def prioritize_findings(self, findings: list[Finding]) -> list[Finding]:
        """Sort findings by business priority.

        Priority factors:
        1. Severity (critical > high > medium > low > info)
        2. Security findings first
        3. Deprecated APIs with known deadlines
        4. Code smells by complexity impact
        """
        severity_order = {
            SeverityLevel.CRITICAL: 0,
            SeverityLevel.HIGH: 1,
            SeverityLevel.MEDIUM: 2,
            SeverityLevel.LOW: 3,
            SeverityLevel.INFO: 4,
        }

        type_bonus = {
            "security": -1,
            "deprecated_api": 0,
            "code_smell": 1,
            "todo_comment": 2,
            "missing_type_hints": 3,
        }

        def sort_key(f: Finding) -> tuple:
            sev = severity_order.get(f.severity, 5)
            bonus = type_bonus.get(f.type.value, 5)
            return (sev + bonus, f.file, f.line)

        sorted_findings = sorted(findings, key=sort_key)
        logger.info("Prioritized %d findings", len(sorted_findings))
        return sorted_findings

    def estimate_effort(self, finding: Finding) -> str:
        """Estimate effort for fixing a finding.

        Returns: "trivial" | "small" | "medium" | "large"
        """
        if finding.type.value in ("todo_comment", "missing_type_hints"):
            return "trivial"
        elif finding.type.value == "deprecated_api":
            return "small"
        elif finding.type.value == "code_smell" or finding.type.value == "security":
            return "medium"
        return "small"


# ── Work IQ MCP context provider ──────────────────────────────────────────


class WorkIQContextProvider:
    """Query the Microsoft Work IQ MCP server for organizational context.

    Uses ``fastmcp.Client`` over stdio to communicate with the
    ``@microsoft/workiq`` MCP server.  Falls back gracefully when the
    server is unavailable (e.g. no M365 Copilot license or npm missing).

    Args:
        command: The command to spawn the MCP server.
        args: Arguments passed to the command.
        env: Extra environment variables for the subprocess.
        timeout: Seconds to wait for each MCP tool call.
    """

    def __init__(
        self,
        command: str = "npx",
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.command = command
        self.args = args or ["-y", "@microsoft/workiq", "mcp"]
        self.env = env or {}
        self.timeout = timeout
        self._available: bool | None = None

    # ── MCP tool invocation helper ─────────────────────────────────────

    async def _call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Invoke a Work IQ MCP tool via fastmcp.Client (stdio).

        Returns the parsed JSON result or an empty dict on failure.
        """
        try:
            from fastmcp import Client
            from fastmcp.client.transports import StdioTransport

            transport = StdioTransport(
                command=self.command,
                args=self.args,
                env=self.env,
            )

            async with Client(transport) as client:
                result = await asyncio.wait_for(
                    client.call_tool(tool_name, arguments),
                    timeout=self.timeout,
                )
                self._available = True
                # result is a list of TextContent / similar — extract text
                if result and hasattr(result[0], "text"):
                    import json

                    return json.loads(result[0].text)  # type: ignore[union-attr]
                return {"raw": str(result)}

        except TimeoutError:
            logger.warning("Work IQ MCP call '%s' timed out", tool_name)
            self._available = False
            return {}
        except Exception as exc:
            logger.warning("Work IQ MCP call '%s' failed: %s", tool_name, exc)
            self._available = False
            return {}

    # ── Public API ─────────────────────────────────────────────────────

    async def get_expert_for_finding(self, finding: Finding) -> ExpertResult:
        """Find the best expert to review a finding (FR-WORKIQ-100).

        Queries Work IQ ``search_people`` for engineers who recently
        touched the affected file or have domain expertise.
        """
        data = await self._call_tool(
            "search_people",
            {
                "query": f"expert on {finding.file} {finding.type.value}",
                "limit": 1,
            },
        )
        if not data:
            return ExpertResult()

        return ExpertResult(
            name=data.get("name", ""),
            email=data.get("email", ""),
            relevance_score=float(data.get("relevance", 0.0)),
            recent_files=data.get("recent_files", []),
            teams=data.get("teams", []),
            alternatives=data.get("alternatives", []),
            available=data.get("available", True),
        )

    async def get_sprint_context(self) -> SprintContext:
        """Get current sprint status (FR-WORKIQ-101).

        Uses Work IQ ``search_messages`` / ``search_events`` to infer
        sprint state from Teams channels and calendar events.
        """
        data = await self._call_tool(
            "search_events",
            {
                "query": "sprint planning OR sprint review OR code freeze",
                "limit": 5,
            },
        )
        if not data:
            return SprintContext()

        events = data.get("events", [data]) if isinstance(data, dict) else []
        is_freeze = any("freeze" in str(e).lower() for e in events)

        return SprintContext(
            sprint_name=data.get("sprint_name", "current"),
            days_remaining=int(data.get("days_remaining", 0)),
            velocity=float(data.get("velocity", 0.0)),
            capacity_pct=float(data.get("capacity_pct", 100.0)),
            active_incidents=int(data.get("active_incidents", 0)),
            active_work_items=int(data.get("active_work_items", 0)),
            committed_work_at_risk=bool(data.get("committed_work_at_risk", False)),
            is_code_freeze=is_freeze,
        )

    async def should_create_pr_now(self, finding: Finding) -> bool:
        """Decide whether to create a PR now or defer (FR-WORKIQ-101).

        Considers sprint capacity, code-freeze status, and severity.  If
        Work IQ is unreachable, defaults to ``True`` (always create).
        """
        sprint = await self.get_sprint_context()

        # If Work IQ is unreachable, default to creating PRs
        if self._available is False:
            return True

        priority = float(getattr(finding, "priority_score", 0.0))

        days_remaining_raw = getattr(sprint, "days_remaining", None)
        capacity_pct_raw = getattr(sprint, "capacity_pct", 100.0)
        incidents_raw = getattr(sprint, "active_incidents", 0)
        committed_risk_raw = getattr(sprint, "committed_work_at_risk", False)
        is_code_freeze = bool(getattr(sprint, "is_code_freeze", False))

        try:
            days_remaining = int(days_remaining_raw)
        except Exception:
            days_remaining = 999

        try:
            capacity_pct = float(capacity_pct_raw)
        except Exception:
            capacity_pct = 100.0

        try:
            active_incidents = int(incidents_raw)
        except Exception:
            active_incidents = 0

        committed_work_at_risk = bool(committed_risk_raw)

        # Never during code freeze (unless critical/high security)
        if is_code_freeze:
            is_urgent = (
                finding.severity in (SeverityLevel.CRITICAL, SeverityLevel.HIGH)
                and finding.type.value == "security"
            )
            if is_urgent:
                return True
            logger.info(
                "Deferring PR for %s — code freeze active", finding.id
            )
            return False

        if days_remaining < 3 and priority < 150:
            logger.info(
                "Deferring PR for %s — sprint ending soon (%d days)",
                finding.id,
                days_remaining,
            )
            return False

        if active_incidents > 0 and priority < 100:
            logger.info(
                "Deferring PR for %s — %d active incident(s)",
                finding.id,
                active_incidents,
            )
            return False

        if committed_work_at_risk and priority <= 150:
            logger.info(
                "Deferring PR for %s — committed work is at risk",
                finding.id,
            )
            return False

        # Defer if sprint is over-capacity (>90%)
        if capacity_pct > 90.0:
            logger.info(
                "Deferring PR for %s — sprint capacity at %.0f%%",
                finding.id,
                capacity_pct,
            )
            return False

        return True

    async def get_organizational_context(
        self,
        query: str,
    ) -> OrgContext:
        """Fetch organizational context for a topic (FR-WORKIQ-102).

        Queries Work IQ for related documents, recent Teams discussions,
        upcoming meetings, and relevant teams.
        """
        docs_data = await self._call_tool(
            "search_documents",
            {"query": query, "limit": 5},
        )
        msgs_data = await self._call_tool(
            "search_messages",
            {"query": query, "limit": 5},
        )
        meetings_data = await self._call_tool(
            "search_events",
            {"query": f"roadmap OR dependency OR {query}", "limit": 5},
        )

        return OrgContext(
            related_documents=[
                d.get("title", d.get("name", ""))
                for d in docs_data.get("documents", [])
            ]
            if docs_data
            else [],
            recent_discussions=[
                m.get("summary", m.get("text", ""))
                for m in msgs_data.get("messages", [])
            ]
            if msgs_data
            else [],
            upcoming_meetings=[
                e.get("title", e.get("subject", ""))
                for e in meetings_data.get("events", [])
            ]
            if meetings_data
            else [],
            related_teams=docs_data.get("teams", []) if docs_data else [],
        )

    @property
    def is_available(self) -> bool | None:
        """Return the last-known availability of the Work IQ server.

        ``None`` means we haven't tried yet.
        """
        return self._available


def get_work_iq_mcp_config() -> dict[str, Any]:
    """Return the MCPLocalServerConfig dict for Copilot SDK sessions.

    This is passed to ``SessionConfig.mcp_servers`` so the AI planner
    can invoke Work IQ tools during plan generation.

    Example::

        from codecustodian.integrations.work_iq import get_work_iq_mcp_config
        session = SessionConfig(mcp_servers={"work-iq": get_work_iq_mcp_config()})
    """
    return {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@microsoft/workiq", "mcp"],
        "timeout": 30,
    }
