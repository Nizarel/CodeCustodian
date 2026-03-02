"""Prompt templates for the AI planner.

System and user prompts for Copilot SDK conversations,
designed for safe and accurate refactoring suggestions.
Includes per-finding-type variants and token-budget management.
"""

from __future__ import annotations

from codecustodian.models import CodeContext, Finding, FindingType

# ── System prompt ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are CodeCustodian, an expert Python refactoring assistant. Your job is to
transform deprecated or problematic code into modern, maintainable equivalents
while preserving exact functionality.

Core Principles:
1. Preserve behavior: Never change what the code does, only how it does it
2. Minimal changes: Only modify what's necessary to fix the issue
3. Type safety: Maintain or improve type annotations
4. Readability: Prefer clarity over cleverness
5. Test compatibility: Ensure existing tests still pass

Output Format — JSON following this schema:
{
  "summary": "<one-line summary of changes>",
  "description": "<detailed description of the refactoring>",
  "changes": [
    {
      "file_path": "<relative path>",
      "change_type": "replace|insert|delete|rename",
      "old_content": "<exact text to replace>",
      "new_content": "<replacement text>",
      "start_line": <int or null>,
      "end_line": <int or null>,
      "description": "<why this change>"
    }
  ],
  "confidence_score": <1-10>,
  "risk_level": "low|medium|high",
  "ai_reasoning": "<step-by-step reasoning>",
  "changes_signature": <true|false>,
  "requires_manual_verification": <true|false>,
  "alternatives": [
    {
      "name": "<approach name>",
      "description": "<what this alternative does>",
      "pros": ["<pro1>", "<pro2>"],
      "cons": ["<con1>"],
      "confidence_score": <1-10>
    }
  ]
}

Confidence guide:
- 9-10: Direct 1:1 replacement, comprehensive tests, no signature changes
- 7-8: Clear replacement with minor adaptations, some test coverage
- 5-6: Moderate complexity, partial test coverage, review recommended
- 1-4: Uncertain — output a simpler proposal instead of a full plan

When confidence would be < 5, STOP and output a proposal:
{
  "is_proposal": true,
  "recommended_steps": ["<step1>", "<step2>"],
  "estimated_effort": "low|medium|high",
  "risks": ["<risk1>"]
}

Guidelines:
- Provide exact code replacements (not descriptions)
- Include enough context in old_content for unique matching
- Flag any risks or assumptions
- Mark changes_signature=true if any public function signature changes
"""


# ── Finding-type prompt builders ───────────────────────────────────────────


def _deprecated_api_prompt(finding: Finding) -> str:
    """Prompt enrichment for deprecated API findings."""
    meta = finding.metadata
    replacement = meta.get("replacement", "unknown")
    migration_url = meta.get("migration_guide_url", "")
    removed_in = meta.get("removed_in", "unknown")
    urgency = meta.get("urgency", "medium")

    parts = [
        f"Deprecated API: {finding.description}",
        f"Replacement: {replacement}",
        f"Removed in: {removed_in}",
        f"Urgency: {urgency}",
    ]
    if migration_url:
        parts.append(f"Migration guide: {migration_url}")
    return "\n".join(parts)


def _code_smell_prompt(finding: Finding) -> str:
    """Prompt enrichment for code smell findings."""
    meta = finding.metadata
    parts = [f"Code smell: {finding.description}"]
    cc = meta.get("cyclomatic_complexity")
    if cc is not None:
        parts.append(f"Cyclomatic complexity: {cc}")
    cog = meta.get("cognitive_complexity")
    if cog is not None:
        parts.append(f"Cognitive complexity: {cog}")
    mi = meta.get("maintainability_index")
    if mi is not None:
        parts.append(f"Maintainability index: {mi:.1f}")
    parts.append(
        "Suggested patterns: Extract Method, Replace Conditional with Polymorphism, "
        "Introduce Parameter Object"
    )
    return "\n".join(parts)


def _security_prompt(finding: Finding) -> str:
    """Prompt enrichment for security findings."""
    meta = finding.metadata
    parts = [f"Security issue: {finding.description}"]
    cwe = meta.get("cwe")
    if cwe:
        parts.append(f"CWE: {cwe}")
    exploit = meta.get("exploit_scenario")
    if exploit:
        parts.append(f"Exploit scenario: {exploit}")
    compliance = meta.get("compliance_impact")
    if compliance:
        parts.append(f"Compliance: {', '.join(compliance)}")
    parts.append(
        "Requirements: Fix must eliminate the vulnerability without breaking "
        "functionality. Prefer stdlib or well-known libraries."
    )
    return "\n".join(parts)


def _todo_prompt(finding: Finding) -> str:
    """Prompt enrichment for TODO comment findings."""
    meta = finding.metadata
    parts = [f"TODO comment: {finding.description}"]
    age = meta.get("age_days")
    if age is not None:
        parts.append(f"Age: {age} days")
    author = meta.get("author")
    if author:
        parts.append(f"Author: {author}")
    if meta.get("auto_issue"):
        parts.append("Action: Convert to a GitHub Issue for tracking.")
    return "\n".join(parts)


def _type_coverage_prompt(finding: Finding) -> str:
    """Prompt enrichment for type coverage findings."""
    meta = finding.metadata
    parts = [f"Type coverage: {finding.description}"]
    coverage = meta.get("coverage_percentage")
    if coverage is not None:
        parts.append(f"Current coverage: {coverage:.1f}%")
    strict = meta.get("strict_mode", False)
    if strict:
        parts.append("Strict mode: enabled (all functions must be typed)")
    parts.append("Add precise type annotations using modern Python typing syntax.")
    return "\n".join(parts)


_TYPE_PROMPT_MAP: dict[str, object] = {
    FindingType.DEPRECATED_API.value: _deprecated_api_prompt,
    FindingType.CODE_SMELL.value: _code_smell_prompt,
    FindingType.SECURITY.value: _security_prompt,
    FindingType.TODO_COMMENT.value: _todo_prompt,
    FindingType.TYPE_COVERAGE.value: _type_coverage_prompt,
}


# ── Public prompt builders ─────────────────────────────────────────────────


def build_finding_prompt(
    finding: Finding,
    context: CodeContext,
    *,
    preferences: str = "",
    historical_context: str = "",
) -> str:
    """Build a comprehensive user prompt for refactoring a specific finding.

    Includes type-specific enrichments, code context, test info,
    call-site information, and optionally learned preferences and
    historical pattern context (FR-LEARN-100, FR-LEARN-101).

    Args:
        finding: The finding to plan for.
        context: Code context surrounding the finding.
        preferences: Formatted team/user preferences for prompt injection.
        historical_context: Formatted historical pattern context.
    """
    # Type-specific enrichment
    type_builder = _TYPE_PROMPT_MAP.get(finding.type.value)
    type_section = type_builder(finding) if type_builder else finding.description  # type: ignore[operator]

    # Test info
    test_info = (
        f"Tests: {', '.join(context.related_tests)}"
        if context.related_tests
        else "Tests: None found"
    )

    # Call sites
    call_site_info = (
        f"Call sites ({len(context.call_sites)}): "
        + ", ".join(context.call_sites[:5])
        + ("..." if len(context.call_sites) > 5 else "")
        if context.call_sites
        else "Call sites: Unknown"
    )

    # Function signature
    sig_info = (
        f"Signature: {context.function_signature}"
        if context.function_signature
        else ""
    )

    # Coverage
    cov_info = f"Coverage: {context.coverage_percentage:.0f}%"

    # Truncate source if too long
    source = truncate_context(context.source_code)

    # Learned preferences and history (FR-LEARN-100, FR-LEARN-101)
    pref_section = f"\n\n{preferences}" if preferences else ""
    hist_section = f"\n\n{historical_context}" if historical_context else ""

    return f"""\
{type_section}

