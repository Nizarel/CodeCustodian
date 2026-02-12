"""Onboarding module — project analysis and setup.

Analyzes a repository to auto-configure CodeCustodian
with sensible defaults based on project characteristics.
"""

from __future__ import annotations

from pathlib import Path

from codecustodian.config.defaults import get_default_config
from codecustodian.config.schema import CodeCustodianConfig
from codecustodian.logging import get_logger

logger = get_logger("onboarding")


class ProjectAnalyzer:
    """Analyze a repository for auto-configuration."""

    def analyze(self, repo_path: str | Path) -> dict:
        """Analyze project structure and return characteristics."""
        root = Path(repo_path)

        characteristics = {
            "has_tests": (root / "tests").exists(),
            "has_pyproject": (root / "pyproject.toml").exists(),
            "has_setup_py": (root / "setup.py").exists(),
            "has_ci": (root / ".github" / "workflows").exists(),
            "python_files": len(list(root.rglob("*.py"))),
            "has_type_hints": self._check_type_hints(root),
            "frameworks": self._detect_frameworks(root),
        }

        logger.info("Project analysis: %s", characteristics)
        return characteristics

    def generate_config(self, repo_path: str | Path) -> CodeCustodianConfig:
        """Generate a recommended configuration based on analysis."""
        analysis = self.analyze(repo_path)
        config = get_default_config()

        # Adjust based on analysis
        if not analysis.get("has_tests"):
            config.behavior.confidence_threshold = 8  # Higher bar without tests

        if analysis.get("python_files", 0) > 500:
            config.behavior.max_prs_per_run = 3  # Limit for large repos

        return config

    @staticmethod
    def _check_type_hints(root: Path) -> bool:
        """Quick check if project uses type hints."""
        for py_file in list(root.rglob("*.py"))[:10]:
            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")
                if "-> " in content or ": str" in content or ": int" in content:
                    return True
            except OSError:
                continue
        return False

    @staticmethod
    def _detect_frameworks(root: Path) -> list[str]:
        """Detect common Python frameworks in use."""
        frameworks: list[str] = []
        indicators = {
            "django": ["manage.py", "django"],
            "flask": ["flask"],
            "fastapi": ["fastapi"],
            "pytest": ["pytest", "conftest.py"],
        }

        pyproject = root / "pyproject.toml"
        content = ""
        if pyproject.exists():
            content = pyproject.read_text(encoding="utf-8", errors="ignore")

        for framework, markers in indicators.items():
            for marker in markers:
                if marker in content or (root / marker).exists():
                    frameworks.append(framework)
                    break

        return frameworks
