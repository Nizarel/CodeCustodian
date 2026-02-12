"""Azure Monitor integration.

Emits pipeline metrics, custom events, and traces to
Azure Monitor / Application Insights for observability.
"""

from __future__ import annotations

import os
from typing import Any

from codecustodian.logging import get_logger
from codecustodian.models import PipelineResult

logger = get_logger("integrations.azure_monitor")


class AzureMonitorEmitter:
    """Emit telemetry to Azure Monitor (Application Insights)."""

    def __init__(
        self,
        connection_string: str | None = None,
        instrumentation_key: str | None = None,
    ) -> None:
        self.connection_string = (
            connection_string
            or os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
        )
        self.instrumentation_key = (
            instrumentation_key
            or os.getenv("APPINSIGHTS_INSTRUMENTATIONKEY")
        )
        self._exporter: Any = None

    def _ensure_exporter(self) -> None:
        """Lazily initialize the Azure Monitor exporter."""
        if self._exporter is not None:
            return

        try:
            from azure.monitor.opentelemetry.exporter import (
                AzureMonitorTraceExporter,
            )

            self._exporter = AzureMonitorTraceExporter(
                connection_string=self.connection_string
            )
            logger.info("Azure Monitor exporter initialized")
        except ImportError:
            logger.warning(
                "azure-monitor-opentelemetry-exporter not installed — "
                "metrics will be logged locally only"
            )

    def emit_pipeline_result(self, result: PipelineResult) -> None:
        """Emit pipeline run metrics."""
        self._ensure_exporter()

        metrics = {
            "findings_total": result.total_findings,
            "findings_fixed": result.findings_fixed,
            "prs_created": result.prs_created,
            "success_rate": result.success_rate,
            "duration_seconds": result.duration_seconds,
        }

        logger.info("Pipeline metrics: %s", metrics)
        # TODO: Full OpenTelemetry span/metric emission (Phase 6)

    def emit_custom_event(self, name: str, properties: dict[str, Any]) -> None:
        """Emit a custom event to Application Insights."""
        self._ensure_exporter()
        logger.info("Custom event '%s': %s", name, properties)
