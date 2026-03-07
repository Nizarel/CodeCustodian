"""Safe file editor with atomic operations and rollback.

All file modifications go through this module to ensure:
- Atomic writes (temp file → rename)
- Automatic backups before changes
- Syntax validation before commit
- Multi-file atomic rollback (FR-EXEC-100): all succeed or all revert
- Edge case handling: read-only, binary, encoding, >10MB
"""

from __future__ import annotations

import ast
import os
import tempfile
from pathlib import Path

from codecustodian.executor.backup import BackupManager
from codecustodian.logging import get_logger
from codecustodian.models import ChangeType, FileChange, TransactionLogEntry

logger = get_logger("executor.file_editor")

# Maximum file size we'll attempt to edit (10 MB)
MAX_FILE_SIZE = 10 * 1024 * 1024


class SafeFileEditor:
    """Apply code changes atomically with backup/rollback.

    Supports multi-file transactions (FR-EXEC-100): all files in a batch
    succeed, or all are reverted from backups.
    """

    def __init__(
        self,
        backup_dir: str | Path = ".codecustodian-backups",
        repo_root: str | Path | None = None,
        validate_syntax: bool = True,
        backup_manager: BackupManager | None = None,
    ) -> None:
        self.repo_root = Path(repo_root).resolve() if repo_root is not None else None
        self.validate_syntax = validate_syntax
        if backup_manager is not None:
            self.backup_manager = backup_manager
        else:
            self.backup_manager = BackupManager(backup_dir=backup_dir)

    def apply_change(self, change: FileChange) -> Path | None:
        """Apply a single file change atomically.

        Returns the backup path on success, or raises on failure.
        """
        file_path = Path(change.file_path)

        # Edge case checks
        self._validate_file(file_path, change)

        if change.change_type == ChangeType.REPLACE:
            return self._apply_replace(file_path, change.old_content, change.new_content)
        elif change.change_type == ChangeType.INSERT:
            return self._apply_insert(file_path, change.new_content, change.start_line)
        elif change.change_type == ChangeType.DELETE:
            return self._apply_delete(file_path, change.start_line, change.end_line)
        else:
            raise ValueError(f"Unsupported change type: {change.change_type}")

    def apply_changes(self, changes: list[FileChange]) -> list[Path]:
        """Apply multiple file changes atomically (FR-EXEC-100).

        All changes succeed or all are reverted. Returns list of backup paths.

        Raises:
            Exception: If any change fails. All successful changes are rolled back.
        """
        backup_paths: list[Path] = []
        applied: list[int] = []

        try:
            for i, change in enumerate(changes):
                backup = self.apply_change(change)
                if backup:
                    backup_paths.append(backup)
                applied.append(i)

                self.backup_manager._transaction_log.append(
                    TransactionLogEntry(
                        action="apply",
                        file_path=change.file_path,
                        backup_path=str(backup) if backup else "",
                        success=True,
                    )
                )

            logger.info("Applied %d changes atomically", len(changes))
            return backup_paths

        except Exception as exc:
            logger.error(
                "Change %d/%d failed: %s — rolling back all %d applied changes",
                len(applied) + 1,
                len(changes),
                exc,
                len(applied),
            )
            # Rollback all applied changes
            self.backup_manager.restore_all()

            self.backup_manager._transaction_log.append(
                TransactionLogEntry(
                    action="rollback",
                    file_path=f"batch ({len(applied)} files)",
                    success=True,
                    error=str(exc),
                )
            )
            raise

    # ── Validation helpers ─────────────────────────────────────────────

    def _validate_file(self, file_path: Path, change: FileChange) -> None:
        """Validate file before editing — edge case handling."""
        normalized = Path(file_path)
        if ".." in normalized.parts:
            raise ValueError(f"Path traversal sequence not allowed: {file_path}")

        resolved_target = normalized.resolve(strict=False)
        if self.repo_root is not None and not resolved_target.is_relative_to(self.repo_root):
            raise ValueError(
                f"File path must remain within repository root {self.repo_root}: {file_path}"
            )

        if file_path.exists() and file_path.is_symlink():
            raise ValueError(f"Symlink targets are not editable: {file_path}")

        if change.change_type == ChangeType.INSERT and not file_path.exists():
            # Creating a new file — OK
            return

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Read-only check
        if not os.access(file_path, os.W_OK):
            raise PermissionError(f"File is read-only: {file_path}")

        # Size check (>10MB)
        file_size = file_path.stat().st_size
        if file_size > MAX_FILE_SIZE:
            raise ValueError(
                f"File too large ({file_size / 1024 / 1024:.1f} MB > "
                f"{MAX_FILE_SIZE / 1024 / 1024:.0f} MB limit): {file_path}"
            )

        # Binary file check
        try:
            with open(file_path, "rb") as f:
                chunk = f.read(8192)
                if b"\x00" in chunk:
                    raise ValueError(f"Binary file detected: {file_path}")
        except OSError as e:
            raise ValueError(f"Cannot read file: {file_path}: {e}") from e

    # ── Change type handlers ───────────────────────────────────────────

    def _apply_replace(self, file_path: Path, old_content: str, new_content: str) -> Path:
        """Replace old_content with new_content in file."""
        backup = self.backup_manager.create_backup(file_path)

        try:
            original = file_path.read_text(encoding="utf-8")

            count = original.count(old_content)
            if count == 0:
                raise ValueError("old_content not found in file")
            if count > 1:
                raise ValueError(f"old_content appears {count} times — must be unique")

            modified = original.replace(old_content, new_content, 1)

            if self.validate_syntax and file_path.suffix == ".py":
                ast.parse(modified)

            self._atomic_write(file_path, modified)
            logger.info("Applied replacement in %s", file_path)
            return backup

        except Exception:
            self._restore_backup(backup, file_path)
            raise

    def _apply_insert(self, file_path: Path, content: str, line: int | None) -> Path:
        """Insert content at a specific line."""
        if not file_path.exists():
            # Create new file
            file_path.parent.mkdir(parents=True, exist_ok=True)
            self._atomic_write(file_path, content)
            return file_path  # No backup for new files

        backup = self.backup_manager.create_backup(file_path)

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

    def _apply_delete(self, file_path: Path, start_line: int | None, end_line: int | None) -> Path:
        """Delete lines from start_line to end_line (inclusive)."""
        backup = self.backup_manager.create_backup(file_path)

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

    # ── Internal helpers ───────────────────────────────────────────────

    def _restore_backup(self, backup: Path, target: Path) -> None:
        """Restore file from backup."""
        if backup.exists():
            self.backup_manager.restore(backup, target)

    @staticmethod
    def _atomic_write(file_path: Path, content: str) -> None:
        """Write content atomically via temp file + rename."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=file_path.parent, suffix=".tmp", prefix=file_path.stem)
        try:
            with open(fd, "w", encoding="utf-8") as f:
                f.write(content)
            Path(tmp).replace(file_path)
        except Exception:
            Path(tmp).unlink(missing_ok=True)
            raise
