"""
Unit tests for MCP ToolRegistry and HITL PendingAction integration.
Validates that Terraform and CI/CD tools are registered, formatted properly for Gemini,
and that mutating tools trigger HITL pending actions.
"""

import pytest
from app.mcp_servers.registry import ToolRegistry
from app.mcp_servers.base import ToolCategory


def test_registry_initialization():
    reg = ToolRegistry()
    reg.initialize()
    
    tools = reg.get_all_tools()
    tool_names = [t.name for t in tools]
    
    # Check terraform tools
    assert "terraform_list_files" in tool_names
    assert "terraform_get_file" in tool_names
    assert "terraform_write_file" in tool_names
    assert "terraform_fmt" in tool_names
    assert "terraform_init" in tool_names
    assert "terraform_validate" in tool_names
    assert "terraform_plan" in tool_names
    assert "terraform_apply" not in tool_names
    
    # Check cicd workflow tools
    assert "workflow_list" in tool_names
    assert "workflow_get" in tool_names
    assert "workflow_write" in tool_names
    assert "workflow_validate" in tool_names
    
    # Check mutating flags for registered Terraform and CI/CD tools
    assert reg.is_mutating("terraform_write_file") is True
    assert reg.is_mutating("workflow_write") is True
    
    # Check non-mutating flags
    assert reg.is_mutating("terraform_list_files") is False
    assert reg.is_mutating("terraform_get_file") is False
    assert reg.is_mutating("terraform_fmt") is False
    assert reg.is_mutating("terraform_init") is False
    assert reg.is_mutating("terraform_validate") is False
    assert reg.is_mutating("terraform_plan") is False
    assert reg.is_mutating("workflow_list") is False
    assert reg.is_mutating("workflow_get") is False
    assert reg.is_mutating("workflow_validate") is False


def test_gemini_declarations_format():
    reg = ToolRegistry()
    reg.initialize()
    
    declarations = reg.get_gemini_declarations()
    assert len(declarations) > 0
    
    tf_write_decl = next((d for d in declarations if d["name"] == "terraform_write_file"), None)
    assert tf_write_decl is not None
    assert "parameters" in tf_write_decl
    assert tf_write_decl["parameters"]["type"] == "OBJECT"
    assert "file_path" in tf_write_decl["parameters"]["properties"]
    assert "content" in tf_write_decl["parameters"]["properties"]
    
    wf_write_decl = next((d for d in declarations if d["name"] == "workflow_write"), None)
    assert wf_write_decl is not None
    assert "workflow_name" in wf_write_decl["parameters"]["properties"]
    assert "content" in wf_write_decl["parameters"]["properties"]
