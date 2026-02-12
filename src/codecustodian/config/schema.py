"""Configuration schema — Pydantic models for .codecustodian.yml.

Covers scanner settings, behavior, GitHub integration, notifications,
and advanced tuning knobs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


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
    """Pipeline behavior configuration."""

    max_prs_per_run: int = 5
    pr_strategy: str = "separate"  # separate | grouped | batched
    require_human_review: bool = True
    auto_merge: bool = False
    draft_prs_for_complex: bool = True
    confidence_threshold: int = Field(ge=1, le=10, default=7)
    max_complexity: str = "moderate"  # simple | moderate | complex
    skip_complex_refactorings: bool = False


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
    """Notification configuration."""

    slack: SlackConfig = Field(default_factory=SlackConfig)


# ── Root Config ────────────────────────────────────────────────────────────


class CodeCustodianConfig(BaseModel):
    """Root configuration model for .codecustodian.yml."""

    version: str = "1.0"
    scanners: ScannersConfig = Field(default_factory=ScannersConfig)
    behavior: BehaviorConfig = Field(default_factory=BehaviorConfig)
    github: GitHubConfig = Field(default_factory=GitHubConfig)
    notifications: NotificationsConfig = Field(default_factory=NotificationsConfig)
    advanced: AdvancedConfig = Field(default_factory=AdvancedConfig)

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
