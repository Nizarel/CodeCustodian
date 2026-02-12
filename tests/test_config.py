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
        assert config.scanners.deprecated_api is True
        assert config.scanners.code_smells is True
        assert config.scanners.security is True
        assert config.scanners.todo_comments is True
        assert config.scanners.type_coverage is True

    def test_behavior_defaults(self):
        config = CodeCustodianConfig()
        assert config.behavior.auto_fix is True
        assert config.behavior.create_prs is True
        assert config.behavior.min_confidence >= 1
        assert config.behavior.min_confidence <= 10

    def test_from_file(self):
        """Test loading config from a YAML file."""
        yaml_content = """
version: "1.0"
scanners:
  deprecated_api: true
  code_smells: false
behavior:
  auto_fix: false
  min_confidence: 9
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False
        ) as f:
            f.write(yaml_content)
            f.flush()

            config = CodeCustodianConfig.from_file(f.name)
            assert config.scanners.deprecated_api is True
            assert config.scanners.code_smells is False
            assert config.behavior.auto_fix is False
            assert config.behavior.min_confidence == 9

    def test_to_yaml(self):
        config = CodeCustodianConfig()
        yaml_str = config.to_yaml()
        assert "version" in yaml_str
        parsed = yaml.safe_load(yaml_str)
        assert parsed["version"] == "1.0"


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
        config = BehaviorConfig(min_confidence=1)
        assert config.min_confidence == 1

        config = BehaviorConfig(min_confidence=10)
        assert config.min_confidence == 10
