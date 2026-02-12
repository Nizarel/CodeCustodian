"""Tests for observability / Azure Monitor integration."""

from __future__ import annotations

from codecustodian.integrations.azure_monitor import (
    AzureMonitorEmitter,
    ObservabilityProvider,
)
from codecustodian.models import (
    ExecutionResult,
    Finding,
    FindingType,
    PipelineResult,
    PullRequestInfo,
    SeverityLevel,
)


class TestObservabilityProvider:
    def test_create_without_connection_string(self):
        """Provider works without Azure Monitor (no-op OTel)."""
        provider = ObservabilityProvider()
        assert provider._configured is False
        assert provider.tracer is not None
        assert provider.meter is not None

    def test_record_pipeline_result(self):
        """Metrics can be recorded without Azure Monitor configured."""
        provider = ObservabilityProvider()
        result = PipelineResult(
            findings=[
                Finding(
                    type=FindingType.CODE_SMELL,
                    severity=SeverityLevel.LOW,
                    file="a.py",
                    line=1,
                    description="test",
                )
            ],
            executions=[ExecutionResult(plan_id="p1", success=True)],
            pull_requests=[
                PullRequestInfo(number=1, url="https://example.com/pr/1", title="Fix"),
            ],
            total_duration_seconds=5.0,
        )
        # Should not raise even without Azure Monitor
        provider.record_pipeline_result(result)

    def test_record_sla_metrics(self):
        provider = ObservabilityProvider()
        provider.record_sla_metrics(
            run_id="run-abc",
            success=True,
            duration_seconds=3.5,
        )

    def test_record_sla_metrics_with_failure(self):
        provider = ObservabilityProvider()
        provider.record_sla_metrics(
            run_id="run-xyz",
            success=False,
            duration_seconds=1.0,
            failure_reason="Scanner timeout",
        )


class TestAzureMonitorEmitter:
    def test_backward_compatible_creation(self):
        emitter = AzureMonitorEmitter()
        assert emitter._provider is not None

    def test_emit_pipeline_result(self):
        emitter = AzureMonitorEmitter()
        result = PipelineResult(total_duration_seconds=2.0)
        emitter.emit_pipeline_result(result)

    def test_emit_custom_event(self):
        emitter = AzureMonitorEmitter()
        emitter.emit_custom_event("test_event", {"key": "value"})
