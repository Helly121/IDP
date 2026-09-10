"""
Approval workflow service — CRUD operations for PendingAction records
and execution of approved mutating tool calls.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pending_action import PendingAction, ActionStatus
from app.models.user import User, UserRole
from app.mcp_servers.registry import registry

logger = logging.getLogger(__name__)


async def create_pending_action(
    db: AsyncSession,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    tool_name: str,
    tool_params: dict,
) -> PendingAction:
    """Create a new pending action record for a mutating tool call."""
    action = PendingAction(
        session_id=session_id,
        user_id=user_id,
        tool_name=tool_name,
        tool_params=tool_params,
        status=ActionStatus.PENDING,
    )
    db.add(action)
    await db.flush()
    logger.info("Created pending action %s for tool '%s'", action.id, tool_name)
    return action


async def list_pending_actions(db: AsyncSession) -> list[PendingAction]:
    """List all pending approval requests, newest first."""
    stmt = (
        select(PendingAction)
        .where(PendingAction.status == ActionStatus.PENDING)
        .order_by(PendingAction.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_all_actions(db: AsyncSession, limit: int = 50) -> list[PendingAction]:
    """List all actions (including approved/rejected), newest first."""
    stmt = (
        select(PendingAction)
        .order_by(PendingAction.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def approve_action(
    db: AsyncSession,
    action_id: uuid.UUID,
    reviewer_id: uuid.UUID,
) -> PendingAction | None:
    """
    Approve a pending action:
    1. Validate the reviewer has guide/admin role
    2. Mark the action as approved
    3. Execute the tool call
    4. Store the result
    """
    action = await db.get(PendingAction, action_id)
    if action is None:
        return None
    if action.status != ActionStatus.PENDING:
        raise ValueError(f"Action is already {action.status.value}")

    # Validate reviewer role
    reviewer = await db.get(User, reviewer_id)
    if reviewer is None:
        raise ValueError("Reviewer not found")
    if reviewer.role not in (UserRole.GUIDE, UserRole.ADMIN):
        raise ValueError("Only guides and admins can approve actions")

    # Mark approved
    action.status = ActionStatus.APPROVED
    action.reviewed_by = reviewer_id
    action.reviewed_at = datetime.now(timezone.utc)
    await db.flush()

    # Execute the tool
    try:
        tool_result = await registry.dispatch(action.tool_name, action.tool_params)
        action.result = tool_result.to_dict()
        await db.flush()
        logger.info("Approved action %s executed: success=%s", action_id, tool_result.success)
    except Exception as e:
        action.result = {"success": False, "error": str(e)}
        await db.flush()
        logger.error("Approved action %s execution failed: %s", action_id, e)

    return action


async def reject_action(
    db: AsyncSession,
    action_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    reason: str | None = None,
) -> PendingAction | None:
    """Reject a pending action with an optional reason."""
    action = await db.get(PendingAction, action_id)
    if action is None:
        return None
    if action.status != ActionStatus.PENDING:
        raise ValueError(f"Action is already {action.status.value}")

    reviewer = await db.get(User, reviewer_id)
    if reviewer is None:
        raise ValueError("Reviewer not found")
    if reviewer.role not in (UserRole.GUIDE, UserRole.ADMIN):
        raise ValueError("Only guides and admins can reject actions")

    action.status = ActionStatus.REJECTED
    action.reviewed_by = reviewer_id
    action.reviewed_at = datetime.now(timezone.utc)
    action.rejection_reason = reason
    await db.flush()

    logger.info("Rejected action %s: %s", action_id, reason or "no reason given")
    return action
