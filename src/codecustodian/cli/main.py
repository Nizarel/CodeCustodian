"""CLI interface powered by Typer.

Entry point: ``codecustodian`` command.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from codecustodian import __version__

app = typer.Typer(
    name="codecustodian",
    help="🛡️ CodeCustodian — Autonomous AI agent for technical debt management",
    add_completion=False,
)
console = Console()


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

    if not quiet:
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
) -> None:
    """Initialize CodeCustodian in a repository."""
    from codecustodian.config.defaults import DEFAULT_YAML

    repo_path = Path(path)
    config_file = repo_path / ".codecustodian.yml"

    if config_file.exists():
        console.print("[yellow]⚠ .codecustodian.yml already exists[/]")
        raise typer.Exit(1)

    config_file.write_text(DEFAULT_YAML)
    console.print("[green]✓ Created .codecustodian.yml[/]")
    console.print("  Edit the file to customize scanner settings and behavior.")


@app.command(name="config")
def config_cmd(
    validate: bool = typer.Option(False, "--validate", help="Validate configuration"),
    path: str = typer.Option(".codecustodian.yml", "--path", "-p", help="Config file path"),
) -> None:
    """Manage CodeCustodian configuration."""
    from codecustodian.config.schema import CodeCustodianConfig

    if validate:
        try:
            cfg = CodeCustodianConfig.from_file(path)
            console.print(f"[green]✓ Configuration is valid[/]")
            console.print(f"  Scanners enabled: {sum(1 for s in [cfg.scanners.deprecated_apis, cfg.scanners.todo_comments, cfg.scanners.code_smells, cfg.scanners.security_patterns, cfg.scanners.type_coverage] if s.enabled)}/5")
            console.print(f"  Max PRs: {cfg.behavior.max_prs_per_run}")
            console.print(f"  Confidence threshold: {cfg.behavior.confidence_threshold}")
        except Exception as exc:
            console.print(f"[red]✗ Invalid configuration: {exc}[/]")
            raise typer.Exit(1)


@app.command()
def scan(
    repo_path: str = typer.Option(".", "--repo-path", "-r", help="Repository path"),
    scanner: str = typer.Option("all", "--scanner", "-s", help="Scanner to run"),
) -> None:
    """Run scanners without creating PRs."""
    console.print(f"[yellow]Scanning {repo_path} with {scanner} scanner(s)...[/]")
    # TODO: Wire up scanner registry (Phase 2)
    console.print("[dim]Scanner execution not yet implemented — coming in Phase 2[/]")


if __name__ == "__main__":
    app()
