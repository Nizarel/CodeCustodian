"""Enterprise secrets management with Azure Key Vault (FR-SEC-101).

Wraps ``azure.keyvault.secrets.SecretClient`` with
``DefaultAzureCredential`` for zero-config Managed Identity auth.
Falls back to environment variables when Key Vault is not configured,
making local development seamless.

Features:
- Get / set / list secrets via Azure Key Vault
- Local env-var fallback for development
- Rotation-age checks with configurable thresholds
- Audit logging of secret access (read-only; values never logged)

Usage::

    sm = SecretsManager(vault_name="my-vault")
    token = await sm.get_secret("GITHUB_TOKEN")

    # Without Key Vault (env fallback):
    sm = SecretsManager()
    token = await sm.get_secret("GITHUB_TOKEN")  # reads os.environ
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from codecustodian.logging import get_logger

logger = get_logger("enterprise.secrets")


# ── Models ─────────────────────────────────────────────────────────────────


class SecretInfo(BaseModel):
    """Metadata about a secret (value is never serialized)."""

    name: str
    source: str = "env"           # keyvault | env
    created_on: str = ""
    updated_on: str = ""
    expires_on: str = ""
    enabled: bool = True
    days_since_rotation: int = -1  # -1 = unknown


# ── Manager ────────────────────────────────────────────────────────────────


class SecretsManager:
    """Centralized secret retrieval with Key Vault + env fallback (FR-SEC-101).

    When ``vault_name`` is provided, authenticates via
    ``DefaultAzureCredential`` (supports Managed Identity, Azure CLI,
    Visual Studio, and env-var-based service principals).

    Args:
        vault_name: Azure Key Vault name (e.g. ``"my-kv"``).
            The vault URL is derived as ``https://{vault_name}.vault.azure.net``.
        rotation_warning_days: Emit a warning when a secret hasn't been
            rotated for this many days.
    """

    def __init__(
        self,
        vault_name: str = "",
        rotation_warning_days: int = 90,
    ) -> None:
        self.vault_name = vault_name
        self.rotation_warning_days = rotation_warning_days
        self._client: Any = None

        if vault_name:
            self._init_keyvault_client()

    def _init_keyvault_client(self) -> None:
        """Initialize the Azure Key Vault SecretClient."""
        try:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient

            vault_url = f"https://{self.vault_name}.vault.azure.net"
            credential = DefaultAzureCredential()
            self._client = SecretClient(vault_url=vault_url, credential=credential)
            logger.info("Key Vault client initialized: %s", vault_url)
        except ImportError:
            logger.warning(
                "azure-identity / azure-keyvault-secrets not installed — "
                "falling back to env vars"
            )
        except Exception as exc:
            logger.warning(
                "Failed to initialize Key Vault client: %s — "
                "falling back to env vars",
                exc,
            )

    # ── Get ─────────────────────────────────────────────────────────────

    async def get_secret(self, name: str) -> str:
        """Retrieve a secret value.

        Tries Key Vault first, then falls back to ``os.environ``.
        Returns empty string if not found anywhere.
        """
        if self._client:
            try:
                secret = self._client.get_secret(name)
                self._check_rotation(name, secret)
                logger.debug("Secret '%s' retrieved from Key Vault", name)
                return secret.value or ""
            except Exception as exc:
                logger.warning(
                    "Key Vault get '%s' failed: %s — trying env", name, exc
                )

        # Env fallback
        value = os.environ.get(name, "")
        if value:
            logger.debug("Secret '%s' retrieved from environment", name)
        else:
            logger.warning("Secret '%s' not found in Key Vault or env", name)
        return value

    # ── Set ─────────────────────────────────────────────────────────────

    async def set_secret(self, name: str, value: str) -> SecretInfo:
        """Store a secret in Key Vault (or log a warning if unavailable)."""
        if not self._client:
            logger.warning(
                "No Key Vault client — cannot store secret '%s'", name
            )
            return SecretInfo(name=name, source="env")

        try:
            result = self._client.set_secret(name, value)
            logger.info("Secret '%s' stored in Key Vault", name)
            return SecretInfo(
                name=name,
                source="keyvault",
                created_on=str(result.properties.created_on or ""),
                updated_on=str(result.properties.updated_on or ""),
                expires_on=str(result.properties.expires_on or ""),
                enabled=result.properties.enabled or True,
            )
        except Exception as exc:
            logger.error("Failed to set secret '%s': %s", name, exc)
            raise

    # ── List ────────────────────────────────────────────────────────────

    async def list_secrets(self) -> list[SecretInfo]:
        """List secret metadata (names only — no values)."""
        if not self._client:
            return []

        infos: list[SecretInfo] = []
        try:
            for prop in self._client.list_properties_of_secrets():
                days = self._days_since_update(prop.updated_on)
                infos.append(
                    SecretInfo(
                        name=prop.name,
                        source="keyvault",
                        created_on=str(prop.created_on or ""),
                        updated_on=str(prop.updated_on or ""),
                        expires_on=str(prop.expires_on or ""),
                        enabled=prop.enabled or True,
                        days_since_rotation=days,
                    )
                )
        except Exception as exc:
            logger.warning("Failed to list secrets: %s", exc)
        return infos

    # ── Rotation check ─────────────────────────────────────────────────

    async def check_rotation_status(self) -> list[SecretInfo]:
        """Return secrets that need rotation (past threshold)."""
        all_secrets = await self.list_secrets()
        stale = [
            s
            for s in all_secrets
            if s.days_since_rotation >= self.rotation_warning_days
        ]
        if stale:
            logger.warning(
                "%d secret(s) need rotation (>%d days)",
                len(stale),
                self.rotation_warning_days,
            )
        return stale

    async def get_github_token(self) -> str:
        """Retrieve GitHub token from Key Vault/env."""
        return await self.get_secret("github-token")

    async def get_copilot_token(self) -> str:
        """Retrieve Copilot token from Key Vault/env."""
        return await self.get_secret("copilot-token")

    async def get_devops_pat(self) -> str:
        """Retrieve Azure DevOps PAT from Key Vault/env."""
        return await self.get_secret("devops-pat")

    # ── Internal ───────────────────────────────────────────────────────

    def _check_rotation(self, name: str, secret: Any) -> None:
        """Warn if a secret hasn't been rotated recently."""
        try:
            updated = secret.properties.updated_on
            if updated:
                days = self._days_since_update(updated)
                if days >= self.rotation_warning_days:
                    logger.warning(
                        "Secret '%s' last rotated %d days ago (threshold: %d)",
                        name,
                        days,
                        self.rotation_warning_days,
                    )
        except Exception:
            pass

    @staticmethod
    def _days_since_update(updated_on: Any) -> int:
        """Calculate days since last update."""
        if not updated_on:
            return -1
        try:
            if isinstance(updated_on, datetime):
                dt = updated_on
            else:
                dt = datetime.fromisoformat(str(updated_on))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            delta = datetime.now(timezone.utc) - dt
            return delta.days
        except Exception:
            return -1
