"""
Unit and integration tests for the Terraform MCP server.
Tests tool listing, sandboxing/path traversal rejection, file reading,
mutating operations (write), and CLI execution (fmt, init, validate, plan).
"""

import pytest
from pathlib import Path

from app.mcp_servers.base import ToolCategory
from app.mcp_servers.terraform_server import TerraformMCPServer


@pytest.fixture
def temp_iac_workspace(tmp_path):
    """Create a temporary IaC workspace mimicking the repository structure."""
    iac_dir = tmp_path / "iac"
    iac_dir.mkdir()
    
    dev_dir = iac_dir / "environments" / "dev"
    dev_dir.mkdir(parents=True)
    
    main_tf = dev_dir / "main.tf"
    main_tf.write_text(
        'terraform {\n  required_version = ">= 1.9"\n}\n\nlocals {\n  env = "dev"\n}\n'
    )
    
    var_tf = dev_dir / "variables.tf"
    var_tf.write_text('variable "region" {\n  default = "us-east-1"\n}\n')
    
    return iac_dir


@pytest.mark.asyncio
async def test_terraform_server_tool_definitions(temp_iac_workspace):
    server = TerraformMCPServer(iac_root=temp_iac_workspace)
    tools = server.list_tools()
    
    tool_names = [t.name for t in tools]
    assert "terraform_list_files" in tool_names
    assert "terraform_get_file" in tool_names
    assert "terraform_write_file" in tool_names
    assert "terraform_fmt" in tool_names
    assert "terraform_init" in tool_names
    assert "terraform_validate" in tool_names
    assert "terraform_plan" in tool_names
    
    # Verify terraform_apply is NOT present
    assert "terraform_apply" not in tool_names
    
    # Verify mutating flags
    write_tool = next(t for t in tools if t.name == "terraform_write_file")
    assert write_tool.is_mutating is True
    assert write_tool.category == ToolCategory.TERRAFORM
    
    # Read-only tools must not be mutating
    for t in tools:
        if t.name != "terraform_write_file":
            assert t.is_mutating is False, f"Tool {t.name} should not be mutating"


@pytest.mark.asyncio
async def test_terraform_list_files(temp_iac_workspace):
    server = TerraformMCPServer(iac_root=temp_iac_workspace)
    result = await server.execute_tool("terraform_list_files", {})
    
    assert result.success is True
    assert result.data["count"] >= 2
    paths = [f["path"] for f in result.data["files"]]
    assert "environments/dev/main.tf" in paths or "environments/dev/main.tf".replace("/", "\\") in paths


@pytest.mark.asyncio
async def test_terraform_get_file(temp_iac_workspace):
    server = TerraformMCPServer(iac_root=temp_iac_workspace)
    result = await server.execute_tool("terraform_get_file", {"file_path": "environments/dev/main.tf"})
    
    assert result.success is True
    assert 'locals {\n  env = "dev"\n}' in result.data["content"]


@pytest.mark.asyncio
async def test_terraform_write_file(temp_iac_workspace):
    server = TerraformMCPServer(iac_root=temp_iac_workspace)
    new_content = 'output "test" {\n  value = "hello"\n}\n'
    result = await server.execute_tool(
        "terraform_write_file",
        {"file_path": "environments/dev/outputs.tf", "content": new_content},
    )
    
    assert result.success is True
    written_file = temp_iac_workspace / "environments" / "dev" / "outputs.tf"
    assert written_file.exists()
    assert written_file.read_text() == new_content


@pytest.mark.asyncio
async def test_terraform_sandboxing_path_traversal(temp_iac_workspace):
    server = TerraformMCPServer(iac_root=temp_iac_workspace)
    
    # Attempting to access ../ escapes the workspace
    result = await server.execute_tool("terraform_get_file", {"file_path": "../../etc/passwd"})
    assert result.success is False
    assert "escapes IaC workspace" in result.error

    # Attempting to write outside workspace
    result = await server.execute_tool(
        "terraform_write_file",
        {"file_path": "../escape.txt", "content": "malicious"},
    )
    assert result.success is False
    assert "escapes IaC workspace" in result.error


@pytest.mark.asyncio
async def test_terraform_fmt_and_validate(temp_iac_workspace):
    server = TerraformMCPServer(iac_root=temp_iac_workspace)
    
    # Test fmt in check mode
    fmt_res = await server.execute_tool("terraform_fmt", {"path": "environments/dev", "check": True})
    assert fmt_res.success is True
    
    # Test init with -backend=false
    init_res = await server.execute_tool("terraform_init", {"directory": "environments/dev"})
    assert init_res.success is True
    
    # Test validate
    val_res = await server.execute_tool("terraform_validate", {"directory": "environments/dev"})
    assert val_res.success is True
    assert val_res.data["valid"] is True


def test_terraform_output_sanitization():
    from app.mcp_servers.terraform_server import _sanitize_output

    sample_output = (
        'An execution plan has been generated and is shown below.\n'
        '+ resource "k8s_secret" "db" {\n'
        '    + password = "SuperSecretPassword123"\n'
        '    + api_key = "ak_live_998877665544"\n'
        '}\n'
        'AWS key: AKIAIOSFODNN7EXAMPLE\n'
        'Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozS6-m_W_example\n'
        '-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0...\n-----END RSA PRIVATE KEY-----\n'
    )

    sanitized = _sanitize_output(sample_output)

    assert "SuperSecretPassword123" not in sanitized
    assert "ak_live_998877665544" not in sanitized
    assert "AKIAIOSFODNN7EXAMPLE" not in sanitized
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in sanitized
    assert "MIIEowIBAAKCAQEA0" not in sanitized

    assert "[REDACTED_SECRET]" in sanitized
    assert "[REDACTED_AWS_KEY]" in sanitized
    assert "[REDACTED_JWT_TOKEN]" in sanitized
    assert "[REDACTED_PRIVATE_KEY]" in sanitized
