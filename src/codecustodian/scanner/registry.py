"""Scanner registry — discover, register, and manage scanner plugins.

Provides ``ScannerRegistry`` for dynamic scanner management and a
convenience ``get_default_registry()`` function.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from codecustodian.logging import get_logger
from codecustodian.scanner.base import BaseScanner

if TYPE_CHECKING:
    from codecustodian.config.schema import CodeCustodianConfig

logger = get_logger("scanner.registry")


class ScannerRegistry:
    """Registry for managing scanner instances.

    Usage::

        registry = ScannerRegistry(config)
        registry.register(DeprecatedAPIScanner)
        registry.register(TodoCommentScanner)

        for scanner in registry.get_enabled():
            findings = scanner.scan(repo_path)
    """

    def __init__(self, config: CodeCustodianConfig | None = None) -> None:
        self.config = config
        self._scanners: dict[str, type[BaseScanner]] = {}

    def register(self, scanner_cls: type[BaseScanner]) -> None:
        """Register a scanner class by its ``name`` attribute."""
        name = scanner_cls.name
        if name in self._scanners:
            logger.warning("Scanner %r already registered — overwriting", name)
        self._scanners[name] = scanner_cls
        logger.debug("Registered scanner %r", name)

    def get(self, name: str) -> BaseScanner | None:
        """Return an instantiated scanner by name, or ``None``."""
        cls = self._scanners.get(name)
        if cls is None:
            return None
        return cls(config=self.config)

    def get_enabled(self) -> list[BaseScanner]:
        """Return instances of all enabled scanners (per config).

        A scanner is disabled when:
        1. Its class attribute ``enabled`` is ``False``, **or**
        2. The matching config section sets ``enabled = False``.
        """
        enabled: list[BaseScanner] = []
        for name, cls in self._scanners.items():
            # Class-level opt-out
            if not getattr(cls, "enabled", True):
                continue
            # Config-level opt-out
            if self.config and hasattr(self.config.scanners, name):
                scanner_cfg = getattr(self.config.scanners, name)
                if hasattr(scanner_cfg, "enabled") and not scanner_cfg.enabled:
                    continue
            enabled.append(cls(config=self.config))
        return enabled

    def list_scanners(self) -> list[str]:
        """Return names of all registered scanners."""
        return sorted(self._scanners.keys())

    def list_catalog(self) -> list[dict[str, str]]:
        """Return a marketplace-style catalog of registered scanners.

        Each entry contains ``name``, ``description``, and ``detects``
        (the finding type the scanner targets).
        """
        catalog: list[dict[str, str]] = []
        for _name, cls in sorted(self._scanners.items()):
            catalog.append(
                {
                    "name": cls.name,
                    "description": cls.description,
                    "detects": cls.name,
                    "enabled": str(getattr(cls, "enabled", True)),
                }
            )
        return catalog

    def __len__(self) -> int:
        return len(self._scanners)


def get_default_registry(config: CodeCustodianConfig | None = None) -> ScannerRegistry:
    """Create a registry pre-loaded with all built-in scanners.

    Lazily imports scanner modules to avoid circular imports.
    """
    registry = ScannerRegistry(config)

    # Import and register built-in scanners
    # These will be implemented in Phase 2
    try:
        from codecustodian.scanner.deprecated_api import DeprecatedAPIScanner

        registry.register(DeprecatedAPIScanner)
    except ImportError:
        pass

    try:
        from codecustodian.scanner.todo_comments import TodoCommentScanner

        registry.register(TodoCommentScanner)
    except ImportError:
        pass

    try:
        from codecustodian.scanner.code_smells import CodeSmellScanner

        registry.register(CodeSmellScanner)
    except ImportError:
        pass

    try:
        from codecustodian.scanner.security import SecurityScanner

        registry.register(SecurityScanner)
    except ImportError:
        pass

    try:
        from codecustodian.scanner.type_coverage import TypeCoverageScanner

        registry.register(TypeCoverageScanner)
    except ImportError:
        pass

    try:
        from codecustodian.scanner.dependency_upgrades import DependencyUpgradeScanner

        registry.register(DependencyUpgradeScanner)
    except ImportError:
        pass

    try:
        from codecustodian.scanner.architectural_drift import ArchitecturalDriftScanner

        registry.register(ArchitecturalDriftScanner)
    except ImportError:
        pass

    logger.info("Default registry loaded: %d scanners", len(registry))
    return registry
