"""Tests for the reachability analysis module."""

from __future__ import annotations

from pathlib import Path

from codecustodian.intelligence.reachability import EntryPoint, ReachabilityAnalyzer
from codecustodian.models import Finding, FindingType, ReachabilityResult, SeverityLevel


def _make_finding(**overrides: object) -> Finding:
    defaults: dict[str, object] = {
        "type": FindingType.DEPRECATED_API,
        "severity": SeverityLevel.HIGH,
        "file": "src/example.py",
        "line": 10,
        "description": "Deprecated API usage",
        "suggestion": "Use modern alternative",
        "priority_score": 120.0,
    }
    defaults.update(overrides)
    return Finding(**defaults)


class TestReachabilityAnalyzer:
    """Unit tests for ReachabilityAnalyzer."""

    def _write_modules(self, root: Path, files: dict[str, str]) -> None:
        for rel_path, content in files.items():
            fp = root / rel_path
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(content)

    # ── Graph building ─────────────────────────────────────────────────

    def test_build_graph_finds_imports(self, tmp_path: Path) -> None:
        self._write_modules(
            tmp_path,
            {
                "app/__init__.py": "",
                "app/main.py": "import app.utils\n",
                "app/utils.py": "x = 1\n",
            },
        )
        analyzer = ReachabilityAnalyzer(str(tmp_path))
        analyzer.build_graph()

        # Imports are tracked at top-level package level
        assert "app" in analyzer._forward.get("app.main", set())

    def test_build_graph_from_import(self, tmp_path: Path) -> None:
        self._write_modules(
            tmp_path,
            {
                "pkg/__init__.py": "",
                "pkg/core.py": "from pkg.helpers import do_stuff\n",
                "pkg/helpers.py": "def do_stuff(): pass\n",
            },
        )
        analyzer = ReachabilityAnalyzer(str(tmp_path))
        analyzer.build_graph()

        # from X.Y import Z tracks top-level 'X'
        assert "pkg" in analyzer._forward.get("pkg.core", set())

    # ── Entry point detection ──────────────────────────────────────────

    def test_detect_flask_entry_point(self, tmp_path: Path) -> None:
        self._write_modules(
            tmp_path,
            {
                "app.py": (
                    "from flask import Flask\n"
                    "app = Flask(__name__)\n"
                    "@app.route('/hello')\n"
                    "def hello():\n"
                    "    return 'hi'\n"
                ),
            },
        )
        analyzer = ReachabilityAnalyzer(str(tmp_path))
        analyzer.build_graph()
        eps = analyzer.detect_entry_points()

        assert len(eps) >= 1
        assert any(ep.kind == "flask" for ep in eps)

    def test_detect_fastapi_entry_point(self, tmp_path: Path) -> None:
        self._write_modules(
            tmp_path,
            {
                "api.py": (
                    "from fastapi import APIRouter\n"
                    "router = APIRouter()\n"
                    "@router.get('/items')\n"
                    "def get_items():\n"
                    "    return []\n"
                ),
            },
        )
        analyzer = ReachabilityAnalyzer(str(tmp_path))
        analyzer.build_graph()
        eps = analyzer.detect_entry_points()

        assert len(eps) >= 1
        assert any(ep.kind == "fastapi" for ep in eps)

    def test_detect_main_entry_point(self, tmp_path: Path) -> None:
        self._write_modules(
            tmp_path,
            {
                "cli.py": ("if __name__ == \"__main__\":\n    print('hello')\n"),
            },
        )
        analyzer = ReachabilityAnalyzer(str(tmp_path))
        analyzer.build_graph()
        eps = analyzer.detect_entry_points()

        assert len(eps) >= 1
        assert any(ep.kind == "main" for ep in eps)

    def test_detect_lambda_entry_point(self, tmp_path: Path) -> None:
        self._write_modules(
            tmp_path,
            {
                "handler.py": ("def handler(event, context):\n    return {'statusCode': 200}\n"),
            },
        )
        analyzer = ReachabilityAnalyzer(str(tmp_path))
        analyzer.build_graph()
        eps = analyzer.detect_entry_points()

        assert len(eps) >= 1
        assert any(ep.kind == "lambda" for ep in eps)

    def test_no_entry_points_for_plain_module(self, tmp_path: Path) -> None:
        self._write_modules(
            tmp_path,
            {
                "utils.py": "def helper(): pass\n",
            },
        )
        analyzer = ReachabilityAnalyzer(str(tmp_path))
        analyzer.build_graph()
        eps = analyzer.detect_entry_points()
        assert len(eps) == 0

    # ── Reachability tracing ───────────────────────────────────────────

    def test_trace_reachability_from_entry(self, tmp_path: Path) -> None:
        """Trace reachability using top-level package imports."""
        self._write_modules(
            tmp_path,
            {
                "main.py": ('if __name__ == "__main__":\n    import utils\n'),
                "utils.py": "x = 1\n",
            },
        )
        analyzer = ReachabilityAnalyzer(str(tmp_path))
        analyzer.build_graph()

        chains = analyzer.trace_reachability("utils")
        assert len(chains) >= 1

    def test_trace_unreachable_module(self, tmp_path: Path) -> None:
        self._write_modules(
            tmp_path,
            {
                "main.py": 'if __name__ == "__main__":\n    pass\n',
                "orphan.py": "x = 1\n",
            },
        )
        analyzer = ReachabilityAnalyzer(str(tmp_path))
        analyzer.build_graph()

        chains = analyzer.trace_reachability("orphan")
        assert len(chains) == 0

    # ── Finding analysis ───────────────────────────────────────────────

    def test_analyze_finding_reachable(self, tmp_path: Path) -> None:
        self._write_modules(
            tmp_path,
            {
                "main.py": ('if __name__ == "__main__":\n    import target\n'),
                "target.py": "import os  # deprecated use\n",
            },
        )
        finding = _make_finding(file="target.py")

        analyzer = ReachabilityAnalyzer(str(tmp_path))
        analyzer.build_graph()

        result = analyzer.analyze_finding(finding)
        assert isinstance(result, ReachabilityResult)
        assert result.is_reachable is True
        assert result.reachability_tag in ("reachable", "entry_point")

    def test_analyze_finding_not_reachable(self, tmp_path: Path) -> None:
        self._write_modules(
            tmp_path,
            {
                "main.py": 'if __name__ == "__main__":\n    pass\n',
                "orphan.py": "x = 1\n",
            },
        )
        finding = _make_finding(file="orphan.py")

        analyzer = ReachabilityAnalyzer(str(tmp_path))
        analyzer.build_graph()

        result = analyzer.analyze_finding(finding)
        assert result.is_reachable is False
        assert result.reachability_tag == "internal_only"

    def test_analyze_findings_batch(self, tmp_path: Path) -> None:
        self._write_modules(
            tmp_path,
            {
                "main.py": ('if __name__ == "__main__":\n    import a\n'),
                "a.py": "x = 1\n",
                "b.py": "y = 2\n",
            },
        )
        findings = [
            _make_finding(file="a.py"),
            _make_finding(file="b.py"),
        ]

        analyzer = ReachabilityAnalyzer(str(tmp_path))
        analyzer.build_graph()

        results = analyzer.analyze_findings(findings)
        assert len(results) == 2
        assert results[0].is_reachable is True
        assert results[1].is_reachable is False


class TestEntryPointModel:
    """Validate the EntryPoint pydantic model."""

    def test_entry_point_creation(self) -> None:
        ep = EntryPoint(module="app.main", kind="flask", detail="@app.route('/api')")
        assert ep.module == "app.main"
        assert ep.kind == "flask"

    def test_entry_point_kind_values(self) -> None:
        for kind in ("flask", "fastapi", "django", "lambda", "main"):
            ep = EntryPoint(module="mod", kind=kind, detail="")
            assert ep.kind == kind
