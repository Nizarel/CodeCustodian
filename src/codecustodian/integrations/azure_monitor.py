"""Azure Monitor integration with OpenTelemetry (FR-OBS-001, FR-OBS-002).

Uses ``configure_azure_monitor()`` from the Azure Monitor OpenTelemetry
distro — the SDK best-practice one-liner that bootstraps traces, metrics,
and logs together with auto-instrumentation.

Provides:
- ``ObservabilityProvider`` — full OTel tracer + meter with custom counters
- ``AzureMonitorEmitter`` — backward-compatible wrapper for existing callers
"""

from __future__ import annotations

import os
from typing import Any

from codecustodian.logging import get_logger
from codecustodian.models import PipelineResult

logger = get_logger("integrations.azure_monitor")


class ObservabilityProvider:
    """Centralized observability via Azure Monitor + OpenTelemetry (3.5.2).

    When a ``connection_string`` is supplied, calls
    ``azure.monitor.opentelemetry.configure_azure_monitor()`` which
    sets up ``TracerProvider``, ``MeterProvider``, and ``LoggerProvider``
    in one shot.  When no string is supplied, falls back to no-op
    OTel providers so all instrumentation code still works safely.

    Args:
        connection_string: Application Insights connection string.
            Falls back to the ``APPLICATIONINSIGHTS_CONNECTION_STRING``
            environment variable.
    """

    def __init__(self, connection_string: str | None = None) -> None:
        self.connection_string = connection_string or os.getenv(
            "APPLICATIONINSIGHTS_CONNECTION_STRING"
        )
        self._configured = False

        # Bootstrap Azure Monitor if we have a connection string
        if self.connection_string:
            try:
                from azure.monitor.opentelemetry import configure_azure_monitor

                configure_azure_monitor(
                    connection_string=self.connection_string,
                )
                self._configured = True
                logger.info("Azure Monitor OpenTelemetry configured")
            except ImportError:
                logger.warning(
                    "azure-monitor-opentelemetry not installed — "
                    "metrics will be logged locally only"
                )
            except Exception as exc:
                logger.warning("Failed to configure Azure Monitor: %s", exc)

        # These work whether Azure Monitor is configured or not —
        # without a configured provider they are no-op.
        from opentelemetry import metrics, trace

        self.tracer = trace.get_tracer("codecustodian", "1.0.0")
        self.meter = metrics.get_meter("codecustodian", "1.0.0")

        # ── Custom metrics (3.5.2) ─────────────────────────────────────
        self.findings_counter = self.meter.create_counter(
            "codecustodian.findings.total",
            unit="1",
            description="Total technical debt findings discovered",
        )
        self.pr_success_rate = self.meter.create_histogram(
            "codecustodian.pr.success_rate",
            unit="%",
            description="Success rate of PR creation",
        )
        self.cost_savings = self.meter.create_counter(
            "codecustodian.roi.savings",
            unit="USD",
            description="Estimated cost savings from automated refactoring",
        )
        self.cost_per_pr = self.meter.create_histogram(
            "codecustodian.cost.per_pr",
            unit="USD",
            description="AI cost per pull request",
        )
        self.pipeline_duration = self.meter.create_histogram(
            "codecustodian.pipeline.duration_ms",
            unit="ms",
            description="Pipeline run duration",
        )

    # ── Recording helpers ──────────────────────────────────────────────

    def record_pipeline_result(self, result: PipelineResult) -> None:
        """Emit counters and histograms from a completed pipeline run (3.5.3)."""
        self.findings_counter.add(
            result.total_findings,
            {"pipeline.run_id": result.run_id},
        )
        self.pipeline_duration.record(
            result.duration_seconds * 1000,
            {"pipeline.run_id": result.run_id},
        )
        if result.executions:
            self.pr_success_rate.record(
                result.success_rate,
                {"pipeline.run_id": result.run_id},
            )

        logger.info(
            "Pipeline metrics emitted: findings=%d, prs=%d, success=%.1f%%, duration=%.1fs",
            result.total_findings,
            result.prs_created,
            result.success_rate,
            result.duration_seconds,
        )

    def record_sla_metrics(
        self,
        run_id: str,
        success: bool,
        duration_seconds: float,
        failure_reason: str = "",
    ) -> None:
        """Record SLA-related metrics for reliability tracking (BR-ENT-002, 3.5.4).

        Args:
            run_id: Pipeline run identifier.
            success: Whether the run completed successfully.
            duration_seconds: Total run duration.
            failure_reason: Human-readable failure reason (if any).
        """
        attributes = {
            "pipeline.run_id": run_id,
            "pipeline.success": str(success),
        }
        if failure_reason:
            attributes["pipeline.failure_reason"] = failure_reason

        self.pipeline_duration.record(duration_seconds * 1000, attributes)
        logger.info(
            "SLA metric: run_id=%s success=%s duration=%.1fs reason=%s",
            run_id,
            success,
            duration_seconds,
            failure_reason or "n/a",
        )


class AzureMonitorEmitter:
    """Backward-compatible wrapper delegating to ``ObservabilityProvider``.

    Existing code referencing ``AzureMonitorEmitter`` continues to work.
    New code should use ``ObservabilityProvider`` directly.
    """

    def __init__(
        self,
        connection_string: str | None = None,
        instrumentation_key: str | None = None,
    ) -> None:
        cs = connection_string or os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
        # instrumentation_key is legacy — ignored if connection_string present
        self._provider = ObservabilityProvider(connection_string=cs)

    def emit_pipeline_result(self, result: PipelineResult) -> None:
        """Emit pipeline run metrics."""
        self._provider.record_pipeline_result(result)

    def emit_custom_event(self, name: str, properties: dict[str, Any]) -> None:
        """Emit a custom event (logged; sent to Azure Monitor if configured)."""
        logger.info("Custom event '%s': %s", name, properties)
