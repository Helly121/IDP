"""
Unit tests for AI service orchestrator, loop hygiene, retry backoff, and duplicate tool call guards.
"""

import asyncio
import json
import uuid
import pytest
from unittest.mock import MagicMock

from app.core.config import settings
from app.services.ai_service import (
    _is_rate_limit_error,
    _extract_retry_delay,
    _send_chat_message_with_retry,
    run_agent_stream,
)
from google.generativeai import protos
from google.api_core import exceptions


def test_rate_limit_error_detection():
    # 1. ResourceExhausted exception
    exc = exceptions.ResourceExhausted("429 Resource has been exhausted (e.g. check quota)")
    assert _is_rate_limit_error(exc) is True

    # 2. Generic exception with 429 or quota in text
    assert _is_rate_limit_error(Exception("HTTP 429: Too Many Requests")) is True
    assert _is_rate_limit_error(Exception("quota limit exceeded")) is True
    assert _is_rate_limit_error(Exception("rate limit reached")) is True

    # 3. Non-rate-limit exception
    assert _is_rate_limit_error(ValueError("Invalid argument")) is False
    assert _is_rate_limit_error(Exception("500 Internal Server Error")) is False


def test_extract_retry_delay():
    # Default delay fallback
    assert _extract_retry_delay(Exception("generic error"), 3.5) == 3.5

    # Regex extracted delay from message
    msg_exc = Exception("Quota exceeded, please retry after 8.5s")
    assert _extract_retry_delay(msg_exc, 2.0) == 8.5

    msg_exc2 = Exception("Rate limit reached. Retry in 15 seconds")
    assert _extract_retry_delay(msg_exc2, 2.0) == 15.0


@pytest.mark.asyncio
async def test_duplicate_call_guard():
    """Verify that calling the same tool with identical arguments twice is suppressed."""
    call_log = []

    class MockChat:
        def __init__(self):
            self.turn = 0

        async def send_message_async(self, content):
            self.turn += 1
            if self.turn == 1:
                # Turn 1: model requests policy_estimate_cost TWICE with identical arguments
                return protos.GenerateContentResponse(
                    candidates=[
                        protos.Candidate(
                            content=protos.Content(
                                parts=[
                                    protos.Part(
                                        function_call=protos.FunctionCall(
                                            name="policy_estimate_cost",
                                            args={"replicas": 2, "environment": "dev"},
                                        )
                                    ),
                                    protos.Part(
                                        function_call=protos.FunctionCall(
                                            name="policy_estimate_cost",
                                            args={"replicas": 2, "environment": "dev"},
                                        )
                                    ),
                                ]
                            )
                        )
                    ],
                    usage_metadata=protos.GenerateContentResponse.UsageMetadata(
                        prompt_token_count=100, candidates_token_count=30, total_token_count=130
                    ),
                )
            else:
                # Record what the model received in turn 2
                call_log.append(content)
                return protos.GenerateContentResponse(
                    candidates=[
                        protos.Candidate(
                            content=protos.Content(parts=[protos.Part(text="Done.")])
                        )
                    ],
                    usage_metadata=protos.GenerateContentResponse.UsageMetadata(
                        prompt_token_count=150, candidates_token_count=10, total_token_count=160
                    ),
                )

    class MockModel:
        def start_chat(self, history=None):
            return MockChat()

    events = []
    async for sse in run_agent_stream("Test duplicate guard", str(uuid.uuid4()), model=MockModel()):
        for line in sse.splitlines():
            if line.startswith("data:"):
                events.append(json.loads(line[5:].strip()))

    # Verify tool events
    tool_results = [e for e in events if e.get("type") == "tool_result"]
    assert len(tool_results) == 2
    # Second tool result must be suppressed with "already retrieved above"
    assert "already retrieved above" in tool_results[1]["data"]["result"]["message"]

    # Verify function_responses received by the model in turn 2
    assert len(call_log) == 1
    func_responses = call_log[0]
    assert len(func_responses) == 2
    assert func_responses[1].function_response.response["result"] == "already retrieved above"


@pytest.mark.asyncio
async def test_quota_retry_and_clear_error_on_exhaustion():
    """Verify that 429 retries twice with THINKING event and yields clear error when exhausted."""
    attempts = 0

    class FailingChat:
        async def send_message_async(self, content):
            nonlocal attempts
            attempts += 1
            # Always fail with ResourceExhausted with retry delay of 0.05s
            raise exceptions.ResourceExhausted("429 Quota reached, retry after 0.05s")

    class FailingModel:
        def start_chat(self, history=None):
            return FailingChat()

    events = []
    async for sse in run_agent_stream("Test quota retry", str(uuid.uuid4()), model=FailingModel()):
        for line in sse.splitlines():
            if line.startswith("data:"):
                events.append(json.loads(line[5:].strip()))

    # Must attempt 1 initial + 2 retries = 3 total attempts
    assert attempts == 3

    # Must emit THINKING events during retry backoff
    thinking_events = [e for e in events if e.get("type") == "thinking"]
    retry_thinking = [e for e in thinking_events if "Rate limited, retrying in" in e["data"].get("message", "")]
    assert len(retry_thinking) == 2

    # Must emit final clear ERROR event
    error_events = [e for e in events if e.get("type") == "error"]
    assert len(error_events) == 1
    assert "AI quota was reached" in error_events[0]["data"]["message"]


@pytest.mark.asyncio
async def test_quota_retry_succeeds_on_second_attempt():
    """Verify that a transient rate limit retries and proceeds when subsequent attempt succeeds."""
    attempts = 0

    class TransientRateLimitChat:
        async def send_message_async(self, content):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise exceptions.ResourceExhausted("429 Too Many Requests, retry in 0.02s")
            return protos.GenerateContentResponse(
                candidates=[
                    protos.Candidate(
                        content=protos.Content(parts=[protos.Part(text="Successfully recovered.")])
                    )
                ],
                usage_metadata=protos.GenerateContentResponse.UsageMetadata(
                    prompt_token_count=50, candidates_token_count=10, total_token_count=60
                ),
            )

    class TransientModel:
        def start_chat(self, history=None):
            return TransientRateLimitChat()

    events = []
    async for sse in run_agent_stream("Test recovery", str(uuid.uuid4()), model=TransientModel()):
        for line in sse.splitlines():
            if line.startswith("data:"):
                events.append(json.loads(line[5:].strip()))

    assert attempts == 2
    final_events = [e for e in events if e.get("type") == "final_response"]
    assert len(final_events) == 1
    assert "Successfully recovered." in final_events[0]["data"]["message"]
