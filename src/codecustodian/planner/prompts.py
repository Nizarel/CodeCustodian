"""Prompt templates for the AI planner.

System and user prompts for Copilot SDK conversations,
designed for safe and accurate refactoring suggestions.
"""

from __future__ import annotations

from codecustodian.models import CodeContext, Finding


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

Output Format (JSON):
{
  "summary": "<one-line summary of changes>",
  "changes": [
    {
      "file_path": "<relative path>",
      "old_content": "<exact text to replace>",
      "new_content": "<replacement text>",
      "description": "<why this change>"
    }
  ],
  "confidence": <1-10>,
  "risk_level": "low|medium|high",
  "reasoning": "<step-by-step reasoning>",
  "alternatives": ["<alt1>", "<alt2>"]
}

Guidelines:
- Provide exact code replacements (not descriptions)
- Include enough context in old_content for unique matching
- Specify confidence level (1-10)
- Flag any risks or assumptions
"""


def build_user_prompt(finding: Finding, context: CodeContext) -> str:
    """Build a user prompt for refactoring a specific finding."""
    test_info = (
        f"Tests: {', '.join(context.related_tests)}"
        if context.related_tests
        else "Tests: None found"
    )

    call_site_info = (
        f"Call sites: {', '.join(context.call_sites[:5])}"
        if context.call_sites
        else "Call sites: Unknown"
    )

    return f"""\
Issue: {finding.description}

File: {context.file_path}
Line: {finding.line}

Code Context:
```python
{context.source_code}
```

{test_info}
{call_site_info}
Has test coverage: {context.has_tests}

Suggestion: {finding.suggestion}

Task: Refactor to fix this issue while maintaining exact behavior.

Requirements:
- Preserve function signatures unless explicitly needed
- Keep type hints
- Ensure tests still pass
"""


def build_context_request_prompt(finding: Finding) -> str:
    """Build a prompt asking the AI to request more context."""
    return f"""\
I need to refactor the following issue. Before I plan the changes,
I need to gather more context. Please use the available tools to:

1. Get the full function definition
2. Check if tests exist
3. Find all references to the affected code

Issue: {finding.description}
File: {finding.file}
Line: {finding.line}
"""
