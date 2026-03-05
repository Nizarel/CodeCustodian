"""Core data models for CodeCustodian pipeline.

All models use Pydantic v2 for validation and serialization.
Leverages ``@computed_field``, ``@field_validator``, ``@model_validator``
and ``ConfigDict`` for idiomatic Pydantic v2 usage.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

# ── Enums ──────────────────────────────────────────────────────────────────

_EFFORT_LEVELS = {"low", "medium", "high"}
_CRITICALITY_LEVELS = {"normal", "high", "critical"}


class SeverityLevel(StrEnum):
    """Severity classification for findings."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class FindingType(StrEnum):
    """Categories of technical debt findings."""

    DEPRECATED_API = "deprecated_api"
    TODO_COMMENT = "todo_comment"
    CODE_SMELL = "code_smell"
    SECURITY = "security"
    TYPE_COVERAGE = "type_coverage"
    DEPENDENCY_UPGRADE = "dependency_upgrade"


class ChangeType(StrEnum):
    """Types of code changes."""

    REPLACE = "replace"
    INSERT = "insert"
    DELETE = "delete"
    RENAME = "rename"


class PipelineStage(StrEnum):
    """Stages in the CodeCustodian pipeline."""

    ONBOARD = "onboard"
    SCAN = "scan"
    DEDUP = "dedup"
    PRIORITIZE = "prioritize"
    PLAN = "plan"
    EXECUTE = "execute"
    VERIFY = "verify"
    PR = "pr"
    FEEDBACK = "feedback"


