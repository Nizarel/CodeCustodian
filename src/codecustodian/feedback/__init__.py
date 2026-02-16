"""Feedback and learning loop for continuous improvement."""

from codecustodian.feedback.history import (
    HistoricalPatternRecognizer,
    HistoricalRefactoring,
    SimilarPattern,
)
from codecustodian.feedback.learning import FeedbackCollector, PROutcome
from codecustodian.feedback.preferences import Preference, PreferenceStore
from codecustodian.feedback.store import FeedbackEntry, FeedbackStore

__all__ = [
    "FeedbackCollector",
    "FeedbackEntry",
    "FeedbackStore",
    "HistoricalPatternRecognizer",
    "HistoricalRefactoring",
    "PROutcome",
    "Preference",
    "PreferenceStore",
    "SimilarPattern",
]
