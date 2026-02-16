"""Team and engineer preference storage (FR-LEARN-100).

Stores learned coding preferences from ``@codecustodian feedback``
commands and PR review outcomes.  Preferences are injected into
Copilot SDK system prompts so generated code matches team style.

Storage: TinyDB-backed for lightweight persistence.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from codecustodian.logging import get_logger

logger = get_logger("feedback.preferences")


# ── Models ─────────────────────────────────────────────────────────────────


class Preference(BaseModel):
    """A single coding preference."""

    team: str = ""
    user: str = ""
    preference: str
    category: str = "general"  # style | pattern | library | testing | general
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    source: str = ""  # pr_comment | feedback_command | review_outcome


# ── Store ──────────────────────────────────────────────────────────────────


class PreferenceStore:
    """Store team/engineer preferences learned from feedback (FR-LEARN-100).

    Preferences are stored in TinyDB and retrieved for prompt injection.

    Usage::

        store = PreferenceStore()
        store.record_preference("team-alpha", "prefer async/await over callbacks")
        prefs = store.get_preferences("team-alpha")
        # → ["prefer async/await over callbacks"]

    Args:
        db_path: Path to the TinyDB JSON file.
    """

    # Maximum preferences returned to keep prompt size manageable
    MAX_PREFERENCES = 20

    def __init__(self, db_path: str = ".codecustodian-cache/preferences.json") -> None:
        from tinydb import TinyDB

        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = TinyDB(str(path))
        self._table = self.db.table("preferences")

    def close(self) -> None:
        """Close the underlying TinyDB to release file locks."""
        self.db.close()

    # ── Recording ──────────────────────────────────────────────────────

    def record_preference(
        self,
        team_or_user: str,
        preference: str,
        *,
        category: str = "general",
        source: str = "feedback_command",
        is_user: bool = False,
    ) -> None:
        """Record a coding preference.

        Args:
            team_or_user: Team name or username.
            preference: The preference text, e.g. ``"prefer dataclasses over dicts"``.
            category: One of style, pattern, library, testing, general.
            source: Where the preference came from.
            is_user: If ``True``, store as user pref; otherwise team pref.
        """
        entry = Preference(
            team="" if is_user else team_or_user,
            user=team_or_user if is_user else "",
            preference=preference,
            category=category,
            source=source,
        )

        # Avoid exact duplicates
        from tinydb import where

        existing = self._table.search(
            (where("preference") == preference)
            & (where("team") == entry.team)
            & (where("user") == entry.user)
        )
        if existing:
            logger.debug("Preference already exists, skipping duplicate")
            return

        self._table.insert(entry.model_dump())
        logger.info(
            "Preference recorded for %s: %s [%s]",
            team_or_user,
            preference[:60],
            category,
        )

    # ── Retrieval ──────────────────────────────────────────────────────

    def get_preferences(
        self,
        team: str = "",
        user: str = "",
        *,
        category: str = "",
    ) -> list[str]:
        """Return all learned preferences for prompt injection.

        Merges team-level and user-level preferences (user overrides
        take priority).

        Args:
            team: Team name to look up.
            user: Optional username for user-specific prefs.
            category: Filter by category (empty = all).

        Returns:
            List of preference strings, newest first, up to
            ``MAX_PREFERENCES``.
        """
        from tinydb import where

        results: list[dict] = []

        # Team-level preferences
        if team:
            query = where("team") == team
            if category:
                query = query & (where("category") == category)
            results.extend(self._table.search(query))

        # User-level preferences
        if user:
            query = where("user") == user
            if category:
                query = query & (where("category") == category)
            results.extend(self._table.search(query))

        # De-duplicate by preference text (user prefs override)
        seen: set[str] = set()
        unique: list[dict] = []
        # Process user-level first for priority
        user_prefs = [r for r in results if r.get("user")]
        team_prefs = [r for r in results if not r.get("user")]
        for r in user_prefs + team_prefs:
            pref = r.get("preference", "")
            if pref not in seen:
                seen.add(pref)
                unique.append(r)

        # Sort by timestamp descending, limit
        unique.sort(key=lambda r: r.get("timestamp", ""), reverse=True)

        return [r["preference"] for r in unique[:self.MAX_PREFERENCES]]

    def get_preferences_for_prompt(
        self,
        team: str = "",
        user: str = "",
    ) -> str:
        """Format preferences as a prompt section for Copilot SDK.

        Returns an empty string if no preferences exist.
        """
        prefs = self.get_preferences(team=team, user=user)
        if not prefs:
            return ""

        lines = ["Team/Engineer Preferences (follow these coding style guidelines):"]
        for i, pref in enumerate(prefs, 1):
            lines.append(f"  {i}. {pref}")
        return "\n".join(lines)

    # ── Management ─────────────────────────────────────────────────────

    def remove_preference(
        self,
        team_or_user: str,
        preference: str,
        *,
        is_user: bool = False,
    ) -> bool:
        """Remove a specific preference.

        Returns:
            ``True`` if the preference was found and removed.
        """
        from tinydb import where

        if is_user:
            query = (where("user") == team_or_user) & (where("preference") == preference)
        else:
            query = (where("team") == team_or_user) & (where("preference") == preference)

        removed = self._table.remove(query)
        return len(removed) > 0

    def clear_all(self, team: str = "", user: str = "") -> int:
        """Clear all preferences for a team or user.

        Returns:
            Number of preferences removed.
        """
        from tinydb import where

        if team:
            removed = self._table.remove(where("team") == team)
        elif user:
            removed = self._table.remove(where("user") == user)
        else:
            removed = self._table.clear_cache()
            self._table.truncate()
            return -1  # Can't know exact count after truncate

        return len(removed)

    def get_summary(self) -> dict:
        """Return a summary of stored preferences."""
        all_prefs = self._table.all()
        teams: set[str] = set()
        users: set[str] = set()
        categories: dict[str, int] = {}

        for p in all_prefs:
            if p.get("team"):
                teams.add(p["team"])
            if p.get("user"):
                users.add(p["user"])
            cat = p.get("category", "general")
            categories[cat] = categories.get(cat, 0) + 1

        return {
            "total": len(all_prefs),
            "teams": len(teams),
            "users": len(users),
            "by_category": categories,
        }
