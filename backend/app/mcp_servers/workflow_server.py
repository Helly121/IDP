"""
GitHub Actions Workflow MCP Server — Tools for CI/CD workflow management and validation.

All operations are sandboxed to the .github/workflows/ workspace.
All mutating operations (workflow_write) require HITL approval.
Workflow files are validated with PyYAML before being written.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any
import yaml

from app.core.config import settings
from app.mcp_servers.base import (
    MCPServerBase,
    ToolCategory,
    ToolDefinition,
    ToolParameter,
    ToolResult,
)

logger = logging.getLogger(__name__)


def _get_workflows_root() -> Path:
    """Determine the base directory for GitHub Actions workflows with fallbacks for dev/test."""
    configured = Path(settings.WORKFLOWS_DIR).resolve()
    if configured.exists() and configured.is_dir():
        return configured

    # Fallback to local repo .github/workflows directory if running outside Docker (e.g. tests)
    cwd = Path.cwd().resolve()
    for candidate in [
        cwd / ".github" / "workflows",
        cwd.parent / ".github" / "workflows",
        cwd / ".." / ".github" / "workflows",
    ]:
        resolved = candidate.resolve()
        if resolved.exists() and resolved.is_dir():
            return resolved

    return configured


class WorkflowMCPServer(MCPServerBase):
    """MCP server for managing GitHub Actions CI/CD workflows."""

    def __init__(self, workflows_root: Path | None = None) -> None:
        self._workflows_root = (workflows_root or _get_workflows_root()).resolve()

    # ------------------------------------------------------------------
    # Security / Sandboxing
    # ------------------------------------------------------------------

    def _resolve_safe_path(self, workflow_name: str, root: Path | None = None) -> Path:
        """
        Safely resolve a workflow file path inside the allowed workflows root (or staging root).
        Rejects path traversal, slashes, or escaping files.
        """
        base_root = (root or self._workflows_root).resolve()
        clean_name = workflow_name.strip().lstrip("/\\")

        # Filename cannot contain directory traversal components
        if "/" in clean_name or "\\" in clean_name or ".." in clean_name:
            raise PermissionError(
                f"Access denied: Invalid workflow file name '{workflow_name}'"
            )

        if not (clean_name.endswith(".yml") or clean_name.endswith(".yaml")):
            clean_name += ".yml"

        target = (base_root / clean_name).resolve()

        try:
            target.relative_to(base_root)
        except ValueError:
            raise PermissionError(
                f"Access denied: Path '{workflow_name}' escapes workflows workspace '{base_root}'"
            )

        return target

    def _get_active_root(self, ctx: dict | None = None) -> Path:
        """Return the session staging workflows root if staged files exist, else the base workflows root."""
        if ctx and ctx.get("session_id"):
            from app.services.staging_service import has_staged_workflows, get_staged_workflows_root
            sid = ctx["session_id"]
            if has_staged_workflows(sid):
                staged = get_staged_workflows_root(sid)
                if staged:
                    return staged
        return self._workflows_root

    # ------------------------------------------------------------------
    # MCPServerBase interface
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        return True

    def list_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="workflow_list",
                description="List workflow files under .github/workflows/.",
                parameters=[],
                is_mutating=False,
                category=ToolCategory.CICD,
            ),
            ToolDefinition(
                name="workflow_get",
                description="Read a GitHub Actions workflow YAML file.",
                parameters=[
                    ToolParameter(
                        name="workflow_name",
                        type="string",
                        description="Workflow file name (e.g. 'ci-cd.yml')",
                        required=True,
                    ),
                ],
                is_mutating=False,
                category=ToolCategory.CICD,
            ),
            ToolDefinition(
                name="workflow_write",
                description="Create or update workflow file under .github/workflows/. Validates YAML.",
                parameters=[
                    ToolParameter(
                        name="workflow_name",
                        type="string",
                        description="Workflow file name (e.g. 'terraform.yml')",
                        required=True,
                    ),
                    ToolParameter(
                        name="content",
                        type="string",
                        description="Complete YAML content",
                        required=True,
                    ),
                ],
                is_mutating=True,
                category=ToolCategory.CICD,
            ),
            ToolDefinition(
                name="workflow_validate",
                description="Validate YAML syntax and structure for a workflow.",
                parameters=[
                    ToolParameter(
                        name="content",
                        type="string",
                        description="YAML content to validate",
                        required=True,
                    ),
                ],
                is_mutating=False,
                category=ToolCategory.CICD,
            ),
            ToolDefinition(
                name="workflow_patch",
                description="Patch workflow file under .github/workflows/ by replacing old_string with new_string. Fails if old_string is not found exactly once.",
                parameters=[
                    ToolParameter(
                        name="file_path",
                        type="string",
                        description="Workflow file name (e.g. 'ci.yml')",
                        required=True,
                    ),
                    ToolParameter(
                        name="old_string",
                        type="string",
                        description="Exact string to replace (must appear exactly once)",
                        required=True,
                    ),
                    ToolParameter(
                        name="new_string",
                        type="string",
                        description="Replacement string",
                        required=True,
                    ),
                ],
                is_mutating=True,
                category=ToolCategory.CICD,
            ),
        ]

    async def execute_tool(
        self,
        tool_name: str,
        params: dict,
        ctx: dict | None = None,
    ) -> ToolResult:
        effective_root = self._get_active_root(ctx)
        dispatch = {
            "workflow_list": lambda p: self._list_workflows(p, root=effective_root),
            "workflow_get": lambda p: self._get_workflow(p, root=effective_root),
            "workflow_write": self._write_workflow,
            "workflow_patch": self._patch_workflow,
            "workflow_validate": lambda p: self._validate_workflow(p, root=effective_root),
        }
        handler = dispatch.get(tool_name)
        if handler is None:
            return ToolResult(success=False, error=f"Unknown tool: {tool_name}")
        try:
            return await handler(params)
        except PermissionError as pe:
            logger.warning("Workflow sandboxing violation: %s", pe)
            return ToolResult(success=False, error=str(pe))
        except Exception as e:
            logger.exception("Workflow tool %s failed", tool_name)
            return ToolResult(success=False, error=str(e))

    # ------------------------------------------------------------------
    # Tool Implementations
    # ------------------------------------------------------------------

    async def _list_workflows(self, params: dict, root: Path | None = None) -> ToolResult:
        target_root = (root or self._workflows_root).resolve()
        if not target_root.exists() or not target_root.is_dir():
            return ToolResult(
                success=True,
                data={"workflows": [], "count": 0, "message": "Workflows directory does not exist yet"},
            )

        workflows = []
        for file in target_root.iterdir():
            if file.is_file() and (file.name.endswith(".yml") or file.name.endswith(".yaml")):
                workflow_info: dict[str, Any] = {
                    "file_name": file.name,
                    "size_bytes": file.stat().st_size,
                }
                try:
                    parsed = yaml.safe_load(file.read_text(encoding="utf-8"))
                    if isinstance(parsed, dict):
                        workflow_info["name"] = parsed.get("name", file.stem)
                        # In YAML, `on:` can be parsed as bool True unless quoted
                        workflow_info["triggers"] = list(parsed.get("on", parsed.get(True, {})).keys()) if isinstance(parsed.get("on", parsed.get(True, {})), dict) else str(parsed.get("on", parsed.get(True, "configured")))
                        workflow_info["jobs"] = list(parsed.get("jobs", {}).keys()) if isinstance(parsed.get("jobs"), dict) else []
                except Exception:
                    workflow_info["parsed"] = False
                workflows.append(workflow_info)

        return ToolResult(
            success=True,
            data={"count": len(workflows), "workflows": workflows},
        )

    async def _get_workflow(self, params: dict, root: Path | None = None) -> ToolResult:
        workflow_name = params["workflow_name"]
        target_file = self._resolve_safe_path(workflow_name, root=root)

        if not target_file.exists() or not target_file.is_file():
            return ToolResult(success=False, error=f"Workflow file '{workflow_name}' does not exist")

        content = target_file.read_text(encoding="utf-8", errors="replace")
        return ToolResult(
            success=True,
            data={
                "file_name": target_file.name,
                "content": content,
                "size_bytes": len(content),
            },
        )

    async def _write_workflow(self, params: dict) -> ToolResult:
        workflow_name = params["workflow_name"]
        content = params["content"]

        # 1. Validate YAML syntax before writing
        try:
            parsed = yaml.safe_load(content)
            if not isinstance(parsed, dict):
                return ToolResult(
                    success=False,
                    error="Invalid workflow: Top-level content must be a YAML mapping (dictionary)",
                )
        except yaml.YAMLError as ye:
            return ToolResult(success=False, error=f"Invalid YAML syntax: {ye}")

        # 2. Resolve safe path in real root and write
        target_file = self._resolve_safe_path(workflow_name, root=self._workflows_root)
        target_file.parent.mkdir(parents=True, exist_ok=True)

        target_file.write_text(content, encoding="utf-8")
        logger.info("Workflow file written: %s (%d bytes)", target_file.name, len(content))

        return ToolResult(
            success=True,
            data={
                "file_name": target_file.name,
                "size_bytes": len(content),
                "message": f"Successfully wrote workflow to .github/workflows/{target_file.name}",
            },
        )

    async def _patch_workflow(self, params: dict) -> ToolResult:
        workflow_name = params.get("file_path") or params.get("workflow_name", "")
        if not workflow_name:
            return ToolResult(success=False, error="Parameter 'file_path' is required.")

        old_string = params.get("old_string", "")
        new_string = params.get("new_string", "")

        target_file = self._resolve_safe_path(workflow_name, root=self._workflows_root)
        if not target_file.exists() or not target_file.is_file():
            return ToolResult(
                success=False,
                error=f"Patch failed on approval: real workflow '{workflow_name}' not found.",
            )

        content = target_file.read_text(encoding="utf-8")
        count = content.count(old_string)
        if count == 0:
            return ToolResult(
                success=False,
                error=(
                    f"Patch failed on approval: old_string not found in real workflow '{workflow_name}'. "
                    f"The real file has changed since the patch was proposed."
                ),
            )
        if count > 1:
            return ToolResult(
                success=False,
                error=(
                    f"Patch failed on approval: old_string occurs {count} times in real workflow '{workflow_name}'. "
                    f"The real file has changed since the patch was proposed."
                ),
            )

        patched = content.replace(old_string, new_string, 1)

        try:
            yaml.safe_load(patched)
        except yaml.YAMLError as ye:
            return ToolResult(success=False, error=f"YAML syntax error after patch: {ye}")

        target_file.write_text(patched, encoding="utf-8")
        logger.info("Workflow patched on approval: %s", target_file.name)

        return ToolResult(
            success=True,
            data={
                "workflow_name": target_file.name,
                "status": "patched",
                "size_bytes": len(patched),
                "message": f"Successfully patched workflow {target_file.name}",
            },
        )

    async def _validate_workflow(self, params: dict, root: Path | None = None) -> ToolResult:
        content = params.get("content")
        workflow_name = params.get("workflow_name")

        # If content is not directly supplied, load from staging/real file
        if not content and workflow_name:
            target_file = self._resolve_safe_path(workflow_name, root=root)
            if target_file.exists() and target_file.is_file():
                content = target_file.read_text(encoding="utf-8")

        if not content:
            return ToolResult(
                success=False,
                error="Parameter 'content' or valid 'workflow_name' is required for validation",
            )

        try:
            parsed = yaml.safe_load(content)
        except yaml.YAMLError as ye:
            return ToolResult(
                success=False,
                error=f"YAML syntax error: {ye}",
                data={"valid": False, "error": str(ye)},
            )

        if not isinstance(parsed, dict):
            return ToolResult(
                success=False,
                error="Workflow must be a YAML object/dictionary",
                data={"valid": False, "error": "Not a YAML mapping"},
            )

        # Basic schema checks for GitHub Actions
        errors = []
        has_on = "on" in parsed or True in parsed  # unquoted `on:` parses as boolean True
        if not has_on:
            errors.append("Missing trigger configuration ('on')")

        if "jobs" not in parsed:
            errors.append("Missing 'jobs' section")
        elif not isinstance(parsed["jobs"], dict) or len(parsed["jobs"]) == 0:
            errors.append("'jobs' section must contain at least one job definition")

        if errors:
            return ToolResult(
                success=False,
                error="; ".join(errors),
                data={"valid": False, "errors": errors},
            )

        jobs_list = list(parsed["jobs"].keys())
        return ToolResult(
            success=True,
            data={
                "valid": True,
                "name": parsed.get("name", "Unnamed Workflow"),
                "jobs": jobs_list,
                "message": "Workflow YAML structure is valid",
            },
        )
