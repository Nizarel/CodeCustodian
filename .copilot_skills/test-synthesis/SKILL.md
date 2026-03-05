---
name: test-synthesis
description: AI-powered regression test generation for code findings
---

# Test Synthesis Skill

## Purpose

Generate pytest regression tests for code findings so that refactored
code has an automated safety net **before** changes are applied.

## Workflow

1. **Inspect** the finding's surrounding code via `get_function_definition` and `get_imports`.
2. **Check existing coverage** with `find_test_coverage` to avoid duplicating existing tests.
3. **Generate** a pytest test that exercises the *current* (pre-refactor) behaviour.
4. **Validate syntax** with `check_test_syntax` — must pass `ast.parse`.
5. **Run** the test with `run_pytest_subset` — must pass on the original code.
6. **Discard** any test that fails syntax validation or runtime execution.

## Test Guidelines

- Each test function should start with `test_` and target one logical behaviour.
- Prefer a direct import of the module under test.
- Use `pytest.raises` for expected exceptions.
- Keep tests under 30 lines — no complex fixtures unless required.
- Avoid `unittest.mock.patch` unless the function has side effects that can't be isolated.
- Include a one-line docstring describing what the test verifies.

## Quality Gate

A synthesised test is kept only when:

| Check          | Requirement                |
|---------------|---------------------------|
| Syntax         | `ast.parse(code)` succeeds |
| Original pass  | `pytest` exit code 0       |
| Test count     | At least 1 `test_*` func   |
