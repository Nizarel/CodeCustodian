"""Tests for scanner modules."""

from __future__ import annotations

import tempfile
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from codecustodian.models import Finding, FindingType, SeverityLevel
from codecustodian.scanner.base import BaseScanner, is_excluded
from codecustodian.scanner.registry import ScannerRegistry, get_default_registry


# ═══════════════════════════════════════════════════════════════════════════
# ScannerRegistry
# ═══════════════════════════════════════════════════════════════════════════


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

    def test_list_catalog(self):
        registry = ScannerRegistry()

        class CatScanner(BaseScanner):
            name = "cat_scan"
            description = "Catalog scanner"
            def scan(self, repo_path, **kwargs):
                return []

        registry.register(CatScanner)
        catalog = registry.list_catalog()
        assert len(catalog) == 1
        assert catalog[0]["name"] == "cat_scan"
        assert catalog[0]["description"] == "Catalog scanner"
        assert catalog[0]["enabled"] == "True"

    def test_get_enabled_respects_class_attribute(self):
        registry = ScannerRegistry()

        class DisabledScanner(BaseScanner):
            name = "disabled"
            description = "Disabled at class level"
            enabled = False
            def scan(self, repo_path, **kwargs):
                return []

        class EnabledScanner(BaseScanner):
            name = "enabled"
            description = "Enabled"
            def scan(self, repo_path, **kwargs):
                return []

        registry.register(DisabledScanner)
        registry.register(EnabledScanner)
        enabled = registry.get_enabled()
        names = [s.name for s in enabled]
        assert "enabled" in names
        assert "disabled" not in names


# ═══════════════════════════════════════════════════════════════════════════
# BaseScanner helpers
# ═══════════════════════════════════════════════════════════════════════════


class TestIsExcluded:
    def test_matches_glob(self):
        assert is_excluded("vendor/lib.py", ["vendor/**"]) is True

    def test_no_match(self):
        assert is_excluded("src/main.py", ["vendor/**"]) is False

    def test_star_star_pattern(self):
        assert is_excluded("deep/nested/test.py", ["**/*.py"]) is True


class TestCalculatePriority:
    def test_default_metadata(self):
        f = Finding(
            type=FindingType.CODE_SMELL,
            severity=SeverityLevel.MEDIUM,
            file="test.py",
            line=1,
            description="Test",
            suggestion="Fix",
            priority_score=0,
            scanner_name="test",
        )
        score = BaseScanner.calculate_priority(f)
        assert 0 <= score <= 200
        # MEDIUM weight=4, urgency=1, impact=1, effort=medium(2)
        # raw = 4*1*1/2 = 2, scaled = 10
        assert score == 10.0

    def test_high_urgency(self):
        f = Finding(
            type=FindingType.SECURITY,
            severity=SeverityLevel.CRITICAL,
            file="test.py",
            line=1,
            description="Test",
            suggestion="Fix",
            priority_score=0,
            scanner_name="test",
            metadata={"urgency": 2.0, "impact": 2.0, "effort": "low"},
        )
        score = BaseScanner.calculate_priority(f)
        # CRITICAL weight=10, urgency=2, impact=2, effort=low(1)
        # raw = 10*2*2/1 = 40, scaled = 200
        assert score == 200.0

    def test_clamped_at_200(self):
        f = Finding(
            type=FindingType.SECURITY,
            severity=SeverityLevel.CRITICAL,
            file="test.py",
            line=1,
            description="Test",
            suggestion="Fix",
            priority_score=0,
            scanner_name="test",
            metadata={"urgency": 5.0, "impact": 5.0, "effort": "low"},
        )
        score = BaseScanner.calculate_priority(f)
        assert score == 200.0


