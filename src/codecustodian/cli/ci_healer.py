"""Utilities for converting CI failure logs into actionable remediation plans."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FailureSignal:
    """Detected failure category with a suggested remediation command."""

    key: str
    title: str
    confidence: float
    command: str
    evidence: str


_SIGNAL_PATTERNS: list[tuple[str, str, float, str, str]] = [
    (
        "ruff",
        "Ruff lint or format failure",
        0.9,
        "ruff check src tests --fix",
        r"ruff|\bF\d{3}\b|\bE\d{3}\b|Ruff check|Ruff format",
    ),
    (
        "mypy",
        "Mypy type-check failure",
        0.9,
        "mypy src/codecustodian",
        r"mypy|error: Incompatible|error: Argument|error: Return value",
    ),
    (
        "pytest",
        "Pytest test failure",
        0.85,
        "pytest -q",
        r"== FAILURES ==|FAILED\s+\w|AssertionError|E\s+assert",
    ),
    (
        "bandit",
        "Bandit security finding",
        0.8,
        "bandit -r src/codecustodian -f json",
        r"bandit|issue_severity|B\d{3}:|>> Issue:",
    ),
    (
        "packaging",
        "Dependency resolution or install failure",
        0.75,
        "pip install -U pip setuptools wheel",
        r"ResolutionImpossible|No matching distribution found|Could not find a version",
    ),
]


def _extract_evidence(pattern: str, text: str) -> str:
    match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
    if not match:
        return ""
    start = max(0, match.start() - 60)
    end = min(len(text), match.end() + 60)
    return text[start:end].replace("\n", " ").strip()


def detect_failure_signals(log_text: str) -> list[FailureSignal]:
    """Detect known failure categories from CI output text."""
    signals: list[FailureSignal] = []
    for key, title, confidence, command, pattern in _SIGNAL_PATTERNS:
        if re.search(pattern, log_text, flags=re.IGNORECASE | re.MULTILINE):
            signals.append(
                FailureSignal(
                    key=key,
                    title=title,
                    confidence=confidence,
                    command=command,
                    evidence=_extract_evidence(pattern, log_text),
                )
            )
    return signals


def build_patch_candidates(log_text: str) -> list[dict[str, Any]]:
    """Generate deterministic patch candidates for known lint/type failures."""
    candidates: list[dict[str, Any]] = []

    for match in re.finditer(
        r"(?m)^(?P<file>[^\n:]+):(?P<line>\d+):\d+:\s+F401\s+`(?P<symbol>[^`]+)`\s+imported but unused",
        log_text,
    ):
        candidates.append(
            {
                "id": "ruff-f401-remove-unused-import",
                "title": "Remove unused import",
                "confidence": 0.92,
                "target_file": match.group("file"),
                "target_line": int(match.group("line")),
                "rationale": f"Unused import `{match.group('symbol')}` reported by Ruff F401.",
                "patch_hint": (
                    f"Delete the import at line {match.group('line')} in {match.group('file')} "
                    f"or reference `{match.group('symbol')}` where needed."
                ),
            }
        )

    if "F401" in log_text and not any(
        c["id"] == "ruff-f401-remove-unused-import" for c in candidates
    ):
        candidates.append(
            {
                "id": "ruff-f401-remove-unused-import",
                "title": "Remove unused import",
                "confidence": 0.75,
                "target_file": "unknown",
                "target_line": 0,
                "rationale": "Ruff reported F401 imported-but-unused issue.",
                "patch_hint": "Remove the unused import or use it explicitly where intended.",
            }
        )

    for match in re.finditer(
        r"(?m)^(?P<file>[^\n:]+):(?P<line>\d+):\s+error:\s+Incompatible return value type",
        log_text,
    ):
        candidates.append(
            {
                "id": "mypy-incompatible-return",
                "title": "Align return type annotation and implementation",
                "confidence": 0.88,
                "target_file": match.group("file"),
                "target_line": int(match.group("line")),
                "rationale": "Mypy detected incompatible return value type.",
                "patch_hint": (
                    f"At {match.group('file')}:{match.group('line')}, either update the function "
                    "return annotation to match the returned value, or convert the value before return."
                ),
            }
        )

    if "Incompatible return value type" in log_text and not any(
        c["id"] == "mypy-incompatible-return" for c in candidates
    ):
        candidates.append(
            {
                "id": "mypy-incompatible-return",
                "title": "Align return type annotation and implementation",
                "confidence": 0.72,
                "target_file": "unknown",
                "target_line": 0,
                "rationale": "Mypy reported incompatible return value type.",
                "patch_hint": "Update return annotation or convert returned value to expected type.",
            }
        )

    unique: dict[tuple[str, str, int], dict[str, Any]] = {}
    for candidate in candidates:
        key = (
            candidate["id"],
            str(candidate.get("target_file", "")),
            int(candidate.get("target_line", 0)),
        )
        unique[key] = candidate

    return list(unique.values())


def build_healing_plan(log_text: str) -> dict[str, Any]:
    """Build a deterministic remediation plan from CI logs."""
    signals = detect_failure_signals(log_text)
    patch_candidates = build_patch_candidates(log_text)
    commands = list(dict.fromkeys(signal.command for signal in signals))

    if not signals:
        return {
            "status": "no-signals-detected",
            "summary": "No known CI failure patterns were detected.",
            "signals": [],
            "patch_candidates": patch_candidates,
            "recommended_commands": ["pytest -q", "ruff check src tests", "mypy src/codecustodian"],
            "next_steps": [
                "Inspect raw CI logs for a custom tool failure.",
                "Add a custom healing rule to the analyzer for this pattern.",
            ],
        }

    return {
        "status": "signals-detected",
        "summary": f"Detected {len(signals)} failure signal(s).",
        "signals": [
            {
                "key": signal.key,
                "title": signal.title,
                "confidence": signal.confidence,
                "evidence": signal.evidence,
            }
            for signal in signals
        ],
        "patch_candidates": patch_candidates,
        "recommended_commands": commands,
        "next_steps": [
            "Apply suggested fixes in a dedicated branch.",
            "Run the recommended commands locally.",
            "Re-run CI and attach the updated logs if failures persist.",
        ],
    }
