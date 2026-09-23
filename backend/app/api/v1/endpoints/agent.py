"""
Agent SSE streaming endpoint — The primary interface for the AI DevOps mentor.

POST /api/v1/agent/run accepts a user message and returns a Server-Sent Events
stream that the frontend consumes to render live multi-step reasoning.
"""

from typing import Optional
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.core.security import get_current_user
from app.schemas.agent import AgentRequest
from app.services.ai_service import run_agent_stream

router = APIRouter(prefix="/agent", tags=["Agent"])


@router.post(
    "/run",
    summary="Run the AI DevOps agent with SSE streaming",
    description=(
        "Accepts a natural-language message and streams the agent's multi-step "
        "reasoning as Server-Sent Events. Events include: thinking, tool_call, "
        "tool_result, approval_required, final_response, and error."
    ),
    response_class=StreamingResponse,
)
async def run_agent(
    payload: AgentRequest,
    current_user: Optional[dict] = Depends(get_current_user),
):
    """
    Start an agentic loop:
    1. Send the user's message to Gemini with MCP tool declarations
    2. Stream each reasoning step as an SSE event
    3. For read-only tools, execute and continue
    4. For mutating tools, create a PendingAction and stream approval_required
    5. Continue until Gemini produces a final text response
    """
    effective_user_id = (current_user.get("sub") if current_user else None) or payload.user_id

    return StreamingResponse(
        run_agent_stream(
            message=payload.message,
            user_id=effective_user_id,
            project_id=payload.project_id,
            session_id=payload.session_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
