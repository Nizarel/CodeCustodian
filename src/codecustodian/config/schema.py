"""Configuration schema — Pydantic models for .codecustodian.yml.

Covers scanner settings, behavior, GitHub integration, notifications,
Azure integration, budget governance, approval gates, and advanced tuning.
Uses Pydantic v2 ``@field_validator``, ``@model_validator``, and ``ConfigDict``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing_extensions import Self


# ── Scanner Config ─────────────────────────────────────────────────────────


class DeprecatedAPIScannerConfig(BaseModel):
    """Configuration for the deprecated API scanner."""

    enabled: bool = True
    severity: str = "high"
    libraries: list[str] = Field(
        default_factory=lambda: ["pandas", "numpy", "requests", "django", "flask"]
    )
    custom_patterns: list[dict[str, str]] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=lambda: ["migrations/**", "vendor/**"])


class TodoScannerConfig(BaseModel):
    """Configuration for the TODO comment scanner."""

    enabled: bool = True
    max_age_days: int = 90
    patterns: list[str] = Field(
        default_factory=lambda: ["TODO", "FIXME", "HACK", "XXX"]
    )
    auto_issue: bool = False
    notify_authors: bool = False


class CodeSmellScannerConfig(BaseModel):
    """Configuration for the code smell scanner."""

    enabled: bool = True
    cyclomatic_complexity: int = 10
    function_length: int = 50
    nesting_depth: int = 4
    max_parameters: int = 5
    file_length: int = 500


class SecurityScannerConfig(BaseModel):
    """Configuration for the security pattern scanner."""

    enabled: bool = True
    detect_hardcoded_secrets: bool = True
    detect_weak_crypto: bool = True
    detect_sql_injection: bool = True
    detect_command_injection: bool = True


class TypeCoverageScannerConfig(BaseModel):
    """Configuration for the type coverage scanner."""

    enabled: bool = True
    target_coverage: int = 80
    strict_mode: bool = False


class ScannersConfig(BaseModel):
    """Aggregate scanner configuration."""

    deprecated_apis: DeprecatedAPIScannerConfig = Field(
        default_factory=DeprecatedAPIScannerConfig
    )
    todo_comments: TodoScannerConfig = Field(default_factory=TodoScannerConfig)
    code_smells: CodeSmellScannerConfig = Field(default_factory=CodeSmellScannerConfig)
    security_patterns: SecurityScannerConfig = Field(
        default_factory=SecurityScannerConfig
    )
    type_coverage: TypeCoverageScannerConfig = Field(
        default_factory=TypeCoverageScannerConfig
    )


# ── Behavior Config ────────────────────────────────────────────────────────


class BehaviorConfig(BaseModel):
    """Pipeline behavior configuration.

    Includes PR sizing controls (BR-PLN-002), proposal mode threshold
    (BR-PR-003), and a cross-field validator ensuring
    ``proposal_mode_threshold <= confidence_threshold``.
    """

    model_config = ConfigDict(validate_assignment=True)

    max_prs_per_run: int = 5
    pr_strategy: str = "separate"  # separate | grouped | batched
    require_human_review: bool = True
    auto_merge: bool = False
    draft_prs_for_complex: bool = True
    confidence_threshold: int = Field(ge=1, le=10, default=7)
    max_complexity: str = "moderate"  # simple | moderate | complex
    skip_complex_refactorings: bool = False
    # ── NEW — Phase 1 fields ──────────────────────────────────────────
    max_files_per_pr: int = Field(
        default=5, ge=1, description="Max files per PR (BR-PLN-002)"
    )
    max_lines_per_pr: int = Field(
        default=500, ge=1, description="Max changed lines per PR (BR-PLN-002)"
    )
    auto_split_prs: bool = Field(
        default=True, description="Split PRs when limits exceeded (BR-PLN-002)"
    )
    proposal_mode_threshold: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Confidence below this → proposal only (BR-PR-003)",
    )
    enable_alternatives: bool = Field(
        default=True, description="Generate alternative solutions (FR-PLAN-102)"
    )

    @model_validator(mode="after")
    def _threshold_ordering(self) -> Self:
        """Ensure proposal threshold ≤ confidence threshold."""
        if self.proposal_mode_threshold > self.confidence_threshold:
            raise ValueError(
                f"proposal_mode_threshold ({self.proposal_mode_threshold}) must be "
                f"<= confidence_threshold ({self.confidence_threshold})"
            )
        return self


# ── GitHub Config ──────────────────────────────────────────────────────────


class GitHubConfig(BaseModel):
    """GitHub integration configuration."""

    pr_labels: list[str] = Field(
        default_factory=lambda: ["tech-debt", "automated", "codecustodian"]
    )
    pr_title_format: str = "🔄 {type}: {summary}"
    reviewers: list[str] = Field(default_factory=list)
    team_reviewers: list[str] = Field(default_factory=list)
    base_branch: str = "main"
    branch_prefix: str = "tech-debt"
    delete_branch_on_merge: bool = True


# ── Copilot Config ─────────────────────────────────────────────────────────


class CopilotConfig(BaseModel):
    """GitHub Copilot SDK configuration."""

    model_selection: str = "auto"  # auto | fast | balanced | reasoning
    temperature: float = 0.1
    max_tokens: int = 4096
    timeout: int = 30
    max_cost_per_run: float = 5.00
    requests_per_minute: int = 20
    concurrent_sessions: int = 3


# ── Git Config ─────────────────────────────────────────────────────────────


class GitConfig(BaseModel):
    """Git operations configuration."""

    commit_message_format: str = "refactor: {summary}\n\n{body}"
    branch_name_format: str = "{category}-{file}-{timestamp}"
    author_name: str = "CodeCustodian"
    author_email: str = "bot@codecustodian.dev"


# ── Testing Config ─────────────────────────────────────────────────────────


class TestingConfig(BaseModel):
    """Testing and verification configuration."""

    framework: str = "pytest"
    timeout: int = 300
    coverage_threshold: int = 80
    fail_on_coverage_decrease: bool = True
    parallel: bool = True


# ── Linting Config ─────────────────────────────────────────────────────────


class LintingConfig(BaseModel):
    """Linting configuration."""

    tools: list[str] = Field(default_factory=lambda: ["ruff", "mypy", "bandit"])
    fail_on: str = "new_violations_only"  # any | new_violations_only | critical_only


# ── Advanced Config ────────────────────────────────────────────────────────


class AdvancedConfig(BaseModel):
    """Advanced settings."""

    copilot: CopilotConfig = Field(default_factory=CopilotConfig)
    git: GitConfig = Field(default_factory=GitConfig)
    testing: TestingConfig = Field(default_factory=TestingConfig)
    linting: LintingConfig = Field(default_factory=LintingConfig)
    backup_enabled: bool = True
    backup_retention_days: int = 7
    atomic_operations: bool = True
    validate_syntax: bool = True
    cache_enabled: bool = True
    cache_ttl: int = 3600
    parallel_scanning: bool = True
    max_workers: int = 4
    exclude_paths: list[str] = Field(
        default_factory=lambda: [
            "vendor/**",
            "node_modules/**",
            "*.min.js",
            "migrations/**",
            ".venv/**",
            "build/**",
            "dist/**",
        ]
    )


# ── Notification Config ───────────────────────────────────────────────────


class SlackConfig(BaseModel):
    """Slack notification settings."""

    enabled: bool = False
    webhook_url: str = ""
    channel: str = "#tech-debt"


class NotificationsConfig(BaseModel):
    """Notification configuration (BR-NOT-001)."""

    slack: SlackConfig = Field(default_factory=SlackConfig)
    channels: list[str] = Field(
        default_factory=list,
        description="Notification channel identifiers",
    )
    severity_threshold: str = Field(
        default="medium",
        description="Minimum severity to trigger notifications",
    )
    events: list[str] = Field(
        default_factory=lambda: ["pr_created", "pipeline_failed"],
        description="Events that trigger notifications",
    )


# ── Azure Config ───────────────────────────────────────────────────────────


class AzureConfig(BaseModel):
    """Azure integration configuration (DevOps, Monitor, Key Vault)."""

    model_config = ConfigDict(validate_assignment=True)

    devops_org_url: str = ""
    devops_pat: str = ""
    devops_project: str = ""
    monitor_connection_string: str = ""
    tenant_id: str = ""
    keyvault_name: str = ""

    @field_validator("devops_org_url", "monitor_connection_string")
    @classmethod
    def _validate_url_format(cls, v: str) -> str:
        """Basic URL validation when non-empty."""
        if v and not (v.startswith("http://") or v.startswith("https://")
                      or v.startswith("InstrumentationKey=")):
            raise ValueError(f"Invalid URL or connection string format: {v!r}")
        return v


class WorkIQConfig(BaseModel):
    """Microsoft Work IQ MCP configuration."""

    enabled: bool = False
    mcp_server_url: str = ""
    api_key: str = ""


class BudgetConfig(BaseModel):
    """Cost governance configuration (FR-COST-100)."""

    model_config = ConfigDict(validate_assignment=True)

    monthly_budget: float = Field(default=500.0, ge=0.0)
    alert_thresholds: list[int] = Field(
        default_factory=lambda: [50, 80, 90, 100],
        description="Budget usage % thresholds triggering alerts",
    )
    hard_limit: bool = Field(
        default=True,
        description="When True, pipeline stops at 100% budget usage",
    )

    @field_validator("alert_thresholds")
    @classmethod
    def _validate_thresholds(cls, v: list[int]) -> list[int]:
        """Ensure thresholds are sorted ascending and within 0-100."""
        for t in v:
            if t < 0 or t > 100:
                raise ValueError(f"Alert threshold {t} must be between 0 and 100")
        return sorted(v)


class ApprovalConfig(BaseModel):
    """Approval gate configuration (BR-GOV-002)."""

    require_plan_approval: bool = False
    require_pr_approval: bool = True
    approved_repos: list[str] = Field(
        default_factory=list,
        description="Repos pre-approved for auto-refactoring",
    )
    sensitive_paths: list[str] = Field(
        default_factory=lambda: ["**/auth/**", "**/payments/**", "**/security/**"],
        description="Glob patterns for paths requiring proposal-only mode",
    )


# ── Root Config ────────────────────────────────────────────────────────────


class CodeCustodianConfig(BaseModel):
    """Root configuration model for .codecustodian.yml."""

    version: str = "1.0"
    scanners: ScannersConfig = Field(default_factory=ScannersConfig)
    behavior: BehaviorConfig = Field(default_factory=BehaviorConfig)
    github: GitHubConfig = Field(default_factory=GitHubConfig)
    notifications: NotificationsConfig = Field(default_factory=NotificationsConfig)
    advanced: AdvancedConfig = Field(default_factory=AdvancedConfig)
    # ── NEW — Phase 1 config sections ─────────────────────────────────
    azure: AzureConfig = Field(default_factory=AzureConfig)
    work_iq: WorkIQConfig = Field(default_factory=WorkIQConfig)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    approval: ApprovalConfig = Field(default_factory=ApprovalConfig)

    @classmethod
    def from_file(cls, path: str | Path) -> CodeCustodianConfig:
        """Load configuration from a YAML file.

        Falls back to defaults for missing keys.
        """
        config_path = Path(path)
        if not config_path.exists():
            return cls()

        with open(config_path) as f:
            raw: dict[str, Any] = yaml.safe_load(f) or {}

        return cls.model_validate(raw)

    def to_yaml(self, path: str | Path) -> None:
        """Write configuration to a YAML file."""
        with open(path, "w") as f:
            yaml.dump(
                self.model_dump(exclude_defaults=True),
                f,
                default_flow_style=False,
                sort_keys=False,
            )
