"""
AI Agent Orchestrator â€” Gemini-powered agentic loop with MCP tool calling.

Replaces the previous static prompt-wrapper with an autonomous agent that:
1. Receives a user message
2. Sends it to Gemini with all MCP tool declarations
3. Processes function_call responses by dispatching to the correct MCP server
4. For read-only tools: executes immediately and feeds results back to Gemini
5. For mutating tools: creates a PendingAction and yields an approval_required event
6. Loops until Gemini produces a final text response
7. Yields structured SSE events at each step for the frontend to render live
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.core.database import async_session_factory
from app.mcp_servers.registry import registry
from app.schemas.agent import AgentEvent, AgentEventType
from app.services import approval_service
from app.services.context_budget import (
    compact_for_model,
    compact_for_ui,
    compact_chat_history,
)

from app.mcp_servers.base import ToolCategory
from app.services.tool_router import select_tool_categories

logger = logging.getLogger(__name__)

# Cache one GenerativeModel per frozenset of ToolCategory
_model_cache: dict[frozenset[ToolCategory], Any] = {}


def _get_gemini_model(categories: frozenset[ToolCategory] | None = None) -> Any:
    """
    Build and cache a Gemini GenerativeModel configured specifically
    with the tool declarations for the given categories.
    """
    global _model_cache
    if not settings.GEMINI_API_KEY:
        return None

    cat_key = categories if categories is not None else frozenset(ToolCategory)

    if cat_key not in _model_cache:
        try:
            import google.generativeai as genai

            genai.configure(api_key=settings.GEMINI_API_KEY)

            # Build tool declarations filtered by selected categories
            tool_declarations = registry.get_gemini_declarations(set(cat_key))
            logger.info(
                "Initializing Gemini model for categories %s with %d tools (model: %s)",
                [c.value for c in cat_key],
                len(tool_declarations),
                settings.GEMINI_MODEL,
            )

            _model_cache[cat_key] = genai.GenerativeModel(
                settings.GEMINI_MODEL,
                tools=[{"function_declarations": tool_declarations}] if tool_declarations else None,
                system_instruction=_build_system_prompt(),
            )
        except Exception as e:
            logger.warning("Failed to initialize Gemini agent model: %s", e)
            return None

    return _model_cache[cat_key]


def _is_rate_limit_error(exc: Exception) -> bool:
    """Check if exception represents an HTTP 429 or quota limit exhaustion."""
    try:
        from google.api_core import exceptions
        if isinstance(exc, exceptions.ResourceExhausted):
            return True
    except ImportError:
        pass
    if getattr(exc, "status_code", None) == 429 or getattr(exc, "code", None) == 429:
        return True
    exc_str = str(exc).lower()
    return "429" in exc_str or "resourceexhausted" in exc_str or "quota" in exc_str or "rate limit" in exc_str


def _extract_retry_delay(exc: Exception, default_delay: float) -> float:
    """Extract retry delay seconds from exception message or metadata if present."""
    import re
    msg = str(exc)
    match = re.search(r"retry[-_\s]?(?:in|after)?[:\s]+([0-9.]+)\s*s?", msg, re.IGNORECASE)
    if match:
        try:
            return float(match.group(1))
        except (ValueError, TypeError):
            pass
    metadata = getattr(exc, "metadata", None)
    if metadata:
        for k, v in metadata:
            if "retry" in str(k).lower():
                try:
                    return float(v)
                except (ValueError, TypeError):
                    pass
    return default_delay


async def _send_chat_message_with_retry(
    chat: Any,
    content: Any,
    max_retries: int = 2,
) -> AsyncGenerator[tuple[str | None, Any | None], None]:
    """
    Send message asynchronously using SDK async method (chat.send_message_async),
    with thread pool fallback for synchronous chats.

    Handles quota errors (HTTP 429 / ResourceExhausted) by retrying at most 2 times
    with exponential backoff plus jitter, honoring any specified retry delay.
    Yields (sse_event_string, None) during retry waits so callers can stream THINKING events live.
    Yields (None, response) when successful.
    """
    import asyncio
    import inspect
    import random

    retries = 0
    while True:
        try:
            if hasattr(chat, "send_message_async"):
                resp = await chat.send_message_async(content)
            elif hasattr(chat, "send_message"):
                if inspect.iscoroutinefunction(chat.send_message):
                    resp = await chat.send_message(content)
                else:
                    resp = await asyncio.to_thread(chat.send_message, content)
            else:
                raise AttributeError("Chat session has no send_message or send_message_async method")
            yield (None, resp)
            return
        except Exception as e:
            if _is_rate_limit_error(e) and retries < max_retries:
                retries += 1
                base_delay = 2.0 ** retries
                jitter = random.uniform(0.1, 1.0)
                delay = _extract_retry_delay(e, base_delay + jitter)
                logger.warning(
                    "LLM rate limited (retry %d/%d). Retrying in %.1f s: %s",
                    retries,
                    max_retries,
                    delay,
                    e,
                )
                yield (
                    AgentEvent(
                        type=AgentEventType.THINKING,
                        data={"message": f"Rate limited, retrying in {delay:.1f} s"},
                        timestamp=datetime.now(timezone.utc),
                    ).to_sse(),
                    None,
                )
                await asyncio.sleep(delay)
            else:
                raise

def _build_system_prompt() -> str:
    """Concise system prompt for the Academic IDP DevOps agent."""
    return """You are the DevOps AI agent for the Academic Internal Developer Platform (IDP).
