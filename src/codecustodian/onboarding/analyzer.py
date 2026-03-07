"""Onboarding module — project analysis and setup.

Analyzes a repository to auto-configure CodeCustodian
with sensible defaults based on project characteristics.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from codecustodian.config.defaults import get_default_config
from codecustodian.config.schema import CodeCustodianConfig
from codecustodian.logging import get_logger

logger = get_logger("onboarding")

# ── File-extension → language mapping ──────────────────────────────────────

_LANGUAGE_EXTENSIONS: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".cs": "csharp",
    ".rb": "ruby",
    ".rs": "rust",
    ".cpp": "cpp",
    ".c": "c",
}

_SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    ".tox",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
}


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
            # v0.14.0 — enhanced detection
            "languages": self._detect_languages(root),
            "package_managers": self._detect_package_managers(root),
            "test_frameworks": self._detect_test_frameworks(root),
            "ci_platforms": self._detect_ci_platform(root),
            "linters": self._detect_linters(root),
            "sensitive_paths": self._detect_sensitive_paths(root),
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

    def recommend_template(self, analysis: dict) -> str:
        """Auto-select the best policy template based on analysis.

        Returns:
            Template name: ``"security_first"`` | ``"deprecations_first"``
            | ``"full_scan"``.
        """
        sensitive = analysis.get("sensitive_paths", [])
        if sensitive:
            return "security_first"

        frameworks = analysis.get("frameworks", [])
        if (
            any(fw in ("django", "flask", "fastapi") for fw in frameworks)
            and "django" in frameworks
        ):
            return "security_first"

        # If the codebase is large and has many Python files, focus on deprecations
        if analysis.get("python_files", 0) > 200:
            return "deprecations_first"

        return "full_scan"

    # ── Language detection ─────────────────────────────────────────────

    @staticmethod
    def _detect_languages(root: Path) -> dict[str, int]:
        """Count source files by language."""
        counts: Counter[str] = Counter()
        for path in root.rglob("*"):
            if path.is_file() and not any(p in _SKIP_DIRS for p in path.parts):
                lang = _LANGUAGE_EXTENSIONS.get(path.suffix.lower())
                if lang:
                    counts[lang] += 1
        return dict(counts.most_common(10))

    # ── Package manager detection ──────────────────────────────────────

    @staticmethod
    def _detect_package_managers(root: Path) -> list[str]:
        """Detect which package managers are in use."""
        managers: list[str] = []
        indicators = {
            "pip": ["requirements.txt", "requirements-dev.txt"],
            "poetry": ["poetry.lock"],
            "uv": ["uv.lock"],
            "npm": ["package.json"],
            "yarn": ["yarn.lock"],
            "pnpm": ["pnpm-lock.yaml"],
            "cargo": ["Cargo.toml"],
            "go": ["go.mod"],
        }
        for manager, files in indicators.items():
            for fname in files:
                if (root / fname).exists():
                    managers.append(manager)
                    break
        return managers

    # ── Test framework detection ───────────────────────────────────────

    @staticmethod
    def _detect_test_frameworks(root: Path) -> list[str]:
        """Detect test frameworks in use."""
        frameworks: list[str] = []
        pyproject = root / "pyproject.toml"
        content = ""
        if pyproject.exists():
            content = pyproject.read_text(encoding="utf-8", errors="ignore")

        has_conftest = (root / "conftest.py").exists() or (root / "tests" / "conftest.py").exists()
        if has_conftest or "pytest" in content:
            frameworks.append("pytest")

        if "unittest" in content:
            frameworks.append("unittest")

        if (root / "jest.config.js").exists() or (root / "jest.config.ts").exists():
            frameworks.append("jest")

        package_json = root / "package.json"
        if package_json.exists():
            try:
                pkg_content = package_json.read_text(encoding="utf-8", errors="ignore")
                if '"mocha"' in pkg_content:
                    frameworks.append("mocha")
                if '"jest"' in pkg_content and "jest" not in frameworks:
                    frameworks.append("jest")
            except OSError:
                pass

        if (root / "go.mod").exists() and list(root.rglob("*_test.go")):
            frameworks.append("go-test")

        return frameworks

    # ── CI platform detection ──────────────────────────────────────────

    @staticmethod
    def _detect_ci_platform(root: Path) -> list[str]:
        """Detect CI/CD platforms configured in the repo."""
        platforms: list[str] = []
        if (root / ".github" / "workflows").is_dir():
            platforms.append("github-actions")
        if (root / "azure-pipelines.yml").exists():
            platforms.append("azure-pipelines")
        if (root / ".gitlab-ci.yml").exists():
            platforms.append("gitlab-ci")
        if (root / ".circleci").is_dir():
            platforms.append("circleci")
        if (root / "Jenkinsfile").exists():
            platforms.append("jenkins")
        if (root / ".travis.yml").exists():
            platforms.append("travis")
        return platforms

    # ── Linter detection ───────────────────────────────────────────────

    @staticmethod
    def _detect_linters(root: Path) -> list[str]:
        """Detect linter configurations present."""
        linters: list[str] = []
        pyproject = root / "pyproject.toml"
        content = ""
        if pyproject.exists():
            content = pyproject.read_text(encoding="utf-8", errors="ignore")

        if (root / "ruff.toml").exists() or "[tool.ruff]" in content:
            linters.append("ruff")
        if (
            (root / "mypy.ini").exists()
            or (root / ".mypy.ini").exists()
            or "[tool.mypy]" in content
        ):
            linters.append("mypy")
        if (root / ".eslintrc.js").exists() or (root / ".eslintrc.json").exists():
            linters.append("eslint")
        if (root / ".prettierrc").exists() or (root / ".prettierrc.json").exists():
            linters.append("prettier")
        if (root / ".flake8").exists() or "[flake8]" in content:
            linters.append("flake8")
        if (root / "setup.cfg").exists():
            try:
                setup_content = (root / "setup.cfg").read_text(encoding="utf-8", errors="ignore")
                if "[pylint" in setup_content:
                    linters.append("pylint")
            except OSError:
                pass
        return linters

    # ── Sensitive path detection ───────────────────────────────────────

    @staticmethod
    def _detect_sensitive_paths(root: Path) -> list[str]:
        """Find directories that likely contain sensitive code."""
        sensitive_names = {
            "auth",
            "authentication",
            "payments",
            "billing",
            "security",
            "crypto",
            "secrets",
            "credentials",
        }
        found: list[str] = []
        for path in root.iterdir():
            if path.is_dir() and path.name.lower() in sensitive_names:
                found.append(f"**/{path.name}/**")
        # Also check one level deeper (src/auth, app/security, etc.)
        for subdir in root.iterdir():
            if not subdir.is_dir() or subdir.name.startswith("."):
                continue
            for path in subdir.iterdir():
                if path.is_dir() and path.name.lower() in sensitive_names:
                    found.append(f"**/{path.name}/**")
        return sorted(set(found))

    # ── Existing helpers ───────────────────────────────────────────────

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
