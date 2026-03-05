"""AI Test Synthesis engine.

Uses the Copilot SDK to generate regression tests for findings, then
validates them via AST parsing + subprocess execution against the
original code.  Tests that pass on the original code are kept; tests
that fail are discarded with a reason.

Flow:
    1. Ask the AI to generate a pytest test for the finding
    2. Parse the response for valid Python (ast.parse)
    3. Write to a temp file and execute via ``pytest --tb=short``
    4. Populate ``TestSynthesisResult`` with pass/fail + errors
"""

from __future__ import annotations

import ast
import asyncio
import contextlib
import subprocess
import tempfile
import textwrap
from pathlib import Path
from typing import TYPE_CHECKING, Any

from codecustodian.logging import get_logger
from codecustodian.models import CodeContext, Finding, TestSynthesisResult

if TYPE_CHECKING:
    from codecustodian.config.schema import TestSynthesisConfig

logger = get_logger("planner.test_synthesizer")

# ── Prompt template ──────────────────────────────────────────────────

_SYNTH_PROMPT = textwrap.dedent("""\
    Generate a pytest test for the following code finding.

    **Finding:**
    - Type: {finding_type}
    - File: {file_path}
    - Line: {line}
    - Description: {description}

    **Surrounding code:**
    ```python
    {code_snippet}
    ```

    Requirements:
    1. Produce ONLY valid Python source — no markdown fencing.
    2. Import the module under test using a relative or absolute import.
    3. Write one or more ``test_*`` functions using ``pytest``.
    4. Each test must assert expected behaviour of the *current* code
       (pre-refactor) so it can serve as a regression guard.
    5. Do not use ``unittest.mock`` unless strictly necessary.
    6. Keep tests concise — no docstrings longer than one line.
""")


class TestSynthesizer:
    """Generates and validates AI-synthesised tests for findings."""

    def __init__(
        self,
        config: TestSynthesisConfig,
        copilot_client: Any | None = None,
    ) -> None:
        self.config = config
        self.client = copilot_client
        self._session: Any | None = None

    # ── public API ────────────────────────────────────────────────────

    async def synthesize(
        self,
        finding: Finding,
        context: CodeContext,
        session: Any | None = None,
    ) -> TestSynthesisResult:
        """Generate a test for *finding*, validate it, and return the result."""
        if not self.config.enabled:
            return TestSynthesisResult(
                finding_id=finding.id,
                discarded=True,
                discard_reason="test_synthesis disabled in config",
            )

        prompt = _SYNTH_PROMPT.format(
            finding_type=finding.type.value,
            file_path=finding.file,
            line=finding.line,
            description=finding.description,
            code_snippet=context.source_code[:2000],
        )

        # ── Ask the AI ────────────────────────────────────────────────
        raw_code = await self._ask_ai(prompt, session)
        if not raw_code:
            return TestSynthesisResult(
                finding_id=finding.id,
                discarded=True,
                discard_reason="AI returned empty response",
            )

        # ── Strip markdown fencing ────────────────────────────────────
        test_code = self._strip_fencing(raw_code)

        # ── Validate syntax ───────────────────────────────────────────
        syntax_errors = self._check_syntax(test_code)
        if syntax_errors:
            return TestSynthesisResult(
                finding_id=finding.id,
                test_code=test_code,
                validation_errors=syntax_errors,
                discarded=True,
                discard_reason="syntax error",
            )

        # ── Run against original code ─────────────────────────────────
        passed, errors = await self._run_test(test_code)
        test_count = self._count_tests(test_code)

        result = TestSynthesisResult(
            finding_id=finding.id,
            test_code=test_code,
            test_count=test_count,
            passed_original=passed,
            validation_errors=errors,
        )

        if not passed and self.config.require_passing_original:
            result.discarded = True
            result.discard_reason = "test failed on original code"

        logger.info(
            "Synthesised %d test(s) for %s — passed=%s discarded=%s",
            test_count,
            finding.id,
            passed,
            result.discarded,
        )
        return result

    async def synthesize_batch(
        self,
        findings: list[Finding],
        contexts: dict[str, CodeContext],
        session: Any | None = None,
    ) -> list[TestSynthesisResult]:
        """Synthesise tests for up to ``max_per_run`` findings."""
        results: list[TestSynthesisResult] = []
        for finding in findings[: self.config.max_per_run]:
            ctx = contexts.get(finding.id)
            if ctx is None:
                results.append(
                    TestSynthesisResult(
                        finding_id=finding.id,
                        discarded=True,
                        discard_reason="no code context available",
                    )
                )
                continue
            result = await self.synthesize(finding, ctx, session=session)
            results.append(result)
        return results

    # ── internals ─────────────────────────────────────────────────────

    async def _ask_ai(self, prompt: str, session: Any | None = None) -> str:
        """Send prompt to the Copilot SDK and return raw text."""
        target = session or self._session
        if target is None or self.client is None:
            logger.warning("No Copilot session — returning empty test code")
            return ""
        try:
            return await self.client.send_and_wait(target, prompt)
        except Exception:
            logger.exception("AI test synthesis call failed")
            return ""

    @staticmethod
    def _strip_fencing(text: str) -> str:
        """Remove markdown code fences from AI output."""
        lines = text.strip().splitlines()
        out: list[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("```"):
                continue
            out.append(line)
        return "\n".join(out).strip()

    @staticmethod
    def _check_syntax(code: str) -> list[str]:
        """Return syntax errors if code cannot be parsed."""
        try:
            ast.parse(code)
            return []
        except SyntaxError as exc:
            return [f"SyntaxError at line {exc.lineno}: {exc.msg}"]

    @staticmethod
    def _count_tests(code: str) -> int:
        """Count test functions in code."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return 0
        return sum(
            1
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("test_")
        )

    async def _run_test(self, test_code: str) -> tuple[bool, list[str]]:
        """Write test to a temp file and run with pytest."""
        errors: list[str] = []
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix="_synth_test.py",
                delete=False,
            ) as tmp:
                tmp.write(test_code)
                tmp_path = tmp.name

            proc = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    "python",
                    "-m",
                    "pytest",
                    tmp_path,
                    "--tb=short",
                    "-q",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                ),
                timeout=self.config.timeout_per_test,
            )
            stdout, _stderr = await proc.communicate()
            passed = proc.returncode == 0
            if not passed:
                output = (stdout or b"").decode(errors="replace")
                errors.append(output[:500])
        except TimeoutError:
            errors.append(f"Test execution timed out after {self.config.timeout_per_test}s")
            passed = False
        except Exception as exc:
            errors.append(f"Test execution error: {exc}")
            passed = False
        finally:
            with contextlib.suppress(Exception):
                Path(tmp_path).unlink(missing_ok=True)
        return passed, errors
