"""
Context Budgeting & Result Compaction Service.

Optimizes token consumption by pruning, truncating, and summarizing tool outputs
before feeding them back to Gemini or streaming them to the UI:
- Enforces strict character budgets (TOOL_RESULT_MAX_CHARS, UI_RESULT_MAX_CHARS)
- Preserves full error messages
- Applies specialized per-tool summarization rules (terraform_plan, terraform_init, k8s logs, etc.)
- In-place compaction of older turns in chat history while preserving model thought signatures
"""

from __future__ import annotations

import copy
import json
import logging
import re
from typing import Any

from app.core.config import settings
from google.generativeai import protos

logger = logging.getLogger(__name__)


def truncate_head_tail(
    text: str,
    max_chars: int,
    tool_name: str = "",
) -> str:
    """
    Truncates a large string by keeping head and tail portions,
    inserting an explicit marker indicating how many characters were omitted.
    Error messages must never be truncated.
    """
    if not text or len(text) <= max_chars:
        return text

    if "file" in tool_name:
        marker_template = "\n[... {omitted} chars omitted; use terraform_get_file with start_line/end_line to read more ...]\n"
    else:
        marker_template = "\n[... {omitted} chars omitted ...]\n"

    # Estimate marker length (~100 chars)
    dummy_marker = marker_template.format(omitted=len(text))
    available = max_chars - len(dummy_marker)
    if available < 100:
        available = 100

    keep_half = available // 2
    head = text[:keep_half]
    tail = text[-keep_half:]
    omitted = len(text) - (len(head) + len(tail))
    marker = marker_template.format(omitted=max(0, omitted))

    return head + marker + tail


def collapse_identical_lines(text: str) -> str:
    """Collapses consecutive identical lines in log outputs into 'line (x N)'."""
    if not text:
        return ""
    lines = text.splitlines()
    if not lines:
        return ""

    collapsed: list[str] = []
    current_line = lines[0]
    count = 1

    for line in lines[1:]:
        if line == current_line:
            count += 1
        else:
            if count > 1:
                collapsed.append(f"{current_line} (x {count})")
            else:
                collapsed.append(current_line)
            current_line = line
            count = 1

    if count > 1:
        collapsed.append(f"{current_line} (x {count})")
    else:
        collapsed.append(current_line)

    return "\n".join(collapsed)


def compact_terraform_plan(plan_text: str, max_chars: int) -> str:
    """
    Summarizes a Terraform plan:
    - Retains lines starting with '# <resource> will be ...'
    - Retains 'Plan: X to add, Y to change, Z to destroy' (or 'No changes...')
    - If overall plan is small or structured markers aren't found, uses head/tail truncation.
    """
    if not plan_text:
        return ""

    lines = plan_text.splitlines()
    resource_headers: list[str] = []
    plan_summary_line = ""

    for line in lines:
        stripped = line.strip()
        # Capture resource headers like: '# aws_instance.web will be created'
        if stripped.startswith("# ") and " will be " in stripped:
            resource_headers.append(stripped)
        # Capture plan summary line like: 'Plan: 1 to add, 0 to change, 0 to destroy.'
        elif stripped.startswith("Plan:") or "No changes. Your infrastructure matches the configuration." in stripped:
            plan_summary_line = stripped

    if resource_headers or plan_summary_line:
        summary_parts = ["[Compacted Speculative Terraform Plan]"]
        if resource_headers:
            summary_parts.extend(resource_headers)
        if plan_summary_line:
            summary_parts.append(plan_summary_line)
        else:
            summary_parts.append("(Attribute details truncated to conserve context budget)")
        result = "\n".join(summary_parts)
        if len(result) <= max_chars:
            return result

    # Fallback to head/tail truncation
    return truncate_head_tail(plan_text, max_chars, tool_name="terraform_plan")


