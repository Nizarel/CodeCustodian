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


class TestProjectAnalyzerDetection:
    """Tests for the v0.14.0 enhanced detection methods."""

    def test_detect_languages(self, tmp_path: Path) -> None:
        (tmp_path / "app.py").write_text("print('hello')\n")
        (tmp_path / "lib.js").write_text("console.log('hi');\n")
        analyzer = ProjectAnalyzer()
        langs = analyzer._detect_languages(tmp_path)
        assert "python" in langs
        assert "javascript" in langs

    def test_detect_package_managers_pip(self, tmp_path: Path) -> None:
        (tmp_path / "requirements.txt").write_text("requests>=2.0\n")
        analyzer = ProjectAnalyzer()
        pms = analyzer._detect_package_managers(tmp_path)
        assert "pip" in pms

    def test_detect_package_managers_poetry(self, tmp_path: Path) -> None:
        (tmp_path / "poetry.lock").write_text("")
        analyzer = ProjectAnalyzer()
        pms = analyzer._detect_package_managers(tmp_path)
        assert "poetry" in pms

    def test_detect_test_frameworks_pytest(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "x"\nversion = "0.1.0"\n'
            '[project.optional-dependencies]\ntest = ["pytest"]\n'
        )
        analyzer = ProjectAnalyzer()
        frameworks = analyzer._detect_test_frameworks(tmp_path)
        assert "pytest" in frameworks

    def test_detect_ci_platform_github_actions(self, tmp_path: Path) -> None:
        workflows = tmp_path / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "ci.yml").write_text("on: push\n")
        analyzer = ProjectAnalyzer()
        ci = analyzer._detect_ci_platform(tmp_path)
        assert "github-actions" in ci

    def test_detect_linters_ruff(self, tmp_path: Path) -> None:
        (tmp_path / "ruff.toml").write_text("[lint]\n")
        analyzer = ProjectAnalyzer()
        linters = analyzer._detect_linters(tmp_path)
        assert "ruff" in linters

    def test_detect_sensitive_paths(self, tmp_path: Path) -> None:
        auth_dir = tmp_path / "src" / "auth"
        auth_dir.mkdir(parents=True)
        (auth_dir / "login.py").write_text("pass\n")
        analyzer = ProjectAnalyzer()
        paths = analyzer._detect_sensitive_paths(tmp_path)
        assert len(paths) >= 1
        assert any("auth" in p for p in paths)

    def test_recommend_template_security_first(self, tmp_path: Path) -> None:
        analyzer = ProjectAnalyzer()
        analysis = {
            "sensitive_paths": ["src/auth/**"],
            "frameworks": [],
            "python_files": 50,
        }
        template = analyzer.recommend_template(analysis)
        assert template == "security_first"

    def test_recommend_template_deprecations_first(self, tmp_path: Path) -> None:
        analyzer = ProjectAnalyzer()
        analysis = {
            "sensitive_paths": [],
            "frameworks": [],
            "python_files": 300,
        }
        template = analyzer.recommend_template(analysis)
        assert template == "deprecations_first"

    def test_recommend_template_full_scan_default(self, tmp_path: Path) -> None:
        analyzer = ProjectAnalyzer()
        analysis = {
            "sensitive_paths": [],
            "frameworks": [],
            "python_files": 50,
        }
        template = analyzer.recommend_template(analysis)
        assert template == "full_scan"
