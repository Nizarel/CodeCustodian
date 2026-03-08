"""Remote repository cloner for scanning public Git repositories.

Provides shallow-clone support for scanning any public HTTPS Git repository
in a temporary directory.  Usage::

    async with cloned_repo("https://github.com/owner/repo") as path:
        findings = _scan_findings(str(path), config_path, scanner_filter)
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from git import GitCommandError, Repo

from codecustodian.exceptions import ExecutorError
from codecustodian.logging import get_logger

logger = get_logger("executor.repo_cloner")

# Allowed hosts for cloning (HTTPS only — no SSH, no file://)
_ALLOWED_HOSTS = frozenset(
    {
        "github.com",
        "dev.azure.com",
        "gitlab.com",
        "bitbucket.org",
    }
)


def validate_clone_url(url: str) -> str:
    """Validate and normalise a Git clone URL.

    Raises ``ExecutorError`` for unsafe or unsupported URLs.
    """
    parsed = urlparse(url)

    if parsed.scheme != "https":
        raise ExecutorError(f"Only HTTPS clone URLs are supported, got: {parsed.scheme!r}")

    if not parsed.hostname or parsed.hostname not in _ALLOWED_HOSTS:
        raise ExecutorError(
            f"Host {parsed.hostname!r} is not in the allow-list: "
            f"{', '.join(sorted(_ALLOWED_HOSTS))}"
        )

    # Ensure path looks like a repo (at least /owner/repo)
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(parts) < 2:
        raise ExecutorError(f"URL path must contain at least owner/repo: {parsed.path!r}")

    return url


def clone_repo(url: str, *, branch: str | None = None, depth: int = 1, token: str | None = None) -> Path:
    """Shallow-clone a Git repo into a temporary directory.

    Args:
        url: HTTPS clone URL (validated against allow-list).
        branch: Optional branch to clone; defaults to the remote HEAD.
        depth: Clone depth (default ``1`` for speed).
        token: Optional access token for private repos.
               Only injected for ``github.com`` URLs.

    Returns:
        Path to the cloned working tree.
    """
    url = validate_clone_url(url)

    # Inject token into HTTPS URL for authenticated cloning (github.com only)
    clone_url = url
    if token:
        parsed = urlparse(url)
        if parsed.hostname == "github.com":
            clone_url = f"https://x-access-token:{token}@github.com{parsed.path}"
            logger.info("Using authenticated clone for %s", url)
        else:
            logger.warning("Token provided but host %s is not github.com — ignoring token", parsed.hostname)

    tmp = Path(tempfile.mkdtemp(prefix="codecustodian_"))
    logger.info("Cloning %s (depth=%d) into %s", url, depth, tmp)

    kwargs: dict = {"depth": depth}
    if branch:
        kwargs["branch"] = branch

    try:
        Repo.clone_from(clone_url, str(tmp), **kwargs)
    except GitCommandError as exc:
        shutil.rmtree(tmp, ignore_errors=True)
        # Use original URL in error message to avoid leaking token
        raise ExecutorError(f"Git clone failed for {url}: {exc}") from exc

    logger.info("Clone complete: %s", tmp)
    return tmp


def cleanup_clone(path: Path) -> None:
    """Remove a previously cloned temporary directory."""
    if path.exists():
        logger.info("Cleaning up clone directory: %s", path)
        shutil.rmtree(path, ignore_errors=True)


@asynccontextmanager
async def cloned_repo(
    url: str, *, branch: str | None = None, token: str | None = None,
) -> AsyncIterator[Path]:
    """Async context manager: clone → yield path → cleanup."""
    path = clone_repo(url, branch=branch, token=token)
    try:
        yield path
    finally:
        cleanup_clone(path)
