"""Domain skill loader for the AI planner.

Loads ``SKILL.md`` knowledge files from the ``.copilot_skills/`` directory
and injects their content into the Copilot SDK ``system_message`` so the AI
planner has deep, domain-specific expertise for each finding type.

SKILL.md format — YAML front-matter followed by Markdown body::

    ---
    name: security-remediation
    description: OWASP Top 10, CWE mappings, secure coding patterns
    ---

    # Security Remediation Skill
    ...
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from codecustodian.logging import get_logger
from codecustodian.models import FindingType

logger = get_logger("planner.skills")

# ── Skill data model ──────────────────────────────────────────────────────


@dataclass
class SkillDefinition:
    """A loaded skill with parsed front-matter and markdown body."""

    name: str
    description: str
    content: str
    path: Path = field(default_factory=lambda: Path("."))


# ── Finding-type → skill mapping ──────────────────────────────────────────

FINDING_TYPE_SKILL_MAP: dict[str, list[str]] = {
    FindingType.SECURITY.value: ["security-remediation", "code-quality"],
    FindingType.DEPRECATED_API.value: ["api-migration", "general-refactoring"],
    FindingType.CODE_SMELL.value: ["code-quality", "general-refactoring"],
    FindingType.TYPE_COVERAGE.value: ["python-typing"],
    FindingType.TODO_COMMENT.value: ["todo-resolution"],
    FindingType.DEPENDENCY_UPGRADE.value: ["dependency-management"],
}


# ── YAML front-matter parser ──────────────────────────────────────────────

_FRONTMATTER_RE = re.compile(
    r"\A---\s*\n(?P<yaml>.*?)\n---\s*\n(?P<body>.*)",
    re.DOTALL,
)


def _parse_skill_md(text: str) -> tuple[dict[str, Any], str]:
    """Parse YAML front-matter and markdown body from a SKILL.md file.

    Returns:
        (front_matter_dict, markdown_body)
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text

    raw_yaml = match.group("yaml")
    body = match.group("body").strip()

    try:
        front_matter = yaml.safe_load(raw_yaml) or {}
    except yaml.YAMLError as exc:
        logger.warning("Failed to parse YAML front-matter: %s", exc)
        front_matter = {}

    return front_matter, body


# ── Skill registry ────────────────────────────────────────────────────────


class SkillRegistry:
    """Discovers and loads SKILL.md files from a skill directory tree.

    Usage::

        registry = SkillRegistry()
        registry.load_skills(Path(".copilot_skills"))
        skills = registry.get_skills_for_finding(FindingType.SECURITY)
        context = registry.format_skill_context(skills)
    """

    def __init__(self) -> None:
        self._skills: dict[str, SkillDefinition] = {}

    # ── Loading ────────────────────────────────────────────────────────

    def load_skills(self, skill_dir: Path | str | None = None) -> None:
        """Recursively find and parse all ``SKILL.md`` files under *skill_dir*.

        Each immediate subdirectory that contains a ``SKILL.md`` file is
        treated as a skill.  The subdirectory name becomes the key when the
        front-matter ``name`` field is absent.

        When *skill_dir* is ``None``, defaults to ``.copilot_skills/`` in the
        current working directory.
        """
        if skill_dir is None:
            skill_dir = Path(".copilot_skills")
        else:
            skill_dir = Path(skill_dir)
        if not skill_dir.is_dir():
            logger.info("Skill directory %s not found — no skills loaded", skill_dir)
            return

        for child in sorted(skill_dir.iterdir()):
            skill_file = child / "SKILL.md" if child.is_dir() else None
            if skill_file is None or not skill_file.is_file():
                continue

            try:
                text = skill_file.read_text(encoding="utf-8")
            except OSError as exc:
                logger.warning("Could not read %s: %s", skill_file, exc)
                continue

            fm, body = _parse_skill_md(text)
            name = fm.get("name", child.name)
            description = fm.get("description", "")
            if isinstance(description, str):
                description = description.strip()

            skill = SkillDefinition(
                name=name,
                description=description,
                content=body,
                path=skill_file,
            )
            self._skills[name] = skill

        logger.info("Loaded %d skill(s) from %s", len(self._skills), skill_dir)

    # ── Querying ───────────────────────────────────────────────────────

    def get_skill(self, name: str) -> SkillDefinition | None:
        """Return a single skill by name, or ``None``."""
        return self._skills.get(name)

    def list_skills(self) -> list[str]:
        """Return sorted list of loaded skill names."""
        return sorted(self._skills)

    def get_skills_for_finding(
        self, finding_type: FindingType | str,
    ) -> list[SkillDefinition]:
        """Return skills relevant to a finding type."""
        type_value = finding_type.value if hasattr(finding_type, "value") else str(finding_type)
        skill_names = FINDING_TYPE_SKILL_MAP.get(type_value, ["general-refactoring"])
        return [self._skills[n] for n in skill_names if n in self._skills]

    def get_skills_by_names(self, names: list[str]) -> list[SkillDefinition]:
        """Return skills matching the given names (order preserved)."""
        return [self._skills[n] for n in names if n in self._skills]

    # ── Formatting ─────────────────────────────────────────────────────

    @staticmethod
    def format_skill_context(skills: list[SkillDefinition]) -> str:
        """Format skill content for injection into the system prompt.

        Returns a single string block with skill headers and bodies
        delimited for clarity.
        """
        if not skills:
            return ""

        parts: list[str] = ["[Domain Skills]"]
        for skill in skills:
            parts.append(f"\n## Skill: {skill.name}")
            if skill.description:
                parts.append(skill.description)
            parts.append(skill.content)
        parts.append("\n[End Domain Skills]\n")
        return "\n".join(parts)
