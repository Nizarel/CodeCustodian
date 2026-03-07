"""CLI interface powered by Typer.

Entry point: ``codecustodian`` command.
"""

from __future__ import annotations

import asyncio
import csv
import difflib
import json
import sys
import tempfile
from io import StringIO
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.syntax import Syntax
from rich.table import Table

from codecustodian import __version__
from codecustodian.models import Finding

# Force UTF-8 output on Windows to avoid cp1252 encoding errors with emoji/Unicode
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

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
        "dependency_upgrades": "dependency_upgrades",
        "dependency_upgrade": "dependency_upgrades",
        "dependencies": "dependency_upgrades",
        "architectural_drift": "architectural_drift",
        "architecture": "architectural_drift",
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
        "dependency_upgrades",
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


def _print_findings(
    findings: list[Finding], output_format: str, repo_root: str | None = None
) -> None:
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

    if fmt == "sarif":
        from codecustodian.cli.sarif_formatter import findings_to_sarif

        typer.echo(findings_to_sarif(findings, repo_root=repo_root))
        return

    severity_styles = {
        "critical": "bold red",
        "high": "red",
        "medium": "yellow",
        "low": "dim",
        "info": "blue",
    }

    table = Table(title="Scan Findings")
    table.add_column("Type", style="cyan")
    table.add_column("Severity")
    table.add_column("File", style="green")
    table.add_column("Line", justify="right")
    table.add_column("Description", style="white")
    for finding in findings:
        sev = finding.severity.value
        sev_style = severity_styles.get(sev, "white")
        table.add_row(
            finding.type.value,
            f"[{sev_style}]{sev}[/]",
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
    enabled = list(registry.get_enabled())
    findings: list[Finding] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Scanning...", total=len(enabled))
        for scanner_instance in enabled:
            progress.update(task, description=f"Running {scanner_instance.name}...")
            findings.extend(scanner_instance.scan(repo_path))
            progress.advance(task)

    return findings


def _print_scan_summary(findings: list[Finding]) -> None:
    """Print a rich summary panel with severity breakdown and bar chart."""
    total = len(findings)
    if total == 0:
        console.print(
            Panel("[green]No findings detected.[/]", title="Scan Complete", border_style="green")
        )
        return

    by_severity: dict[str, int] = {}
    unique_files: set[str] = set()
    for f in findings:
        sev = f.severity.value
        by_severity[sev] = by_severity.get(sev, 0) + 1
        unique_files.add(f.file)

    severity_meta = [
        ("critical", "bold red", "🔴"),
        ("high", "red", "🟠"),
        ("medium", "yellow", "🟡"),
        ("low", "dim", "⚪"),
        ("info", "blue", "🔵"),
    ]

    lines: list[str] = [f"[bold]{total} findings[/bold] across {len(unique_files)} files\n"]
    for sev, style, icon in severity_meta:
        count = by_severity.get(sev, 0)
        if count == 0:
            continue
        pct = count / total
        bar_len = int(pct * 20)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        lines.append(f"  {icon} [{style}]{sev.upper():<9}[/] {count:>3}  {bar}  {pct:.0%}")

    # Estimated savings (industry avg: critical=4h, high=2h, medium=1h, low=0.5h)
    manual_hours = (
        by_severity.get("critical", 0) * 4
        + by_severity.get("high", 0) * 2
        + by_severity.get("medium", 0) * 1
        + by_severity.get("low", 0) * 0.5
    )
    if manual_hours > 0:
        savings = manual_hours * 85
        lines.append(
            f"\n  💰 Est. manual effort: {manual_hours:.0f}h  │  Savings: [bold green]${savings:,.0f}[/]"
        )

    lines.append("\n  [dim]Next → codecustodian run --dry-run[/]")

    console.print(
        Panel(
            "\n".join(lines),
            title="✅ Scan Complete",
            border_style="green",
            padding=(1, 2),
        )
    )


def _print_diff_preview(plans: list) -> None:
    """Render unified diffs for each plan's file changes."""
    from codecustodian.models import RefactoringPlan

    if not plans:
        return

    console.print(Panel("[bold cyan]Diff Preview (dry-run)[/]", border_style="cyan"))

    for plan in plans:
        if not isinstance(plan, RefactoringPlan):
            continue
        for change in plan.changes:
            old_lines = change.old_content.splitlines(keepends=True) if change.old_content else []
            new_lines = change.new_content.splitlines(keepends=True) if change.new_content else []
            diff = list(
                difflib.unified_diff(
                    old_lines,
                    new_lines,
                    fromfile=f"a/{change.file_path}",
                    tofile=f"b/{change.file_path}",
                    lineterm="",
                )
            )
            if not diff:
                continue
            diff_text = "\n".join(diff)
            console.print(
                Panel(
                    Syntax(diff_text, "diff", theme="monokai"),
                    title=f"📝 {change.file_path} ({change.description or change.change_type.value})",
                    border_style="cyan",
                    padding=(0, 1),
                )
            )


def _print_finding_detail(finding: Finding, repo_root: str | None = None) -> None:
    """Print a detailed Rich panel for a single finding."""

    sev_colors = {
        "critical": "bold red",
        "high": "red",
        "medium": "yellow",
        "low": "dim",
        "info": "blue",
    }
    sev = finding.severity.value
    sev_style = sev_colors.get(sev, "white")

    lines: list[str] = [
        f"[bold]ID:[/] {finding.id}",
        f"[bold]Type:[/] {finding.type.value}",
        f"[bold]Severity:[/] [{sev_style}]{sev.upper()}[/]",
        f"[bold]File:[/] {finding.file}:{finding.line}",
        f"[bold]Priority:[/] {finding.priority_score:.1f}",
        f"[bold]Business Impact:[/] {finding.business_impact_score:.1f}",
    ]
    if finding.scanner_name:
        lines.append(f"[bold]Scanner:[/] {finding.scanner_name}")
    lines.append(f"\n[bold]Description:[/]\n  {finding.description}")
    if finding.suggestion:
        lines.append(f"\n[bold]Suggestion:[/]\n  [green]{finding.suggestion}[/]")

    # Show code context if file exists
    if repo_root:
        file_path = Path(repo_root) / finding.file
        if file_path.exists():
            try:
                all_lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
                start = max(0, finding.line - 4)
                end = min(len(all_lines), (finding.end_line or finding.line) + 3)
                snippet = "\n".join(all_lines[start:end])
                lines.append(f"\n[bold]Code Context:[/] (lines {start + 1}-{end})")
                lines.append("")
                console.print(
                    Panel(
                        Syntax(
                            snippet,
                            "python",
                            line_numbers=True,
                            start_line=start + 1,
                            highlight_lines={finding.line},
                        ),
                        border_style="dim",
                        padding=(0, 1),
                    )
                )
            except Exception:
                pass

    if finding.metadata:
        interesting = {k: v for k, v in finding.metadata.items() if k not in ("dedup_key",)}
        if interesting:
            lines.append("\n[bold]Metadata:[/]")
            for k, v in interesting.items():
                lines.append(f"  {k}: {v}")

    console.print(
        Panel(
            "\n".join(lines),
            title="🔍 Finding Detail",
            border_style="blue",
            padding=(1, 2),
        )
    )


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


def _build_pr_review_summary(
    findings: list[Finding],
    healing_plan: dict[str, Any] | None = None,
    block_on: set[str] | None = None,
) -> dict[str, Any]:
    """Build a structured PR review payload from findings and optional healing data."""
    block_levels = block_on or {"critical", "high"}

    by_severity: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for finding in findings:
        sev = finding.severity.value
        by_severity[sev] = by_severity.get(sev, 0) + 1
        typ = finding.type.value
        by_type[typ] = by_type.get(typ, 0) + 1

    if by_severity.get("critical", 0) > 0:
        risk_level = "critical"
    elif by_severity.get("high", 0) > 0:
        risk_level = "high"
    elif by_severity.get("medium", 0) > 0:
        risk_level = "medium"
    elif findings:
        risk_level = "low"
    else:
        risk_level = "none"

    blocking_count = sum(by_severity.get(level, 0) for level in block_levels)
    status = "changes-requested" if blocking_count > 0 else "approved-with-notes"

    suggested_labels: list[str] = []
    if blocking_count > 0:
        suggested_labels.append("needs-fix")
    if by_type.get("security", 0) > 0:
        suggested_labels.append("security-risk")
    if by_type.get("type_coverage", 0) > 0:
        suggested_labels.append("type-issues")
    if by_type.get("dependency_upgrade", 0) > 0:
        suggested_labels.append("dependency-upgrade")

    top_findings = sorted(findings, key=lambda f: f.priority_score, reverse=True)[:10]

    summary: dict[str, Any] = {
        "status": status,
        "risk_level": risk_level,
        "blocking_issues": blocking_count,
        "total_findings": len(findings),
        "by_severity": by_severity,
        "by_type": by_type,
        "suggested_labels": suggested_labels,
        "top_findings": [
            {
                "type": finding.type.value,
                "severity": finding.severity.value,
                "file": finding.file,
                "line": finding.line,
                "description": finding.description,
                "suggestion": finding.suggestion,
                "priority_score": finding.priority_score,
            }
            for finding in top_findings
        ],
    }

    if healing_plan:
        summary["healing_plan"] = {
            "status": healing_plan.get("status", "unknown"),
            "signals": healing_plan.get("signals", []),
            "recommended_commands": healing_plan.get("recommended_commands", []),
            "patch_candidates": healing_plan.get("patch_candidates", []),
        }

    return summary


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
    log_file: str | None = typer.Option(None, "--log-file", help="Log to file"),
    enable_work_iq: bool = typer.Option(False, "--enable-work-iq", help="Enable Work IQ"),
    azure_devops_project: str | None = typer.Option(
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
        console.print("\n[bold]Results:[/]")
        console.print(f"  Findings:      {len(result.findings)}")
        console.print(f"  Plans:         {len(result.plans)}")
        console.print(f"  PRs created:   {result.prs_created}")
        console.print(f"  Success rate:  {result.success_rate:.0f}%")
        console.print(f"  Duration:      {result.total_duration_seconds:.1f}s")
        if result.cost_savings_estimate:
            cs = result.cost_savings_estimate
            console.print("\n[bold]Cost Savings Estimate:[/]")
            console.print(f"  Manual effort: {cs.get('manual_hours', 0):.1f}h")
            console.print(f"  Automated:     {cs.get('automated_hours', 0):.1f}h")
            console.print(f"  Hours saved:   {cs.get('hours_saved', 0):.1f}h")
            console.print(
                f"  [green bold]Savings:       ${cs.get('savings_usd', 0):,.2f}[/]"
                f" (@ ${cs.get('hourly_rate', 85):.0f}/hr)"
            )
        if result.errors:
            console.print(f"  [red]Errors:      {len(result.errors)}[/]")

        # Diff preview in dry-run mode
        if dry_run and result.plans:
            _print_diff_preview(result.plans)


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
                cfg.scanners.dependency_upgrades,
            ]
            if scanner_cfg.enabled
        )
        console.print("[green]✓ Configuration is valid[/]")
        console.print(f"  Scanners enabled: {enabled_count}/6")
        console.print(f"  Max PRs: {cfg.behavior.max_prs_per_run}")
        console.print(f"  Confidence threshold: {cfg.behavior.confidence_threshold}")
        console.print(f"  Proposal threshold: {cfg.behavior.proposal_mode_threshold}")
        console.print(f"  Monthly budget: {cfg.budget.monthly_budget}")
        console.print(f"  Require PR approval: {cfg.approval.require_pr_approval}")
    except Exception as exc:
        console.print(f"[red]✗ Invalid configuration: {exc}[/]")
        raise typer.Exit(1) from exc


