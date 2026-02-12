"""Policy management for organization and team-level overrides.

Supports hierarchical policy resolution:
  org defaults → team overrides → repo overrides → CLI flags
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from codecustodian.config.schema import CodeCustodianConfig


class PolicyOverride(BaseModel):
    """A scoped configuration override."""

    scope: str  # e.g. "org:contoso", "team:platform", "repo:frontend"
    overrides: dict[str, Any] = Field(default_factory=dict)
    description: str = ""
    enabled: bool = True


class PolicyManager:
    """Resolve configuration by merging policies in priority order."""

    def __init__(self) -> None:
        self._policies: list[PolicyOverride] = []

    def add_policy(self, policy: PolicyOverride) -> None:
        self._policies.append(policy)

    def load_policies_from_file(self, path: str | Path) -> None:
        """Load policies from a YAML file."""
        with open(path) as f:
            raw = yaml.safe_load(f) or {}

        for entry in raw.get("policies", []):
            self._policies.append(PolicyOverride.model_validate(entry))

    def resolve(self, base: CodeCustodianConfig | None = None) -> CodeCustodianConfig:
        """Merge all enabled policies onto *base* (or defaults)."""
        config_dict = (base or CodeCustodianConfig()).model_dump()

        for policy in self._policies:
            if policy.enabled:
                config_dict = _deep_merge(config_dict, policy.overrides)

        return CodeCustodianConfig.model_validate(config_dict)


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge *overrides* into *base*."""
    merged = base.copy()
    for key, value in overrides.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged
