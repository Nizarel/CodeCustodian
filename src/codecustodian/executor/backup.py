"""Backup manager for file change rollback.

Handles backup creation, retention, restoration, and transaction logging
for forensic analysis (FR-EXEC-100).
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

from codecustodian.logging import get_logger
from codecustodian.models import TransactionLogEntry

logger = get_logger("executor.backup")


class BackupManager:
    """Manage file backups for safe rollback with transaction logging.

    Supports multi-file atomic operations: all files succeed or all revert.
    A transaction log records every action for forensic analysis.
    """

    def __init__(
        self,
        backup_dir: str | Path = ".codecustodian-backups",
        retention_days: int = 7,
    ) -> None:
        self.backup_dir = Path(backup_dir)
        self.retention_days = retention_days
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self._transaction_log: list[TransactionLogEntry] = []
        # Map original file → backup path for multi-file rollback
        self._backup_map: dict[str, Path] = {}

    @property
    def transaction_log(self) -> list[TransactionLogEntry]:
        """Return the transaction log entries."""
        return list(self._transaction_log)

    def create_backup(self, file_path: Path) -> Path:
        """Create a backup of the given file and record in transaction log."""
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
        backup_name = f"{file_path.name}-{timestamp}.bak"
        backup_path = self.backup_dir / backup_name
        shutil.copy2(file_path, backup_path)

        # Record in map for rollback
        self._backup_map[str(file_path.resolve())] = backup_path

        entry = TransactionLogEntry(
            action="backup",
            file_path=str(file_path),
            backup_path=str(backup_path),
            success=True,
        )
        self._transaction_log.append(entry)
        logger.debug("Created backup: %s → %s", file_path, backup_path)
        return backup_path

    def restore(self, backup_path: Path, target_path: Path) -> None:
        """Restore a file from backup."""
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup not found: {backup_path}")
        shutil.copy2(backup_path, target_path)

        entry = TransactionLogEntry(
            action="rollback",
            file_path=str(target_path),
            backup_path=str(backup_path),
            success=True,
        )
        self._transaction_log.append(entry)
        logger.info("Restored %s from %s", target_path, backup_path)

    def restore_all(self, backup_paths: list[str] | None = None, repo_path: str | Path = ".") -> int:
        """Restore all backed-up files. Returns count restored.

        If ``backup_paths`` is provided, restore from those paths using the
        backup map. Otherwise, restore all files in the backup map.
        """
        restored = 0

        if backup_paths:
            for bp in backup_paths:
                backup = Path(bp)
                # Find original path from backup map
                target = None
                for orig, bk in self._backup_map.items():
                    if str(bk) == str(backup.resolve()) or str(bk) == bp:
                        target = Path(orig)
                        break

                if target is None:
                    # Fallback: extract filename from backup
                    original_name = backup.name.rsplit("-", 3)[0]
                    target = Path(repo_path) / original_name

                try:
                    self.restore(backup, target)
                    restored += 1
                except Exception as exc:
                    entry = TransactionLogEntry(
                        action="rollback",
                        file_path=str(target),
                        backup_path=bp,
                        success=False,
                        error=str(exc),
                    )
                    self._transaction_log.append(entry)
                    logger.error("Failed to restore %s: %s", backup, exc)
        else:
            # Restore everything in the backup map
            for orig_path, backup_path in self._backup_map.items():
                try:
                    self.restore(backup_path, Path(orig_path))
                    restored += 1
                except Exception as exc:
                    entry = TransactionLogEntry(
                        action="rollback",
                        file_path=orig_path,
                        backup_path=str(backup_path),
                        success=False,
                        error=str(exc),
                    )
                    self._transaction_log.append(entry)
                    logger.error("Failed to restore %s: %s", orig_path, exc)

        if restored:
            logger.info("Restored %d files from backup", restored)
        return restored

    def clear_session(self) -> None:
        """Clear session-specific state (backup map) but keep log."""
        self._backup_map.clear()

    def cleanup(self) -> int:
        """Remove backups older than retention period. Returns count removed."""
        cutoff = datetime.now(UTC) - timedelta(days=self.retention_days)
        removed = 0
        for backup in self.backup_dir.glob("*.bak"):
            stat = backup.stat()
            modified = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
            if modified < cutoff:
                backup.unlink()
                removed += 1
        if removed:
            logger.info("Cleaned up %d old backups", removed)
        return removed

    def write_transaction_log(self, log_path: Path | None = None) -> Path:
        """Write the transaction log to a JSON file for forensic analysis.

        Returns the path to the log file.
        """
        if log_path is None:
            timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
            log_path = self.backup_dir / f"transaction-log-{timestamp}.json"

        entries = [e.model_dump(mode="json") for e in self._transaction_log]
        log_path.write_text(json.dumps(entries, indent=2, default=str), encoding="utf-8")
        logger.info("Transaction log written to %s", log_path)
        return log_path
