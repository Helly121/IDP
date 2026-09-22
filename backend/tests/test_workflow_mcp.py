"""
Unit and integration tests for the GitHub Actions Workflow MCP server.
Tests listing workflows, reading workflows, mutating workflow writes with validation,
and YAML syntax validation.
"""

import pytest
from pathlib import Path

from app.mcp_servers.base import ToolCategory
from app.mcp_servers.workflow_server import WorkflowMCPServer


@pytest.fixture
def temp_workflow_workspace(tmp_path):
    """Create a temporary .github/workflows workspace."""
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    
    sample_wf = wf_dir / "ci-cd.yml"
    sample_wf.write_text(
        "name: Sample CI\n"
        "on:\n"
        "  push:\n"
        "    branches: ['main']\n"
        "jobs:\n"
        "  build:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@v4\n"
    )
    return wf_dir


@pytest.mark.asyncio
async def test_workflow_server_tool_definitions(temp_workflow_workspace):
    server = WorkflowMCPServer(workflows_root=temp_workflow_workspace)
    tools = server.list_tools()
    
    tool_names = [t.name for t in tools]
    assert "workflow_list" in tool_names
    assert "workflow_get" in tool_names
    assert "workflow_write" in tool_names
    assert "workflow_validate" in tool_names
    
    write_tool = next(t for t in tools if t.name == "workflow_write")
    assert write_tool.is_mutating is True
    assert write_tool.category == ToolCategory.CICD
    
    for t in tools:
        if t.name != "workflow_write":
            assert t.is_mutating is False, f"Tool {t.name} should not be mutating"


@pytest.mark.asyncio
async def test_workflow_list(temp_workflow_workspace):
    server = WorkflowMCPServer(workflows_root=temp_workflow_workspace)
    result = await server.execute_tool("workflow_list", {})
    
    assert result.success is True
    assert result.data["count"] == 1
    assert result.data["workflows"][0]["file_name"] == "ci-cd.yml"
    assert result.data["workflows"][0]["name"] == "Sample CI"


@pytest.mark.asyncio
async def test_workflow_get(temp_workflow_workspace):
    server = WorkflowMCPServer(workflows_root=temp_workflow_workspace)
    result = await server.execute_tool("workflow_get", {"workflow_name": "ci-cd.yml"})
    
    assert result.success is True
    assert "name: Sample CI" in result.data["content"]


@pytest.mark.asyncio
async def test_workflow_write_valid(temp_workflow_workspace):
    server = WorkflowMCPServer(workflows_root=temp_workflow_workspace)
    new_wf = (
        "name: Terraform CI\n"
        "on:\n"
        "  pull_request:\n"
        "    branches: ['main']\n"
        "jobs:\n"
        "  lint:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@v4\n"
    )
    result = await server.execute_tool(
        "workflow_write",
        {"workflow_name": "terraform.yml", "content": new_wf},
    )
    
    assert result.success is True
    created = temp_workflow_workspace / "terraform.yml"
    assert created.exists()
    assert "Terraform CI" in created.read_text()


@pytest.mark.asyncio
async def test_workflow_write_invalid_yaml(temp_workflow_workspace):
    server = WorkflowMCPServer(workflows_root=temp_workflow_workspace)
    bad_yaml = "name: Bad:\n  - incomplete: {"
    result = await server.execute_tool(
        "workflow_write",
        {"workflow_name": "bad.yml", "content": bad_yaml},
    )
    
    assert result.success is False
    assert "Invalid YAML" in result.error


@pytest.mark.asyncio
async def test_workflow_validate(temp_workflow_workspace):
    server = WorkflowMCPServer(workflows_root=temp_workflow_workspace)
    
    # Valid workflow
    valid_content = "name: Test\non:\n  push:\njobs:\n  test:\n    runs-on: ubuntu-latest"
    res_valid = await server.execute_tool("workflow_validate", {"content": valid_content})
    assert res_valid.success is True
    assert res_valid.data["valid"] is True
    
    # Missing jobs
    invalid_content = "name: Test\non:\n  push:"
    res_invalid = await server.execute_tool("workflow_validate", {"content": invalid_content})
    assert res_invalid.success is False
    assert "Missing 'jobs'" in res_invalid.error


@pytest.mark.asyncio
async def test_workflow_sandboxing(temp_workflow_workspace):
    server = WorkflowMCPServer(workflows_root=temp_workflow_workspace)
    result = await server.execute_tool(
        "workflow_get",
        {"workflow_name": "../../../secret.txt"},
    )
    assert result.success is False
    assert "Invalid workflow file name" in result.error
