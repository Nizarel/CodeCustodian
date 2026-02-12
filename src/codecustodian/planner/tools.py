"""Copilot SDK tool definitions.

Custom tools that the AI planner can call during multi-turn
conversations to inspect the codebase and gather context.
"""

from __future__ import annotations

import ast
from pathlib import Path

from codecustodian.logging import get_logger

logger = get_logger("planner.tools")


def get_function_definition(file_path: str, function_name: str) -> dict:
    """Get the full definition of a function including docstring.

    Used by Copilot SDK as a tool call to inspect code.
    """
    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}

    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == function_name:
                    lines = source.splitlines()
                    start = node.lineno - 1
                    end = getattr(node, "end_lineno", start + 20)
                    code = "\n".join(lines[start:end])
                    return {
                        "function": function_name,
                        "file": file_path,
                        "start_line": node.lineno,
                        "end_line": end,
                        "code": code,
                    }

        return {"error": f"Function '{function_name}' not found in {file_path}"}

    except SyntaxError as e:
        return {"error": f"Syntax error in {file_path}: {e}"}


def get_imports(file_path: str) -> dict:
    """Get all import statements from a file."""
    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}

    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append(f"{module}.{alias.name}")

        return {"file": file_path, "imports": imports}

    except SyntaxError as e:
        return {"error": f"Syntax error: {e}"}


def find_references(repo_path: str, symbol: str) -> dict:
    """Find all files referencing a symbol (simple text search)."""
    root = Path(repo_path)
    references: list[dict] = []

    for py_file in root.rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            for i, line in enumerate(content.splitlines(), start=1):
                if symbol in line:
                    references.append({
                        "file": str(py_file.relative_to(root)),
                        "line": i,
                        "text": line.strip(),
                    })
        except OSError:
            continue

    return {"symbol": symbol, "count": len(references), "references": references[:50]}


def find_tests(repo_path: str, file_path: str) -> dict:
    """Find test files that may cover a given source file."""
    root = Path(repo_path)
    source = Path(file_path)
    test_files: list[str] = []

    stem = source.stem
    tests_dir = root / "tests"

    if tests_dir.exists():
        for tf in tests_dir.rglob("test_*.py"):
            if stem in tf.stem:
                test_files.append(str(tf.relative_to(root)))

    return {
        "source": file_path,
        "test_files": test_files,
        "has_tests": len(test_files) > 0,
    }
