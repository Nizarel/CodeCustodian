"""Safe file editor with atomic operations and rollback.

All file modifications go through this module to ensure:
- Atomic writes (temp file → rename)
- Automatic backups before changes
- Syntax validation before commit
- Rollback on any failure
"""

from __future__ import annotations

import ast
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from codecustodian.logging import get_logger
from codecustodian.models import FileChange, ChangeType

logger = get_logger("executor.file_editor")


class SafeFileEditor:
    """Apply code changes atomically with backup/rollback."""

    def __init__(
        self,
        backup_dir: str | Path = ".codecustodian-backups",
        validate_syntax: bool = True,
    ) -> None:
        self.backup_dir = Path(backup_dir)
        self.validate_syntax = validate_syntax
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def apply_change(self, change: FileChange) -> Path | None:
        """Apply a single file change atomically.

        Returns the backup path on success, or raises on failure.
        """
        file_path = Path(change.file_path)

        if change.change_type == ChangeType.REPLACE:
            return self._apply_replace(file_path, change.old_content, change.new_content)
        elif change.change_type == ChangeType.INSERT:
            return self._apply_insert(file_path, change.new_content, change.start_line)
        elif change.change_type == ChangeType.DELETE:
            return self._apply_delete(file_path, change.start_line, change.end_line)
        else:
            raise ValueError(f"Unsupported change type: {change.change_type}")

    def _apply_replace(
        self, file_path: Path, old_content: str, new_content: str
    ) -> Path:
        """Replace old_content with new_content in file."""
        backup = self._create_backup(file_path)

        try:
            original = file_path.read_text(encoding="utf-8")

            count = original.count(old_content)
            if count == 0:
                raise ValueError("old_content not found in file")
            if count > 1:
                raise ValueError(
                    f"old_content appears {count} times — must be unique"
                )

            modified = original.replace(old_content, new_content, 1)

            if self.validate_syntax and file_path.suffix == ".py":
                ast.parse(modified)

            self._atomic_write(file_path, modified)
            logger.info("Applied replacement in %s", file_path)
            return backup

        except Exception:
            self._restore_backup(backup, file_path)
            raise

    def _apply_insert(
        self, file_path: Path, content: str, line: int | None
    ) -> Path:
        """Insert content at a specific line."""
        backup = self._create_backup(file_path)

        try:
            lines = file_path.read_text(encoding="utf-8").splitlines(keepends=True)
            insert_at = (line or len(lines)) - 1
            lines.insert(insert_at, content + "\n")
            modified = "".join(lines)

            if self.validate_syntax and file_path.suffix == ".py":
                ast.parse(modified)

            self._atomic_write(file_path, modified)
            return backup

        except Exception:
            self._restore_backup(backup, file_path)
            raise

    def _apply_delete(
        self, file_path: Path, start_line: int | None, end_line: int | None
    ) -> Path:
        """Delete lines from start_line to end_line (inclusive)."""
        backup = self._create_backup(file_path)

        try:
            lines = file_path.read_text(encoding="utf-8").splitlines(keepends=True)
            s = (start_line or 1) - 1
            e = end_line or len(lines)
            del lines[s:e]
            modified = "".join(lines)

            if self.validate_syntax and file_path.suffix == ".py":
                ast.parse(modified)

            self._atomic_write(file_path, modified)
            return backup

        except Exception:
            self._restore_backup(backup, file_path)
            raise

    def _create_backup(self, file_path: Path) -> Path:
        """Create a timestamped backup."""
        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        backup_path = self.backup_dir / f"{file_path.name}-{timestamp}.bak"
        shutil.copy2(file_path, backup_path)
        logger.debug("Backup created: %s", backup_path)
        return backup_path

    def _restore_backup(self, backup: Path, target: Path) -> None:
        """Restore file from backup."""
        if backup.exists():
            shutil.copy2(backup, target)
            logger.info("Restored %s from backup", target)

    @staticmethod
    def _atomic_write(file_path: Path, content: str) -> None:
        """Write content atomically via temp file + rename."""
        fd, tmp = tempfile.mkstemp(
            dir=file_path.parent, suffix=".tmp", prefix=file_path.stem
        )
        try:
            with open(fd, "w", encoding="utf-8") as f:
                f.write(content)
            Path(tmp).replace(file_path)
        except Exception:
            Path(tmp).unlink(missing_ok=True)
            raise
