"""Core data models for CodeCustodian pipeline.

All models use Pydantic v2 for validation and serialization.
Leverages ``@computed_field``, ``@field_validator``, ``@model_validator``
and ``ConfigDict`` for idiomatic Pydantic v2 usage.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator
from typing_extensions import Self


# ── Enums ──────────────────────────────────────────────────────────────────

_EFFORT_LEVELS = {"low", "medium", "high"}
_CRITICALITY_LEVELS = {"normal", "high", "critical"}


class SeverityLevel(str, Enum):
    """Severity classification for findings."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class FindingType(str, Enum):
    """Categories of technical debt findings."""

    DEPRECATED_API = "deprecated_api"
    TODO_COMMENT = "todo_comment"
    CODE_SMELL = "code_smell"
    SECURITY = "security"
    TYPE_COVERAGE = "type_coverage"


class ChangeType(str, Enum):
    """Types of code changes."""

    REPLACE = "replace"
    INSERT = "insert"
    DELETE = "delete"
    RENAME = "rename"


class PipelineStage(str, Enum):
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


class RiskLevel(str, Enum):
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
    lint_violations: list[dict[str, Any]] = Field(default_factory=list)
    security_passed: bool = True
    security_issues: list[dict[str, Any]] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0


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