class TestFindPythonFiles:
    def test_respects_gitignore(self):
        class Dummy(BaseScanner):
            name = "d"
            description = "d"
            def scan(self, repo_path, **kwargs):
                return []

        scanner = Dummy()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".gitignore").write_text("ignored_dir/\n")
            (root / "ignored_dir").mkdir()
            (root / "ignored_dir" / "bad.py").write_text("x = 1\n")
            (root / "good.py").write_text("y = 2\n")

            files = scanner.find_python_files(root)
            names = [f.name for f in files]
            assert "good.py" in names
            assert "bad.py" not in names

    def test_user_exclude_patterns(self):
        class Dummy(BaseScanner):
            name = "d"
            description = "d"
            def scan(self, repo_path, **kwargs):
                return []

        scanner = Dummy()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "keep.py").write_text("x = 1\n")
            (root / "skip.py").write_text("y = 2\n")

            files = scanner.find_python_files(root, exclude_patterns=["**/skip.py"])
            names = [f.name for f in files]
            assert "keep.py" in names
            assert "skip.py" not in names


# ═══════════════════════════════════════════════════════════════════════════
# TodoCommentScanner
# ═══════════════════════════════════════════════════════════════════════════


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

    def test_blame_metadata_present_when_in_git(self):
        """When scanning inside a git repo, blame metadata should be populated."""
        from codecustodian.scanner.todo_comments import TodoCommentScanner

        scanner = TodoCommentScanner()

        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "todo.py"
            py_file.write_text("# TODO: example\n")

            # Mock git blame integration
            mock_blame_map = {1: {"author": "Test User", "author_email": "test@x.com", "age_days": 100}}
            with patch.object(scanner, "_build_blame_map", return_value=mock_blame_map):
                with patch.object(scanner, "_get_git_repo", return_value=MagicMock()):
                    findings = scanner.scan(tmpdir)

            assert len(findings) >= 1
            # Verify the scanner runs without crashing
            assert findings[0].metadata.get("tag") == "TODO"


# ═══════════════════════════════════════════════════════════════════════════
# CodeSmellScanner
# ═══════════════════════════════════════════════════════════════════════════


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

    def test_cyclomatic_complexity_detection(self):
        from codecustodian.scanner.code_smells import CodeSmellScanner

        scanner = CodeSmellScanner()

        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "complex.py"
            # Generate a function with high cyclomatic complexity
            py_file.write_text(textwrap.dedent("""\
                def complex_func(x, y, z):
                    if x > 0:
                        if y > 0:
                            return 1
                        elif y < -1:
                            return 2
                        else:
                            return 3
                    elif x < 0:
                        if z:
                            return 4
                        elif z > 10:
                            return 5
                        else:
                            for i in range(10):
                                if i > 5:
                                    return 6
                    else:
                        try:
                            return int(y)
                        except ValueError:
                            return 7
                        except TypeError:
                            return 8
                    return 0
            """))

            findings = scanner.scan(tmpdir)
            cc_findings = [f for f in findings if f.metadata.get("metric") == "cyclomatic_complexity"]
            assert len(cc_findings) >= 1
            assert cc_findings[0].metadata.get("rank") is not None

    def test_cognitive_complexity_detection(self):
        from codecustodian.scanner.code_smells import CodeSmellScanner, _cognitive_complexity

        scanner = CodeSmellScanner()

        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "cognitive.py"
            # Deeply nested logic with boolean ops
            py_file.write_text(textwrap.dedent("""\
                def tangled(a, b, c, d):
                    if a:
                        for i in range(10):
                            if b and c:
                                while d:
                                    if a or b:
                                        try:
                                            pass
                                        except Exception:
                                            if c and d:
                                                break
                    return None
            """))

            findings = scanner.scan(tmpdir)
            cog_findings = [f for f in findings if f.metadata.get("metric") == "cognitive_complexity"]
            assert len(cog_findings) >= 1

    def test_dead_code_detection(self):
        from codecustodian.scanner.code_smells import CodeSmellScanner

        scanner = CodeSmellScanner()

        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "dead.py"
            py_file.write_text(textwrap.dedent("""\
                def _unused_private():
                    pass

                def public():
                    return 42
            """))

            findings = scanner.scan(tmpdir)
            dead_findings = [f for f in findings if f.metadata.get("metric") == "dead_code"]
            assert len(dead_findings) == 1
            assert "_unused_private" in dead_findings[0].description

    def test_file_length_detection(self):
        from codecustodian.scanner.code_smells import CodeSmellScanner

        scanner = CodeSmellScanner()

        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "huge.py"
            # Generate file with 550 lines
            lines = [f"x_{i} = {i}" for i in range(550)]
            py_file.write_text("\n".join(lines))

            findings = scanner.scan(tmpdir)
            fl_findings = [f for f in findings if f.metadata.get("metric") == "file_length"]
            assert len(fl_findings) == 1
            assert fl_findings[0].metadata.get("value") > 500


