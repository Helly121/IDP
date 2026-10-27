"""
Staging Workspace Service for DevHub AI Agent.

Manages isolated, per-session staging copies of IaC files and CI/CD workflows:
- When a mutating tool (terraform_write_file or workflow_write) is proposed,
  content is staged in a per-session staging tree while awaiting human approval.
- The staging tree copies the base iac/ directory (skipping .terraform and *.tfstate)
  and layers the proposed changes on top.
- Read and verify tools (fmt, init, validate, plan, get_file, list_files) run
  against this staging tree if staged files exist for the session.
- Automatically cleans up staging workspaces upon approval, rejection, or TTL expiration.
"""

from __future__ import annotations

import logging
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


def get_staging_root() -> Path:
    """Resolve the base directory for staging workspaces."""
    p = Path(settings.STAGING_ROOT)
    if not p.is_absolute():
        p = Path.cwd() / p
    p.mkdir(parents=True, exist_ok=True)
    return p.resolve()


def get_session_dir(session_id: str | uuid.UUID) -> Path:
    """Return the isolated staging directory for a specific session."""
    sid_str = str(session_id).replace("-", "")
    return get_staging_root() / sid_str


def _is_expired(session_dir: Path) -> bool:
    """Check if a session staging directory has exceeded STAGING_TTL_MINUTES."""
    try:
        ttl_seconds = settings.STAGING_TTL_MINUTES * 60
        mtime = session_dir.stat().st_mtime
        return (time.time() - mtime) > ttl_seconds
    except OSError:
        return True


def cleanup_staging(session_id: str | uuid.UUID) -> None:
    """Clean up and remove the staging directory for a session."""
    try:
        sdir = get_session_dir(session_id)
        if sdir.exists():
            shutil.rmtree(sdir, ignore_errors=True)
            logger.info("Cleaned up staging directory for session %s", session_id)
    except Exception as e:
        logger.warning("Failed to clean up staging for session %s: %s", session_id, e)


def cleanup_expired_sessions() -> int:
    """Scan staging root and remove workspaces older than STAGING_TTL_MINUTES."""
    root = get_staging_root()
    count = 0
    if not root.exists():
        return 0

    for item in root.iterdir():
        if item.is_dir() and _is_expired(item):
            try:
                shutil.rmtree(item, ignore_errors=True)
                count += 1
            except Exception as e:
                logger.warning("Error pruning expired staging dir %s: %s", item, e)
    if count:
        logger.info("Pruned %d expired staging sessions", count)
    return count


def has_staged_files(session_id: str | uuid.UUID | None) -> bool:
    """Check whether an active, non-expired staging workspace exists for this session."""
    if not session_id:
        return False
    sdir = get_session_dir(session_id)
    if not sdir.exists():
        return False
    if _is_expired(sdir):
        cleanup_staging(session_id)
        return False
    return any(sdir.iterdir())


def has_staged_terraform(session_id: str | uuid.UUID | None) -> bool:
    """Check if the session has staged Terraform files."""
    if not session_id:
        return False
    iac_staged = get_session_dir(session_id) / "iac"
    if not iac_staged.exists():
        return False
    if _is_expired(get_session_dir(session_id)):
        cleanup_staging(session_id)
        return False
    return any(iac_staged.iterdir())


def has_staged_workflows(session_id: str | uuid.UUID | None) -> bool:
    """Check if the session has staged GitHub Actions workflow files."""
    if not session_id:
        return False
    wf_staged = get_session_dir(session_id) / ".github" / "workflows"
    if not wf_staged.exists():
        return False
    if _is_expired(get_session_dir(session_id)):
        cleanup_staging(session_id)
        return False
    return any(wf_staged.iterdir())


def get_staged_iac_root(session_id: str | uuid.UUID | None) -> Path | None:
    """Return the path to the staged iac/ root directory if it exists."""
    if not session_id or not has_staged_terraform(session_id):
        return None
    return (get_session_dir(session_id) / "iac").resolve()


def get_staged_workflows_root(session_id: str | uuid.UUID | None) -> Path | None:
    """Return the path to the staged .github/workflows directory if it exists."""
    if not session_id or not has_staged_workflows(session_id):
        return None
    return (get_session_dir(session_id) / ".github" / "workflows").resolve()


def stage_terraform_file(
    session_id: str | uuid.UUID,
    file_path: str,
    content: str,
    real_iac_root: Path | None = None,
) -> Path:
    """
    Stage a proposed Terraform file in the session's staging workspace.
    Builds the initial copy from real_iac_root (skipping .terraform and *.tfstate)
    if the staging tree does not exist yet.
    """
    session_dir = get_session_dir(session_id)
    staged_iac = session_dir / "iac"

    if not staged_iac.exists():
        session_dir.mkdir(parents=True, exist_ok=True)
        if real_iac_root and real_iac_root.exists() and real_iac_root.is_dir():
            def _ignore_tf(path: str, names: list[str]) -> set[str]:
                ignored = set()
                for name in names:
                    if name == ".terraform" or name.endswith(".tfstate") or name.endswith(".tfstate.backup"):
                        ignored.add(name)
                return ignored

            shutil.copytree(real_iac_root, staged_iac, ignore=_ignore_tf)
            logger.info("Cloned base iac tree into staging workspace for session %s", session_id)
        else:
            staged_iac.mkdir(parents=True, exist_ok=True)

    # Safe path resolution within staged_iac
    clean_rel = file_path.strip().lstrip("/\\")
    target = (staged_iac / clean_rel).resolve()
    try:
        target.relative_to(staged_iac.resolve())
    except ValueError:
        raise PermissionError(
            f"Access denied: Path '{file_path}' escapes staging workspace '{staged_iac}'"
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")

    # Touch session directory to refresh TTL
    try:
        os.utime(session_dir, None)
    except OSError:
        pass

    logger.info("Staged Terraform file '%s' in session %s", file_path, session_id)
    return target


def stage_workflow_file(
    session_id: str | uuid.UUID,
    workflow_name: str,
    content: str,
    real_workflows_root: Path | None = None,
) -> Path:
    """
    Stage a proposed workflow file in the session's staging workspace.
    """
    session_dir = get_session_dir(session_id)
    staged_wf = session_dir / ".github" / "workflows"

    if not staged_wf.exists():
        session_dir.mkdir(parents=True, exist_ok=True)
        if real_workflows_root and real_workflows_root.exists() and real_workflows_root.is_dir():
            shutil.copytree(real_workflows_root, staged_wf)
            logger.info("Cloned base workflows into staging workspace for session %s", session_id)
        else:
            staged_wf.mkdir(parents=True, exist_ok=True)

    clean_name = workflow_name.strip().lstrip("/\\")
    if "/" in clean_name or "\\" in clean_name or ".." in clean_name:
        raise PermissionError(f"Access denied: Invalid workflow file name '{workflow_name}'")

    if not (clean_name.endswith(".yml") or clean_name.endswith(".yaml")):
        clean_name += ".yml"

    target = (staged_wf / clean_name).resolve()
    try:
        target.relative_to(staged_wf.resolve())
    except ValueError:
        raise PermissionError(
            f"Access denied: Path '{workflow_name}' escapes staging workspace '{staged_wf}'"
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")

    try:
        os.utime(session_dir, None)
    except OSError:
        pass

    logger.info("Staged workflow file '%s' in session %s", workflow_name, session_id)
    return target