File: {context.file_path}
Line: {finding.line}
{sig_info}

Code Context:
```python
{source}
```

{test_info}
{call_site_info}
{cov_info}
Has test coverage: {context.has_tests}

Suggestion: {finding.suggestion}
{pref_section}{hist_section}

Task: Generate a refactoring plan as JSON following the output schema.
Preserve exact behavior. Minimize changes.
"""


# Keep backward-compatible alias
def build_user_prompt(finding: Finding, context: CodeContext) -> str:
    """Build a user prompt for refactoring a specific finding.

    Delegates to ``build_finding_prompt`` for richer context.
    """
    return build_finding_prompt(finding, context)


def build_context_request_prompt(finding: Finding) -> str:
    """Build a prompt asking the AI to gather more context via tools.

    This is used in Turn 1 where the AI should call tools like
    ``get_function_definition``, ``find_test_coverage``,
    ``search_references``, ``get_call_sites``.
    """
    return f"""\
I need to refactor the following issue. Before planning changes,
please use the available tools to gather context:

1. Get the full function definition with surrounding code
2. Check if tests exist for the affected code
3. Find all references to the affected symbol
4. Find all call sites for the affected function
5. Check type annotations on the function

Issue: {finding.description}
File: {finding.file}
Line: {finding.line}
Type: {finding.type.value}
Severity: {finding.severity.value}

Use the tools first, then I'll ask you to generate a plan.
"""


def build_alternatives_prompt(primary_plan_summary: str) -> str:
    """Build a prompt requesting alternative refactoring approaches.

    Used in Turn 3 when ``enable_alternatives`` is set.
    """
    return f"""\
You generated this refactoring plan:
{primary_plan_summary}

Now generate 2-3 alternative approaches with different tradeoffs.
For each alternative, provide as JSON array:
[
  {{
    "name": "<approach name>",
    "description": "<what this alternative does differently>",
    "pros": ["<advantage1>", "<advantage2>"],
    "cons": ["<disadvantage1>"],
    "confidence_score": <1-10>,
    "recommended": false
  }}
]

Consider approaches like:
- Minimal fix (suppress/defer) vs full refactor
- Different design patterns or library choices
- Performance-oriented vs readability-oriented
"""


# ── Token budget ───────────────────────────────────────────────────────────


def truncate_context(
    source_code: str,
    max_tokens: int = 3000,
    chars_per_token: float = 3.5,
) -> str:
    """Truncate source code while preserving function boundaries.

    Uses a rough chars-per-token estimate. Keeps the first and last
    portions to preserve function signatures and return statements.

    Args:
        source_code: The source code to potentially truncate.
        max_tokens: Approximate token budget.
        chars_per_token: Estimated characters per token (conservative).

    Returns:
        Truncated source with ``... (truncated) ...`` marker if needed.
    """
    max_chars = int(max_tokens * chars_per_token)
    if len(source_code) <= max_chars:
        return source_code

    # Keep head (function signatures, imports) and tail (return statements)
    head_size = int(max_chars * 0.6)
    tail_size = int(max_chars * 0.3)
    head = source_code[:head_size]
    tail = source_code[-tail_size:]

    # Try to break at line boundaries
    last_newline_head = head.rfind("\n")
    if last_newline_head > 0:
        head = head[:last_newline_head]
    first_newline_tail = tail.find("\n")
    if first_newline_tail > 0:
        tail = tail[first_newline_tail + 1:]

    omitted = len(source_code) - len(head) - len(tail)
    return f"{head}\n\n    # ... ({omitted} chars truncated) ...\n\n{tail}"