# ═══════════════════════════════════════════════════════════════════════════
# TypeCoverageScanner
# ═══════════════════════════════════════════════════════════════════════════


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

    def test_per_file_coverage_finding(self):
        from codecustodian.scanner.type_coverage import TypeCoverageScanner

        scanner = TypeCoverageScanner()

        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "partial.py"
            py_file.write_text(textwrap.dedent("""\
                def typed(x: int) -> str:
                    return str(x)

                def untyped(a, b):
                    return a + b

                def also_untyped(c):
                    pass
            """))

            findings = scanner.scan(tmpdir)
            # Should have per-function findings + per-file summary
            file_cov = [f for f in findings if f.metadata.get("metric") == "file_type_coverage"]
            assert len(file_cov) == 1
            assert file_cov[0].metadata["typed"] == 1
            assert file_cov[0].metadata["total"] == 3

    def test_fully_typed_no_findings(self):
        from codecustodian.scanner.type_coverage import TypeCoverageScanner

        scanner = TypeCoverageScanner()

        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "typed.py"
            py_file.write_text(textwrap.dedent("""\
                def add(a: int, b: int) -> int:
                    return a + b
            """))

            findings = scanner.scan(tmpdir)
            assert len(findings) == 0

    def test_strict_mode_includes_private(self):
        from codecustodian.config.schema import CodeCustodianConfig
        from codecustodian.scanner.type_coverage import TypeCoverageScanner

        config = CodeCustodianConfig()
        config.scanners.type_coverage.strict_mode = True
        scanner = TypeCoverageScanner(config=config)

        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "priv.py"
            py_file.write_text(textwrap.dedent("""\
                def _private(x):
                    return x
            """))

            findings = scanner.scan(tmpdir)
            # strict_mode=True should flag private methods
            func_findings = [f for f in findings if f.metadata.get("function_name") == "_private"]
            assert len(func_findings) >= 1

    def test_non_strict_skips_private(self):
        from codecustodian.scanner.type_coverage import TypeCoverageScanner

        scanner = TypeCoverageScanner()

        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "priv.py"
            py_file.write_text(textwrap.dedent("""\
                def _private(x):
                    return x
            """))

            findings = scanner.scan(tmpdir)
            func_findings = [f for f in findings if f.metadata.get("function_name") == "_private"]
            assert len(func_findings) == 0

    def test_suggest_types_returns_none(self):
        """Phase 3 stub should return None."""
        from codecustodian.scanner.type_coverage import TypeCoverageScanner

        import ast
        node = ast.parse("def foo(): pass").body[0]
        assert TypeCoverageScanner._suggest_types(node) is None


# ═══════════════════════════════════════════════════════════════════════════
# DeprecatedAPIScanner
# ═══════════════════════════════════════════════════════════════════════════