@app.command(name="config")
def config_cmd(
    validate: bool = typer.Option(False, "--validate", help="Validate configuration"),
    show: bool = typer.Option(False, "--show", help="Show resolved configuration as JSON"),
    get: str | None = typer.Option(
        None,
        "--get",
        help="Get a specific config key (dot-notation, e.g. behavior.max_prs_per_run)",
    ),
    path: str = typer.Option(".codecustodian.yml", "--path", "-p", help="Config file path"),
) -> None:
    """Manage CodeCustodian configuration."""
    from codecustodian.config.schema import CodeCustodianConfig

    if validate:
        validate_config(path)
        return

    if show or get:
        try:
            cfg = CodeCustodianConfig.from_file(path)
        except Exception as exc:
            console.print(f"[red]✗ Failed to load config: {exc}[/]")
            raise typer.Exit(1) from exc

        data = cfg.model_dump(mode="json")
        if get:
            keys = get.split(".")
            current = data
            for key in keys:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    console.print(f"[red]Key not found: {get}[/]")
                    raise typer.Exit(1)
            typer.echo(
                json.dumps(current, indent=2) if isinstance(current, (dict, list)) else current
            )
        else:
            typer.echo(json.dumps(data, indent=2, default=str))
        return

    console.print("Usage: codecustodian config [--validate] [--show] [--get KEY] [--path FILE]")
    console.print("  --validate   Validate config file")
    console.print("  --show       Show resolved config as JSON")
    console.print("  --get KEY    Get a specific key (e.g. behavior.max_prs_per_run)")


