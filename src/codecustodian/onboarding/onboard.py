"""Onboarding orchestrator — org and repo self-service setup (BR-ONB-001).

Provides ``OnboardingManager`` that handles organization-level and
single-repo onboarding, generating ``.codecustodian.yml`` configurations
from policy templates and project analysis.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from codecustodian.config.defaults import get_default_config
from codecustodian.config.policies import _deep_merge
from codecustodian.logging import get_logger
from codecustodian.onboarding.analyzer import ProjectAnalyzer
from codecustodian.onboarding.policy_templates import TEMPLATES, get_template

logger = get_logger("onboarding")


class OnboardingManager:
    """Self-service onboarding for organizations and repositories.

    Args:
        github_client: Optional PyGithub ``Github`` instance for org-level ops.
        policy_templates: Override the built-in template registry.
    """

    def __init__(
        self,
        github_client: Any | None = None,
        policy_templates: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.github = github_client
        self.templates = policy_templates or TEMPLATES
        self._analyzer = ProjectAnalyzer()
        self._statuses: dict[str, str] = {}  # repo → status

    # ── Organization onboarding ────────────────────────────────────────

    def onboard_organization(
        self,
        org_name: str,
        template: str = "full_scan",
    ) -> dict[str, Any]:
        """Enroll an organization with a policy template (BR-ONB-001).

        Lists all repos via the GitHub API, filters archived /
        sensitive repos, and calls ``onboard_repo`` per eligible repo.

        Returns:
            Dict with ``configured``, ``excluded``, and ``errors`` counts.
        """
        if self.github is None:
            logger.warning("No GitHub client — running in local-only mode")
            return {"configured": 0, "excluded": 0, "errors": ["no_github_client"]}

        try:
            org = self.github.get_organization(org_name)
            repos = list(org.get_repos(type="all"))
        except Exception as exc:
            logger.error("Failed to list repos for org %s: %s", org_name, exc)
            return {"configured": 0, "excluded": 0, "errors": [str(exc)]}

        configured = 0
        excluded = 0
        errors: list[str] = []

        for repo in repos:
            if repo.archived:
                excluded += 1
                continue

            try:
                result = self.onboard_repo(repo.full_name, template=template)
                if result.get("status") == "configured":
                    configured += 1
                else:
                    errors.append(f"{repo.full_name}: {result.get('error', 'unknown')}")
            except Exception as exc:
                errors.append(f"{repo.full_name}: {exc}")

        logger.info(
            "Org onboarding complete: configured=%d, excluded=%d, errors=%d",
            configured,
            excluded,
            len(errors),
        )
        return {"configured": configured, "excluded": excluded, "errors": errors}

    # ── Single-repo onboarding ─────────────────────────────────────────

    def onboard_repo(
        self,
        repo_path: str,
        template: str = "auto",
    ) -> dict[str, Any]:
        """Onboard a single repository with a policy template.

        1. Runs ``ProjectAnalyzer.analyze()`` to detect characteristics.
        2. Auto-selects template (or uses explicit override).
        3. Merges template with defaults + analysis-driven adjustments.
        4. Auto-populates sensitive paths from detection.
        5. Optionally generates GitHub Actions workflow.
        6. Optionally runs a health check.

        Args:
            repo_path: Local filesystem path or ``owner/repo`` name.
            template: Policy template name, or ``"auto"`` for auto-selection.

        Returns:
            Status dict with ``status``, ``template``, ``config_path``,
            ``analysis``, ``workflow_path``, ``health_check``.
        """
        local_path = Path(repo_path)

        # If it looks like a local path, analyze it
        analysis = self._analyzer.analyze(local_path) if local_path.exists() else {}

        # v0.14.0 — auto-select template based on analysis
        if template == "auto" and analysis:
            template = self._analyzer.recommend_template(analysis)
            logger.info("Auto-selected template: %s", template)

        # Get template and merge with default config
        try:
            template_overrides = get_template(template)
        except KeyError as exc:
            return {"status": "error", "error": str(exc)}

        config = get_default_config()
        config_dict = config.model_dump()
        config_dict = _deep_merge(config_dict, template_overrides)

        # Adjust based on analysis
        if analysis.get("python_files", 0) > 500:
            config_dict["behavior"]["max_prs_per_run"] = 3

        if not analysis.get("has_tests"):
            config_dict["behavior"]["confidence_threshold"] = max(
                config_dict["behavior"].get("confidence_threshold", 7), 8
            )
            # Ensure proposal threshold stays valid
            if config_dict["behavior"].get("proposal_mode_threshold", 5) > config_dict["behavior"]["confidence_threshold"]:
                config_dict["behavior"]["proposal_mode_threshold"] = config_dict["behavior"]["confidence_threshold"]

        # v0.14.0 — auto-populate sensitive paths
        config_dict = self._auto_populate_sensitive_paths(analysis, config_dict)

        from codecustodian.config.schema import CodeCustodianConfig

        final_config = CodeCustodianConfig.model_validate(config_dict)

        # Write .codecustodian.yml if local path
        config_path = ""
        workflow_path = ""
        health_check_result: dict[str, Any] = {}

        if local_path.exists():
            config_path = str(local_path / ".codecustodian.yml")
            final_config.to_yaml(config_path)
            logger.info("Generated config at %s", config_path)

            # v0.14.0 — generate GitHub Actions workflow
            workflow_path = self._generate_workflow(local_path, analysis)

            # v0.14.0 — run health check
            health_check_result = self._run_health_check(local_path, final_config)

        self._statuses[repo_path] = "configured"

        return {
            "status": "configured",
            "template": template,
            "config_path": config_path,
            "analysis": analysis,
            "workflow_path": workflow_path,
            "health_check": health_check_result,
        }

    # ── v0.14.0 — Enhanced onboarding helpers ─────────────────────────

    @staticmethod
    def _auto_populate_sensitive_paths(
        analysis: dict, config_dict: dict,
    ) -> dict:
        """Merge detected sensitive paths into the approval config."""
        detected = analysis.get("sensitive_paths", [])
        if not detected:
            return config_dict

        existing = config_dict.get("approval", {}).get("sensitive_paths", [])
        merged = sorted(set(existing + detected))
        config_dict.setdefault("approval", {})["sensitive_paths"] = merged
        return config_dict

    @staticmethod
    def _generate_workflow(repo_path: Path, analysis: dict) -> str:
        """Generate a GitHub Actions workflow for CodeCustodian CI.

        Returns the path to the generated file, or empty string if
        skipped (e.g. no .github directory).
        """
        workflows_dir = repo_path / ".github" / "workflows"
        target = workflows_dir / "codecustodian-onboard.yml"

        # Don't overwrite existing workflow
        if target.exists():
            logger.info("Workflow already exists: %s", target)
            return str(target)

        ci_platforms = analysis.get("ci_platforms", [])
        if "github-actions" not in ci_platforms and not workflows_dir.exists():
            return ""

        workflows_dir.mkdir(parents=True, exist_ok=True)

        # Detect Python version from pyproject.toml or default
        python_version = "3.11"

        workflow = f"""\
