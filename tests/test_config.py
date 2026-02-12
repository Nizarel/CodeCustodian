"""Tests for configuration schema and defaults."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

from codecustodian.config.defaults import DEFAULT_YAML, get_default_config
from codecustodian.config.schema import (
    BehaviorConfig,
    CodeCustodianConfig,
    CopilotConfig,
    ScannersConfig,
)


class TestCodeCustodianConfig:
    def test_default_creation(self):
        config = CodeCustodianConfig()
        assert config.version == "1.0"
        assert config.scanners is not None
        assert config.behavior is not None

    def test_scanners_defaults(self):
        config = CodeCustodianConfig()
        assert config.scanners.deprecated_apis.enabled is True
        assert config.scanners.code_smells.enabled is True
        assert config.scanners.security_patterns.enabled is True
        assert config.scanners.todo_comments.enabled is True
        assert config.scanners.type_coverage.enabled is True

    def test_behavior_defaults(self):
        config = CodeCustodianConfig()
        assert config.behavior.require_human_review is True
        assert config.behavior.auto_merge is False
        assert config.behavior.confidence_threshold >= 1
        assert config.behavior.confidence_threshold <= 10

    def test_from_file(self):
        """Test loading config from a YAML file."""
        yaml_content = """
version: "1.0"
scanners:
  deprecated_apis:
    enabled: true
  code_smells:
    enabled: false
behavior:
  auto_merge: true
  confidence_threshold: 9
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False
        ) as f:
            f.write(yaml_content)
            f.flush()

            config = CodeCustodianConfig.from_file(f.name)
            assert config.scanners.deprecated_apis.enabled is True
            assert config.scanners.code_smells.enabled is False
            assert config.behavior.auto_merge is True
            assert config.behavior.confidence_threshold == 9

    def test_to_yaml(self):
        config = CodeCustodianConfig(version="2.0")
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False
        ) as f:
            config.to_yaml(f.name)
            yaml_str = Path(f.name).read_text()
        assert "version" in yaml_str
        parsed = yaml.safe_load(yaml_str)
        assert parsed["version"] == "2.0"


class TestDefaultConfig:
    def test_get_default_config(self):
        config = get_default_config()
        assert isinstance(config, CodeCustodianConfig)

    def test_default_yaml_parseable(self):
        parsed = yaml.safe_load(DEFAULT_YAML)
        assert parsed["version"] == "1.0"


class TestCopilotConfig:
    def test_defaults(self):
        config = CopilotConfig()
        assert config.model_selection == "auto"
        assert config.max_tokens == 4096
        assert config.streaming is True
        assert config.github_token == ""
        assert config.enable_alternatives is True
        assert config.proposal_mode_threshold == 5
        assert config.azure_openai_provider is None
        assert config.reasoning_effort == ""


class TestBehaviorConfig:
    def test_confidence_range(self):
        # confidence_threshold=1 requires proposal_mode_threshold <= 1
        config = BehaviorConfig(confidence_threshold=1, proposal_mode_threshold=1)
        assert config.confidence_threshold == 1

        config = BehaviorConfig(confidence_threshold=10)
        assert config.confidence_threshold == 10

    def test_new_pr_sizing_fields(self):
        config = BehaviorConfig()
        assert config.max_files_per_pr == 5
        assert config.max_lines_per_pr == 500
        assert config.auto_split_prs is True
        assert config.enable_alternatives is True

    def test_proposal_mode_threshold_default(self):
        config = BehaviorConfig()
        assert config.proposal_mode_threshold == 5
        assert config.proposal_mode_threshold <= config.confidence_threshold

    def test_threshold_ordering_validation(self):
        """proposal_mode_threshold must be <= confidence_threshold."""
        with pytest.raises(Exception, match="proposal_mode_threshold"):
            BehaviorConfig(confidence_threshold=3, proposal_mode_threshold=5)


class TestAzureConfig:
    def test_defaults(self):
        from codecustodian.config.schema import AzureConfig

        config = AzureConfig()
        assert config.devops_org_url == ""
        assert config.monitor_connection_string == ""

    def test_valid_url(self):
        from codecustodian.config.schema import AzureConfig

        config = AzureConfig(devops_org_url="https://dev.azure.com/myorg")
        assert config.devops_org_url == "https://dev.azure.com/myorg"

    def test_valid_connection_string(self):
        from codecustodian.config.schema import AzureConfig

        config = AzureConfig(
            monitor_connection_string="InstrumentationKey=abc-123"
        )
        assert "InstrumentationKey=" in config.monitor_connection_string

    def test_invalid_url_rejected(self):
        from codecustodian.config.schema import AzureConfig

        with pytest.raises(Exception, match="Invalid URL"):
            AzureConfig(devops_org_url="not-a-url")


class TestBudgetConfig:
    def test_defaults(self):
        from codecustodian.config.schema import BudgetConfig

        config = BudgetConfig()
        assert config.monthly_budget == 500.0
        assert config.hard_limit is True
        assert config.alert_thresholds == [50, 80, 90, 100]

    def test_thresholds_sorted(self):
        from codecustodian.config.schema import BudgetConfig

        config = BudgetConfig(alert_thresholds=[90, 50, 100, 80])
        assert config.alert_thresholds == [50, 80, 90, 100]

    def test_threshold_out_of_range(self):
        from codecustodian.config.schema import BudgetConfig

        with pytest.raises(Exception, match="between 0 and 100"):
            BudgetConfig(alert_thresholds=[50, 150])


class TestApprovalConfig:
    def test_defaults(self):
        from codecustodian.config.schema import ApprovalConfig

        config = ApprovalConfig()
        assert config.require_plan_approval is False
        assert config.require_pr_approval is True
        assert len(config.sensitive_paths) >= 1


class TestWorkIQConfig:
    def test_defaults(self):
        from codecustodian.config.schema import WorkIQConfig

        config = WorkIQConfig()
        assert config.enabled is False
        assert config.mcp_server_url == ""


class TestRootConfigExtensions:
    def test_new_sections_present(self):
        config = CodeCustodianConfig()
        assert config.azure is not None
        assert config.work_iq is not None
        assert config.budget is not None
        assert config.approval is not None
