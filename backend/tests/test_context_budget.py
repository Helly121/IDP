"""
Unit tests for context_budget module and per-tool compaction rules.
"""

import pytest
from app.core.config import settings
from app.services.context_budget import (
    truncate_head_tail,
    collapse_identical_lines,
    compact_terraform_plan,
    compact_for_model,
    compact_for_ui,
    compact_chat_history,
)
from google.generativeai import protos


def test_truncate_head_tail():
    short_text = "This is a short line."
    assert truncate_head_tail(short_text, max_chars=100) == short_text

    long_text = "A" * 5000
    truncated = truncate_head_tail(long_text, max_chars=500, tool_name="terraform_get_file")
    assert len(truncated) <= 600
    assert "chars omitted; use terraform_get_file with start_line/end_line to read more" in truncated
    assert truncated.startswith("AAAA")
    assert truncated.endswith("AAAA")


def test_collapse_identical_lines():
    logs = (
        "Starting container\n"
        "Connecting to database...\n"
        "Connecting to database...\n"
        "Connecting to database...\n"
        "Connecting to database...\n"
        "Connection successful\n"
        "Heartbeat OK\n"
        "Heartbeat OK\n"
    )
    collapsed = collapse_identical_lines(logs)
    expected = (
        "Starting container\n"
        "Connecting to database... (x 4)\n"
        "Connection successful\n"
        "Heartbeat OK (x 2)"
    )
    assert collapsed == expected


def test_compact_terraform_plan():
    raw_plan = """
Terraform used the selected providers to generate the following execution plan.
Resource actions are indicated with the following symbols:
  + create
  ~ update in-place

Terraform will perform the following actions:

  # aws_instance.web will be created
  + resource "aws_instance" "web" {
      + ami                          = "ami-0c55b159cbfafe1f0"
      + arn                          = (known after apply)
      + associate_public_ip_address = (known after apply)
      + availability_zone           = (known after apply)
      + cpu_core_count               = (known after apply)
      + cpu_threads_per_core         = (known after apply)
      + id                           = (known after apply)
      + instance_state               = (known after apply)
      + instance_type                = "t3.micro"
    }

  # aws_s3_bucket.data will be updated in-place
  ~ resource "aws_s3_bucket" "data" {
      ~ bucket_prefix = "old-" -> "new-"
    }

Plan: 1 to add, 1 to change, 0 to destroy.

─────────────────────────────────────────────────────────────────────────────
"""
    compacted = compact_terraform_plan(raw_plan, max_chars=500)
    assert "# aws_instance.web will be created" in compacted
    assert "# aws_s3_bucket.data will be updated in-place" in compacted
    assert "Plan: 1 to add, 1 to change, 0 to destroy." in compacted
    assert "+ cpu_threads_per_core" not in compacted  # Attribute details omitted!


def test_compact_for_model_per_tool():
    # 1. Error messages are never truncated
    err_result = {"success": False, "error": "Very long error details: " + ("E" * 10000)}
    compacted_err = compact_for_model("any_tool", err_result)
    assert len(compacted_err["error"]) > 10000

    # 2. terraform_init: last 10 lines
    init_out = "\n".join([f"Init line {i}" for i in range(50)])
    init_result = {"success": True, "data": {"output": init_out}}
    compacted_init = compact_for_model("terraform_init", init_result)
    lines = compacted_init["data"]["output"].splitlines()
    assert len(lines) == 10
    assert lines[-1] == "Init line 49"

    # 3. terraform_validate: cap diagnostics at 20
    diagnostics = [{"severity": "warning", "summary": f"Warning {i}"} for i in range(35)]
    val_result = {"success": True, "data": {"diagnostics": diagnostics}}
    compacted_val = compact_for_model("terraform_validate", val_result)
    assert len(compacted_val["data"]["diagnostics"]) == 20
    assert "15 dropped" in compacted_val["data"]["diagnostics_summary"]

    # 4. terraform_list_files & workflow_list: cap at 100
    files = [{"path": f"iac/file_{i}.tf"} for i in range(150)]
    list_result = {"success": True, "data": {"files": files}}
    compacted_list = compact_for_model("terraform_list_files", list_result)
    assert len(compacted_list["data"]["files"]) == 100
    assert compacted_list["data"]["total_count"] == 150
    assert compacted_list["data"]["truncated"] is True

    # 5. File contents over TOOL_RESULT_MAX_CHARS (4000)
    file_content = "resource \"test\" {\n" + ("  attr = true\n" * 500) + "}\n"
    file_result = {"success": True, "data": {"content": file_content}}
    compacted_file = compact_for_model("terraform_get_file", file_result)
    assert len(compacted_file["data"]["content"]) <= settings.TOOL_RESULT_MAX_CHARS + 200
    assert "chars omitted" in compacted_file["data"]["content"]


def test_compact_for_ui_budget():
    # Result between 4,000 and 20,000 chars stays full for UI but truncated for model
    mid_content = "X" * 8000
    res = {"success": True, "data": {"content": mid_content}}

    ui_res = compact_for_ui("terraform_get_file", res)
    assert len(ui_res["data"]["content"]) == 8000  # Within UI budget (20,000)

    model_res = compact_for_model("terraform_get_file", res)
    assert len(model_res["data"]["content"]) < 4200  # Truncated to model budget (4,000)


def test_compact_chat_history_preserves_model_thought_signatures():
    # Setup history with model thought/function call and older user function_response
    history = [
        protos.Content(
            role="user",
            parts=[protos.Part(text="Check terraform files")]
        ),
        protos.Content(
            role="model",
            parts=[
                protos.Part(text="Thinking: User wants file inspection..."),  # Thought signature
                protos.Part(function_call=protos.FunctionCall(name="terraform_plan", args={"dir": "dev"})),
            ]
        ),
        protos.Content(
            role="user",
            parts=[
                protos.Part(
                    function_response=protos.FunctionResponse(
                        name="terraform_plan",
                        response={"result": {"plan_output": "Huge output " * 500, "success": True}}
                    )
                )
            ]
        ),
        protos.Content(
            role="model",
            parts=[
                protos.Part(function_call=protos.FunctionCall(name="terraform_validate", args={})),
            ]
        ),
    ]

    compact_chat_history(history)

    # 1. Model parts must remain strictly untouched
    assert len(history[1].parts) == 2
    assert "Thinking: User wants file inspection..." in history[1].parts[0].text
    assert history[1].parts[1].function_call.name == "terraform_plan"

    # 2. Older function_response in user role is compacted to a short stub
    fc_resp = history[2].parts[0].function_response
    stub = fc_resp.response["result"]
    assert "terraform_plan" in stub
    assert "(older turn output compacted)" in stub
    assert len(stub) < 400
