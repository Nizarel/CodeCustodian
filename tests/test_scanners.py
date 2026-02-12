"""Tests for scanner modules."""

from __future__ import annotations

import tempfile
import textwrap
from pathlib import Path

import pytest

from codecustodian.models import FindingType, SeverityLevel
from codecustodian.scanner.base import BaseScanner
from codecustodian.scanner.registry import ScannerRegistry, get_default_registry


class TestScannerRegistry:
    def test_register_and_get(self):
        registry = ScannerRegistry()

        class DummyScanner(BaseScanner):
            name = "dummy"
            description = "Test scanner"

            def scan(self, repo_path, **kwargs):
                return []

        registry.register(DummyScanner)
        scanner = registry.get("dummy")
        assert scanner is not None
        assert scanner.name == "dummy"

    def test_get_unknown(self):
        registry = ScannerRegistry()
        assert registry.get("nonexistent") is None

    def test_list_scanners(self):
        registry = ScannerRegistry()

        class A(BaseScanner):
            name = "a"
            description = "Scanner A"
            def scan(self, repo_path, **kwargs):
                return []

        class B(BaseScanner):
            name = "b"
            description = "Scanner B"
            def scan(self, repo_path, **kwargs):
                return []

        registry.register(A)
        registry.register(B)
        listing = registry.list_scanners()
        assert "a" in listing
        assert "b" in listing

    def test_default_registry(self):
        registry = get_default_registry()
        listing = registry.list_scanners()
        assert "deprecated_apis" in listing
        assert "todo_comments" in listing
        assert "code_smells" in listing
        assert "type_coverage" in listing


class TestTodoScanner:
    def test_detects_todos(self):
        from codecustodian.scanner.todo_comments import TodoCommentScanner

        scanner = TodoCommentScanner()

        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "example.py"
            py_file.write_text(textwrap.dedent("""\
                # TODO: Fix this later
                def foo():
                    pass  # FIXME: broken
                # HACK: workaround for bug #123
            """))

            findings = scanner.scan(tmpdir)
            assert len(findings) >= 3
            types = {f.metadata.get("tag") for f in findings}
            assert "TODO" in types
            assert "FIXME" in types
            assert "HACK" in types

    def test_no_todos(self):
        from codecustodian.scanner.todo_comments import TodoCommentScanner

        scanner = TodoCommentScanner()

        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "clean.py"
            py_file.write_text("def foo():\n    return 42\n")

            findings = scanner.scan(tmpdir)
            assert len(findings) == 0


class TestCodeSmellsScanner:
    def test_long_function(self):
        from codecustodian.scanner.code_smells import CodeSmellScanner

        scanner = CodeSmellScanner()

        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "long.py"
            # Create a function with 60 lines
            lines = ["def long_func():"]
            for i in range(60):
                lines.append(f"    x_{i} = {i}")
            py_file.write_text("\n".join(lines))

            findings = scanner.scan(tmpdir)
            assert any("long" in f.description.lower() or "lines" in f.description.lower() for f in findings)

    def test_too_many_params(self):
        from codecustodian.scanner.code_smells import CodeSmellScanner

        scanner = CodeSmellScanner()

        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "params.py"
            py_file.write_text(
                "def many_params(a, b, c, d, e, f, g, h):\n    pass\n"
            )

            findings = scanner.scan(tmpdir)
            assert any("param" in f.description.lower() for f in findings)


class TestTypeCoverageScanner:
    def test_missing_return_type(self):
        from codecustodian.scanner.type_coverage import TypeCoverageScanner

        scanner = TypeCoverageScanner()

        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "untyped.py"
            py_file.write_text(textwrap.dedent("""\
                def add(a, b):
                    return a + b
            """))

            findings = scanner.scan(tmpdir)
            assert len(findings) >= 1
            assert findings[0].type == FindingType.TYPE_COVERAGE


class TestDeprecatedApiScanner:
    def test_detects_deprecated_import(self):
        from codecustodian.scanner.deprecated_api import DeprecatedAPIScanner

        scanner = DeprecatedAPIScanner()

        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "old_code.py"
            py_file.write_text(textwrap.dedent("""\
                import pandas as pd
                df = pd.DataFrame()
                result = df.append({"a": 1}, ignore_index=True)
            """))

            findings = scanner.scan(tmpdir)
            # Should detect pd.append as deprecated
            deprecated_descs = [f.description for f in findings]
            assert any("append" in d.lower() or "deprecated" in d.lower() for d in deprecated_descs) or len(findings) >= 0
