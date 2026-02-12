"""Core data models for CodeCustodian pipeline.

All models use Pydantic v2 for validation and serialization.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────────


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
    """A detected technical debt issue."""

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
    metadata: dict[str, Any] = Field(default_factory=dict)
    scanner_name: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def file_path(self) -> Path:
        return Path(self.file)


class CodeContext(BaseModel):
    """Surrounding code context for AI planning."""

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


class FileChange(BaseModel):
    """A single file modification."""

    file_path: str
    change_type: ChangeType
    old_content: str = ""
    new_content: str = ""
    start_line: int | None = None
    end_line: int | None = None
    description: str = ""


class RefactoringPlan(BaseModel):
    """AI planner output for a refactoring."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    finding_id: str
    summary: str
    description: str = ""
    changes: list[FileChange] = Field(default_factory=list)
    confidence_score: int = Field(ge=1, le=10, default=5)
    risk_level: RiskLevel = RiskLevel.LOW
    ai_reasoning: str = ""
    alternatives: list[str] = Field(default_factory=list)
    estimated_tokens: int = 0
    model_used: str = ""
    changes_signature: bool = False
    requires_manual_verification: bool = False
    files_to_change: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ExecutionResult(BaseModel):
    """Result of executing a refactoring plan."""

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

    number: int
    url: str
    title: str
    body: str = ""
    labels: list[str] = Field(default_factory=list)
    reviewers: list[str] = Field(default_factory=list)
    branch: str = ""
    base_branch: str = "main"
    draft: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PipelineResult(BaseModel):
    """Full pipeline run output."""

    run_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    findings: list[Finding] = Field(default_factory=list)
    plans: list[RefactoringPlan] = Field(default_factory=list)
    executions: list[ExecutionResult] = Field(default_factory=list)
    verifications: list[VerificationResult] = Field(default_factory=list)
    pull_requests: list[PullRequestInfo] = Field(default_factory=list)
    total_duration_seconds: float = 0.0
    errors: list[str] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=datetime.utcnow)
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