name: CodeCustodian Scan

on:
  schedule:
    - cron: '0 6 * * 1'  # Weekly Monday 6am UTC
  workflow_dispatch:

permissions:
  contents: read
  pull-requests: write

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '{python_version}'

      - name: Install CodeCustodian
        run: pip install codecustodian

      - name: Run scan
        env:
          GITHUB_TOKEN: ${{{{ secrets.GITHUB_TOKEN }}}}
        run: codecustodian scan --repo-path . --output json

      - name: Run pipeline (dry-run)
        env:
          GITHUB_TOKEN: ${{{{ secrets.GITHUB_TOKEN }}}}
        run: codecustodian run --dry-run --max-prs 3
"""
        target.write_text(workflow, encoding="utf-8")
        logger.info("Generated workflow at %s", target)
        return str(target)

    @staticmethod
    def _run_health_check(
        repo_path: Path, config: Any,
    ) -> dict[str, Any]:
        """Run a quick validation that config works with the repo.

        Returns a status dict with ``passed``, ``scanners_available``,
        and ``issues``.
        """
        issues: list[str] = []

        # Check config is valid
        try:
            from codecustodian.scanner.registry import get_default_registry

            registry = get_default_registry(config)
            enabled = registry.get_enabled()
            scanner_count = len(enabled)
        except Exception as exc:
            return {"passed": False, "scanners_available": 0, "issues": [str(exc)]}

        if scanner_count == 0:
            issues.append("No scanners are enabled — check scanner configuration")

        # Check repo has scannable files
        py_files = list(repo_path.rglob("*.py"))
        if not py_files:
            issues.append("No Python files found — scanner results may be empty")

        return {
            "passed": len(issues) == 0,
            "scanners_available": scanner_count,
            "issues": issues,
        }

    # ── Status tracking ────────────────────────────────────────────────

    def get_onboarding_status(self, org_or_repo: str) -> str:
        """Return onboarding status for an org or repo.

        Returns:
            One of ``configured``, ``scanning``, ``blocked``,
            ``requires_approval``, or ``not_started``.
        """
        return self._statuses.get(org_or_repo, "not_started")