Assist users with Terraform (under iac/), GitHub Actions (under .github/workflows/), Kubernetes/ArgoCD deployments, diagnostics, and RBAC/cost policies.

Key Rules:
1. Mutating tools trigger HITL approval. Inform the user when actions are queued.
2. Terraform apply is NOT an MCP capability; deployments occur via approved CI/CD.
3. Keep Terraform scoped to iac/ and workflows to .github/workflows/.
4. Be concise, validate configurations, and never expose secrets or credentials."""

async def run_agent_stream(
    message: str,
    user_id: str,
    project_id: str | None = None,
    session_id: str | None = None,
    model: Any = None,
) -> AsyncGenerator[str, None]:
    """
    Main entry point: run the agentic loop and yield SSE events.

    Each yield is a fully-formatted SSE string (event + data + newlines).
    """
    sid = uuid.UUID(session_id) if session_id else uuid.uuid4()
    uid = uuid.UUID(user_id) if user_id else None
    now = lambda: datetime.now(timezone.utc)

    # Yield: thinking
    yield AgentEvent(
        type=AgentEventType.THINKING,
        data={"message": "Analyzing your request and determining the best approach..."},
        timestamp=now(),
    ).to_sse()

    # Route minimal tool categories based on message intent
    selected_categories = select_tool_categories(message, target_project=project_id)
    cat_key = frozenset(selected_categories)

    if model is None:
        model = _get_gemini_model(cat_key)
    if model is None:
        yield AgentEvent(
            type=AgentEventType.ERROR,
            data={"message": "AI agent is not available. Please configure GEMINI_API_KEY."},
            timestamp=now(),
        ).to_sse()
        return

    # Build initial context
    context_parts = [message]
    if project_id:
        context_parts.append(f"\n[Context: This request is related to project ID {project_id}]")
    context_parts.append(f"\n[User ID: {user_id}]")

    try:
        # Start a chat session for multi-turn tool calling
        chat = model.start_chat(history=[])
        response = None
        async for sse_event, resp in _send_chat_message_with_retry(chat, "\n".join(context_parts)):
            if sse_event:
                yield sse_event
            if resp is not None:
                response = resp

        if response is None:
            yield AgentEvent(
                type=AgentEventType.ERROR,
                data={"message": "No response received from AI model"},
                timestamp=now(),
            ).to_sse()
            return

        # Agentic loop: keep processing until we get a text response
        max_iterations = settings.AGENT_MAX_ITERATIONS
        iteration = 0
        seen_tool_calls: set[str] = set()

        # Token usage tracking
        total_prompt_tokens = 0
        total_candidates_tokens = 0
        total_model_tokens = 0
        call_count = 0
        call_usages: list[dict[str, Any]] = []

        while iteration < max_iterations:
            iteration += 1

            # Extract usage metadata from response
            usage_meta = getattr(response, "usage_metadata", None)
            prompt_tokens = getattr(usage_meta, "prompt_token_count", 0) if usage_meta else 0
            candidates_tokens = getattr(usage_meta, "candidates_token_count", 0) if usage_meta else 0
            total_tokens = getattr(usage_meta, "total_token_count", prompt_tokens + candidates_tokens) if usage_meta else (prompt_tokens + candidates_tokens)

            call_count += 1
            total_prompt_tokens += prompt_tokens
            total_candidates_tokens += candidates_tokens
            total_model_tokens += total_tokens
            call_usages.append({
                "call_index": call_count,
                "iteration": iteration,
                "prompt_tokens": prompt_tokens,
                "candidates_tokens": candidates_tokens,
                "total_tokens": total_tokens,
            })

            logger.info(
                "Agent iteration %d token usage: prompt=%d, candidates=%d, total=%d",
                iteration,
                prompt_tokens,
                candidates_tokens,
                total_tokens,
            )

            # Check if the response contains function calls
            candidate = response.candidates[0] if response.candidates else None
            if candidate is None:
                yield AgentEvent(
                    type=AgentEventType.ERROR,
                    data={"message": "No response from AI model"},
                    timestamp=now(),
                ).to_sse()
                return

            parts = candidate.content.parts if candidate.content else []

            # Collect all function calls from this response
            function_calls = [p for p in parts if hasattr(p, "function_call") and p.function_call]
            text_parts = [p.text for p in parts if hasattr(p, "text") and p.text]

            # If we only have text (no function calls), this is the final response
            if not function_calls:
                final_text = "\n".join(text_parts) if text_parts else "I've completed the analysis."
                yield AgentEvent(
                    type=AgentEventType.FINAL_RESPONSE,
                    data={
                        "message": final_text,
                        "usage": {
                            "prompt_tokens": total_prompt_tokens,
                            "candidates_tokens": total_candidates_tokens,
                            "total_tokens": total_model_tokens,
                            "api_calls": call_count,
                            "iterations": iteration,
                            "calls": call_usages,
                        },
                    },
                    timestamp=now(),
                ).to_sse()
                return

            # Process each function call
            from google.generativeai import protos

            function_responses = []

            for fc_part in function_calls:
                fc = fc_part.function_call
                tool_name = fc.name
                tool_params = dict(fc.args) if fc.args else {}

                # Yield: tool_call event
                yield AgentEvent(
                    type=AgentEventType.TOOL_CALL,
                    data={
                        "tool_name": tool_name,
                        "params": tool_params,
                        "is_mutating": registry.is_mutating(tool_name),
                    },
                    timestamp=now(),
                ).to_sse()

                # Duplicate-call guard: check canonical JSON args
                canonical_args = json.dumps(tool_params, sort_keys=True, separators=(",", ":"))
                call_signature = f"{tool_name}:{canonical_args}"

                if call_signature in seen_tool_calls:
                    logger.info("Duplicate tool call suppressed: %s", call_signature)
                    dup_message = "already retrieved above"
                    yield AgentEvent(
                        type=AgentEventType.TOOL_RESULT,
                        data={
                            "tool_name": tool_name,
                            "success": True,
                            "result": {"message": dup_message},
                        },
                        timestamp=now(),
                    ).to_sse()

                    function_responses.append(
                        protos.Part(
                            function_response=protos.FunctionResponse(
                                name=tool_name,
                                response={"result": dup_message},
                            )
                        )
                    )
                    continue

                seen_tool_calls.add(call_signature)

                # Check if this is a mutating tool
                if registry.is_mutating(tool_name):
                    # Create a pending action and yield approval_required
                    async with async_session_factory() as db:
                        action = await approval_service.create_pending_action(
                            db=db,
                            session_id=sid,
                            user_id=uid,
                            tool_name=tool_name,
                            tool_params=tool_params,
                        )
                        await db.commit()

                        yield AgentEvent(
                            type=AgentEventType.APPROVAL_REQUIRED,
                            data={
                                "action_id": str(action.id),
                                "tool_name": tool_name,
                                "params": tool_params,
                                "message": (
                                    f"The action '{tool_name}' requires approval from a guide or admin. "
                                    f"Action ID: {action.id}"
                                ),
                            },
                            timestamp=now(),
                        ).to_sse()

                    # Feed back a "pending" result to Gemini so it can continue reasoning
                    function_responses.append(
                        protos.Part(
                            function_response=protos.FunctionResponse(
                                name=tool_name,
                                response={
                                    "result": {
                                        "status": "pending_approval",
                                        "action_id": str(action.id),
                                        "message": "This mutating action requires human approval before execution. The request has been queued.",
                                    }
                                },
                            )
                        )
                    )
                else:
                    # Read-only tool: execute immediately
                    result = await registry.dispatch(tool_name, tool_params)
                    raw_result = result.to_dict()

                    # Yield: tool_result event using UI limit (UI_RESULT_MAX_CHARS)
                    ui_result = compact_for_ui(tool_name, raw_result)
                    yield AgentEvent(
                        type=AgentEventType.TOOL_RESULT,
                        data={
                            "tool_name": tool_name,
                            "success": result.success,
                            "result": ui_result,
                        },
                        timestamp=now(),
                    ).to_sse()

                    # Feed compacted result to model using model limit (TOOL_RESULT_MAX_CHARS)
                    model_result = compact_for_model(tool_name, raw_result)
                    function_responses.append(
                        protos.Part(
                            function_response=protos.FunctionResponse(
                                name=tool_name,
                                response={"result": model_result},
                            )
                        )
                    )

            # History control: compact older function_response turns in chat.history to one-line stubs.
            # Latest iteration's function_responses stay full.
            # Model-role parts (thought signatures, tool calls) are NEVER touched.
            if hasattr(chat, "history") and isinstance(chat.history, list):
                compact_chat_history(chat.history)

            # Send all function responses back to Gemini asynchronously for the next iteration
            response = None
            async for sse_event, resp in _send_chat_message_with_retry(chat, function_responses):
                if sse_event:
                    yield sse_event
                if resp is not None:
                    response = resp

            if response is None:
                yield AgentEvent(
                    type=AgentEventType.ERROR,
                    data={"message": "No response received from AI model"},
                    timestamp=now(),
                ).to_sse()
                return

        # If we hit max iterations, yield a warning
        yield AgentEvent(
            type=AgentEventType.FINAL_RESPONSE,
            data={
                "message": "I've reached the maximum number of reasoning steps. Here's what I've found so far.",
                "usage": {
                    "prompt_tokens": total_prompt_tokens,
                    "candidates_tokens": total_candidates_tokens,
                    "total_tokens": total_model_tokens,
                    "api_calls": call_count,
                    "iterations": iteration,
                    "calls": call_usages,
                },
            },
            timestamp=now(),
        ).to_sse()

    except Exception as e:
        if _is_rate_limit_error(e):
            logger.error("AI quota exhausted: %s", e)
            yield AgentEvent(
                type=AgentEventType.ERROR,
                data={"message": "AI quota was reached. Please wait a moment or try again later."},
                timestamp=now(),
            ).to_sse()
            return

        logger.exception("Agent loop error")
        yield AgentEvent(
            type=AgentEventType.ERROR,
            data={"message": f"Agent encountered an error: {str(e)}"},
            timestamp=now(),
        ).to_sse()