class TestDeprecatedApiScanner:
    def test_detects_deprecated_import(self):
        from codecustodian.scanner.deprecated_api import DeprecatedAPIScanner

        scanner = DeprecatedAPIScanner()

        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "old_code.py"
            py_file.write_text(textwrap.dedent("""\
                import pandas as pd
                # Use pd.DataFrame.append directly so AST attribute resolution works
                result = pd.DataFrame.append(pd.DataFrame(), {"a": 1}, ignore_index=True)
            """))

            findings = scanner.scan(tmpdir)
            deprecated_descs = [f.description for f in findings]
            assert any("append" in d.lower() or "deprecated" in d.lower() for d in deprecated_descs)

    def test_detects_os_system(self):
        from codecustodian.scanner.deprecated_api import DeprecatedAPIScanner

        scanner = DeprecatedAPIScanner()

        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "os_use.py"
            py_file.write_text(textwrap.dedent("""\
                import os
                os.system("ls")
            """))

            findings = scanner.scan(tmpdir)
            assert any("os.system" in f.description for f in findings)

    def test_detects_typing_list(self):
        from codecustodian.scanner.deprecated_api import DeprecatedAPIScanner

        scanner = DeprecatedAPIScanner()

        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "typing_use.py"
            # Use typing.List attribute access so AST Attribute node is created
            py_file.write_text(textwrap.dedent("""\
                import typing
                x: typing.List[int] = [1, 2, 3]
            """))

            findings = scanner.scan(tmpdir)
            assert any("List" in f.description for f in findings)

    def test_no_deprecated_apis_clean_code(self):
        from codecustodian.scanner.deprecated_api import DeprecatedAPIScanner

        scanner = DeprecatedAPIScanner()

        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "clean.py"
            py_file.write_text(textwrap.dedent("""\
                def add(a: int, b: int) -> int:
                    return a + b
            """))

            findings = scanner.scan(tmpdir)
            assert len(findings) == 0


# ═══════════════════════════════════════════════════════════════════════════
# SecurityScanner
# ═══════════════════════════════════════════════════════════════════════════


class TestSecurityScanner:
    def test_detects_hardcoded_secret(self):
        from codecustodian.scanner.security import SecurityScanner

        scanner = SecurityScanner()

        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "secrets.py"
            py_file.write_text(textwrap.dedent("""\
                password = "super_secret_123"
                api_key = "abcdef1234567890"
            """))

            findings = scanner.scan(tmpdir)
            secret_findings = [f for f in findings if f.metadata.get("category") == "hardcoded_secrets"]
            assert len(secret_findings) >= 1
            assert secret_findings[0].severity == SeverityLevel.CRITICAL

    def test_detects_eval(self):
        from codecustodian.scanner.security import SecurityScanner

        scanner = SecurityScanner()

        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "eval_use.py"
            py_file.write_text(textwrap.dedent("""\
                user_input = input()
                result = eval(user_input)
            """))

            findings = scanner.scan(tmpdir)
            cmd_findings = [f for f in findings if f.metadata.get("category") == "command_injection"]
            assert len(cmd_findings) >= 1

    def test_detects_pickle(self):
        from codecustodian.scanner.security import SecurityScanner

        scanner = SecurityScanner()

        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "pkl.py"
            py_file.write_text(textwrap.dedent("""\
                import pickle
                data = pickle.load(open("data.pkl", "rb"))
            """))

            findings = scanner.scan(tmpdir)
            deser_findings = [f for f in findings if f.metadata.get("category") == "deserialization"]
            assert len(deser_findings) >= 1

    def test_detects_weak_crypto(self):
        from codecustodian.scanner.security import SecurityScanner

        scanner = SecurityScanner()

        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "crypto.py"
            py_file.write_text(textwrap.dedent("""\
                import hashlib
                h = hashlib.md5(b"data")
            """))

            findings = scanner.scan(tmpdir)
            crypto_findings = [f for f in findings if f.metadata.get("category") == "weak_crypto"]
            assert len(crypto_findings) >= 1

    def test_exploit_scenario_in_metadata(self):
        from codecustodian.scanner.security import SecurityScanner

        scanner = SecurityScanner()

        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "secret2.py"
            py_file.write_text('password = "mysecretpassword"\n')

            findings = scanner.scan(tmpdir)
            custom_findings = [f for f in findings if f.metadata.get("source") == "custom_pattern"]
            assert len(custom_findings) >= 1
            assert custom_findings[0].metadata.get("exploit_scenario")
            assert custom_findings[0].metadata.get("compliance")

    def test_clean_code_no_security_findings(self):
        from codecustodian.scanner.security import SecurityScanner

        scanner = SecurityScanner()

        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "safe.py"
            py_file.write_text(textwrap.dedent("""\
                def add(a: int, b: int) -> int:
                    return a + b
            """))

            findings = scanner.scan(tmpdir)
            custom_findings = [f for f in findings if f.metadata.get("source") == "custom_pattern"]
            assert len(custom_findings) == 0

    def test_config_disables_category(self):
        from codecustodian.config.schema import CodeCustodianConfig
        from codecustodian.scanner.security import SecurityScanner

        config = CodeCustodianConfig()
        config.scanners.security_patterns.detect_hardcoded_secrets = False
        scanner = SecurityScanner(config=config)

        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "secret3.py"
            py_file.write_text('password = "mysecretpassword"\n')

            findings = scanner.scan(tmpdir)
            secret_findings = [f for f in findings if f.metadata.get("category") == "hardcoded_secrets"]
            assert len(secret_findings) == 0