def validate_config(path: str) -> None:
    """Compatibility helper for legacy `config --validate` invocation."""
    validate(path=path)


@app.command()
def scan(
    repo_path: str = typer.Option(".", "--repo-path", "-r", help="Repository path"),
    url: str = typer.Option("", "--url", "-u", help="Clone and scan a remote Git repo (HTTPS)"),
    scanner: str = typer.Option("all", "--scanner", "-s", help="Scanner to run"),
    config: str = typer.Option(
        ".codecustodian.yml", "--config", "-c", help="Configuration file path"
    ),
    output_format: str = typer.Option(
        "table",
        "--output-format",
        help="Output format: table, json, csv, or sarif",
    ),
) -> None:
    """Run scanners without creating PRs.

    Pass ``--url`` to shallow-clone a public Git repository and scan it.
    The clone is automatically cleaned up after scanning.
    """
    output_format = output_format.lower()
    if output_format not in {"table", "json", "csv", "sarif"}:
        raise typer.BadParameter("--output-format must be one of: table, json, csv, sarif")

    if url:
        from codecustodian.executor.repo_cloner import cleanup_clone, clone_repo

        clone_path = clone_repo(url)
        try:
            findings = _scan_findings(str(clone_path), config, scanner)
            _print_findings(findings, output_format, repo_root=str(clone_path))
            if output_format == "table":
                _print_scan_summary(findings)
        finally:
            cleanup_clone(clone_path)
        return

    findings = _scan_findings(repo_path, config, scanner)

    _print_findings(findings, output_format, repo_root=repo_path)
    if output_format == "table":
        _print_scan_summary(findings)


