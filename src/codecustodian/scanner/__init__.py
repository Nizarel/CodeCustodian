"""Scanner modules for detecting technical debt issues."""

from codecustodian.scanner.base import BaseScanner, is_excluded
from codecustodian.scanner.code_smells import CodeSmellScanner
from codecustodian.scanner.deduplication import DeduplicationEngine
from codecustodian.scanner.deprecated_api import DeprecatedAPIScanner
from codecustodian.scanner.registry import ScannerRegistry, get_default_registry
from codecustodian.scanner.security import SecurityScanner
from codecustodian.scanner.todo_comments import TodoCommentScanner
from codecustodian.scanner.type_coverage import TypeCoverageScanner

__all__ = [
    "BaseScanner",
    "CodeSmellScanner",
    "DeduplicationEngine",
    "DeprecatedAPIScanner",
    "ScannerRegistry",
    "SecurityScanner",
    "TodoCommentScanner",
    "TypeCoverageScanner",
    "get_default_registry",
    "is_excluded",
]
