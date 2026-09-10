"""
Pydantic v2 schemas for the Agent system — requests, SSE events, and approvals.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AgentRequest(BaseModel):
    """Input to the /agent/run SSE endpoint."""
    message: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="The user's natural-language request or question",
    )
    user_id: str = Field(
        default="00000000-0000-0000-0000-000000000001",
        description="UUID of the requesting user",
    )
    project_id: str | None = Field(
        None,
        description="Optional project UUID for context",
    )
    session_id: str | None = Field(
        None,
        description="Optional session ID to resume a conversation",
    )


class AgentEventType(str, Enum):
    """Types of SSE events the agent can emit."""
    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    APPROVAL_REQUIRED = "approval_required"
    FINAL_RESPONSE = "final_response"
    ERROR = "error"


class AgentEvent(BaseModel):
    """A single SSE event from the agent stream."""
    type: AgentEventType
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime | None = None

    def to_sse(self) -> str:
        """Format as a Server-Sent Event string."""
        import json
        payload = self.model_dump(mode="json")
        return f"event: {self.type.value}\ndata: {json.dumps(payload)}\n\n"


class PendingActionStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PendingActionResponse(BaseModel):
    """Response schema for a pending approval action."""
    id: UUID
    session_id: UUID | None = None
    user_id: UUID
    tool_name: str
    tool_params: dict[str, Any]
    status: PendingActionStatus
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None
    result: dict[str, Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApprovalDecision(BaseModel):
    """Input for approving or rejecting an action."""
    reviewer_id: str = Field(..., description="UUID of the guide/admin approving or rejecting")
    reason: str | None = Field(None, description="Optional reason for rejection")
