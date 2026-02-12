"""Backup manager for file change rollback.

Handles backup creation, retention, and restoration.
"""

from __future__ import annotations

import shutil
from datetime import datetime, timedelta
from pathlib import Path

from codecustodian.logging import get_logger

logger = get_logger("executor.backup")


class BackupManager:
    """Manage file backups for safe rollback."""

    def __init__(
        self,
        backup_dir: str | Path = ".codecustodian-backups",
        retention_days: int = 7,
    ) -> None:
        self.backup_dir = Path(backup_dir)
        self.retention_days = retention_days
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(self, file_path: Path) -> Path:
        """Create a backup of the given file."""
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S-%f")
        backup_name = f"{file_path.name}-{timestamp}.bak"
        backup_path = self.backup_dir / backup_name
        shutil.copy2(file_path, backup_path)
        logger.debug("Created backup: %s → %s", file_path, backup_path)
        return backup_path

    def restore(self, backup_path: Path, target_path: Path) -> None:
        """Restore a file from backup."""
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup not found: {backup_path}")
        shutil.copy2(backup_path, target_path)
        logger.info("Restored %s from %s", target_path, backup_path)

    def restore_all(self, backup_paths: list[str], repo_path: str | Path) -> int:
        """Restore multiple files from their backups. Returns count restored."""
        restored = 0
        for bp in backup_paths:
            backup = Path(bp)
            # Extract original filename from backup name (remove timestamp + .bak)
            original_name = backup.name.rsplit("-", 3)[0]
            target = Path(repo_path) / original_name
            try:
                self.restore(backup, target)
                restored += 1
            except Exception as exc:
                logger.error("Failed to restore %s: %s", backup, exc)
        return restored

    def cleanup(self) -> int:
        """Remove backups older than retention period. Returns count removed."""
        cutoff = datetime.utcnow() - timedelta(days=self.retention_days)
        removed = 0
        for backup in self.backup_dir.glob("*.bak"):
            stat = backup.stat()
            modified = datetime.utcfromtimestamp(stat.st_mtime)
            if modified < cutoff:
                backup.unlink()
                removed += 1
        if removed:
            logger.info("Cleaned up %d old backups", removed)
        return removed
