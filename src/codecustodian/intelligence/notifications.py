"""Notification engine — GitHub + Teams webhook (BR-NOT-001).

Routes pipeline events (PR created, pipeline failed, budget alerts) to
configured notification channels with severity filtering.

Supported channels:
- **GitHub PR comments** — via PyGithub (already a dependency)
- **Microsoft Teams** — Incoming Webhook with Adaptive Cards via httpx

Usage::

    engine = NotificationEngine(
        github_token="ghp_...",
        teams_webhook_url="https://outlook.office.com/webhook/...",
    )
    await engine.notify(
        event="pr_created",
        severity="high",
        title="PR #42 created",
        body="Fixed deprecated API in auth module",
        metadata={"pr_number": 42, "repo": "owner/repo"},
    )
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from codecustodian.logging import get_logger

logger = get_logger("intelligence.notifications")


# ── Models ─────────────────────────────────────────────────────────────────

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


class NotificationEvent(BaseModel):
    """A structured notification event."""

    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    event: str                     # pr_created | pipeline_failed | budget_alert | ...
    severity: str = "info"         # critical | high | medium | low | info
    title: str = ""
    body: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    channels_sent: list[str] = Field(default_factory=list)


class NotificationResult(BaseModel):
    """Result of sending a notification batch."""

    event: str
    channels_attempted: list[str] = Field(default_factory=list)
    channels_succeeded: list[str] = Field(default_factory=list)
    channels_failed: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


# ── Engine ─────────────────────────────────────────────────────────────────


class NotificationEngine:
    """Multi-channel notification engine (BR-NOT-001).

    Args:
        github_token: GitHub PAT for PR comments.
        teams_webhook_url: MS Teams Incoming Webhook URL.
        severity_threshold: Minimum severity to send (default ``"medium"``).
        enabled_events: List of event types that trigger notifications.
            Empty list = all events.
    """

    def __init__(
        self,
        github_token: str = "",
        teams_webhook_url: str = "",
        severity_threshold: str = "medium",
        enabled_events: list[str] | None = None,
    ) -> None:
        self.github_token = github_token
        self.teams_webhook_url = teams_webhook_url
        self.severity_threshold = severity_threshold
        self.enabled_events = enabled_events or []
        self._history: list[NotificationEvent] = []

    # ── Public API ─────────────────────────────────────────────────────

    async def notify(
        self,
        event: str,
        severity: str = "info",
        title: str = "",
        body: str = "",
        *,
        metadata: dict[str, Any] | None = None,
    ) -> NotificationResult:
        """Send a notification to all configured channels.

        Filters by severity threshold and enabled events before sending.
        """
        result = NotificationResult(event=event)

        # Severity filter
        if not self._passes_severity(severity):
            logger.debug(
                "Notification '%s' (%s) below threshold '%s' — skipped",
                event,
                severity,
                self.severity_threshold,
            )
            return result

        # Event filter
        if self.enabled_events and event not in self.enabled_events:
            logger.debug("Event '%s' not in enabled_events — skipped", event)
            return result

        evt = NotificationEvent(
            event=event,
            severity=severity,
            title=title,
            body=body,
            metadata=metadata or {},
        )

        # GitHub PR comment
        if self.github_token and metadata and metadata.get("pr_number"):
            result.channels_attempted.append("github")
            try:
                await self._send_github_comment(evt)
                result.channels_succeeded.append("github")
                evt.channels_sent.append("github")
            except Exception as exc:
                result.channels_failed.append("github")
                result.errors.append(f"github: {exc}")
                logger.warning("GitHub notification failed: %s", exc)

        # Teams webhook
        if self.teams_webhook_url:
            result.channels_attempted.append("teams")
            try:
                await self._send_teams_card(evt)
                result.channels_succeeded.append("teams")
                evt.channels_sent.append("teams")
            except Exception as exc:
                result.channels_failed.append("teams")
                result.errors.append(f"teams: {exc}")
                logger.warning("Teams notification failed: %s", exc)

        self._history.append(evt)
        logger.info(
            "Notification '%s' sent to %d/%d channels",
            event,
            len(result.channels_succeeded),
            len(result.channels_attempted),
        )
        return result

    def get_history(self, limit: int = 50) -> list[NotificationEvent]:
        """Return recent notification history."""
        return self._history[-limit:]

    # ── GitHub channel ─────────────────────────────────────────────────

    async def _send_github_comment(self, evt: NotificationEvent) -> None:
        """Post a comment on a GitHub PR."""
        from github import Github

        repo_name = evt.metadata.get("repo", "")
        pr_number = evt.metadata.get("pr_number")
        if not repo_name or not pr_number:
            raise ValueError("Missing 'repo' or 'pr_number' in metadata")

        gh = Github(self.github_token)
        repo = gh.get_repo(repo_name)
        pr = repo.get_pull(int(pr_number))

        comment_body = (
            f"### {self._severity_emoji(evt.severity)} {evt.title}\n\n"
            f"{evt.body}\n\n"
            f"---\n"
            f"*Event:* `{evt.event}` | *Severity:* `{evt.severity}` | "
            f"*Time:* {evt.timestamp}"
        )
        pr.create_issue_comment(comment_body)

    # ── Teams channel ──────────────────────────────────────────────────

    async def _send_teams_card(self, evt: NotificationEvent) -> None:
        """Send an Adaptive Card to Teams via Incoming Webhook."""
        import httpx

        card = self._build_adaptive_card(evt)
        payload = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "contentUrl": None,
                    "content": card,
                }
            ],
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(self.teams_webhook_url, json=payload)
            resp.raise_for_status()

    def _build_adaptive_card(self, evt: NotificationEvent) -> dict[str, Any]:
        """Build an Adaptive Card JSON for Teams."""
        color = {
            "critical": "attention",
            "high": "warning",
            "medium": "accent",
            "low": "good",
            "info": "default",
        }.get(evt.severity, "default")

        facts = [
            {"title": "Event", "value": evt.event},
            {"title": "Severity", "value": evt.severity},
            {"title": "Time", "value": evt.timestamp},
        ]
        for k, v in evt.metadata.items():
            facts.append({"title": k, "value": str(v)})

        return {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [
                {
                    "type": "TextBlock",
                    "size": "Large",
                    "weight": "Bolder",
                    "text": f"{self._severity_emoji(evt.severity)} {evt.title}",
                    "color": color,
                },
                {
                    "type": "TextBlock",
                    "text": evt.body,
                    "wrap": True,
                },
                {
                    "type": "FactSet",
                    "facts": facts,
                },
            ],
        }

    # ── Helpers ────────────────────────────────────────────────────────

    def _passes_severity(self, severity: str) -> bool:
        """Check if ``severity`` meets the configured threshold."""
        s_order = SEVERITY_ORDER.get(severity, 5)
        t_order = SEVERITY_ORDER.get(self.severity_threshold, 5)
        return s_order <= t_order

    @staticmethod
    def _severity_emoji(severity: str) -> str:
        return {
            "critical": "\U0001f534",  # 🔴
            "high": "\U0001f7e0",       # 🟠
            "medium": "\U0001f7e1",     # 🟡
            "low": "\U0001f7e2",        # 🟢
            "info": "\U0001f535",       # 🔵
        }.get(severity, "\u2139\ufe0f")
