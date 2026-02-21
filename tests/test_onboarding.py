"""Tests for onboarding analyzer, templates, and manager."""

from __future__ import annotations

from pathlib import Path

from codecustodian.config.schema import CodeCustodianConfig
from codecustodian.onboarding.analyzer import ProjectAnalyzer
from codecustodian.onboarding.onboard import OnboardingManager
from codecustodian.onboarding.policy_templates import get_template, list_templates


FIXTURE_REPO = Path("tests/fixtures/sample_repo")


class TestProjectAnalyzer:
    def test_analyze_fixture_repo(self) -> None:
        analyzer = ProjectAnalyzer()
        result = analyzer.analyze(FIXTURE_REPO)

        assert result["has_pyproject"] is True
        assert result["python_files"] >= 2
        assert isinstance(result["frameworks"], list)

    def test_generate_config_returns_model(self) -> None:
        analyzer = ProjectAnalyzer()
        config = analyzer.generate_config(FIXTURE_REPO)
        assert isinstance(config, CodeCustodianConfig)
        assert config.behavior.max_prs_per_run >= 1


class TestPolicyTemplates:
    def test_list_templates_contains_all_expected(self) -> None:
        templates = list_templates()
        assert "security_first" in templates
        assert "deprecations_first" in templates
        assert "low_risk_maintenance" in templates
        assert "full_scan" in templates

    def test_get_template_valid(self) -> None:
        template = get_template("security_first")
        assert template["scanners"]["security_patterns"]["enabled"] is True

    def test_get_template_invalid_raises(self) -> None:
        try:
            get_template("does_not_exist")
            raise AssertionError("Expected KeyError")
        except KeyError:
            pass


class TestOnboardingManager:
    def test_onboard_repo_local_path(self, tmp_path: Path) -> None:
        repo = tmp_path / "repo"
        repo.mkdir(parents=True)
        (repo / "pyproject.toml").write_text('[project]\nname="demo"\nversion="0.1.0"\n')

        manager = OnboardingManager()
        result = manager.onboard_repo(str(repo), template="full_scan")

        assert result["status"] == "configured"
        assert (repo / ".codecustodian.yml").exists()
        assert manager.get_onboarding_status(str(repo)) == "configured"

    def test_onboard_org_without_github_client(self) -> None:
        manager = OnboardingManager(github_client=None)
        result = manager.onboard_organization("my-org", template="full_scan")
        assert result["configured"] == 0
        assert result["errors"] == ["no_github_client"]