@app.command()
def onboard(
    repo_path: str = typer.Option(".", "--repo-path", "-r", help="Repository path"),
    org: str | None = typer.Option(
        None, "--org", help="Organization name for org-level onboarding"
    ),
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
    period: str | None = typer.Option(None, "--period", help="Period in YYYY-MM"),
    format: str = typer.Option("json", "--format", help="Report format: json, csv, or html"),
    output: str | None = typer.Option(None, "--output", help="Output file path"),
) -> None:
    """Generate ROI report in JSON, CSV, or HTML."""
    from codecustodian.enterprise.roi_calculator import ROICalculator

    fmt = format.lower()
    if fmt not in {"json", "csv", "html"}:
        raise typer.BadParameter("--format must be 'json', 'csv', or 'html'")

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

    if fmt == "html":
        html = calculator.export_html(report_data)
        out_path = Path(output) if output else Path(f"roi-report-{report_data.period}.html")
        out_path.write_text(html, encoding="utf-8")
        console.print(f"[green]✓ Wrote HTML report to {out_path}[/]")
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
    type: str | None = typer.Option(None, "--type", help="Filter by finding type"),
    severity: str | None = typer.Option(None, "--severity", help="Filter by severity"),
    status: str | None = typer.Option(None, "--status", help="Filter by status (open/resolved)"),
    file: str | None = typer.Option(None, "--file", help="Filter by file path substring"),
    output_format: str = typer.Option(
        "table", "--output-format", help="Output format: table, json, csv, sarif"
    ),
) -> None:
    """List findings with filtering support."""
    if status and status.lower() not in {"open", "resolved"}:
        raise typer.BadParameter("--status must be 'open' or 'resolved'")

    output_format = output_format.lower()
    if output_format not in {"table", "json", "csv", "sarif"}:
        raise typer.BadParameter("--output-format must be one of: table, json, csv, sarif")

    all_findings = _scan_findings(repo_path, config, "all")
    filtered = _filter_findings(all_findings, type, severity, file)

    if status:
        expected_open = status.lower() == "open"
        filtered = [
            finding
            for finding in filtered
            if finding.metadata.get("resolved", False) is (not expected_open)
        ]

    _print_findings(filtered, output_format, repo_root=repo_path)
    if output_format == "table":
        console.print(f"\n[bold]Filtered findings:[/] {len(filtered)}")


