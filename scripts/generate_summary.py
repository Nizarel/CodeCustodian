#!/usr/bin/env python3
"""Generate a summary report from the latest pipeline run.

Usage:
    python scripts/generate_summary.py --result pipeline-result.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate pipeline summary")
    parser.add_argument(
        "--result",
        type=Path,
        default=Path("pipeline-result.json"),
        help="Path to pipeline result JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports"),
        help="Output directory for reports",
    )
    args = parser.parse_args()

    if not args.result.exists():
        print(f"Error: {args.result} not found")
        sys.exit(1)

    with open(args.result) as f:
        data = json.load(f)

    args.output.mkdir(parents=True, exist_ok=True)

    # Generate Markdown summary
    summary = f"""# CodeCustodian Pipeline Summary

| Metric | Value |
|--------|-------|
| Total findings | {data.get('total_findings', 0)} |
| Fixed | {data.get('findings_fixed', 0)} |
| PRs created | {len(data.get('pull_requests', []))} |
| Success rate | {data.get('success_rate', 0):.1f}% |
| Duration | {data.get('duration_seconds', 0):.1f}s |

## Findings by Type

"""
    findings = data.get("findings", [])
    type_counts: dict[str, int] = {}
    for f in findings:
        t = f.get("type", "unknown")
        type_counts[t] = type_counts.get(t, 0) + 1

    for ftype, count in sorted(type_counts.items()):
        summary += f"- **{ftype}**: {count}\n"

    report_path = args.output / "summary.md"
    report_path.write_text(summary)
    print(f"Summary written to {report_path}")


if __name__ == "__main__":
    main()
