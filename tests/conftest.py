"""Shared test fixtures and factory helpers for CodeCustodian tests."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from typer.testing import CliRunner

from codecustodian.config.schema import CodeCustodianConfig
from codecustodian.models import (
    ChangeType,
    FileChange,
    Finding,
    FindingType,
    RefactoringPlan,
    RiskLevel,
    SeverityLevel,
)


def make_finding(**overrides: object) -> Finding:
    """Build a Finding with sensible defaults for tests."""
    defaults: dict[str, object] = {
        "type": FindingType.DEPRECATED_API,
        "severity": SeverityLevel.HIGH,
        "file": "src/example.py",
        "line": 10,
        "description": "Deprecated API usage",
        "suggestion": "Use modern alternative",
        "priority_score": 120.0,
    }
    defaults.update(overrides)
    return Finding(**defaults)


def make_plan(**overrides: object) -> RefactoringPlan:
    """Build a RefactoringPlan with one default replacement change."""
    default_change = FileChange(
        file_path="src/example.py",
        change_type=ChangeType.REPLACE,
        old_content="old_call()",
        new_content="new_call()",
        start_line=10,
        end_line=10,
        description="Replace deprecated API call",
    )
    defaults: dict[str, object] = {
        "finding_id": "finding-001",
        "summary": "Replace deprecated API",
        "description": "Use supported API",
        "changes": [default_change],
        "confidence_score": 8,
        "risk_level": RiskLevel.LOW,
        "ai_reasoning": "API is deprecated and replacement is mechanical.",
    }
    defaults.update(overrides)
    return RefactoringPlan(**defaults)


def make_config(**overrides: object) -> CodeCustodianConfig:
    """Build a CodeCustodianConfig and apply top-level overrides."""
    config = CodeCustodianConfig()
    for field_name, value in overrides.items():
        setattr(config, field_name, value)
    return config


@pytest.fixture
def cli_runner() -> CliRunner:
    """Typer CLI runner fixture for command tests."""
    return CliRunner()


@pytest.fixture
def tmp_repo() -> Path:
    """Create a temporary repository-like directory with sample source + config."""
    with TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        src_dir = root / "src"
        src_dir.mkdir(parents=True, exist_ok=True)
        (src_dir / "app.py").write_text(
            "def run(value):\n    # TODO: improve implementation\n    return value\n"
        )
        (root / ".codecustodian.yml").write_text('version: "1.0"\n')
        yield root
