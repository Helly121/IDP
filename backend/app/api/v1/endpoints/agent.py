
"""
Agent SSE streaming endpoint — The primary interface for the AI DevOps mentor.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.core.security import require_auth
from app.schemas.agent import AgentRequest
from app.services.ai_service import run_agent_stream

router = APIRouter(prefix="/agent", tags=["Agent"])


@router.post(
    "/run",
    summary="Run the AI DevOps agent with SSE streaming",
    description=(
        "Accepts a natural-language message and streams the agent's multi-step "
        "reasoning as Server-Sent Events."
    ),
    response_class=StreamingResponse,
)
async def run_agent(
    payload: AgentRequest,
    current_user: dict = Depends(require_auth),
):
    """Run the agent for the authenticated user."""
    return StreamingResponse(
        run_agent_stream(
            message=payload.message,
            user_id=current_user["sub"],
            project_id=(
                str(payload.project_id) if payload.project_id else None
            ),
            session_id=payload.session_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
