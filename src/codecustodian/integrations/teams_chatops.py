"""Teams ChatOps connector.

Sends Adaptive Card notifications to Microsoft Teams via incoming
webhooks.  Used by the pipeline to broadcast scan results, approval
requests, PR notifications, and verification outcomes.

No ``botbuilder`` runtime is required for webhook-only delivery; the
dependency is optional and only used if full bot registration is
configured.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import httpx

from codecustodian.logging import get_logger
from codecustodian.models import ChatOpsNotification, MigrationPlan

if TYPE_CHECKING:
    from codecustodian.config.schema import ChatOpsConfig

logger = get_logger("integrations.teams_chatops")


# ── Adaptive Card templates ──────────────────────────────────────────

def _base_card(title: str, body_blocks: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a minimal Adaptive Card v1.4 wrapper."""
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {
                "type": "TextBlock",
                "text": title,
                "weight": "Bolder",
                "size": "Medium",
                "wrap": True,
            },
            *body_blocks,
        ],
    }


def build_scan_complete_card(
    total_findings: int,
    critical: int,
    high: int,
    repo: str = "",
) -> dict[str, Any]:
    """Adaptive Card for ``scan_complete`` events."""
    facts = [
        {"title": "Total Findings", "value": str(total_findings)},
        {"title": "Critical", "value": str(critical)},
        {"title": "High", "value": str(high)},
    ]
    if repo:
        facts.insert(0, {"title": "Repository", "value": repo})

    return _base_card(
        "\U0001f50d Scan Complete",
        [{"type": "FactSet", "facts": facts}],
    )


def build_pr_created_card(
    pr_url: str,
    pr_title: str,
    finding_count: int,
    confidence: int,
) -> dict[str, Any]:
    """Adaptive Card for ``pr_created`` events."""
    return _base_card(
        "\U0001f680 Pull Request Created",
        [
            {"type": "FactSet", "facts": [
                {"title": "PR", "value": f"[{pr_title}]({pr_url})"},
                {"title": "Findings Fixed", "value": str(finding_count)},
                {"title": "Confidence", "value": f"{confidence}/10"},
            ]},
        ],
    )


def build_approval_needed_card(
    finding_id: str,
    summary: str,
    risk: str,
    callback_url: str = "",
) -> dict[str, Any]:
    """Adaptive Card for ``approval_needed`` events."""
    body: list[dict[str, Any]] = [
        {"type": "FactSet", "facts": [
            {"title": "Finding", "value": finding_id},
            {"title": "Summary", "value": summary},
            {"title": "Risk", "value": risk},
        ]},
    ]
    if callback_url:
        body.append({
            "type": "ActionSet",
            "actions": [
                {
                    "type": "Action.OpenUrl",
                    "title": "\u2705 Approve",
                    "url": f"{callback_url}?action=approve&finding={finding_id}",
                },
                {
                    "type": "Action.OpenUrl",
                    "title": "\u274c Reject",
                    "url": f"{callback_url}?action=reject&finding={finding_id}",
                },
            ],
        })
    return _base_card("\u26a0\ufe0f Approval Needed", body)


def build_verification_failed_card(
    finding_id: str,
    errors: list[str],
) -> dict[str, Any]:
    """Adaptive Card for ``verification_failed`` events."""
    error_text = "\n".join(f"- {e}" for e in errors[:5])
    return _base_card(
        "\u274c Verification Failed",
        [
            {"type": "FactSet", "facts": [
                {"title": "Finding", "value": finding_id},
            ]},
            {"type": "TextBlock", "text": error_text, "wrap": True, "isSubtle": True},
        ],
    )


def build_migration_card(plan: MigrationPlan) -> dict[str, Any]:
    """Adaptive Card for migration plan overview."""
    stage_lines = "\n".join(
        f"- **{s.name}** ({s.status}): {s.description}" for s in plan.stages
    )
    return _base_card(
        f"\U0001f504 Migration: {plan.framework} {plan.from_version} \u2192 {plan.to_version}",
        [
            {"type": "FactSet", "facts": [
                {"title": "Stages", "value": str(len(plan.stages))},
                {"title": "Complexity", "value": plan.estimated_complexity},
                {"title": "PR Strategy", "value": plan.pr_strategy},
                {"title": "Files Affected", "value": str(plan.total_files_affected)},
            ]},
            {"type": "TextBlock", "text": stage_lines, "wrap": True},
        ],
    )


# ── Notification card dispatcher ─────────────────────────────────────

CARD_BUILDERS: dict[str, Any] = {
    "scan_complete": build_scan_complete_card,
    "pr_created": build_pr_created_card,
    "approval_needed": build_approval_needed_card,
    "verification_failed": build_verification_failed_card,
}


def build_card_for_notification(notification: ChatOpsNotification) -> dict[str, Any]:
    """Build the appropriate Adaptive Card from a ChatOpsNotification."""
    builder = CARD_BUILDERS.get(notification.message_type)
    if builder:
        return builder(**notification.payload)
    return _base_card(
        f"CodeCustodian — {notification.message_type}",
        [{"type": "TextBlock", "text": json.dumps(notification.payload, indent=2), "wrap": True}],
    )


# ── Teams connector ──────────────────────────────────────────────────

class TeamsConnector:
    """Send Adaptive Card notifications to Microsoft Teams via webhook."""

    def __init__(self, config: ChatOpsConfig) -> None:
        self.config = config
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=15.0)
        return self._client

    async def send(self, notification: ChatOpsNotification) -> bool:
        """Deliver a notification to Teams. Returns True on success."""
        if not self.config.enabled:
            logger.debug("ChatOps disabled — skipping notification %s", notification.id)
            return False

        webhook_url = (
            self.config.notification_channels.get(notification.message_type)
            or self.config.teams_webhook_url
        )
        if not webhook_url:
            logger.warning("No webhook URL for message_type=%s", notification.message_type)
            return False

        card = notification.adaptive_card_json or build_card_for_notification(notification)

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

        try:
            client = await self._get_client()
            resp = await client.post(webhook_url, json=payload)
            resp.raise_for_status()
            notification.delivered = True
            logger.info(
                "Sent %s notification %s to Teams", notification.message_type, notification.id
            )
            return True
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Teams webhook returned %s for notification %s",
                exc.response.status_code,
                notification.id,
            )
            return False
        except Exception:
            logger.exception("Failed to send Teams notification %s", notification.id)
            return False

    async def send_batch(
        self, notifications: list[ChatOpsNotification]
    ) -> list[bool]:
        """Deliver multiple notifications sequentially."""
        return [await self.send(n) for n in notifications]

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
