"""Policy management for organization and team-level overrides.

Supports hierarchical policy resolution:
  org defaults → team overrides → repo overrides → CLI flags

Includes path allowlist/denylist controls (BR-CFG-002) and
proposal-mode gating for sensitive paths (BR-PR-003).
"""

from __future__ import annotations

import os
from copy import deepcopy
from fnmatch import fnmatch
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
    """Resolve configuration by merging policies in priority order.

    Merging order (later wins):
      defaults → org policy → team policy → repo policy → env vars → CLI flags

    Args:
        org_policy: Organization-wide policy overrides.
        repo_overrides: Per-repo policy overrides keyed by repo name.
    """

    def __init__(
        self,
        org_policy: dict[str, Any] | None = None,
        repo_overrides: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self._policies: list[PolicyOverride] = []
        self._org_policy = org_policy or {}
        self._repo_overrides = repo_overrides or {}

    # ── Policy loading ─────────────────────────────────────────────────

    def add_policy(self, policy: PolicyOverride) -> None:
        """Append a policy override."""
        self._policies.append(policy)

    def load_policies_from_file(self, path: str | Path) -> None:
        """Load policies from a YAML file."""
        with open(path) as f:
            raw = yaml.safe_load(f) or {}

        for entry in raw.get("policies", []):
            self._policies.append(PolicyOverride.model_validate(entry))

    # ── Resolution ─────────────────────────────────────────────────────

    def get_effective_policy(self, repo_name: str) -> dict[str, Any]:
        """Merge org-wide policy with repo-specific overrides (BR-CFG-001).

        Returns a raw dict suitable for ``CodeCustodianConfig.model_validate()``.
        """
        base = deepcopy(self._org_policy)
        if repo_name in self._repo_overrides:
            base = _deep_merge(base, self._repo_overrides[repo_name])
        return base

    def resolve(
        self,
        base: CodeCustodianConfig | None = None,
        *,
        repo_name: str = "",
        env_prefix: str = "CODECUSTODIAN_",
    ) -> CodeCustodianConfig:
        """Merge all enabled policies, repo overrides, and env vars onto *base*.

        Merging order:
        1. base config (or defaults)
        2. explicit policies (in order added)
        3. repo-specific overrides
        4. environment variables (``CODECUSTODIAN_<SECTION>__<KEY>``)
        """
        config_dict = (base or CodeCustodianConfig()).model_dump()

        # Layer 1: explicit policies
        for policy in self._policies:
            if policy.enabled:
                config_dict = _deep_merge(config_dict, policy.overrides)

        # Layer 2: repo overrides
        if repo_name:
            effective = self.get_effective_policy(repo_name)
            config_dict = _deep_merge(config_dict, effective)

        # Layer 3: environment variable overrides
        config_dict = _apply_env_overrides(config_dict, env_prefix)

        return CodeCustodianConfig.model_validate(config_dict)

    # ── Path controls (BR-CFG-002) ─────────────────────────────────────

    def is_path_allowed(self, file_path: str, repo_name: str = "") -> bool:
        """Check allowlist/denylist controls for a file path.

        Uses the effective policy for *repo_name*. Denylist is checked
        first; if any pattern matches the path is blocked. Then the
        allowlist is checked (defaults to ``["**"]`` — allow everything).
        """
        policy = self.get_effective_policy(repo_name) if repo_name else {}

        # Check explicit denylist
        for pattern in policy.get("denylist", []):
            if fnmatch(file_path, pattern):
                return False

        # Check allowlist (default: allow everything)
        allowlist = policy.get("allowlist", ["**"])
        return any(fnmatch(file_path, p) for p in allowlist)

    def should_use_proposal_mode(
        self,
        file_path: str,
        finding_type: str = "",
        *,
        sensitive_paths: list[str] | None = None,
        proposal_only_types: set[str] | None = None,
    ) -> bool:
        """Check if proposal-only mode is required for this path/type.

        Returns ``True`` if:
        - *file_path* matches any pattern in *sensitive_paths*
        - *finding_type* is in the *proposal_only_types* set

        Args:
            file_path: File path being considered.
            finding_type: The ``FindingType`` value.
            sensitive_paths: Glob patterns for sensitive paths
                (defaults to ``ApprovalConfig.sensitive_paths``).
            proposal_only_types: Finding types that always require
                proposal mode.
        """
        paths = sensitive_paths or [
            "**/auth/**",
            "**/payments/**",
            "**/security/**",
        ]
        for pattern in paths:
            if fnmatch(file_path, pattern):
                return True

        if proposal_only_types and finding_type in proposal_only_types:
            return True

        return False


# ── Helpers ────────────────────────────────────────────────────────────────


def _deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge *overrides* into *base*."""
    merged = base.copy()
    for key, value in overrides.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _apply_env_overrides(
    config_dict: dict[str, Any],
    prefix: str,
) -> dict[str, Any]:
    """Apply environment variable overrides using ``PREFIX_SECTION__KEY`` convention.

    For example: ``CODECUSTODIAN_BEHAVIOR__CONFIDENCE_THRESHOLD=9``
    sets ``config.behavior.confidence_threshold = 9``.
    """
    for env_key, env_value in os.environ.items():
        if not env_key.startswith(prefix):
            continue
        parts = env_key[len(prefix) :].lower().split("__")
        if len(parts) != 2:
            continue

        section, key = parts
        if section in config_dict and isinstance(config_dict[section], dict):
            # Attempt type coercion from the existing value
            existing = config_dict[section].get(key)
            if isinstance(existing, bool):
                config_dict[section][key] = env_value.lower() in ("true", "1", "yes")
            elif isinstance(existing, int):
                try:
                    config_dict[section][key] = int(env_value)
                except ValueError:
                    pass
            elif isinstance(existing, float):
                try:
                    config_dict[section][key] = float(env_value)
                except ValueError:
                    pass
            else:
                config_dict[section][key] = env_value

    return config_dict