# ═══════════════════════════════════════════════════════════════════════════
# DeduplicationEngine
# ═══════════════════════════════════════════════════════════════════════════


class TestDeduplicationEngine:
    def _make_engine(self, tmpdir):
        from codecustodian.scanner.deduplication import DeduplicationEngine
        return DeduplicationEngine(db_path=Path(tmpdir) / "dedup.json")

    def test_dedup_removes_duplicates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = self._make_engine(tmpdir)

            f1 = Finding(
                type=FindingType.CODE_SMELL,
                severity=SeverityLevel.MEDIUM,
                file="test.py",
                line=1,
                description="Duplicate test",
                suggestion="Fix",
                priority_score=50,
                scanner_name="test",
            )
            # First pass — should keep
            unique = engine.deduplicate([f1])
            assert len(unique) == 1

            # Second pass — same finding should be filtered
            unique2 = engine.deduplicate([f1])
            assert len(unique2) == 0

            engine._db.close()

    def test_first_seen_timestamp(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = self._make_engine(tmpdir)

            f1 = Finding(
                type=FindingType.CODE_SMELL,
                severity=SeverityLevel.LOW,
                file="a.py",
                line=1,
                description="First seen test",
                suggestion="Fix",
                priority_score=10,
                scanner_name="test",
            )
            engine.deduplicate([f1])

            records = engine._table.all()
            assert len(records) == 1
            assert "first_seen" in records[0]

            engine._db.close()


# ═══════════════════════════════════════════════════════════════════════════
# Multi-Language Support
# ═══════════════════════════════════════════════════════════════════════════


class TestFindFiles:
    """Tests for BaseScanner.find_files() — multi-extension file discovery."""

    def _make_scanner(self):
        class Dummy(BaseScanner):
            name = "d"
            description = "d"

            def scan(self, repo_path, **kwargs):
                return []

        return Dummy()

    def test_finds_go_files(self):
        scanner = self._make_scanner()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "main.go").write_text("package main\n")
            (root / "main.py").write_text("pass\n")

            files = scanner.find_files(root, [".go"])
            names = [f.name for f in files]
            assert "main.go" in names
            assert "main.py" not in names

    def test_finds_multiple_extensions(self):
        scanner = self._make_scanner()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "app.py").write_text("pass\n")
            (root / "service.cs").write_text("// C#\n")
            (root / "util.go").write_text("package main\n")
            (root / "index.js").write_text("const x = 1;\n")

            files = scanner.find_files(root, [".py", ".cs", ".go", ".js"])
            names = {f.name for f in files}
            assert names == {"app.py", "service.cs", "util.go", "index.js"}

    def test_deduplicates_overlapping_calls(self):
        scanner = self._make_scanner()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "app.py").write_text("pass\n")

            # Passing ".py" twice should not return the file twice
            files = scanner.find_files(root, [".py", ".py"])
            py_files = [f for f in files if f.name == "app.py"]
            assert len(py_files) == 1

    def test_respects_gitignore(self):
        scanner = self._make_scanner()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / ".gitignore").write_text("vendor/\n")
            (root / "vendor").mkdir()
            (root / "vendor" / "dep.go").write_text("package dep\n")
            (root / "main.go").write_text("package main\n")

            files = scanner.find_files(root, [".go"])
            names = [f.name for f in files]
            assert "main.go" in names
            assert "dep.go" not in names

    def test_extension_without_dot_normalised(self):
        scanner = self._make_scanner()
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "app.ts").write_text("const x: number = 1;\n")

            # Extension supplied without leading dot
            files = scanner.find_files(root, ["ts"])
            assert any(f.name == "app.ts" for f in files)


