---
name: chatops-delivery
description: Sprint-aware Teams notification composition and delivery
---

# ChatOps Delivery Skill

## Purpose

Compose and deliver Adaptive Card notifications to Microsoft Teams
so engineering teams receive actionable scan results, PR links,
approval requests, and verification outcomes in their existing workflow.

## Adaptive Card Types

| Event                  | Card Template          | Key Fields                          |
|-----------------------|------------------------|-------------------------------------|
| `scan_complete`        | Scan Summary           | total, critical, high, repo         |
| `pr_created`           | PR Notification        | url, title, finding_count, confidence |
| `approval_needed`      | Approval Request       | finding_id, summary, risk, actions  |
| `verification_failed`  | Verification Alert     | finding_id, error list              |

## Sprint-Aware Delivery

When Work IQ is enabled, respect crunch-time windows:

- **Crunch time:** batch low-priority notifications into a single daily digest.
- **Normal time:** deliver notifications immediately.
- **Approval requests:** always deliver immediately regardless of crunch time.

## Message Composition Tips

- Keep the title short and emoji-prefixed for visual scanning.
- FactSet for structured key/value data (max 6 facts).
- TextBlock for free-form details or error lists.
- ActionSet with OpenUrl for approve/reject buttons (link to callback URL).
- Limit Adaptive Card body to 5 elements for readability.

## Webhook Configuration

Configure `chatops.teams_webhook_url` as the default. Override per
message type via `chatops.notification_channels` dict:

```yaml
chatops:
  enabled: true
  connector: teams
  teams_webhook_url: "https://..."
  notification_channels:
    approval_needed: "https://...approval-channel"
```
