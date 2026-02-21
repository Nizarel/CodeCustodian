"""CLI interface powered by Typer.

Entry point: ``codecustodian`` command.
"""

from __future__ import annotations

import asyncio
import csv
import json
import tempfile
from io import StringIO
from pathlib import Path
from typing import Any, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from codecustodian import __version__
from codecustodian.models import Finding

app = typer.Typer(
    name="codecustodian",
    help="🛡️ CodeCustodian — Autonomous AI agent for technical debt management",
    add_completion=False,
)
console = Console()


def _apply_scan_type_filter(cfg: Any, scan_type: str) -> None:
    """Enable only the selected scanner when scan_type is not 'all'."""
    normalized = scan_type.strip().lower()
    if normalized in {"", "all"}:
        return

    scanner_map = {
        "deprecated_apis": "deprecated_apis",
        "deprecated_api": "deprecated_apis",
        "todo_comments": "todo_comments",
        "todo_comment": "todo_comments",
        "code_smells": "code_smells",
        "code_smell": "code_smells",
        "security_patterns": "security_patterns",
        "security": "security_patterns",
        "type_coverage": "type_coverage",
        "types": "type_coverage",
    }
    target = scanner_map.get(normalized)
    if target is None:
        raise typer.BadParameter(f"Unknown scan type: {scan_type}")

    scanner_fields = [
        "deprecated_apis",
        "todo_comments",
        "code_smells",
        "security_patterns",
        "type_coverage",
    ]
    for field_name in scanner_fields:
        getattr(cfg.scanners, field_name).enabled = field_name == target


def _finding_to_row(finding: Finding) -> dict[str, Any]:
    return {
        "id": finding.id,
        "type": finding.type.value,
        "severity": finding.severity.value,
        "file": finding.file,
        "line": finding.line,
        "description": finding.description,
        "priority_score": finding.priority_score,
    }