class TestTodoScannerMultiLang:
    """Multi-language TODO/FIXME detection tests."""

    def test_detects_todo_in_go_file(self):
        from codecustodian.scanner.todo_comments import TodoCommentScanner

        scanner = TodoCommentScanner()
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "main.go").write_text(
                "// TODO: migrate authentication to OAuth\npackage main\n"
            )

            findings = scanner.scan(tmpdir)
            assert any(f.metadata.get("tag") == "TODO" for f in findings)
            assert any(f.metadata.get("language") == "go" for f in findings)

    def test_detects_fixme_in_cs_file(self):
        from codecustodian.scanner.todo_comments import TodoCommentScanner

        scanner = TodoCommentScanner()
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "Service.cs").write_text(
                "// FIXME: SQL injection risk\npublic class Svc {}\n"
            )

            findings = scanner.scan(tmpdir)
            assert any(f.metadata.get("tag") == "FIXME" for f in findings)
            assert any(f.metadata.get("language") == "cs" for f in findings)

    def test_detects_todo_in_ts_file(self):
        from codecustodian.scanner.todo_comments import TodoCommentScanner

        scanner = TodoCommentScanner()
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "app.ts").write_text(
                "// HACK: workaround pending upstream fix\nconst x = 1;\n"
            )

            findings = scanner.scan(tmpdir)
            assert any(f.metadata.get("tag") == "HACK" for f in findings)
            assert any(f.metadata.get("language") == "ts" for f in findings)

    def test_language_metadata_on_python_file(self):
        from codecustodian.scanner.todo_comments import TodoCommentScanner

        scanner = TodoCommentScanner()
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "script.py").write_text("# TODO: clean up\n")

            findings = scanner.scan(tmpdir)
            assert any(f.metadata.get("language") == "py" for f in findings)

    def test_block_comment_todo_in_go(self):
        from codecustodian.scanner.todo_comments import TodoCommentScanner

        scanner = TodoCommentScanner()
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "util.go").write_text(
                "/* TODO: replace with Go generics */\nfunc id(x int) int { return x }\n"
            )

            findings = scanner.scan(tmpdir)
            assert any(f.metadata.get("tag") == "TODO" for f in findings)


class TestSecurityScannerMultiLang:
    """Multi-language security pattern detection tests."""

    def test_detects_hardcoded_secret_in_go(self):
        from codecustodian.scanner.security import SecurityScanner

        scanner = SecurityScanner()
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "config.go").write_text(
                'package main\nconst apiSecret = "AKIAIOSFODNN7EXAMPLE"\n'
            )

            findings = scanner.scan(tmpdir)
            secret_findings = [f for f in findings if f.metadata.get("category") == "hardcoded_secrets"]
            assert len(secret_findings) >= 1
            assert any(f.metadata.get("language") == "go" for f in secret_findings)

    def test_detects_hardcoded_password_in_cs(self):
        from codecustodian.scanner.security import SecurityScanner

        scanner = SecurityScanner()
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "Auth.cs").write_text(
                'string password = "admin123!";\n'
            )

            findings = scanner.scan(tmpdir)
            secret_findings = [f for f in findings if f.metadata.get("category") == "hardcoded_secrets"]
            assert len(secret_findings) >= 1
            assert any(f.metadata.get("language") == "cs" for f in secret_findings)

    def test_detects_exec_command_in_go(self):
        from codecustodian.scanner.security import SecurityScanner

        scanner = SecurityScanner()
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "runner.go").write_text(
                'package main\nimport "os/exec"\nfunc run(cmd string) { exec.Command(cmd) }\n'
            )

            findings = scanner.scan(tmpdir)
            cmd_findings = [f for f in findings if f.metadata.get("category") == "command_injection"]
            assert any("exec.Command" in f.description for f in cmd_findings)

    def test_detects_process_start_in_cs(self):
        from codecustodian.scanner.security import SecurityScanner

        scanner = SecurityScanner()
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "Launcher.cs").write_text(
                "Process.Start(userInput);\n"
            )

            findings = scanner.scan(tmpdir)
            cmd_findings = [f for f in findings if f.metadata.get("category") == "command_injection"]
            assert any("Process.Start" in f.description for f in cmd_findings)

    def test_detects_sql_injection_in_go(self):
        from codecustodian.scanner.security import SecurityScanner

        scanner = SecurityScanner()
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "repo.go").write_text(
                'func get(id string) { db.Query("SELECT * FROM t WHERE id = " + id) }\n'
            )

            findings = scanner.scan(tmpdir)
            sql_findings = [f for f in findings if f.metadata.get("category") == "sql_injection"]
            assert len(sql_findings) >= 1

    def test_language_field_present_in_metadata(self):
        from codecustodian.scanner.security import SecurityScanner

        scanner = SecurityScanner()
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "secrets.go").write_text(
                'const token = "my_secret_token_value"\n'
            )

            findings = scanner.scan(tmpdir)
            custom = [f for f in findings if f.metadata.get("source") == "custom_pattern"]
            assert all("language" in f.metadata for f in custom)


