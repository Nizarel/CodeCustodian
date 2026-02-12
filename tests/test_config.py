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
        assert config.temperature == 0.1
        assert config.max_tokens == 4096


class TestBehaviorConfig:
    def test_confidence_range(self):
        config = BehaviorConfig(confidence_threshold=1)
        assert config.confidence_threshold == 1

        config = BehaviorConfig(confidence_threshold=10)
        assert config.confidence_threshold == 10
