"""
Approval management endpoints — List, approve, and reject pending mutating actions.

Guides and admins use these endpoints (via the Approvals Dashboard) to review
and act on tool calls that the AI agent flagged as requiring human approval.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.agent import ApprovalDecision, PendingActionResponse
from app.services import approval_service

router = APIRouter(prefix="/approvals", tags=["Approvals"])


@router.get(
    "/pending",
    response_model=list[PendingActionResponse],
    summary="List all pending approval requests",
)
async def list_pending(db: AsyncSession = Depends(get_db)):
    """
    Returns all PendingAction records with status='pending',
    ordered by creation date (newest first).
    """
    actions = await approval_service.list_pending_actions(db)
    return [PendingActionResponse.model_validate(a) for a in actions]


@router.get(
    "/all",
    response_model=list[PendingActionResponse],
    summary="List all actions (pending, approved, rejected)",
)
async def list_all(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Returns all PendingAction records, newest first."""
    actions = await approval_service.list_all_actions(db, limit=limit)
    return [PendingActionResponse.model_validate(a) for a in actions]


@router.post(
    "/{action_id}/approve",
    response_model=PendingActionResponse,
    summary="Approve a pending action and execute the tool call",
)
async def approve_action(
    action_id: uuid.UUID,
    decision: ApprovalDecision,
    db: AsyncSession = Depends(get_db),
):
    """
    Approve a pending mutating tool call:
    1. Validate the reviewer has guide/admin role
    2. Mark the action as approved
    3. Execute the tool
    4. Return the action with execution results
    """
    try:
        action = await approval_service.approve_action(
            db=db,
            action_id=action_id,
            reviewer_id=uuid.UUID(decision.reviewer_id),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if action is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action {action_id} not found",
        )

    return PendingActionResponse.model_validate(action)


@router.post(
    "/{action_id}/reject",
    response_model=PendingActionResponse,
    summary="Reject a pending action",
)
async def reject_action(
    action_id: uuid.UUID,
    decision: ApprovalDecision,
    db: AsyncSession = Depends(get_db),
):
    """Reject a pending action with an optional reason."""
    try:
        action = await approval_service.reject_action(
            db=db,
            action_id=action_id,
            reviewer_id=uuid.UUID(decision.reviewer_id),
            reason=decision.reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if action is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action {action_id} not found",
        )

    return PendingActionResponse.model_validate(action)
