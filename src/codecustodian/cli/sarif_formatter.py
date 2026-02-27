"""SARIF 2.1.0 formatter for CodeCustodian findings.

Produces a GitHub code-scanning compatible SARIF payload with:
- stable `ruleId` values
- per-result `partialFingerprints`
- repository-relative file URIs when possible
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from codecustodian import __version__
from codecustodian.models import Finding, SeverityLevel

_SCHEMA_URI = "https://json.schemastore.org/sarif-2.1.0.json"


def _sarif_level(severity: SeverityLevel) -> str:
    if severity in {SeverityLevel.CRITICAL, SeverityLevel.HIGH}:
        return "error"
    if severity == SeverityLevel.MEDIUM:
        return "warning"
    return "note"


def _relative_uri(file_path: str, repo_root: str | None) -> str:
    if not repo_root:
        return file_path.replace("\\", "/")

    file_obj = Path(file_path)
    root_obj = Path(repo_root)
    try:
        return str(file_obj.resolve().relative_to(root_obj.resolve())).replace("\\", "/")
    except Exception:
        return file_path.replace("\\", "/")


def _build_rule_help(rule_id: str) -> str:
    return (
        f"CodeCustodian rule `{rule_id}` detected a technical-debt or risk signal. "
        "Review the suggested remediation and associated metadata for safe fixes."
    )


def findings_to_sarif(findings: list[Finding], repo_root: str | None = None) -> str:
    """Convert findings into a SARIF 2.1.0 JSON string."""
    rule_map: dict[str, dict[str, str]] = {}
    results: list[dict] = []

    for finding in findings:
        rule_id = finding.type.value
        if rule_id not in rule_map:
            rule_map[rule_id] = {
                "id": rule_id,
                "name": rule_id,
                "shortDescription": {"text": f"CodeCustodian detection: {rule_id}"},
                "fullDescription": {
                    "text": f"Findings of type `{rule_id}` identified by CodeCustodian scanners."
                },
                "help": {"text": _build_rule_help(rule_id)},
                "defaultConfiguration": {"level": _sarif_level(finding.severity)},
                "properties": {
                    "tags": ["maintainability", "technical-debt"],
                    "precision": "high",
                },
            }

        uri = _relative_uri(finding.file, repo_root)
        start_line = finding.line if finding.line > 0 else 1
        end_line = finding.end_line if finding.end_line and finding.end_line >= start_line else start_line
        start_col = finding.column if finding.column > 0 else 1
        end_col = start_col + 1

        line_hash_source = f"{uri}:{start_line}:{finding.description}"
        line_hash = hashlib.sha256(line_hash_source.encode("utf-8")).hexdigest()[:16]

        results.append(
            {
                "ruleId": rule_id,
                "level": _sarif_level(finding.severity),
                "message": {"text": finding.description},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": uri},
                            "region": {
                                "startLine": start_line,
                                "startColumn": start_col,
                                "endLine": end_line,
                                "endColumn": end_col,
                            },
                        }
                    }
                ],
                "partialFingerprints": {
                    "primaryLocationLineHash": f"{line_hash}:{start_line}",
                },
            }
        )

    sarif_log = {
        "$schema": _SCHEMA_URI,
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "CodeCustodian",
                        "semanticVersion": __version__,
                        "rules": list(rule_map.values()),
                    }
                },
                "results": results,
            }
        ],
    }

    return json.dumps(sarif_log, indent=2)
