"""Starter policy templates for onboarding (BR-ONB-002).

Each template is a partial configuration dict that can be merged into
a ``CodeCustodianConfig`` via ``PolicyManager`` or ``_deep_merge``.
Templates are intentionally *not* full Pydantic models — they are
partial overrides meant to be layered onto defaults.
"""

from __future__ import annotations

from typing import Any

# ── Template definitions ───────────────────────────────────────────────────

SECURITY_FIRST: dict[str, Any] = {
    "scanners": {
        "security_patterns": {"enabled": True},
        "deprecated_apis": {"enabled": True},
        "code_smells": {"enabled": False},
        "todo_comments": {"enabled": False},
        "type_coverage": {"enabled": False},
    },
    "behavior": {
        "confidence_threshold": 8,
        "proposal_mode_threshold": 6,
        "max_files_per_pr": 3,
        "max_lines_per_pr": 300,
        "require_human_review": True,
    },
    "approval": {
        "require_plan_approval": True,
        "sensitive_paths": [
            "**/auth/**",
            "**/payments/**",
            "**/security/**",
            "**/crypto/**",
            "**/secrets/**",
        ],
    },
}

DEPRECATIONS_FIRST: dict[str, Any] = {
    "scanners": {
        "deprecated_apis": {"enabled": True, "severity": "high"},
        "code_smells": {"enabled": True},
        "todo_comments": {"enabled": False},
        "security_patterns": {"enabled": True},
        "type_coverage": {"enabled": False},
    },
    "behavior": {
        "confidence_threshold": 7,
        "proposal_mode_threshold": 5,
        "max_files_per_pr": 8,
        "max_lines_per_pr": 800,
        "auto_split_prs": True,
        "max_prs_per_run": 10,
    },
}

LOW_RISK_MAINTENANCE: dict[str, Any] = {
    "scanners": {
        "deprecated_apis": {"enabled": False},
        "code_smells": {"enabled": False},
        "security_patterns": {"enabled": False},
        "todo_comments": {"enabled": True, "max_age_days": 180},
        "type_coverage": {"enabled": True, "target_coverage": 70},
    },
    "behavior": {
        "confidence_threshold": 9,
        "proposal_mode_threshold": 7,
        "max_files_per_pr": 3,
        "max_lines_per_pr": 200,
        "max_prs_per_run": 3,
        "require_human_review": True,
    },
}

FULL_SCAN: dict[str, Any] = {
    "scanners": {
        "deprecated_apis": {"enabled": True},
        "code_smells": {"enabled": True},
        "security_patterns": {"enabled": True},
        "todo_comments": {"enabled": True},
        "type_coverage": {"enabled": True},
    },
    "behavior": {
        "confidence_threshold": 7,
        "proposal_mode_threshold": 5,
        "max_files_per_pr": 5,
        "max_lines_per_pr": 500,
        "auto_split_prs": True,
        "enable_alternatives": True,
    },
}

# ── Registry ───────────────────────────────────────────────────────────────

TEMPLATES: dict[str, dict[str, Any]] = {
    "security_first": SECURITY_FIRST,
    "deprecations_first": DEPRECATIONS_FIRST,
    "low_risk_maintenance": LOW_RISK_MAINTENANCE,
    "full_scan": FULL_SCAN,
}


def get_template(name: str) -> dict[str, Any]:
    """Return a policy template by name.

    Args:
        name: One of ``security_first``, ``deprecations_first``,
              ``low_risk_maintenance``, ``full_scan``.

    Raises:
        KeyError: If the template name is unknown.
    """
    if name not in TEMPLATES:
        available = ", ".join(sorted(TEMPLATES.keys()))
        raise KeyError(f"Unknown policy template {name!r}. Available: {available}")
    return TEMPLATES[name].copy()


def list_templates() -> list[str]:
    """Return sorted list of available template names."""
    return sorted(TEMPLATES.keys())