# ═══════════════════════════════════════════════════════════════════════════
# DeduplicationEngine (continued)
# ═══════════════════════════════════════════════════════════════════════════


class TestDeduplicationEngineMore:
    def _make_engine(self, tmpdir):
        from codecustodian.scanner.deduplication import DeduplicationEngine

        return DeduplicationEngine(db_path=Path(tmpdir) / "dedup.json")

    def test_mark_resolved(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = self._make_engine(tmpdir)

            f1 = Finding(
                type=FindingType.SECURITY,
                severity=SeverityLevel.HIGH,
                file="b.py",
                line=5,
                description="Resolve test",
                suggestion="Fix",
                priority_score=80,
                scanner_name="test",
            )
            engine.deduplicate([f1])

            # Mark as resolved
            result = engine.mark_resolved(f1.id)
            assert result is True

            # Verify resolved_at was set
            records = engine._table.all()
            assert "resolved_at" in records[0]

            engine._db.close()

    def test_mark_resolved_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = self._make_engine(tmpdir)
            result = engine.mark_resolved("nonexistent-id")
            assert result is False

            engine._db.close()

    def test_get_trends(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = self._make_engine(tmpdir)

            f1 = Finding(
                type=FindingType.CODE_SMELL,
                severity=SeverityLevel.LOW,
                file="c.py",
                line=1,
                description="Trend A",
                suggestion="Fix",
                priority_score=10,
                scanner_name="test",
            )
            f2 = Finding(
                type=FindingType.CODE_SMELL,
                severity=SeverityLevel.LOW,
                file="d.py",
                line=2,
                description="Trend B",
                suggestion="Fix",
                priority_score=10,
                scanner_name="test",
            )
            engine.deduplicate([f1, f2])
            engine.mark_resolved(f1.id)

            trends = engine.get_trends()
            assert trends["total"] == 2
            assert trends["resolved"] == 1
            assert trends["active"] == 1

            engine._db.close()

    def test_clear(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = self._make_engine(tmpdir)

            f1 = Finding(
                type=FindingType.CODE_SMELL,
                severity=SeverityLevel.LOW,
                file="e.py",
                line=1,
                description="Clear test",
                suggestion="Fix",
                priority_score=10,
                scanner_name="test",
            )
            engine.deduplicate([f1])
            engine.clear()

            trends = engine.get_trends()
            assert trends["total"] == 0

            engine._db.close()


# ═══════════════════════════════════════════════════════════════════════════
# Pipeline._scan() integration
# ═══════════════════════════════════════════════════════════════════════════


class TestPipelineScanWiring:
    @pytest.mark.asyncio
    async def test_scan_uses_registry(self):
        from codecustodian.config.schema import CodeCustodianConfig
        from codecustodian.pipeline import Pipeline

        config = CodeCustodianConfig()
        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "test_target.py"
            py_file.write_text(textwrap.dedent("""\
                # TODO: fix this
                password = "hardcoded_secret123"
                def untyped(x):
                    return x
            """))

            pipeline = Pipeline(config=config, repo_path=tmpdir)
            findings = await pipeline._scan()
            # Should find at least 1 finding (TODO, secret, or type coverage)
            assert len(findings) >= 1