class RiskLevel(StrEnum):
    """Risk assessment for refactoring plans."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ── Core Models ────────────────────────────────────────────────────────────


class Finding(BaseModel):
    """A detected technical debt issue.

    ``dedup_key`` is a Pydantic v2 ``@computed_field`` — automatically
    derived from type + file + line + description so it appears in
    ``model_dump()`` and JSON schema without manual assignment.
    """

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    type: FindingType
    severity: SeverityLevel
    file: str
    line: int
    end_line: int | None = None
    column: int = 0
    description: str
    suggestion: str = ""
    priority_score: float = 0.0
    business_impact_score: float = Field(
        default=0.0, description="Business impact score (FR-PRIORITY-100)"
    )
    reviewer_effort_estimate: str = Field(
        default="medium", description="Reviewer effort: low | medium | high (BR-PR-002)"
    )
    metadata: dict[str, Any] = Field(default_factory=dict)
    scanner_name: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("reviewer_effort_estimate")
    @classmethod
    def _validate_effort(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in _EFFORT_LEVELS:
            raise ValueError(f"reviewer_effort_estimate must be one of {_EFFORT_LEVELS}")
        return v

    @computed_field  # type: ignore[prop-decorator]
    @property
    def dedup_key(self) -> str:
        """Deterministic hash for cross-run de-duplication (BR-SCN-001)."""
        raw = f"{self.type.value}:{self.file}:{self.line}:{self.description}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    @property
    def file_path(self) -> Path:
        return Path(self.file)


class CodeContext(BaseModel):
    """Surrounding code context for AI planning."""

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    file_path: str
    source_code: str
    start_line: int
    end_line: int
    imports: list[str] = Field(default_factory=list)
    type_hints: dict[str, str] = Field(default_factory=dict)
    related_tests: list[str] = Field(default_factory=list)
    call_sites: list[str] = Field(default_factory=list)
    has_tests: bool = False
    language: str = "python"
    function_signature: str = ""
    coverage_percentage: float = Field(default=0.0, ge=0.0, le=100.0)
    last_modified: datetime | None = None
    usage_frequency: int = Field(
        default=0, ge=0, description="Telemetry-based call count (FR-PRIORITY-100)"
    )
    criticality_level: str = Field(
        default="normal", description="Critical path detection: normal | high | critical"
    )

    @field_validator("criticality_level")
    @classmethod
    def _validate_criticality(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in _CRITICALITY_LEVELS:
            raise ValueError(f"criticality_level must be one of {_CRITICALITY_LEVELS}")
        return v


class FileChange(BaseModel):
    """A single file modification."""

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    file_path: str
    change_type: ChangeType
    old_content: str = ""
    new_content: str = ""
    start_line: int | None = None
    end_line: int | None = None
    description: str = ""
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Extra metadata, e.g. git_sha for concurrent change detection",
    )


class AlternativeSolution(BaseModel):
    """An alternative refactoring approach (FR-PLAN-102).

    Presented alongside the primary plan so reviewers can choose
    the best path forward.
    """

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    name: str
    description: str
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    changes: list[FileChange] = Field(default_factory=list)
    confidence_score: int = Field(ge=1, le=10, default=5)
    recommended: bool = False


class RefactoringPlan(BaseModel):
    """AI planner output for a refactoring.

    Includes a ``@model_validator`` that auto-flags low-confidence plans
    for manual verification.
    """

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    finding_id: str
    summary: str
    description: str = ""
    changes: list[FileChange] = Field(default_factory=list)
    confidence_score: int = Field(ge=1, le=10, default=5)
    risk_level: RiskLevel = RiskLevel.LOW
    ai_reasoning: str = ""
    alternatives: list[AlternativeSolution] = Field(default_factory=list)
    confidence_factors: list[str] = Field(default_factory=list)
    reviewer_effort: str = Field(
        default="medium", description="Reviewer effort: low | medium | high (BR-PR-002)"
    )
    estimated_tokens: int = 0
    model_used: str = ""
    changes_signature: bool = False
    requires_manual_verification: bool = False
    files_to_change: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("reviewer_effort")
    @classmethod
    def _validate_effort(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in _EFFORT_LEVELS:
            raise ValueError(f"reviewer_effort must be one of {_EFFORT_LEVELS}")
        return v

    @model_validator(mode="after")
    def _flag_low_confidence(self) -> Self:
        """Auto-flag plans with confidence < 7 for manual review."""
        if self.confidence_score < 7 and not self.requires_manual_verification:
            self.requires_manual_verification = True
        return self


class ProposalResult(BaseModel):
    """Advisory-only output when confidence is too low for auto-fix (BR-PR-003).

    Instead of creating a PR, CodeCustodian opens an advisory issue
    with recommended manual steps.
    """

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    finding: Finding
    recommended_steps: list[str] = Field(default_factory=list)
    estimated_effort: str = "medium"
    risks: list[str] = Field(default_factory=list)
    is_proposal_only: bool = True

    @field_validator("estimated_effort")
    @classmethod
    def _validate_effort(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in _EFFORT_LEVELS:
            raise ValueError(f"estimated_effort must be one of {_EFFORT_LEVELS}")
        return v


class SafetyCheckResult(BaseModel):
    """Result of a single pre-execution safety check (FR-EXEC-101)."""

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    name: str = Field(description="Check name, e.g. 'syntax', 'imports'")
    passed: bool = True
    message: str = ""
    severity: str = Field(default="error", description="error | warning | info")

    @property
    def failed(self) -> bool:
        return not self.passed


class SafetyResult(BaseModel):
    """Aggregate result of all 5 safety checks (FR-EXEC-101)."""

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    passed: bool = True
    checks: list[SafetyCheckResult] = Field(default_factory=list)
    action: str = Field(
        default="proceed",
        description="proceed | abort_or_propose",
    )

    @property
    def failures(self) -> list[SafetyCheckResult]:
        return [c for c in self.checks if c.failed]


class LintViolation(BaseModel):
    """A single lint violation (FR-VERIFY-101)."""

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    file: str
    line: int = 0
    code: str = ""
    message: str = ""
    tool: str = ""
    severity: str = Field(default="warning", description="error | warning | info")


class SecurityIssue(BaseModel):
    """A single security issue found during verification (FR-VERIFY-102)."""

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    file: str = ""
    line: int = 0
    severity: str = "LOW"
    confidence: str = "LOW"
    description: str = ""
    test_id: str = ""
    tool: str = ""
    cwe: str = ""


class TransactionLogEntry(BaseModel):
    """Entry in the atomic transaction log for forensic analysis (FR-EXEC-100)."""

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    action: str = Field(description="backup | apply | rollback | commit")
    file_path: str = ""
    backup_path: str = ""
    success: bool = True
    error: str = ""


class ExecutionResult(BaseModel):
    """Result of executing a refactoring plan."""

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    plan_id: str
    success: bool
    changes_applied: list[FileChange] = Field(default_factory=list)
    backup_paths: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    branch_name: str = ""
    commit_sha: str = ""
    duration_seconds: float = 0.0
    transaction_log: list[TransactionLogEntry] = Field(default_factory=list)
    safety_result: SafetyResult | None = None


class VerificationResult(BaseModel):
    """Result of verifying applied changes."""

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    passed: bool
    tests_run: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    tests_skipped: int = 0
    coverage_overall: float = 0.0
    coverage_delta: float = 0.0
    lint_passed: bool = True
    lint_violations: list[LintViolation] = Field(default_factory=list)
    security_passed: bool = True
    security_issues: list[SecurityIssue] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0
    pre_existing_failures: int = Field(
        default=0, description="Count of pre-existing test failures (FR-VERIFY-100)"
    )


class PullRequestInfo(BaseModel):
    """Information about a created pull request."""

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    number: int
    url: str
    title: str
    body: str = ""
    labels: list[str] = Field(default_factory=list)
    reviewers: list[str] = Field(default_factory=list)
    branch: str = ""
    base_branch: str = "main"
    draft: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PipelineResult(BaseModel):
    """Full pipeline run output."""

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    run_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    findings: list[Finding] = Field(default_factory=list)
    plans: list[RefactoringPlan] = Field(default_factory=list)
    proposals: list[ProposalResult] = Field(default_factory=list)
    executions: list[ExecutionResult] = Field(default_factory=list)
    verifications: list[VerificationResult] = Field(default_factory=list)
    pull_requests: list[PullRequestInfo] = Field(default_factory=list)
    total_duration_seconds: float = 0.0
    errors: list[str] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    cost_savings_estimate: dict[str, float] = Field(
        default_factory=dict,
        description="Estimated cost savings: manual_hours, automated_hours, hours_saved, savings_usd",
    )

    @property
    def success_rate(self) -> float:
        if not self.executions:
            return 0.0
        successful = sum(1 for e in self.executions if e.success)
        return successful / len(self.executions) * 100

    @property
    def total_findings(self) -> int:
        return len(self.findings)

    @property
    def findings_fixed(self) -> int:
        return sum(1 for e in self.executions if e.success)

    @property
    def duration_seconds(self) -> float:
        return self.total_duration_seconds

    @property
    def prs_created(self) -> int:
        return len(self.pull_requests)


# ── v0.14.0 — Production Intelligence Models ──────────────────────────────


class DebtSnapshot(BaseModel):
    """Point-in-time snapshot of technical debt state for trend analysis."""

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    date: datetime = Field(default_factory=lambda: datetime.now(UTC))
    repo_path: str = "."
    total_findings: int = 0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_severity: dict[str, int] = Field(default_factory=dict)
    churn_rate: float = Field(default=0.0, ge=0.0, description="File churn rate (changes/week)")
    complexity_avg: float = Field(default=0.0, ge=0.0, description="Average cyclomatic complexity")
    coverage_pct: float = Field(default=0.0, ge=0.0, le=100.0, description="Test coverage %")


class DebtForecast(BaseModel):
    """Predicted future state of technical debt from trend analysis."""

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    forecast_date: datetime = Field(default_factory=lambda: datetime.now(UTC))
    predicted_findings: int = Field(default=0, ge=0)
    predicted_by_severity: dict[str, int] = Field(default_factory=dict)
    confidence_interval: tuple[int, int] = Field(
        default=(0, 0), description="(lower_bound, upper_bound) for predicted findings"
    )
    trend: str = Field(
        default="stable", description="improving | stable | worsening"
    )
    hotspot_directories: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    snapshots_used: int = Field(default=0, ge=0, description="Number of snapshots used")
    slope: float = Field(default=0.0, description="Linear regression slope (findings/day)")

    @field_validator("trend")
    @classmethod
    def _validate_trend(cls, v: str) -> str:
        allowed = {"improving", "stable", "worsening"}
        if v not in allowed:
            raise ValueError(f"trend must be one of {allowed}")
        return v


class ReachabilityResult(BaseModel):
    """Reachability analysis result for a single finding."""

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    finding_id: str
    entry_points: list[str] = Field(default_factory=list)
    call_chains: list[list[str]] = Field(
        default_factory=list, description="Paths from entry points to the finding's module"
    )
    is_reachable: bool = False
    reachability_tag: str = Field(
        default="internal_only", description="reachable | internal_only"
    )
    framework: str = Field(
        default="unknown", description="Detected framework: flask | fastapi | django | lambda | unknown"
    )

    @field_validator("reachability_tag")
    @classmethod
    def _validate_tag(cls, v: str) -> str:
        allowed = {"reachable", "internal_only"}
        if v not in allowed:
            raise ValueError(f"reachability_tag must be one of {allowed}")
        return v


# ── v0.15.0: AI Test Synthesis ─────────────────────────────────────────────


class TestSynthesisResult(BaseModel):
    """Result of AI-generated test synthesis for a finding."""

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    finding_id: str
    test_code: str = ""
    test_file_path: str = ""
    test_count: int = 0
    passed_original: bool = False
    passed_refactored: bool | None = Field(
        default=None, description="None until refactored code is verified"
    )
    validation_errors: list[str] = Field(default_factory=list)
    discarded: bool = False
    discard_reason: str = ""


# ── v0.15.0: Agentic Migrations ───────────────────────────────────────────


class MigrationStage(BaseModel):
    """A single stage within a multi-stage framework migration."""

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    name: str
    description: str = ""
    order: int = 0
    depends_on: list[str] = Field(default_factory=list)
    file_changes: list[FileChange] = Field(default_factory=list)
    files_affected: list[str] = Field(default_factory=list)
    patterns: list[dict[str, str]] = Field(
        default_factory=list, description="Find/replace pattern pairs"
    )
    status: str = Field(default="pending", description="pending | running | passed | failed | rolled_back")

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v: str) -> str:
        allowed = {"pending", "running", "passed", "failed", "rolled_back"}
        if v not in allowed:
            raise ValueError(f"status must be one of {allowed}")
        return v


class MigrationPlan(BaseModel):
    """Multi-stage framework migration plan."""

    model_config = ConfigDict(extra="ignore", validate_assignment=True)

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    framework: str
    from_version: str
    to_version: str
    migration_guide_url: str = ""
    stages: list[MigrationStage] = Field(default_factory=list)
    breaking_changes: list[str] = Field(default_factory=list)
    estimated_complexity: str = Field(
        default="simple", description="simple | complex | expert-only"
    )
    pr_strategy: str = Field(default="staged", description="single | staged")
    total_files_affected: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("estimated_complexity")
    @classmethod
    def _validate_complexity(cls, v: str) -> str:
        allowed = {"simple", "complex", "expert-only"}
        if v not in allowed:
            raise ValueError(f"estimated_complexity must be one of {allowed}")
        return v

    @field_validator("pr_strategy")
    @classmethod
    def _validate_pr_strategy(cls, v: str) -> str:
        allowed = {"single", "staged"}
        if v not in allowed:
            raise ValueError(f"pr_strategy must be one of {allowed}")
        return v


class MigrationPlaybook(BaseModel):
    """Reusable migration playbook with find/replace patterns."""

    model_config = ConfigDict(extra="ignore")

    name: str
    framework: str
    from_version: str = ""
    to_version: str = ""
    guide_url: str = ""
    patterns: list[dict[str, str]] = Field(
        default_factory=list,
        description="List of {pattern, replacement} dicts",
    )


# ── v0.15.0: ChatOps ──────────────────────────────────────────────────────


class ChatOpsNotification(BaseModel):
    """A notification to be sent via ChatOps (Teams)."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    message_type: str = Field(
        description="pr_created | approval_needed | scan_complete | verification_failed"
    )
    channel: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    adaptive_card_json: dict[str, Any] = Field(default_factory=dict)
    delivered: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("message_type")
    @classmethod
    def _validate_message_type(cls, v: str) -> str:
        allowed = {"pr_created", "approval_needed", "scan_complete", "verification_failed"}
        if v not in allowed:
            raise ValueError(f"message_type must be one of {allowed}")
        return v
