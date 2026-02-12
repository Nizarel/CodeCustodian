"""Onboarding orchestrator — org and repo self-service setup (BR-ONB-001).

Provides ``OnboardingManager`` that handles organization-level and
single-repo onboarding, generating ``.codecustodian.yml`` configurations
from policy templates and project analysis.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from codecustodian.config.defaults import get_default_config
from codecustodian.config.policies import PolicyManager, _deep_merge
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
        template: str = "full_scan",
    ) -> dict[str, Any]:
        """Onboard a single repository with a policy template.

        1. Runs ``ProjectAnalyzer.analyze()`` to detect characteristics.
        2. Selects / merges the policy template.
        3. Generates ``.codecustodian.yml``.

        Args:
            repo_path: Local filesystem path or ``owner/repo`` name.
            template: Policy template name (see ``policy_templates.py``).

        Returns:
            Status dict with ``status``, ``template``, ``config_path``.
        """
        local_path = Path(repo_path)

        # If it looks like a local path, analyze it
        if local_path.exists():
            analysis = self._analyzer.analyze(local_path)
        else:
            analysis = {}

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

        from codecustodian.config.schema import CodeCustodianConfig

        final_config = CodeCustodianConfig.model_validate(config_dict)

        # Write .codecustodian.yml if local path
        config_path = ""
        if local_path.exists():
            config_path = str(local_path / ".codecustodian.yml")
            final_config.to_yaml(config_path)
            logger.info("Generated config at %s", config_path)

        self._statuses[repo_path] = "configured"

        return {
            "status": "configured",
            "template": template,
            "config_path": config_path,
            "analysis": analysis,
        }

    # ── Status tracking ────────────────────────────────────────────────

    def get_onboarding_status(self, org_or_repo: str) -> str:
        """Return onboarding status for an org or repo.

        Returns:
            One of ``configured``, ``scanning``, ``blocked``,
            ``requires_approval``, or ``not_started``.
        """
        return self._statuses.get(org_or_repo, "not_started")
