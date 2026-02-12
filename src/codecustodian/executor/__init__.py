"""Executor module for applying code changes safely.

Exports the key executor components:
- ``SafetyCheckRunner`` — 5-point pre-execution safety system
- ``SafeFileEditor`` — Atomic file editing with rollback
- ``BackupManager`` — Backup creation, retention, and transaction logging
- ``GitManager`` — Git branch/commit/push workflow
"""

from codecustodian.executor.backup import BackupManager
from codecustodian.executor.file_editor import SafeFileEditor
from codecustodian.executor.git_manager import GitManager
from codecustodian.executor.safety_checks import SafetyCheckRunner

__all__ = [
    "BackupManager",
    "GitManager",
    "SafeFileEditor",
    "SafetyCheckRunner",
]
