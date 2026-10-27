"""
Token Benchmark Script for DevHub AI Agent.

Evaluates token consumption across 3 canonical DevOps scenarios:
1. "Create the Terraform infrastructure for my project and prepare a CI/CD workflow"
2. "Why is my pod in CrashLoopBackOff?"
3. "Estimate cost for 4 replicas with postgres"

Supports:
- Real Gemini API mode (uses settings.GEMINI_API_KEY)
- Scripted Fake Model mode (offline replay of canned function calls with length-based usage estimation)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import uuid
from typing import Any
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.core.database import async_session_factory, init_db
from app.models.user import User, UserRole
from app.mcp_servers.registry import registry
from app.services.ai_service import run_agent_stream
from google.generativeai import protos

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("token_bench")


SCENARIOS = [
    {
        "id": "a",
        "name": "Scenario (a): Provisioning IaC & CI/CD Pipeline",
        "prompt": "Create the Terraform infrastructure for my project and prepare a CI/CD workflow",
    },
    {
        "id": "b",
        "name": "Scenario (b): Diagnostic Kubernetes Troubleshooting",
        "prompt": "Why is my pod in CrashLoopBackOff?",
    },
    {
        "id": "c",
        "name": "Scenario (c): Policy & Cost Estimation",
        "prompt": "Estimate cost for 4 replicas with postgres",
    },
]

# Baseline fixed overhead: ~2,850 tokens (system prompt + 29 tool schema declarations)
FIXED_PROMPT_OVERHEAD = 2850


class ScriptedFakeChatSession:
    """Simulates Gemini ChatSession for offline evaluation with realistic token metrics."""

    def __init__(self, scenario_id: str):
        self.scenario_id = scenario_id
        self.turn = 0
        self.history_chars = 0

    def send_message(self, content: Any) -> protos.GenerateContentResponse:
        self.turn += 1

        # Track history length (chars) simulating resending the entire chat history
        if isinstance(content, str):
            self.history_chars += len(content)
        elif isinstance(content, list):
            for part in content:
                self.history_chars += len(str(part))

        variable_prompt_tokens = max(10, self.history_chars // 4)
        prompt_tokens = FIXED_PROMPT_OVERHEAD + variable_prompt_tokens

        if self.scenario_id == "a":
            return self._handle_scenario_a(prompt_tokens)
        elif self.scenario_id == "b":
            return self._handle_scenario_b(prompt_tokens)
        else:
            return self._handle_scenario_c(prompt_tokens)

    async def send_message_async(self, content: Any) -> protos.GenerateContentResponse:
        return self.send_message(content)

    def _handle_scenario_a(self, prompt_tokens: int) -> protos.GenerateContentResponse:
        if self.turn == 1:
            # First tool call: create Terraform config
            tf_content = (
                'resource "aws_s3_bucket" "app_storage" {\n'
                '  bucket = "student-app-bucket"\n'
                '  force_destroy = true\n'
                '}\n'
            )
            self.history_chars += len(tf_content)
            candidates_tokens = 92
            return protos.GenerateContentResponse(
                candidates=[
                    protos.Candidate(
                        content=protos.Content(
                            parts=[
                                protos.Part(
                                    function_call=protos.FunctionCall(
                                        name="terraform_write_file",
                                        args={
                                            "file_path": "main.tf",
                                            "content": tf_content,
                                        },
                                    )
                                )
                            ]
                        )
                    )
                ],
                usage_metadata=protos.GenerateContentResponse.UsageMetadata(
                    prompt_token_count=prompt_tokens,
                    candidates_token_count=candidates_tokens,
                    total_token_count=prompt_tokens + candidates_tokens,
                ),
            )
        elif self.turn == 2:
            # Second tool call: create CI/CD workflow
            wf_content = (
                "name: CI Pipeline\n"
                "on: [push]\n"
                "jobs:\n"
                "  test:\n"
                "    runs-on: ubuntu-latest\n"
                "    steps:\n"
                "      - uses: actions/checkout@v4\n"
                "      - run: echo 'Testing and building...'\n"
            )
            self.history_chars += len(wf_content)
            candidates_tokens = 84
            return protos.GenerateContentResponse(
                candidates=[
                    protos.Candidate(
                        content=protos.Content(
                            parts=[
                                protos.Part(
                                    function_call=protos.FunctionCall(
                                        name="workflow_write",
                                        args={
                                            "workflow_name": "ci.yaml",
                                            "content": wf_content,
                                        },
                                    )
                                )
                            ]
                        )
                    )
                ],
                usage_metadata=protos.GenerateContentResponse.UsageMetadata(
                    prompt_token_count=prompt_tokens,
                    candidates_token_count=candidates_tokens,
                    total_token_count=prompt_tokens + candidates_tokens,
                ),
            )
        else:
            # Final text response
            text = (
                "I have prepared the Terraform infrastructure (main.tf) and GitHub Actions CI/CD workflow (ci.yaml). "
                "Both operations are mutating actions requiring approval from a guide or admin before being executed."
            )
            candidates_tokens = 58
            return protos.GenerateContentResponse(
                candidates=[
                    protos.Candidate(
                        content=protos.Content(
                            parts=[protos.Part(text=text)]
                        )
                    )
                ],
                usage_metadata=protos.GenerateContentResponse.UsageMetadata(
                    prompt_token_count=prompt_tokens,
                    candidates_token_count=candidates_tokens,
                    total_token_count=prompt_tokens + candidates_tokens,
                ),
            )

    def _handle_scenario_b(self, prompt_tokens: int) -> protos.GenerateContentResponse:
        if self.turn == 1:
            candidates_tokens = 32
            return protos.GenerateContentResponse(
                candidates=[
                    protos.Candidate(
                        content=protos.Content(
                            parts=[
                                protos.Part(
                                    function_call=protos.FunctionCall(
                                        name="k8s_list_pods",
                                        args={"namespace": "default"},
                                    )
                                )
                            ]
                        )
                    )
                ],
                usage_metadata=protos.GenerateContentResponse.UsageMetadata(
                    prompt_token_count=prompt_tokens,
                    candidates_token_count=candidates_tokens,
                    total_token_count=prompt_tokens + candidates_tokens,
                ),
            )
        elif self.turn == 2:
            candidates_tokens = 46
            return protos.GenerateContentResponse(
                candidates=[
                    protos.Candidate(
                        content=protos.Content(
                            parts=[
                                protos.Part(
                                    function_call=protos.FunctionCall(
                                        name="k8s_get_pod_logs",
                                        args={
                                            "namespace": "default",
                                            "pod_name": "order-service-7f8d6-4x21",
                                            "tail_lines": 50,
                                            "previous": True,
                                        },
                                    )
                                )
                            ]
                        )
                    )
                ],
                usage_metadata=protos.GenerateContentResponse.UsageMetadata(
                    prompt_token_count=prompt_tokens,
                    candidates_token_count=candidates_tokens,
                    total_token_count=prompt_tokens + candidates_tokens,
                ),
            )
        else:
            text = (
                "Diagnosis: The pod 'order-service-7f8d6-4x21' is crashing due to a missing environment variable: "
                "panic: standard_init_linux.go:228: exec user process caused: DATABASE_URL not set. "
                "Please configure DATABASE_URL in your Kubernetes ConfigMap/Secret and redeploy."
            )
            candidates_tokens = 66
            return protos.GenerateContentResponse(
                candidates=[
                    protos.Candidate(
                        content=protos.Content(
                            parts=[protos.Part(text=text)]
                        )
                    )
                ],
                usage_metadata=protos.GenerateContentResponse.UsageMetadata(
                    prompt_token_count=prompt_tokens,
                    candidates_token_count=candidates_tokens,
                    total_token_count=prompt_tokens + candidates_tokens,
                ),
            )

    def _handle_scenario_c(self, prompt_tokens: int) -> protos.GenerateContentResponse:
        if self.turn == 1:
            candidates_tokens = 42
            return protos.GenerateContentResponse(
                candidates=[
                    protos.Candidate(
                        content=protos.Content(
                            parts=[
                                protos.Part(
                                    function_call=protos.FunctionCall(
                                        name="policy_estimate_cost",
                                        args={
                                            "replicas": 4,
                                            "environment": "development",
                                            "instance_type": "t3.medium",
                                            "storage_gb": 50,
                                        },
                                    )
                                )
                            ]
                        )
                    )
                ],
                usage_metadata=protos.GenerateContentResponse.UsageMetadata(
                    prompt_token_count=prompt_tokens,
                    candidates_token_count=candidates_tokens,
                    total_token_count=prompt_tokens + candidates_tokens,
                ),
            )
        else:
            text = (
                "Cost Estimation: Running 4 replicas of t3.medium with 50GB PostgreSQL storage in development "
                "is estimated at $168.00 per month (Compute: $152.00, Storage: $16.00). "
                "This request complies with the standard student resource policy."
            )
            candidates_tokens = 54
            return protos.GenerateContentResponse(
                candidates=[
                    protos.Candidate(
                        content=protos.Content(
                            parts=[protos.Part(text=text)]
                        )
                    )
                ],
                usage_metadata=protos.GenerateContentResponse.UsageMetadata(
                    prompt_token_count=prompt_tokens,
                    candidates_token_count=candidates_tokens,
                    total_token_count=prompt_tokens + candidates_tokens,
                ),
            )


class ScriptedFakeModel:
    """Fake GenerativeModel producing scripted canned responses."""

    def __init__(self, scenario_id: str):
        self.scenario_id = scenario_id

    def start_chat(self, history=None) -> ScriptedFakeChatSession:
        return ScriptedFakeChatSession(self.scenario_id)


async def setup_bench_database(user_id: uuid.UUID) -> None:
    """Ensure database tables exist and benchmark user record is present."""
    await init_db()
    async with async_session_factory() as db:
        user = await db.get(User, user_id)
        if not user:
            user = User(
                id=user_id,
                email="bench@academic-idp.local",
                full_name="Benchmark User",
                role=UserRole.STUDENT,
            )
            db.add(user)
            await db.commit()


async def run_scenario_benchmark(
    scenario: dict[str, str],
    user_id: uuid.UUID,
    use_real: bool,
) -> dict[str, Any]:
    """Run one scenario through run_agent_stream and collect usage metrics."""
    model = None
    if not use_real:
        model = ScriptedFakeModel(scenario["id"])

    collected_events = []
    final_usage: dict[str, Any] = {}

    async for sse_chunk in run_agent_stream(
        message=scenario["prompt"],
        user_id=str(user_id),
        model=model,
    ):
        for line in sse_chunk.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                try:
                    payload = json.loads(line[5:].strip())
                    event_type = payload.get("type")
                    collected_events.append(payload)
                    if event_type == "final_response":
                        final_usage = payload.get("data", {}).get("usage", {})
                except Exception:
                    pass

    return {
        "scenario": scenario,
        "usage": final_usage,
        "event_count": len(collected_events),
    }


def format_markdown_report(results: list[dict[str, Any]], mode_label: str) -> str:
    """Format benchmark results into Markdown for docs/token_efficiency.md."""
    from datetime import datetime, timezone
    utc_now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        f"# Token Efficiency & Quota Optimization Report",
        f"",
        f"## Baseline",
        f"",
        f"**Benchmark Mode:** {mode_label}  ",
        f"**Timestamp:** {utc_now}  ",
        f"**Fixed Prompt Overhead:** ~{FIXED_PROMPT_OVERHEAD} tokens (all 29 tool schemas + system instructions declared on every call)",
        f"",
        f"---",
        f"",
    ]

    grand_calls = 0
    grand_prompt = 0
    grand_candidates = 0
    grand_total = 0

    for res in results:
        sc = res["scenario"]
        usage = res["usage"]
        calls = usage.get("calls", [])

        total_p = usage.get("prompt_tokens", 0)
        total_c = usage.get("candidates_tokens", 0)
        total_t = usage.get("total_tokens", 0)
        api_calls = usage.get("api_calls", len(calls))

        grand_calls += api_calls
        grand_prompt += total_p
        grand_candidates += total_c
        grand_total += total_t

        lines.append(f"### {sc['name']}")
        lines.append(f"**Prompt:** `{sc['prompt']}`  ")
        lines.append(f"**API Calls:** {api_calls}  ")
        lines.append("")
        lines.append("| Call # | Iteration | Prompt Tokens | Output Tokens | Total Tokens |")
        lines.append("| :--- | :--- | :--- | :--- | :--- |")

        for c in calls:
            lines.append(
                f"| Call {c.get('call_index')} | Iteration {c.get('iteration')} | "
                f"{c.get('prompt_tokens'):,} | {c.get('candidates_tokens'):,} | {c.get('total_tokens'):,} |"
            )

        lines.append(
            f"| **Total** | - | **{total_p:,}** | **{total_c:,}** | **{total_t:,}** |"
        )
        lines.append("")

    lines.append("---")
    lines.append("## Baseline Summary Totals")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| :--- | :--- |")
    lines.append(f"| **Total Scenarios Evaluated** | {len(results)} |")
    lines.append(f"| **Total API Calls Across Scenarios** | {grand_calls} |")
    lines.append(f"| **Total Cumulative Prompt Tokens** | {grand_prompt:,} |")
    lines.append(f"| **Total Cumulative Output Tokens** | {grand_candidates:,} |")
    lines.append(f"| **Grand Total Tokens Consumed** | **{grand_total:,}** |")
    lines.append(f"| **Average Tokens Per Request** | {grand_total // max(1, len(results)):,} |")
    lines.append("")

    return "\n".join(lines)


async def main():
    parser = argparse.ArgumentParser(description="DevHub AI Agent Token Benchmark")
    parser.add_argument("--real", action="store_true", help="Force real Gemini API call")
    parser.add_argument("--fake", action="store_true", help="Force offline fake model")
    parser.add_argument(
        "--output-file",
        type=str,
        default=str(backend_dir.parent / "docs" / "token_efficiency.md"),
        help="Path to save markdown results",
    )
    args = parser.parse_args()

    use_real = False
    if args.real:
        if not settings.GEMINI_API_KEY:
            print("ERROR: --real requested but GEMINI_API_KEY is not configured.", file=sys.stderr)
            sys.exit(1)
        use_real = True
    elif args.fake:
        use_real = False
    else:
        # Default: if GEMINI_API_KEY is present and valid, can use real, else fake
        use_real = bool(settings.GEMINI_API_KEY)

    mode_label = "Real Gemini Model" if use_real else "Offline Scripted Fake Model"
    print("=" * 80)
    print(f"DevHub AI Agent Token Benchmark — {mode_label}")
    print("=" * 80)

    # Ensure tools and DB are initialized
    registry.initialize()
    bench_user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    await setup_bench_database(bench_user_id)

    results = []
    for sc in SCENARIOS:
        print(f"\nRunning {sc['name']}...")
        res = await run_scenario_benchmark(sc, bench_user_id, use_real)
        results.append(res)

        usage = res["usage"]
        calls = usage.get("calls", [])
        print(f"  API Calls: {usage.get('api_calls', len(calls))}")
        for c in calls:
            print(
                f"    Call {c.get('call_index')} (Iter {c.get('iteration')}): "
                f"Prompt: {c.get('prompt_tokens'):,} | "
                f"Output: {c.get('candidates_tokens'):,} | "
                f"Total: {c.get('total_tokens'):,}"
            )
        print(
            f"  Totals -> Prompt: {usage.get('prompt_tokens', 0):,} | "
            f"Output: {usage.get('candidates_tokens', 0):,} | "
            f"Total: {usage.get('total_tokens', 0):,}"
        )

    # Format report
    report_md = format_markdown_report(results, mode_label)

    # Save to output file
    out_path = Path(args.output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report_md, encoding="utf-8")
    print(f"\nSaved benchmark results to {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
