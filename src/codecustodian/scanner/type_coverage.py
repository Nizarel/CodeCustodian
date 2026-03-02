"""Type coverage scanner.

Analyzes Python files for missing type annotations on functions
and reports per-file and overall type coverage percentages
(FR-SCAN-050 - FR-SCAN-052, FR-SCAN-104).

Optionally enriches findings with Copilot SDK type suggestions
when explicitly enabled in config.
"""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path

from codecustodian.logging import get_logger
from codecustodian.models import Finding, FindingType, SeverityLevel
from codecustodian.scanner.base import BaseScanner

logger = get_logger("scanner.type_coverage")


class TypeCoverageScanner(BaseScanner):
    """Scan for missing type annotations with per-file coverage reporting.

    When ``strict_mode`` is enabled (via config), private/dunder
    methods are also checked.
    """

    name = "type_coverage"
    description = "Detects functions missing type annotations"

    def scan(self, repo_path: str | Path) -> list[Finding]:
        findings: list[Finding] = []
        target_coverage = 80
        strict_mode = False
        ai_suggest_types = False
        ai_remaining = 0

        if self.config:
            cfg = self.config.scanners.type_coverage
            target_coverage = cfg.target_coverage
            strict_mode = cfg.strict_mode
            ai_suggest_types = cfg.ai_suggest_types
            ai_remaining = cfg.ai_max_suggestions_per_scan

        total_functions = 0
        typed_functions = 0
        per_file_stats: dict[str, dict[str, int]] = {}

        for py_file in self.find_python_files(repo_path):
            try:
                source = py_file.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(source, filename=str(py_file))
            except SyntaxError:
                continue

            file_total = 0
            file_typed = 0

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Skip private methods unless strict_mode
                    if not strict_mode:
                        if node.name.startswith("_") and not node.name.startswith("__"):
                            continue

                    total_functions += 1
                    file_total += 1

                    has_return = node.returns is not None
                    has_param_types = all(
                        arg.annotation is not None
                        for arg in node.args.args
                        if arg.arg != "self" and arg.arg != "cls"
                    )

                    if has_return and has_param_types:
                        typed_functions += 1
                        file_typed += 1
                    else:
                        missing: list[str] = []
                        if not has_return:
                            missing.append("return type")
                        if not has_param_types:
                            missing.append("parameter types")

                        ai_suggestion = None
                        if ai_suggest_types and ai_remaining > 0:
                            ai_suggestion = self._suggest_types_with_copilot(
                                node=node,
                                file_source=source,
                                file_path=str(py_file),
                            )
                            ai_remaining -= 1

                        suggestion = "Add type annotations for better IDE support and safety"
                        if ai_suggestion:
                            suggestion = f"{suggestion}. Suggested: {ai_suggestion}"

                        findings.append(
                            Finding(
                                type=FindingType.TYPE_COVERAGE,
                                severity=SeverityLevel.LOW,
                                file=str(py_file),
                                line=node.lineno,
                                description=(
                                    f"Function '{node.name}' missing: {', '.join(missing)}"
                                ),
                                suggestion=suggestion,
                                priority_score=20.0,
                                scanner_name=self.name,
                                metadata={
                                    "function_name": node.name,
                                    "missing": missing,
                                },
                            )
                        )

            if file_total > 0:
                file_key = str(py_file)
                per_file_stats[file_key] = {
                    "total": file_total,
                    "typed": file_typed,
                }
                file_coverage = file_typed / file_total * 100
                # Generate a per-file summary finding when below target
                if file_coverage < target_coverage:
                    findings.append(
                        Finding(
                            type=FindingType.TYPE_COVERAGE,
                            severity=(
                                SeverityLevel.MEDIUM
                                if file_coverage < target_coverage / 2
                                else SeverityLevel.LOW
                            ),
                            file=file_key,
                            line=1,
                            description=(
                                f"File type coverage {file_coverage:.0f}% "
                                f"({file_typed}/{file_total} functions typed, "
                                f"target: {target_coverage}%)"
                            ),
                            suggestion=(
                                f"Add type annotations to {file_total - file_typed} "
                                f"more functions to reach {target_coverage}% coverage"
                            ),
                            priority_score=25.0 + max(
                                0, (target_coverage - file_coverage) * 0.3
                            ),
                            scanner_name=self.name,
                            metadata={
                                "metric": "file_type_coverage",
                                "file_coverage": round(file_coverage, 1),
                                "total": file_total,
                                "typed": file_typed,
                            },
                        )
                    )

        overall = (typed_functions / total_functions * 100) if total_functions > 0 else 100
        logger.info(
            "Type coverage: %.1f%% (%d/%d functions typed, target: %d%%)",
            overall,
            typed_functions,
            total_functions,
            target_coverage,
        )

        return sorted(findings, key=lambda f: f.priority_score, reverse=True)

    # ── AI type suggestion stub (Phase 3) ─────────────────────────────

    @staticmethod
    def _suggest_types(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
        """Return AI-inferred type suggestions for *node*.

        .. note::

            Placeholder — will integrate GitHub Copilot SDK in Phase 3
            to provide context-aware type suggestions ranked by
            business value (FR-SCAN-104).
        """
        # Fallback stub for tests and offline environments.
        return None

    def _suggest_types_with_copilot(
        self,
        *,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        file_source: str,
        file_path: str,
    ) -> str | None:
        """Get an optional type suggestion from Copilot SDK.

        Safe guards:
        - only runs when scanner config enables it
        - skips if called from within an active event loop
        - returns ``None`` on any SDK/auth/runtime failure
        """
        if not self.config or not self.config.scanners.type_coverage.ai_suggest_types:
            return None

        try:
            asyncio.get_running_loop()
            logger.debug("Skipping AI type suggestion inside active event loop")
            return None
        except RuntimeError:
            pass

        try:
            return asyncio.run(
                self._suggest_types_with_copilot_async(
                    node=node,
                    file_source=file_source,
                    file_path=file_path,
                )
            )
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.debug("AI type suggestion unavailable: %s", exc)
            return None

    async def _suggest_types_with_copilot_async(
        self,
        *,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        file_source: str,
        file_path: str,
    ) -> str | None:
        """Async Copilot SDK call for type suggestions."""
        from codecustodian.models import SeverityLevel
        from codecustodian.planner.copilot_client import CopilotPlannerClient

        copilot_cfg = self.config.advanced.copilot
        function_source = ast.get_source_segment(file_source, node) or f"def {node.name}(...): ..."
        prompt = (
            "Suggest concise Python type annotations for this function. "
            "Return only a single signature line, no explanation.\n\n"
            f"File: {file_path}\n"
            f"Function source:\n{function_source}\n"
        )

        client = CopilotPlannerClient(copilot_cfg)
        await client.start()
        try:
            dummy_finding = type("_Finding", (), {"severity": SeverityLevel.LOW})()
            model = client.select_model(dummy_finding)
            session = await client.create_session(
                model=model,
                tools=[],
                system_prompt=(
                    "You are a Python typing assistant. "
                    "Produce accurate, minimal annotations."
                ),
            )
            response = await client.send_and_wait(
                session,
                prompt,
                timeout=min(copilot_cfg.timeout, 20),
            )
            cleaned = (response or "").strip()
            return cleaned or None
        finally:
            await client.stop()
