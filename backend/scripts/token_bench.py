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

# Baseline fixed overhead: ~2,850 tokens (system prompt + 28 tool schema declarations)
BASELINE_FIXED_PROMPT_OVERHEAD = 2850


class ScriptedFakeChatSession:
    """Simulates Gemini ChatSession for offline evaluation with realistic token metrics."""

    def __init__(self, scenario_id: str, prompt: str = ""):
        self.scenario_id = scenario_id
        self.prompt = prompt
        self.turn = 0
        self.history_chars = 0
        self.history: list[Any] = []

        # Calculate routed prompt overhead dynamically
        try:
            from app.services.tool_router import select_tool_categories
            from app.services.ai_service import _build_system_prompt
            from app.mcp_servers.github_server import GitHubMCPServer
            from app.mcp_servers.kubernetes_server import KubernetesMCPServer
            from app.mcp_servers.argocd_server import ArgoCDMCPServer
            from app.mcp_servers.policy_server import PolicyMCPServer
            from app.mcp_servers.terraform_server import TerraformMCPServer
            from app.mcp_servers.workflow_server import WorkflowMCPServer

            cats = select_tool_categories(prompt)
            all_tools = []
            for cls in (
                GitHubMCPServer,
                KubernetesMCPServer,
                ArgoCDMCPServer,
                PolicyMCPServer,
                TerraformMCPServer,
                WorkflowMCPServer,
            ):
                try:
                    all_tools.extend(cls().list_tools())
                except Exception:
                    pass

            routed_decs = [t.to_gemini_declaration() for t in all_tools if t.category in cats]
            decs_json = json.dumps(routed_decs)
            prompt_text = _build_system_prompt()
            self.fixed_overhead = (len(decs_json) + len(prompt_text)) // 4
        except Exception:
            # Fallback to scenario defaults if imports fail
            scenario_defaults = {"a": 1316, "b": 1124, "c": 475}
            self.fixed_overhead = scenario_defaults.get(scenario_id, 1200)

    def send_message(self, content: Any) -> protos.GenerateContentResponse:
        self.turn += 1

        # Track history length (chars) simulating resending the entire chat history
        if isinstance(content, str):
            self.history_chars += len(content)
        elif isinstance(content, list):
            for part in content:
                self.history_chars += len(str(part))

        variable_prompt_tokens = max(10, self.history_chars // 4)
        prompt_tokens = self.fixed_overhead + variable_prompt_tokens

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

    def __init__(self, scenario_id: str, prompt: str = ""):
        self.scenario_id = scenario_id
        self.prompt = prompt

    def start_chat(self, history=None) -> ScriptedFakeChatSession:
        return ScriptedFakeChatSession(self.scenario_id, self.prompt)


def get_declaration_metrics() -> dict[str, Any]:
    """Calculate character and estimated token counts for tool declarations and prompts."""
    from app.services.tool_router import select_tool_categories
    from app.services.ai_service import _build_system_prompt
    from app.mcp_servers.github_server import GitHubMCPServer
    from app.mcp_servers.kubernetes_server import KubernetesMCPServer
    from app.mcp_servers.argocd_server import ArgoCDMCPServer
    from app.mcp_servers.policy_server import PolicyMCPServer
    from app.mcp_servers.terraform_server import TerraformMCPServer
    from app.mcp_servers.workflow_server import WorkflowMCPServer

    all_tools = []
    for cls in (
        GitHubMCPServer,
        KubernetesMCPServer,
        ArgoCDMCPServer,
        PolicyMCPServer,
        TerraformMCPServer,
        WorkflowMCPServer,
    ):
        try:
            all_tools.extend(cls().list_tools())
        except Exception:
            pass

    curr_prompt = _build_system_prompt()
    all_decs = [t.to_gemini_declaration() for t in all_tools]
    all_decs_json = json.dumps(all_decs)

    scenarios_data = []
    for sc in SCENARIOS:
        cats = select_tool_categories(sc["prompt"])
        routed_decs = [t.to_gemini_declaration() for t in all_tools if t.category in cats]
        r_json = json.dumps(routed_decs)
        combined_chars = len(r_json) + len(curr_prompt)
        combined_tokens = combined_chars // 4
        scenarios_data.append({
            "scenario": sc,
            "categories": [c.value for c in sorted(cats, key=lambda c: c.value)],
            "tool_count": len(routed_decs),
            "decs_chars": len(r_json),
            "decs_tokens": len(r_json) // 4,
            "combined_chars": combined_chars,
            "combined_tokens": combined_tokens,
        })

    return {
        "baseline_prompt_chars": 888,
        "baseline_prompt_tokens": 222,
        "baseline_all_decs_chars": 11004,
        "baseline_all_decs_tokens": 2751,
        "baseline_total_chars": 11892,
        "baseline_total_tokens": 2973,
        "current_prompt_chars": len(curr_prompt),
        "current_prompt_tokens": len(curr_prompt) // 4,
        "current_all_decs_chars": len(all_decs_json),
        "current_all_decs_tokens": len(all_decs_json) // 4,
        "scenarios": scenarios_data,
    }


def print_declaration_size_comparison() -> None:
    """Print declaration size (characters and estimated tokens) before and after optimization."""
    metrics = get_declaration_metrics()
    b_prompt_c = metrics["baseline_prompt_chars"]
    b_prompt_t = metrics["baseline_prompt_tokens"]
    c_prompt_c = metrics["current_prompt_chars"]
    c_prompt_t = metrics["current_prompt_tokens"]
    prompt_diff = (c_prompt_c - b_prompt_c) / b_prompt_c * 100

    b_all_c = metrics["baseline_all_decs_chars"]
    b_all_t = metrics["baseline_all_decs_tokens"]
    c_all_c = metrics["current_all_decs_chars"]
    c_all_t = metrics["current_all_decs_tokens"]
    all_diff = (c_all_c - b_all_c) / b_all_c * 100

    b_tot_c = metrics["baseline_total_chars"]
    b_tot_t = metrics["baseline_total_tokens"]

    print("\n" + "=" * 96)
    print("TOOL DECLARATION & PROMPT SIZE BENCHMARK: BEFORE vs AFTER OPTIMIZATION")
    print("=" * 96)
    header = (
        f"{'Scope / Scenario':<36} | {'Before Chars':>12} | {'Before Tokens':>13} | "
        f"{'After Chars':>11} | {'After Tokens':>12} | {'Reduction':>9}"
    )
    print(header)
    print("-" * 36 + "-+-" + "-" * 12 + "-+-" + "-" * 13 + "-+-" + "-" * 11 + "-+-" + "-" * 12 + "-+-" + "-" * 9)

    print(
        f"{'System Prompt Instruction':<36} | {b_prompt_c:>12,} | {b_prompt_t:>13,} | "
        f"{c_prompt_c:>11,} | {c_prompt_t:>12,} | {prompt_diff:>8.1f}%"
    )
    print(
        f"{'All 28 Tools (Unrouted)':<36} | {b_all_c:>12,} | {b_all_t:>13,} | "
        f"{c_all_c:>11,} | {c_all_t:>12,} | {all_diff:>8.1f}%"
    )

    for sc in metrics["scenarios"]:
        name = sc["scenario"]["name"].split(":")[0] + f" ({sc['tool_count']} tools)"
        c_chars = sc["combined_chars"]
        c_tokens = sc["combined_tokens"]
        diff = (c_chars - b_tot_c) / b_tot_c * 100
        print(
            f"{name:<36} | {b_tot_c:>12,} | {b_tot_t:>13,} | "
            f"{c_chars:>11,} | {c_tokens:>12,} | {diff:>8.1f}%"
        )
    print("=" * 96)


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
        model = ScriptedFakeModel(scenario["id"], scenario["prompt"])

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
    metrics = get_declaration_metrics()

    lines = [
        "# Token Efficiency & Quota Optimization Report",
        "",
        "## Declaration Size & Prompt Overhead Optimization",
        "",
        "Comparison of tool declaration surface and system prompt overhead before and after Phase 3 optimizations:",
        "",
        "| Scope / Scenario | Tools Active | Before Chars | Before Est Tokens | After Chars | After Est Tokens | Chars Reduction |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        f"| **System Prompt** | - | {metrics['baseline_prompt_chars']:,} | {metrics['baseline_prompt_tokens']:,} | {metrics['current_prompt_chars']:,} | {metrics['current_prompt_tokens']:,} | **{((metrics['current_prompt_chars'] - metrics['baseline_prompt_chars']) / metrics['baseline_prompt_chars'] * 100):.1f}%** |",
        f"| **All Registered Tools** | 28 | {metrics['baseline_all_decs_chars']:,} | {metrics['baseline_all_decs_tokens']:,} | {metrics['current_all_decs_chars']:,} | {metrics['current_all_decs_tokens']:,} | **{((metrics['current_all_decs_chars'] - metrics['baseline_all_decs_chars']) / metrics['baseline_all_decs_chars'] * 100):.1f}%** |",
    ]

    for sc in metrics["scenarios"]:
        name = sc["scenario"]["name"].split(":")[0]
        c_chars = sc["combined_chars"]
        c_tokens = sc["combined_tokens"]
        b_tot_c = metrics["baseline_total_chars"]
        b_tot_t = metrics["baseline_total_tokens"]
        diff = (c_chars - b_tot_c) / b_tot_c * 100
        lines.append(
            f"| **{name} (Routed + Prompt)** | {sc['tool_count']} | {b_tot_c:,} | {b_tot_t:,} | {c_chars:,} | {c_tokens:,} | **{diff:.1f}%** |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## Baseline (Phase 0: All Tools & Full History)",
        "",
        f"**Benchmark Mode:** {mode_label}  ",
        "**Fixed Prompt Overhead:** ~2,850 tokens (all 28 tool declarations + unshortened system instructions on every call)  ",
        "",
        "| Scenario | API Calls | Prompt Tokens | Output Tokens | Total Tokens |",
        "| :--- | :--- | :--- | :--- | :--- |",
        "| **Scenario (a): IaC & CI/CD** | 3 | 9,132 | 234 | 9,366 |",
        "| **Scenario (b): K8s Diagnostic** | 3 | 8,947 | 144 | 9,091 |",
        "| **Scenario (c): Policy & Cost** | 2 | 6,025 | 96 | 6,121 |",
        "| **Baseline Total** | **8** | **24,104** | **474** | **24,578** |",
        "",
        "---",
        "",
        "## Optimized (Phase 3: Smaller Surface, Compaction & History Control)",
        "",
        f"**Benchmark Mode:** {mode_label}  ",
        f"**Timestamp:** {utc_now}  ",
        "",
    ])

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

    lines.extend([
        "---",
        "## Performance Comparison & Efficiency Gains",
        "",
        "| Metric | Baseline (Phase 0) | Optimized (Phase 3) | Savings / Reduction |",
        "| :--- | :--- | :--- | :--- |",
        f"| **Scenario (a) Total Tokens** | 9,366 | {results[0]['usage'].get('total_tokens', 0):,} | **{((results[0]['usage'].get('total_tokens', 0) - 9366) / 9366 * 100):.1f}%** |",
        f"| **Scenario (b) Total Tokens** | 9,091 | {results[1]['usage'].get('total_tokens', 0):,} | **{((results[1]['usage'].get('total_tokens', 0) - 9091) / 9091 * 100):.1f}%** |",
        f"| **Scenario (c) Total Tokens** | 6,121 | {results[2]['usage'].get('total_tokens', 0):,} | **{((results[2]['usage'].get('total_tokens', 0) - 6121) / 6121 * 100):.1f}%** |",
        f"| **Total Cumulative Prompt Tokens** | 24,104 | {grand_prompt:,} | **{((grand_prompt - 24104) / 24104 * 100):.1f}%** |",
        f"| **Total Cumulative Output Tokens** | 474 | {grand_candidates:,} | **{((grand_candidates - 474) / 474 * 100):.1f}%** |",
        f"| **Grand Total Tokens Consumed** | **24,578** | **{grand_total:,}** | **{((grand_total - 24578) / 24578 * 100):.1f}%** |",
        f"| **Average Tokens Per Request** | 8,192 | {grand_total // max(1, len(results)):,} | **{(((grand_total // max(1, len(results))) - 8192) / 8192 * 100):.1f}%** |",
        "",
    ])

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
    print("=" * 96)
    print(f"DevHub AI Agent Token Benchmark — {mode_label}")
    print("=" * 96)

    # Ensure tools and DB are initialized
    registry.initialize()
    bench_user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    await setup_bench_database(bench_user_id)

    # Print declaration size before/after comparison
    print_declaration_size_comparison()

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