def _print_findings(findings: list[Finding], output_format: str) -> None:
    fmt = output_format.lower()
    rows = [_finding_to_row(f) for f in findings]

    if fmt == "json":
        typer.echo(json.dumps(rows, indent=2, default=str))
        return

    if fmt == "csv":
        headers = [
            "id",
            "type",
            "severity",
            "file",
            "line",
            "description",
            "priority_score",
        ]
        buffer = StringIO()
        writer = csv.DictWriter(buffer, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
        typer.echo(buffer.getvalue().rstrip("\n"))
        return

    table = Table(title="Scan Findings")
    table.add_column("Type", style="cyan")
    table.add_column("Severity", style="magenta")
    table.add_column("File", style="green")
    table.add_column("Line", justify="right")
    table.add_column("Description", style="white")
    for finding in findings:
        table.add_row(
            finding.type.value,
            finding.severity.value,
            finding.file,
            str(finding.line),
            finding.description,
        )
    console.print(table)


def _scan_findings(repo_path: str, config_path: str, scanner_filter: str = "all") -> list[Finding]:
    """Run enabled scanners and return all findings."""
    from codecustodian.config.schema import CodeCustodianConfig
    from codecustodian.scanner.registry import get_default_registry

    cfg = CodeCustodianConfig.from_file(config_path)
    _apply_scan_type_filter(cfg, scanner_filter)

    registry = get_default_registry(cfg)
    findings: list[Finding] = []
    for scanner_instance in registry.get_enabled():
        findings.extend(scanner_instance.scan(repo_path))
    return findings


def _filter_findings(
    findings: list[Finding],
    finding_type: str | None,
    severity: str | None,
    file_pattern: str | None,
) -> list[Finding]:
    """Filter findings by optional type/severity/file pattern."""
    filtered = findings
    if finding_type:
        expected_type = finding_type.strip().lower()
        filtered = [f for f in filtered if f.type.value == expected_type]
    if severity:
        expected_severity = severity.strip().lower()
        filtered = [f for f in filtered if f.severity.value == expected_severity]
    if file_pattern:
        needle = file_pattern.strip().lower()
        filtered = [f for f in filtered if needle in f.file.lower()]
    return filtered


@app.command()
def run(
    repo_path: str = typer.Option(".", "--repo-path", "-r", help="Path to the repository"),
    config: str = typer.Option(
        ".codecustodian.yml", "--config", "-c", help="Configuration file path"
    ),
    max_prs: int = typer.Option(5, "--max-prs", help="Maximum PRs to create"),
    scan_type: str = typer.Option("all", "--scan-type", help="Scanner filter"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without creating PRs"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress non-error output"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug mode"),
    log_file: Optional[str] = typer.Option(None, "--log-file", help="Log to file"),
    enable_work_iq: bool = typer.Option(False, "--enable-work-iq", help="Enable Work IQ"),
    azure_devops_project: Optional[str] = typer.Option(
        None,
        "--azure-devops-project",
        help="Azure DevOps project override",
    ),
    output_format: str = typer.Option(
        "table",
        "--output-format",
        help="Output format: table or json",
    ),
) -> None:
    """Run CodeCustodian on a repository."""
    from codecustodian.config.schema import CodeCustodianConfig
    from codecustodian.logging import setup_logging
    from codecustodian.pipeline import Pipeline

    # Configure logging
    log_level = "DEBUG" if debug else ("WARNING" if quiet else ("DEBUG" if verbose else "INFO"))
    setup_logging(level=log_level, log_file=log_file)

    # Load config
    cfg = CodeCustodianConfig.from_file(config)
    cfg.behavior.max_prs_per_run = max_prs
    _apply_scan_type_filter(cfg, scan_type)
    if enable_work_iq:
        cfg.work_iq.enabled = True
    if azure_devops_project:
        cfg.azure.devops_project = azure_devops_project

    output_format = output_format.lower()
    if output_format not in {"table", "json"}:
        raise typer.BadParameter("--output-format must be 'table' or 'json'")

    if not quiet and output_format == "table":
        console.print(
            Panel(
                f"[bold green]CodeCustodian v{__version__}[/]\n"
                f"Repository: {repo_path}\n"
                f"Config: {config}\n"
                f"Max PRs: {max_prs}\n"
                f"Dry run: {dry_run}",
                title="🛡️ CodeCustodian",
                border_style="green",
            )
        )

    # Run pipeline
    pipeline = Pipeline(
        config=cfg,
        repo_path=repo_path,
        dry_run=dry_run,
    )
    result = asyncio.run(pipeline.run())

    if output_format == "json":
        typer.echo(result.model_dump_json(indent=2))
        return

    # Summary
    if not quiet:
        console.print(f"\n[bold]Results:[/]")
        console.print(f"  Findings:      {len(result.findings)}")
        console.print(f"  Plans:         {len(result.plans)}")
        console.print(f"  PRs created:   {result.prs_created}")
        console.print(f"  Success rate:  {result.success_rate:.0f}%")
        console.print(f"  Duration:      {result.total_duration_seconds:.1f}s")
        if result.errors:
            console.print(f"  [red]Errors:      {len(result.errors)}[/]")


@app.command()
def version() -> None:
    """Show CodeCustodian version."""
    console.print(f"codecustodian {__version__}")


@app.command()
def init(
    path: str = typer.Argument(".", help="Repository path"),
    template: str = typer.Option(
        "full_scan",
        "--template",
        help="Policy template (security_first, deprecations_first, low_risk_maintenance, full_scan)",
    ),
) -> None:
    """Initialize CodeCustodian in a repository."""
    from codecustodian.config.defaults import get_default_config
    from codecustodian.config.policies import _deep_merge
    from codecustodian.onboarding.policy_templates import get_template

    repo_path = Path(path)
    config_file = repo_path / ".codecustodian.yml"
    workflow_file = repo_path / ".github" / "workflows" / "codecustodian.yml"

    if config_file.exists():
        console.print("[yellow]⚠ .codecustodian.yml already exists[/]")
        raise typer.Exit(1)

    try:
        template_overrides = get_template(template)
    except KeyError as exc:
        raise typer.BadParameter(str(exc)) from exc

    default_cfg = get_default_config().model_dump()
    merged_cfg = _deep_merge(default_cfg, template_overrides)

    from codecustodian.config.schema import CodeCustodianConfig

    config = CodeCustodianConfig.model_validate(merged_cfg)
    config.to_yaml(config_file)

    workflow_file.parent.mkdir(parents=True, exist_ok=True)
    workflow_file.write_text(
        "name: CodeCustodian\n"
        "on:\n"
        "  workflow_dispatch:\n"
        "jobs:\n"
        "  run:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@v4\n"
        "      - name: Setup Python\n"
        "        uses: actions/setup-python@v5\n"
        "        with:\n"
        "          python-version: '3.11'\n"
        "      - name: Install\n"
        "        run: pip install codecustodian\n"
        "      - name: Run\n"
        "        run: codecustodian run --dry-run\n"
    )

    console.print("[green]✓ Created .codecustodian.yml[/]")
    console.print("[green]✓ Created .github/workflows/codecustodian.yml[/]")
    console.print(f"  Applied template: {template}")


@app.command()
def validate(
    path: str = typer.Option(".codecustodian.yml", "--path", "-p", help="Config file path"),
) -> None:
    """Validate a CodeCustodian configuration file."""
    from codecustodian.config.schema import CodeCustodianConfig

    try:
        cfg = CodeCustodianConfig.from_file(path)
        enabled_count = sum(
            1
            for scanner_cfg in [
                cfg.scanners.deprecated_apis,
                cfg.scanners.todo_comments,
                cfg.scanners.code_smells,
                cfg.scanners.security_patterns,
                cfg.scanners.type_coverage,
            ]
            if scanner_cfg.enabled
        )
        console.print("[green]✓ Configuration is valid[/]")
        console.print(f"  Scanners enabled: {enabled_count}/5")
        console.print(f"  Max PRs: {cfg.behavior.max_prs_per_run}")
        console.print(f"  Confidence threshold: {cfg.behavior.confidence_threshold}")
        console.print(f"  Proposal threshold: {cfg.behavior.proposal_mode_threshold}")
        console.print(f"  Monthly budget: {cfg.budget.monthly_budget}")
        console.print(f"  Require PR approval: {cfg.approval.require_pr_approval}")
    except Exception as exc:
        console.print(f"[red]✗ Invalid configuration: {exc}[/]")
        raise typer.Exit(1)


@app.command(name="config")
def config_cmd(
    validate: bool = typer.Option(False, "--validate", help="Validate configuration"),
    path: str = typer.Option(".codecustodian.yml", "--path", "-p", help="Config file path"),
) -> None:
    """Manage CodeCustodian configuration."""
    if validate:
        validate_config(path)


def validate_config(path: str) -> None:
    """Compatibility helper for legacy `config --validate` invocation."""
    validate(path=path)


@app.command()
def scan(
    repo_path: str = typer.Option(".", "--repo-path", "-r", help="Repository path"),
    scanner: str = typer.Option("all", "--scanner", "-s", help="Scanner to run"),
    config: str = typer.Option(
        ".codecustodian.yml", "--config", "-c", help="Configuration file path"
    ),
    output_format: str = typer.Option(
        "table",
        "--output-format",
        help="Output format: table, json, or csv",
    ),
) -> None:
    """Run scanners without creating PRs."""
    output_format = output_format.lower()
    if output_format not in {"table", "json", "csv"}:
        raise typer.BadParameter("--output-format must be one of: table, json, csv")

    findings = _scan_findings(repo_path, config, scanner)

    _print_findings(findings, output_format)
    if output_format == "table":
        console.print(f"\n[bold]Total findings:[/] {len(findings)}")


@app.command()
def onboard(
    repo_path: str = typer.Option(".", "--repo-path", "-r", help="Repository path"),
    org: Optional[str] = typer.Option(None, "--org", help="Organization name for org-level onboarding"),
    template: str = typer.Option("full_scan", "--template", help="Onboarding template"),
) -> None:
    """Onboard a repository or organization."""
    from codecustodian.onboarding.onboard import OnboardingManager

    manager = OnboardingManager()
    if org:
        result = manager.onboard_organization(org_name=org, template=template)
        typer.echo(json.dumps(result, indent=2, default=str))
        return

    result = manager.onboard_repo(repo_path=repo_path, template=template)
    typer.echo(json.dumps(result, indent=2, default=str))


@app.command()
def status(
    repo_path: str = typer.Option(".", "--repo-path", "-r", help="Repository path"),
    config: str = typer.Option(
        ".codecustodian.yml", "--config", "-c", help="Configuration file path"
    ),
) -> None:
    """Show findings, budget, and SLA status."""
    from codecustodian.enterprise.budget_manager import BudgetManager
    from codecustodian.enterprise.sla_reporter import SLAReporter

    findings = _scan_findings(repo_path, config, "all")
    by_type: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for finding in findings:
        by_type[finding.type.value] = by_type.get(finding.type.value, 0) + 1
        by_severity[finding.severity.value] = by_severity.get(finding.severity.value, 0) + 1

    budget = BudgetManager().get_summary()
    sla_reporter = SLAReporter()
    try:
        sla = sla_reporter.generate_report(last_n=20)
    finally:
        sla_reporter.close()

    type_table = Table(title="Findings by Type")
    type_table.add_column("Type")
    type_table.add_column("Count", justify="right")
    for finding_type, count in sorted(by_type.items()):
        type_table.add_row(finding_type, str(count))

    severity_table = Table(title="Findings by Severity")
    severity_table.add_column("Severity")
    severity_table.add_column("Count", justify="right")
    for severity_name, count in sorted(by_severity.items()):
        severity_table.add_row(severity_name, str(count))

    console.print(type_table)
    console.print(severity_table)
    console.print(
        Panel(
            f"[bold]Budget[/]\n"
            f"Spent: ${budget.total_spent:.2f}\n"
            f"Remaining: ${budget.remaining:.2f}\n"
            f"Utilization: {budget.utilization_pct:.1f}%\n"
            f"\n[bold]SLA[/]\n"
            f"Runs: {sla.total_runs}\n"
            f"Success rate: {sla.success_rate:.1f}%\n"
            f"Avg duration: {sla.avg_duration_seconds:.1f}s\n"
            f"Total PRs: {sla.total_prs}",
            title="Operational Status",
            border_style="blue",
        )
    )


@app.command()
def report(
    period: Optional[str] = typer.Option(None, "--period", help="Period in YYYY-MM"),
    format: str = typer.Option("json", "--format", help="Report format: json or csv"),
    output: Optional[str] = typer.Option(None, "--output", help="Output file path"),
) -> None:
    """Generate ROI report in JSON or CSV."""
    from codecustodian.enterprise.roi_calculator import ROICalculator

    fmt = format.lower()
    if fmt not in {"json", "csv"}:
        raise typer.BadParameter("--format must be 'json' or 'csv'")

    calculator = ROICalculator()
    report_data = calculator.generate_report(period=period)

    if fmt == "json":
        payload = report_data.model_dump_json(indent=2)
        if output:
            Path(output).write_text(payload, encoding="utf-8")
            console.print(f"[green]✓ Wrote report to {output}[/]")
        else:
            typer.echo(payload)
        return

    if output:
        csv_path = calculator.export_csv(report_data, output)
        console.print(f"[green]✓ Wrote report to {csv_path}[/]")
        return

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_file = Path(temp_dir) / "roi-report.csv"
        calculator.export_csv(report_data, temp_file)
        typer.echo(temp_file.read_text(encoding="utf-8").rstrip("\n"))


@app.command()
def findings(
    repo_path: str = typer.Option(".", "--repo-path", "-r", help="Repository path"),
    config: str = typer.Option(
        ".codecustodian.yml", "--config", "-c", help="Configuration file path"
    ),
    type: Optional[str] = typer.Option(None, "--type", help="Filter by finding type"),
    severity: Optional[str] = typer.Option(None, "--severity", help="Filter by severity"),
    status: Optional[str] = typer.Option(None, "--status", help="Filter by status (open/resolved)"),
    file: Optional[str] = typer.Option(None, "--file", help="Filter by file path substring"),
    output_format: str = typer.Option("table", "--output-format", help="Output format: table, json, csv"),
) -> None:
    """List findings with filtering support."""
    if status and status.lower() not in {"open", "resolved"}:
        raise typer.BadParameter("--status must be 'open' or 'resolved'")

    output_format = output_format.lower()
    if output_format not in {"table", "json", "csv"}:
        raise typer.BadParameter("--output-format must be one of: table, json, csv")

    all_findings = _scan_findings(repo_path, config, "all")
    filtered = _filter_findings(all_findings, type, severity, file)

    if status:
        expected_open = status.lower() == "open"
        filtered = [
            finding
            for finding in filtered
            if finding.metadata.get("resolved", False) is (not expected_open)
        ]

    _print_findings(filtered, output_format)
    if output_format == "table":
        console.print(f"\n[bold]Filtered findings:[/] {len(filtered)}")


@app.command(name="create-prs")
def create_prs(
    repo_path: str = typer.Option(".", "--repo-path", "-r", help="Repository path"),
    config: str = typer.Option(
        ".codecustodian.yml", "--config", "-c", help="Configuration file path"
    ),
    top: int = typer.Option(5, "--top", help="Top N findings to process"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview mode without PR creation"),
) -> None:
    """Create PRs for top N findings via the pipeline."""
    from codecustodian.config.schema import CodeCustodianConfig
    from codecustodian.pipeline import Pipeline

    cfg = CodeCustodianConfig.from_file(config)
    cfg.behavior.max_prs_per_run = top

    pipeline = Pipeline(config=cfg, repo_path=repo_path, dry_run=dry_run)
    result = asyncio.run(pipeline.run())

    summary = {
        "findings": len(result.findings),
        "plans": len(result.plans),
        "prs_created": result.prs_created,
        "proposals": len(result.proposals),
        "errors": len(result.errors),
        "dry_run": dry_run,
    }
    typer.echo(json.dumps(summary, indent=2))


@app.command()
def interactive(
    repo_path: str = typer.Option(".", "--repo-path", "-r", help="Repository path"),
    config: str = typer.Option(
        ".codecustodian.yml", "--config", "-c", help="Configuration file path"
    ),
) -> None:
    """Interactive menu for common CodeCustodian workflows."""
    try:
        from InquirerPy import inquirer
    except Exception as exc:
        console.print(f"[red]Interactive mode requires InquirerPy: {exc}[/]")
        raise typer.Exit(1)

    while True:
        choice = inquirer.select(
            message="Choose an action:",
            choices=[
                "Show high-priority findings",
                "Create PRs for top 5 findings",
                "View cost summary & ROI",
                "Configure scanners",
                "View scan history",
                "Generate report",
                "Exit",
            ],
        ).execute()

        if choice == "Show high-priority findings":
            findings(
                repo_path=repo_path,
                config=config,
                severity="high",
                output_format="table",
            )
        elif choice == "Create PRs for top 5 findings":
            create_prs(repo_path=repo_path, config=config, top=5, dry_run=False)
        elif choice == "View cost summary & ROI":
            report(format="json")
        elif choice == "Configure scanners":
            validate(path=config)
        elif choice == "View scan history":
            status(repo_path=repo_path, config=config)
        elif choice == "Generate report":
            report(format="json")
        elif choice == "Exit":
            break


if __name__ == "__main__":
    app()
