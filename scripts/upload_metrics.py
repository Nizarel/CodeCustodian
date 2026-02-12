#!/usr/bin/env python3
"""Upload pipeline metrics to Azure Monitor / Application Insights.

Usage:
    python scripts/upload_metrics.py --result pipeline-result.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload pipeline metrics")
    parser.add_argument(
        "--result",
        type=Path,
        required=True,
        help="Path to pipeline result JSON file",
    )
    args = parser.parse_args()

    if not args.result.exists():
        print(f"Error: {args.result} not found")
        sys.exit(1)

    with open(args.result) as f:
        data = json.load(f)

    print(f"Total findings: {data.get('total_findings', 0)}")
    print(f"Fixed: {data.get('findings_fixed', 0)}")
    print(f"PRs created: {data.get('prs_created', 0)}")
    print(f"Duration: {data.get('duration_seconds', 0):.1f}s")

    # Azure Monitor upload
    try:
        from codecustodian.integrations.azure_monitor import AzureMonitorEmitter
        from codecustodian.models import PipelineResult

        result = PipelineResult(**data)
        emitter = AzureMonitorEmitter()
        emitter.emit_pipeline_result(result)
        print("Metrics uploaded to Azure Monitor")
    except ImportError:
        print("Azure Monitor SDK not available — logged locally only")


if __name__ == "__main__":
    main()
