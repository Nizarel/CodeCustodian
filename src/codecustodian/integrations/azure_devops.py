"""Azure DevOps integration.

Work item creation, board updates, and pipeline integration
for enterprise customers using Azure DevOps.
"""

from __future__ import annotations

from typing import Any

import httpx

from codecustodian.logging import get_logger
from codecustodian.models import Finding

logger = get_logger("integrations.azure_devops")


class AzureDevOpsClient:
    """Interact with Azure DevOps REST API."""

    def __init__(
        self,
        organization: str,
        project: str,
        pat: str,
    ) -> None:
        self.base_url = (
            f"https://dev.azure.com/{organization}/{project}/_apis"
        )
        self.auth = ("", pat)
        self.headers = {"Content-Type": "application/json-patch+json"}
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                auth=self.auth,
                headers=self.headers,
                timeout=30,
            )
        return self._client

    async def create_work_item(
        self,
        finding: Finding,
        work_item_type: str = "Bug",
    ) -> dict[str, Any]:
        """Create a work item in Azure DevOps for a finding."""
        client = await self._get_client()

        url = f"{self.base_url}/wit/workitems/${work_item_type}?api-version=7.1"

        operations = [
            {
                "op": "add",
                "path": "/fields/System.Title",
                "value": f"[Tech Debt] {finding.description[:100]}",
            },
            {
                "op": "add",
                "path": "/fields/System.Description",
                "value": (
                    f"<b>File:</b> {finding.file}<br>"
                    f"<b>Line:</b> {finding.line}<br>"
                    f"<b>Type:</b> {finding.type.value}<br>"
                    f"<b>Severity:</b> {finding.severity.value}<br><br>"
                    f"{finding.description}<br><br>"
                    f"<b>Suggestion:</b> {finding.suggestion}"
                ),
            },
            {
                "op": "add",
                "path": "/fields/Microsoft.VSTS.Common.Priority",
                "value": self._severity_to_priority(finding.severity.value),
            },
            {
                "op": "add",
                "path": "/fields/System.Tags",
                "value": "tech-debt; automated; codecustodian",
            },
        ]

        response = await client.patch(url, json=operations)
        response.raise_for_status()

        data = response.json()
        logger.info("Created work item %d", data["id"])
        return data

    @staticmethod
    def _severity_to_priority(severity: str) -> int:
        """Map severity to Azure DevOps priority (1=Critical, 4=Low)."""
        mapping = {
            "critical": 1,
            "high": 1,
            "medium": 2,
            "low": 3,
            "info": 4,
        }
        return mapping.get(severity, 3)

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