@app.command()
def finding(
    finding_id: str = typer.Argument(help="Finding ID or substring to match"),
    repo_path: str = typer.Option(".", "--repo-path", "-r", help="Repository path"),
    config: str = typer.Option(
        ".codecustodian.yml", "--config", "-c", help="Configuration file path"
    ),
) -> None:
    """Show detailed view of a single finding with code context."""
    all_findings = _scan_findings(repo_path, config, "all")
    needle = finding_id.strip().lower()
    matched = [
        f
        for f in all_findings
        if needle in f.id.lower() or needle in f.description.lower() or needle in f.file.lower()
    ]
    if not matched:
        console.print(f"[red]No finding matching '{finding_id}' found.[/]")
        raise typer.Exit(1)
    if len(matched) > 1:
        console.print(f"[yellow]Multiple matches ({len(matched)}). Showing first.[/]")
    _print_finding_detail(matched[0], repo_root=repo_path)


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
def heal(
    failure_log: str = typer.Option(..., "--failure-log", help="Path to CI failure log file"),
    output_format: str = typer.Option(
        "json", "--output-format", help="Output format: json or table"
    ),
) -> None:
    """Analyze CI failures and produce an actionable remediation plan."""
    from codecustodian.cli.ci_healer import build_healing_plan

    log_path = Path(failure_log)
    if not log_path.exists():
        raise typer.BadParameter(f"Failure log file not found: {failure_log}")

    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    plan = build_healing_plan(log_text)

    fmt = output_format.lower()
    if fmt not in {"json", "table"}:
        raise typer.BadParameter("--output-format must be 'json' or 'table'")

    if fmt == "json":
        typer.echo(json.dumps(plan, indent=2))
        return

    console.print(f"[bold]Healing status:[/] {plan['status']}")
    console.print(plan["summary"])

    signals = plan.get("signals", [])
    if signals:
        table = Table(title="Detected CI Failure Signals")
        table.add_column("Signal")
        table.add_column("Confidence", justify="right")
        table.add_column("Evidence")
        for signal in signals:
            table.add_row(
                signal["title"],
                f"{signal['confidence']:.2f}",
                signal.get("evidence", ""),
            )
        console.print(table)

    cmd_table = Table(title="Recommended Commands")
    cmd_table.add_column("Command")
    for command in plan.get("recommended_commands", []):
        cmd_table.add_row(command)
    console.print(cmd_table)

    patch_candidates = plan.get("patch_candidates", [])
    if patch_candidates:
        patch_table = Table(title="Patch Candidates")
        patch_table.add_column("Title")
        patch_table.add_column("Target")
        patch_table.add_column("Hint")
        for candidate in patch_candidates:
            target = f"{candidate.get('target_file', '')}:{candidate.get('target_line', '')}"
            patch_table.add_row(
                str(candidate.get("title", "")),
                target,
                str(candidate.get("patch_hint", "")),
            )
        console.print(patch_table)


@app.command(name="review-pr")
def review_pr(
    repo_path: str = typer.Option(".", "--repo-path", "-r", help="Repository path"),
    config: str = typer.Option(
        ".codecustodian.yml", "--config", "-c", help="Configuration file path"
    ),
    output_format: str = typer.Option(
        "json", "--output-format", help="Output format: json or table"
    ),
    healing_plan_file: str | None = typer.Option(
        None,
        "--healing-plan-file",
        help="Optional healing plan JSON file to enrich review output",
    ),
    block_on: str = typer.Option(
        "critical,high",
        "--block-on",
        help="Comma-separated severities that should block approval",
    ),
) -> None:
    """Generate a PR review summary from scan findings and optional healing plan."""
    fmt = output_format.lower()
    if fmt not in {"json", "table"}:
        raise typer.BadParameter("--output-format must be 'json' or 'table'")

    block_levels = {level.strip().lower() for level in block_on.split(",") if level.strip()}
    valid_levels = {"critical", "high", "medium", "low", "info"}
    if not block_levels.issubset(valid_levels):
        raise typer.BadParameter("--block-on must only contain: critical, high, medium, low, info")

    findings_list = _scan_findings(repo_path, config, "all")

    healing_payload: dict[str, Any] | None = None
    if healing_plan_file:
        plan_path = Path(healing_plan_file)
        if not plan_path.exists():
            raise typer.BadParameter(f"Healing plan file not found: {healing_plan_file}")
        healing_payload = json.loads(plan_path.read_text(encoding="utf-8", errors="replace"))

    review = _build_pr_review_summary(findings_list, healing_payload, block_levels)

    if fmt == "json":
        typer.echo(json.dumps(review, indent=2))
        return

    console.print(f"[bold]PR Review Status:[/] {review['status']}")
    console.print(f"Risk level: {review['risk_level']}")
    console.print(f"Blocking issues: {review['blocking_issues']}")
    console.print(f"Total findings: {review['total_findings']}")

    sev_table = Table(title="Findings by Severity")
    sev_table.add_column("Severity")
    sev_table.add_column("Count", justify="right")
    for sev, count in sorted(review["by_severity"].items()):
        sev_table.add_row(sev, str(count))
    console.print(sev_table)


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
        raise typer.Exit(1) from exc

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
