"""Configuration management with Pydantic validation."""

from codecustodian.config.schema import CodeCustodianConfig
from codecustodian.config.defaults import DEFAULT_CONFIG

__all__ = ["CodeCustodianConfig", "DEFAULT_CONFIG"]
