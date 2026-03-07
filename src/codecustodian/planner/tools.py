"""Copilot SDK tool definitions.

Custom tools decorated with ``@define_tool`` that the AI planner can
call during multi-turn conversations to inspect the codebase and
gather context.  Each tool uses a Pydantic model for typed parameters
and automatic JSON-Schema generation.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from codecustodian.logging import get_logger

logger = get_logger("planner.tools")

# Late-import helper so the module stays importable even if the SDK
# is not installed (tests mock the decorator).
try:
    from copilot import define_tool as _sdk_define_tool  # type: ignore[import-untyped]

    def define_tool(  # type: ignore[misc]
        description: str = "",
    ):
        """Wrap SDK ``define_tool`` but preserve the raw async function as ``_impl``."""
        sdk_decorator = _sdk_define_tool(description=description)

        def wrapper(fn):  # type: ignore[no-untyped-def]
            tool_obj = sdk_decorator(fn)
            tool_obj._impl = fn  # keep raw callable for testing
            return tool_obj

        return wrapper

except ImportError:  # pragma: no cover - SDK optional at import time
    # Provide a passthrough decorator so the module can be imported
    # during testing or when the SDK is not installed.
    def define_tool(  # type: ignore[misc]
        description: str = "",
    ):
        """No-op fallback when ``copilot`` is not installed."""

        def wrapper(fn):  # type: ignore[no-untyped-def]
            fn._tool_description = description
            fn._impl = fn  # same attribute for uniformity
            return fn

        return wrapper


def _get_impl(tool: Any):
    """Return the raw async callable for a tool, regardless of SDK presence."""
    return getattr(tool, "_impl", tool)


# ═══════════════════════════════════════════════════════════════════════════
# 1. get_function_definition
# ═══════════════════════════════════════════════════════════════════════════


class GetFunctionParams(BaseModel):
    """Parameters for ``get_function_definition``."""

    file_path: str = Field(description="Path to the Python file")
    function_name: str = Field(description="Name of the function to retrieve")


@define_tool(
    description=(
        "Get the full definition of a Python function or method "
        "with ±5 lines of surrounding context."
    )
)
async def get_function_definition(params: GetFunctionParams) -> str:
    """Return a numbered source listing of the requested function."""
    path = Path(params.file_path)
    if not path.exists():
        return f"File not found: {params.file_path}"

    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except SyntaxError as exc:
        return f"Syntax error in {params.file_path}: {exc}"

    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == params.function_name
        ):
            lines = source.splitlines()
            start = max(0, node.lineno - 6)
            end_line = getattr(node, "end_lineno", node.lineno + 20)
            end = min(len(lines), end_line + 5)
            numbered = "\n".join(f"{i + 1:4d} | {lines[i]}" for i in range(start, end))
            return numbered

    return f"Function '{params.function_name}' not found in {params.file_path}"


# ═══════════════════════════════════════════════════════════════════════════
# 2. get_imports
# ═══════════════════════════════════════════════════════════════════════════


class GetImportsParams(BaseModel):
    """Parameters for ``get_imports``."""

    file_path: str = Field(description="Path to the Python file")


@define_tool(description="Get all import statements from a Python file.")
async def get_imports(params: GetImportsParams) -> str:
    """Return a newline-delimited list of imports."""
    path = Path(params.file_path)
    if not path.exists():
        return f"File not found: {params.file_path}"

    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except SyntaxError as exc:
        return f"Syntax error: {exc}"

    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append(f"{module}.{alias.name}")

    if not imports:
        return "No imports found."
    return "\n".join(imports)


# ═══════════════════════════════════════════════════════════════════════════
# 3. search_references
# ═══════════════════════════════════════════════════════════════════════════


class SearchReferencesParams(BaseModel):
    """Parameters for ``search_references``."""

    symbol_name: str = Field(description="Symbol name to search for")
    directory: str = Field(default=".", description="Root directory to search in")


@define_tool(description=("Find all references to a symbol across Python files in a directory."))
async def search_references(params: SearchReferencesParams) -> str:
    """Return a summary of files and lines referencing the symbol."""
    root = Path(params.directory)
    if not root.exists():
        return f"Directory not found: {params.directory}"

    references: list[str] = []
    for py_file in root.rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8", errors="ignore")
            for i, line in enumerate(content.splitlines(), start=1):
                if params.symbol_name in line:
                    rel = py_file.relative_to(root)
                    references.append(f"{rel}:{i}: {line.strip()}")
        except OSError:
            continue

    if not references:
        return f"No references to '{params.symbol_name}' found."

    header = f"Found {len(references)} reference(s) to '{params.symbol_name}':\n"
    # Cap output to avoid huge tool returns
    return header + "\n".join(references[:50])


# ═══════════════════════════════════════════════════════════════════════════
# 4. find_test_coverage
# ═══════════════════════════════════════════════════════════════════════════


class FindTestCoverageParams(BaseModel):
    """Parameters for ``find_test_coverage``."""

    function_name: str = Field(description="Name of the function to find tests for")
    test_directory: str = Field(default="tests", description="Test directory to search")


@define_tool(description=("Find test files and test functions that cover a given function name."))
async def find_test_coverage(params: FindTestCoverageParams) -> str:
    """Return list of test files and matching test functions."""
    root = Path(params.test_directory)
    if not root.exists():
        return f"Test directory not found: {params.test_directory}"

    results: list[str] = []
    for tf in root.rglob("test_*.py"):
        try:
            source = tf.read_text(encoding="utf-8", errors="ignore")
            # Check if the function name appears anywhere in the test file
            if params.function_name not in source:
                continue
            # Find specific test functions that reference it
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef)
                ) and node.name.startswith("test_"):
                    func_body = ast.get_source_segment(source, node) or ""
                    if params.function_name in func_body:
                        results.append(f"{tf}::{node.name}")
        except (SyntaxError, OSError):
            continue

    if not results:
        return f"No tests found for '{params.function_name}'."

    return f"Found {len(results)} test(s):\n" + "\n".join(results)


# ═══════════════════════════════════════════════════════════════════════════
# 5. get_call_sites  (NEW)
# ═══════════════════════════════════════════════════════════════════════════


class GetCallSitesParams(BaseModel):
    """Parameters for ``get_call_sites``."""

    function_name: str = Field(description="Function name to locate calls for")
    directory: str = Field(default=".", description="Root directory to search")


@define_tool(
    description=("Find all call sites for a function across Python files using AST analysis.")
)
async def get_call_sites(params: GetCallSitesParams) -> str:
    """Return file:line pairs where the function is called."""
    root = Path(params.directory)
    if not root.exists():
        return f"Directory not found: {params.directory}"

    sites: list[str] = []
    for py_file in root.rglob("*.py"):
        try:
            source = py_file.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(source)
        except (SyntaxError, OSError):
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and (
                (isinstance(node.func, ast.Name) and node.func.id == params.function_name)
                or (isinstance(node.func, ast.Attribute) and node.func.attr == params.function_name)
            ):
                rel = py_file.relative_to(root)
                sites.append(f"{rel}:{node.lineno}")

    if not sites:
        return f"No call sites for '{params.function_name}' found."

    return f"Found {len(sites)} call site(s):\n" + "\n".join(sites[:50])


# ═══════════════════════════════════════════════════════════════════════════
# 6. check_type_hints  (NEW)
# ═══════════════════════════════════════════════════════════════════════════


class CheckTypeHintsParams(BaseModel):
    """Parameters for ``check_type_hints``."""

    file_path: str = Field(description="Path to the Python file")
    function_name: str = Field(description="Name of the function to inspect")


@define_tool(description=("Extract return type and parameter type annotations for a function."))
async def check_type_hints(params: CheckTypeHintsParams) -> str:
    """Return a summary of type annotations for the function."""
    path = Path(params.file_path)
    if not path.exists():
        return f"File not found: {params.file_path}"

    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except SyntaxError as exc:
        return f"Syntax error: {exc}"

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name != params.function_name:
                continue

            # Return annotation
            ret = ast.unparse(node.returns) if node.returns else "None (missing)"

            # Parameter annotations
            param_hints: list[str] = []
            for arg in node.args.args:
                ann = ast.unparse(arg.annotation) if arg.annotation else "missing"
                param_hints.append(f"  {arg.arg}: {ann}")

            lines = [
                f"Function: {params.function_name}",
                f"Return type: {ret}",
                "Parameters:",
            ]
            if param_hints:
                lines.extend(param_hints)
            else:
                lines.append("  (no parameters)")
            return "\n".join(lines)

    return f"Function '{params.function_name}' not found in {params.file_path}"


# ═══════════════════════════════════════════════════════════════════════════
# 7. get_git_history  (NEW)
# ═══════════════════════════════════════════════════════════════════════════


class GetGitHistoryParams(BaseModel):
    """Parameters for ``get_git_history``."""

    file_path: str = Field(description="Path to the file to get history for")
    max_count: int = Field(default=10, ge=1, le=50, description="Maximum number of commits")


@define_tool(description="Get recent git commit history for a file.")
async def get_git_history(params: GetGitHistoryParams) -> str:
    """Return recent commit summaries for the given file."""
    try:
        from git import Repo  # type: ignore[import-untyped]
    except ImportError:
        return "GitPython not installed — cannot retrieve history."

    path = Path(params.file_path)
    if not path.exists():
        return f"File not found: {params.file_path}"

    try:
        repo = Repo(path.parent, search_parent_directories=True)
    except Exception:
        return f"No git repository found for {params.file_path}"

    try:
        rel_path = path.relative_to(repo.working_dir)
    except ValueError:
        rel_path = path

    commits_info: list[str] = []
    for commit in repo.iter_commits(paths=str(rel_path), max_count=params.max_count):
        date = commit.authored_datetime.strftime("%Y-%m-%d")
        author = commit.author.name if commit.author else "unknown"
        summary = commit.summary[:80]
        commits_info.append(f"  {commit.hexsha[:8]} {date} ({author}): {summary}")

    if not commits_info:
        return f"No commit history found for {params.file_path}"

    return f"Last {len(commits_info)} commit(s) for {params.file_path}:\n" + "\n".join(commits_info)


# ═══════════════════════════════════════════════════════════════════════════
# 8. run_pytest_subset  (v0.15.0 — AI Test Synthesis)
# ═══════════════════════════════════════════════════════════════════════════


class RunPytestSubsetParams(BaseModel):
    """Parameters for running a subset of pytest tests."""

    test_file: str = Field(description="Path to the test file to run")
    markers: str = Field(default="", description="Optional pytest markers (-m expression)")
    timeout: int = Field(default=30, ge=5, le=120, description="Timeout in seconds")


@define_tool(
    description=(
        "Run a pytest test file (or marker-filtered subset) and return "
        "the short summary. Use this to validate AI-generated tests."
    ),
)
async def run_pytest_subset(params: RunPytestSubsetParams) -> str:
    import asyncio
    import subprocess as _sp

    test_path = Path(params.test_file).resolve()
    if not test_path.exists():
        return f"Error: test file not found: {params.test_file}"
    if test_path.suffix != ".py":
        return "Error: test file must be a .py file"

    cmd = ["python", "-m", "pytest", str(test_path), "--tb=short", "-q"]
    if params.markers:
        cmd.extend(["-m", params.markers])

    try:
        proc = await asyncio.wait_for(
            asyncio.create_subprocess_exec(
                *cmd,
                stdout=_sp.PIPE,
                stderr=_sp.PIPE,
            ),
            timeout=params.timeout,
        )
        stdout, _stderr = await proc.communicate()
        output = (stdout or b"").decode(errors="replace")[:2000]
        return f"exit_code={proc.returncode}\n{output}"
    except TimeoutError:
        return f"Error: test run timed out after {params.timeout}s"
    except Exception as exc:
        return f"Error running tests: {exc}"


# ═══════════════════════════════════════════════════════════════════════════
# 9. check_test_syntax  (v0.15.0 — AI Test Synthesis)
# ═══════════════════════════════════════════════════════════════════════════


class CheckTestSyntaxParams(BaseModel):
    """Parameters for checking test code syntax."""

    code: str = Field(description="Python test source code to validate")


@define_tool(
    description=(
        "Check whether a block of Python test code is syntactically valid. "
        "Returns the number of test functions found or syntax errors."
    ),
)
async def check_test_syntax(params: CheckTestSyntaxParams) -> str:
    try:
        tree = ast.parse(params.code)
    except SyntaxError as exc:
        return f"SyntaxError at line {exc.lineno}: {exc.msg}"

    test_count = sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    )
    return f"Valid Python — {test_count} test function(s) found"


# ═══════════════════════════════════════════════════════════════════════════
# Tool registry
# ═══════════════════════════════════════════════════════════════════════════


def get_all_tools() -> list[Any]:
    """Return all tool objects for registration with a Copilot session.

    Each tool is a ``@define_tool``-decorated async function that the SDK
    auto-registers with the session.
    """
    return [
        get_function_definition,
        get_imports,
        search_references,
        find_test_coverage,
        get_call_sites,
        check_type_hints,
        get_git_history,
        run_pytest_subset,
        check_test_syntax,
    ]