def compact_for_model(tool_name: str, result_dict: dict[str, Any]) -> dict[str, Any]:
    """
    Compacts a tool execution result dictionary specifically for feeding back to Gemini.
    Enforces settings.TOOL_RESULT_MAX_CHARS (default 4000).
    Never truncates error messages.
    """
    max_chars = settings.TOOL_RESULT_MAX_CHARS
    compacted = copy.deepcopy(result_dict)

    # 1. Never truncate error messages
    if not compacted.get("success", True):
        return compacted

    data = compacted.get("data")
    if not isinstance(data, dict):
        if isinstance(data, str) and len(data) > max_chars:
            compacted["data"] = truncate_head_tail(data, max_chars, tool_name)
        return compacted

    # 2. Per-tool compaction rules
    if tool_name == "terraform_plan":
        plan_raw = data.get("plan_output") or data.get("plan") or data.get("stdout") or ""
        if isinstance(plan_raw, str):
            data["plan_output"] = compact_terraform_plan(plan_raw, max_chars)

    elif tool_name == "terraform_init":
        # Return success flag plus the last 10 lines of output
        out = data.get("output") or data.get("stdout") or ""
        if isinstance(out, str):
            lines = out.splitlines()
            last_10 = lines[-10:] if len(lines) > 10 else lines
            data["output"] = "\n".join(last_10)

    elif tool_name == "terraform_validate":
        # Cap diagnostics at 20 entries and report dropped count
        diagnostics = data.get("diagnostics")
        if isinstance(diagnostics, list) and len(diagnostics) > 20:
            dropped = len(diagnostics) - 20
            data["diagnostics"] = diagnostics[:20]
            data["diagnostics_summary"] = f"Showing first 20 of {len(diagnostics)} diagnostics ({dropped} dropped to conserve tokens)."

    elif tool_name in ("terraform_list_files", "workflow_list"):
        # Cap entries at 100 with total count
        key = "files" if tool_name == "terraform_list_files" else "workflows"
        items = data.get(key)
        if isinstance(items, list) and len(items) > 100:
            dropped = len(items) - 100
            data[key] = items[:100]
            data["total_count"] = len(items)
            data["truncated"] = True
            data["truncation_message"] = f"Showing first 100 entries ({dropped} omitted)."

    elif tool_name in ("k8s_get_logs", "k8s_get_pod_logs"):
        logs = data.get("logs") or data.get("output") or ""
        if isinstance(logs, str):
            # Collapse consecutive identical lines
            collapsed = collapse_identical_lines(logs)
            if len(collapsed) > max_chars:
                collapsed = truncate_head_tail(collapsed, max_chars, tool_name)
            data["logs"] = collapsed

    elif tool_name in ("terraform_get_file", "github_get_file_content"):
        content = data.get("content") or ""
        if isinstance(content, str) and len(content) > max_chars:
            data["content"] = truncate_head_tail(content, max_chars, tool_name)

    else:
        # General fallback: check any large string values
        for k, v in list(data.items()):
            if isinstance(v, str) and len(v) > max_chars:
                data[k] = truncate_head_tail(v, max_chars, tool_name)

    return compacted


def compact_for_ui(tool_name: str, result_dict: dict[str, Any]) -> dict[str, Any]:
    """
    Compacts a tool result for the frontend UI SSE tool_result event.
    Enforces settings.UI_RESULT_MAX_CHARS (default 20000).
    Never truncates error messages.
    """
    max_chars = settings.UI_RESULT_MAX_CHARS
    compacted = copy.deepcopy(result_dict)

    if not compacted.get("success", True):
        return compacted

    data = compacted.get("data")
    if not isinstance(data, dict):
        if isinstance(data, str) and len(data) > max_chars:
            compacted["data"] = truncate_head_tail(data, max_chars, tool_name)
        return compacted

    for k, v in list(data.items()):
        if isinstance(v, str) and len(v) > max_chars:
            data[k] = truncate_head_tail(v, max_chars, tool_name)

    return compacted


def compact_chat_history(history: list[Any]) -> None:
    """
    In-place compaction of older turns in chat history.
    
    Rules:
    - Never modify or drop model-role parts (preserves model thought signatures and function call IDs).
    - Compact ONLY function_response parts that we authored in older iterations.
    - Replaces older function_response contents with a one-line stub: (tool name, success flag, first 200 chars).
    """
    for content in history:
        # Strict rule: NEVER alter model-authored parts
        role = getattr(content, "role", "")
        if role == "model":
            continue

        parts = getattr(content, "parts", [])
        for i, part in enumerate(parts):
            fc_resp = getattr(part, "function_response", None)
            if fc_resp and getattr(fc_resp, "name", None):
                tool_name = fc_resp.name
                resp_payload = getattr(fc_resp, "response", {})

                # Skip if already compacted
                if isinstance(resp_payload, dict) and resp_payload.get("_compacted"):
                    continue

                # Extract success flag
                success = True
                if isinstance(resp_payload, dict):
                    res_val = resp_payload.get("result", {})
                    if isinstance(res_val, dict):
                        success = res_val.get("success", True)
                    elif isinstance(resp_payload.get("success"), bool):
                        success = resp_payload["success"]

                # Extract first 200 chars of result text
                resp_str = json.dumps(resp_payload, default=str) if isinstance(resp_payload, dict) else str(resp_payload)
                first_200 = resp_str[:200].replace("\n", " ").replace('"', "'")

                stub = f"[{tool_name} (success={success}): {first_200}... (older turn output compacted)]"
                parts[i] = protos.Part(
                    function_response=protos.FunctionResponse(
                        name=tool_name,
                        response={"result": stub, "_compacted": True},
                    )
                )
