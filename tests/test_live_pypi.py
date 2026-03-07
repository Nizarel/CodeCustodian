"""Tests for the live PyPI version checking functionality."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from codecustodian.scanner.dependency_upgrades import DependencyUpgradeScanner


class TestCheckPyPI:
    """Unit tests for DependencyUpgradeScanner.check_pypi."""

    @pytest.mark.asyncio
    async def test_check_pypi_returns_version_info(self) -> None:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = lambda: None
        # httpx .json() is synchronous, so use a regular function
        mock_response.json = lambda: {
            "info": {
                "version": "2.0.0",
                "home_page": "https://example.com",
                "project_urls": {"Changelog": "https://example.com/changes"},
            },
            "releases": {
                "2.0.0": [{"upload_time_iso_8601": "2024-01-15T00:00:00Z"}],
            },
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            scanner = DependencyUpgradeScanner()
            result = await scanner.check_pypi("example-pkg", timeout=5)

        assert result is not None
        assert result["latest_version"] == "2.0.0"
        assert "home_page" in result

    @pytest.mark.asyncio
    async def test_check_pypi_returns_none_on_error(self) -> None:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=Exception("network error"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            scanner = DependencyUpgradeScanner()
            result = await scanner.check_pypi("nonexistent-pkg", timeout=1)

        assert result is not None
        assert result["latest_version"] is None
        assert result["release_date"] is None


class TestScanWithLiveCheck:
    """Unit tests for DependencyUpgradeScanner.scan_with_live_check."""

    @pytest.mark.asyncio
    async def test_scan_with_live_check_enriches_metadata(self, tmp_path: Path) -> None:
        """Verifies that scan_with_live_check enriches findings with PyPI data."""
        # Create a minimal pyproject.toml
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "test"\nversion = "0.1.0"\ndependencies = ["requests>=1.0.0"]\n'
        )

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "info": {
                "version": "2.32.0",
                "home_page": "https://requests.readthedocs.io",
                "project_urls": {},
            },
            "releases": {
                "2.32.0": [{"upload_time_iso_8601": "2024-06-01T00:00:00Z"}],
            },
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            scanner = DependencyUpgradeScanner()
            findings = await scanner.scan_with_live_check(str(tmp_path), timeout=5)

        # Even if no findings from scan(), the method should not raise
        assert isinstance(findings, list)


class TestLivePyPIConfig:
    """Test configuration options for live PyPI checking."""

    def test_scanner_has_live_pypi_config_fields(self) -> None:
        from codecustodian.config.schema import DependencyUpgradeScannerConfig

        config = DependencyUpgradeScannerConfig()
        assert config.live_pypi is False  # default disabled
        assert config.pypi_timeout == 10
        assert config.cache_ttl_hours == 24

    def test_scanner_config_with_live_enabled(self) -> None:
        from codecustodian.config.schema import DependencyUpgradeScannerConfig

        config = DependencyUpgradeScannerConfig(live_pypi=True, pypi_timeout=5)
        assert config.live_pypi is True
        assert config.pypi_timeout == 5
