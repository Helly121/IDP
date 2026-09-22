"""
Terraform MCP Server — Tools for Terraform IaC management, formatting, validation, and planning.

Executes the real Terraform CLI inside the Dockerized backend environment.
All operations are strictly sandboxed to the iac/ workspace.
All mutating operations (terraform_write_file) require HITL approval.
Terraform apply is intentionally NOT provided.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.mcp_servers.base import (
    MCPServerBase,
    ToolCategory,
    ToolDefinition,
    ToolParameter,
    ToolResult,
)

logger = logging.getLogger(__name__)


def _sanitize_output(text: str) -> str:
    """
    Redact sensitive credentials, secrets, private keys, tokens,
    passwords, and connection strings from Terraform output before returning.
    """
    if not text:
        return ""

    sanitized = text

    # 1. Private keys
    sanitized = re.sub(
        r"-----BEGIN [A-Z0-9_-]+ PRIVATE KEY-----[\s\S]*?-----END [A-Z0-9_-]+ PRIVATE KEY-----",
        "[REDACTED_PRIVATE_KEY]",
        sanitized,
    )

    # 2. JWT tokens (Header.Payload.Signature)
    sanitized = re.sub(
        r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_.-]+",
        "[REDACTED_JWT_TOKEN]",
        sanitized,
    )

    # 3. AWS Access Key IDs & Secret Access Keys
    sanitized = re.sub(
        r"(?:AKIA|ASIA)[0-9A-Z]{16}",
        "[REDACTED_AWS_KEY]",
        sanitized,
    )

    # 4. URLs with embedded basic authentication
    sanitized = re.sub(
        r"(https?://)([^:\s/@]+):([^@\s/]+)@",
        r"\1\2:[REDACTED]@",
        sanitized,
    )

    # 5. Generic token / password / secret assignments in key-value format (skip if already redacted)
    sanitized = re.sub(
        r'(?i)(\b(?:password|secret|token|api_key|apikey|private_key|client_secret|auth_token|db_password)\b\s*[:=]\s*["\']?)(?!\[REDACTED_)[^\s"\'\n,;]+(["\']?)',
        r'\1[REDACTED_SECRET]\2',
        sanitized,
    )

    # 6. HCL variable / attribute definitions for sensitive attributes (skip if already redacted)
    sanitized = re.sub(
        r'(?i)(^[ \t]*[+~-]?\s*[a-zA-Z0-9_]*(?:password|secret|token|key|credential|cert)[a-zA-Z0-9_]*\s*=\s*)"(?!\[REDACTED_)[^"\n]*"',
        r'\1"[REDACTED_SECRET]"',
        sanitized,
        flags=re.MULTILINE,
    )

    return sanitized


def _get_iac_root() -> Path:
    """Determine the base directory for IaC files, with fallbacks for dev/test."""
    configured = Path(settings.IAC_DIR).resolve()
    if configured.exists() and configured.is_dir():
        return configured

    # Fallback to local repo iac directory if running outside Docker (e.g., local tests)
    cwd = Path.cwd().resolve()
    for candidate in [cwd / "iac", cwd.parent / "iac", cwd / ".." / "iac"]:
        resolved = candidate.resolve()
        if resolved.exists() and resolved.is_dir():
            return resolved

    # Default to configured path even if it will be created
    return configured


class TerraformMCPServer(MCPServerBase):
    """MCP server for Terraform IaC operations inside the containerized environment."""

    def __init__(self, iac_root: Path | None = None) -> None:
        self._iac_root = (iac_root or _get_iac_root()).resolve()

    # ------------------------------------------------------------------
    # Security / Sandboxing
    # ------------------------------------------------------------------

    def _resolve_safe_path(self, relative_path: str = "") -> Path:
        """
        Safely resolve a path within the allowed IaC root.
        Rejects path traversal (e.g. ../), absolute paths outside root,
        or any target outside self._iac_root.
        """
        clean_rel = relative_path.strip().lstrip("/\\")
        target = (self._iac_root / clean_rel).resolve()

        try:
            target.relative_to(self._iac_root)
        except ValueError:
            raise PermissionError(
                f"Access denied: Path '{relative_path}' escapes IaC workspace '{self._iac_root}'"
            )

        return target

    # ------------------------------------------------------------------
    # MCPServerBase interface
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Check if terraform binary is available on PATH or in /usr/local/bin."""
        return bool(shutil.which("terraform") or os.path.exists("/usr/local/bin/terraform"))

    def list_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="terraform_list_files",
                description=(
                    "List all Terraform configuration files and subdirectories within the iac/ directory."
                ),
                parameters=[
                    ToolParameter(
                        name="subpath",
                        type="string",
                        description="Optional subdirectory within iac/ (e.g. 'environments/dev' or 'modules/k8s-namespace')",
                        required=False,
                        default="",
                    ),
                ],
                is_mutating=False,
                category=ToolCategory.TERRAFORM,
            ),
            ToolDefinition(
                name="terraform_get_file",
                description="Read the contents of a Terraform file within the iac/ workspace.",
                parameters=[
                    ToolParameter(
                        name="file_path",
                        type="string",
                        description="Relative path to the file within iac/ (e.g. 'environments/dev/main.tf')",
                        required=True,
                    ),
                ],
                is_mutating=False,
                category=ToolCategory.TERRAFORM,
            ),
            ToolDefinition(
                name="terraform_write_file",
                description=(
                    "Create or update a Terraform file (*.tf, *.tfvars, *.tpl) within the iac/ workspace. "
                    "This is a MUTATING action and requires Human-in-the-Loop (HITL) approval before execution."
                ),
                parameters=[
                    ToolParameter(
                        name="file_path",
                        type="string",
                        description="Relative path within iac/ (e.g. 'environments/dev/main.tf')",
                        required=True,
                    ),
                    ToolParameter(
                        name="content",
                        type="string",
                        description="Complete content to write to the Terraform file",
                        required=True,
                    ),
                ],
                is_mutating=True,
                category=ToolCategory.TERRAFORM,
            ),
            ToolDefinition(
                name="terraform_fmt",
                description=(
                    "Format Terraform files in the iac/ workspace using the real Terraform CLI. "
                    "Supports check mode to verify formatting without modifying files."
                ),
                parameters=[
                    ToolParameter(
                        name="path",
                        type="string",
                        description="Target directory or file path within iac/ (default: root iac directory)",
                        required=False,
                        default="",
                    ),
                    ToolParameter(
                        name="check",
                        type="boolean",
                        description="If true, only checks formatting and reports unformatted files without modifying them",
                        required=False,
                        default=False,
                    ),
                ],
                is_mutating=False,
                category=ToolCategory.TERRAFORM,
            ),
            ToolDefinition(
                name="terraform_init",
                description=(
                    "Initialize a Terraform configuration directory using 'terraform init -backend=false'. "
                    "Downloads provider plugins without requiring remote backend credentials."
                ),
                parameters=[
                    ToolParameter(
                        name="directory",
                        type="string",
                        description="Directory within iac/ to initialize (e.g. 'environments/dev')",
                        required=False,
                        default="environments/dev",
                    ),
                ],
                is_mutating=False,
                category=ToolCategory.TERRAFORM,
            ),
            ToolDefinition(
                name="terraform_validate",
                description=(
                    "Validate the syntax and configuration of a Terraform directory using 'terraform validate'. "
                    "Must be run on an initialized directory."
                ),
                parameters=[
                    ToolParameter(
                        name="directory",
                        type="string",
                        description="Directory within iac/ to validate (e.g. 'environments/dev')",
                        required=False,
                        default="environments/dev",
                    ),
                ],
                is_mutating=False,
                category=ToolCategory.TERRAFORM,
            ),
            ToolDefinition(
                name="terraform_plan",
                description=(
                    "Generate a safe speculative Terraform execution plan using 'terraform plan -no-color'. "
                    "Inspects proposed infrastructure changes without applying them."
                ),
                parameters=[
                    ToolParameter(
                        name="directory",
                        type="string",
                        description="Directory within iac/ to plan (e.g. 'environments/dev')",
                        required=False,
                        default="environments/dev",
                    ),
                    ToolParameter(
                        name="var_file",
                        type="string",
                        description="Optional var-file path relative to the directory (e.g. 'terraform.tfvars')",
                        required=False,
                    ),
                ],
                is_mutating=False,
                category=ToolCategory.TERRAFORM,
            ),
        ]

    async def execute_tool(self, tool_name: str, params: dict) -> ToolResult:
        dispatch = {
            "terraform_list_files": self._list_files,
            "terraform_get_file": self._get_file,
            "terraform_write_file": self._write_file,
            "terraform_fmt": self._fmt,
            "terraform_init": self._init,
            "terraform_validate": self._validate,
            "terraform_plan": self._plan,
        }
        handler = dispatch.get(tool_name)
        if handler is None:
            return ToolResult(success=False, error=f"Unknown tool: {tool_name}")
        try:
            return await handler(params)
        except PermissionError as pe:
            logger.warning("Terraform sandboxing violation: %s", pe)
            return ToolResult(success=False, error=str(pe))
        except Exception as e:
            logger.exception("Terraform tool %s failed", tool_name)
            return ToolResult(success=False, error=str(e))

    # ------------------------------------------------------------------
    # Tool Implementations
    # ------------------------------------------------------------------

    async def _list_files(self, params: dict) -> ToolResult:
        subpath = params.get("subpath", "")
        target_dir = self._resolve_safe_path(subpath)

        if not target_dir.exists():
            return ToolResult(success=False, error=f"Directory '{subpath}' does not exist in iac workspace")

        if not target_dir.is_dir():
            return ToolResult(success=False, error=f"Path '{subpath}' is not a directory")

        files_list = []
        for root, dirs, files in os.walk(target_dir):
            # Skip hidden dirs like .terraform
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for file in files:
                if file.startswith("."):
                    continue
                full_p = Path(root) / file
                rel_p = full_p.relative_to(self._iac_root).as_posix()
                files_list.append({
                    "path": rel_p,
                    "size_bytes": full_p.stat().st_size,
                    "name": file,
                })

        return ToolResult(
            success=True,
            data={
                "base_path": subpath or ".",
                "count": len(files_list),
                "files": files_list,
            },
        )

    async def _get_file(self, params: dict) -> ToolResult:
        file_path = params["file_path"]
        target_file = self._resolve_safe_path(file_path)

        if not target_file.exists():
            return ToolResult(success=False, error=f"File '{file_path}' does not exist in iac workspace")

        if not target_file.is_file():
            return ToolResult(success=False, error=f"Path '{file_path}' is not a file")

        content = target_file.read_text(encoding="utf-8", errors="replace")
        return ToolResult(
            success=True,
            data={
                "path": file_path,
                "content": content,
                "size_bytes": len(content),
            },
        )

    async def _write_file(self, params: dict) -> ToolResult:
        file_path = params["file_path"]
        content = params["content"]
        target_file = self._resolve_safe_path(file_path)

        # Ensure parent directory exists within safe root
        target_file.parent.mkdir(parents=True, exist_ok=True)

        target_file.write_text(content, encoding="utf-8")
        logger.info("Terraform file written: %s (%d bytes)", file_path, len(content))

        return ToolResult(
            success=True,
            data={
                "path": file_path,
                "size_bytes": len(content),
                "message": f"Successfully wrote {file_path}",
            },
        )

    async def _run_terraform_cli(self, args: list[str], cwd: Path) -> tuple[int, str, str]:
        """Execute the real Terraform CLI directly using asyncio subprocess."""
        terraform_bin = shutil.which("terraform") or "/usr/local/bin/terraform"

        proc = await asyncio.create_subprocess_exec(
            terraform_bin,
            *args,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout_b, stderr_b = await proc.communicate()
        stdout = stdout_b.decode("utf-8", errors="replace")
        stderr = stderr_b.decode("utf-8", errors="replace")
        return proc.returncode or 0, stdout, stderr

    async def _fmt(self, params: dict) -> ToolResult:
        subpath = params.get("path", "")
        check = bool(params.get("check", False))
        target_path = self._resolve_safe_path(subpath)

        if not target_path.exists():
            return ToolResult(success=False, error=f"Path '{subpath}' does not exist in iac workspace")

        args = ["fmt", "-recursive"]
        if check:
            args.append("-check")

        cwd = target_path if target_path.is_dir() else target_path.parent
        if target_path.is_file():
            args = ["fmt"]
            if check:
                args.append("-check")
            args.append(target_path.name)

        code, stdout, stderr = await self._run_terraform_cli(args, cwd=cwd)
        stdout = _sanitize_output(stdout)
        stderr = _sanitize_output(stderr)

        # In check mode, exit code 3 means files need formatting, 0 means already formatted
        if check:
            is_formatted = (code == 0)
            unformatted = [line.strip() for line in stdout.splitlines() if line.strip()]
            return ToolResult(
                success=True,
                data={
                    "is_formatted": is_formatted,
                    "unformatted_files": unformatted,
                    "output": stdout or ("All files are correctly formatted" if is_formatted else ""),
                },
            )

        if code != 0:
            return ToolResult(success=False, error=f"terraform fmt failed (code {code}): {stderr}")

        modified = [line.strip() for line in stdout.splitlines() if line.strip()]
        return ToolResult(
            success=True,
            data={
                "formatted_files": modified,
                "message": f"Formatted {len(modified)} file(s)" if modified else "All files were already formatted",
            },
        )

    async def _init(self, params: dict) -> ToolResult:
        directory = params.get("directory", "environments/dev")
        target_dir = self._resolve_safe_path(directory)

        if not target_dir.exists() or not target_dir.is_dir():
            return ToolResult(success=False, error=f"Directory '{directory}' does not exist in iac workspace")

        args = ["init", "-backend=false", "-no-color"]
        code, stdout, stderr = await self._run_terraform_cli(args, cwd=target_dir)
        stdout = _sanitize_output(stdout)
        stderr = _sanitize_output(stderr)

        if code != 0:
            return ToolResult(
                success=False,
                error=f"terraform init failed (code {code}):\n{stderr}\n{stdout}",
                data={"output": stdout, "stderr": stderr},
            )

        return ToolResult(
            success=True,
            data={
                "directory": directory,
                "output": stdout,
                "message": "Terraform directory successfully initialized with -backend=false",
            },
        )

    async def _validate(self, params: dict) -> ToolResult:
        directory = params.get("directory", "environments/dev")
        target_dir = self._resolve_safe_path(directory)

        if not target_dir.exists() or not target_dir.is_dir():
            return ToolResult(success=False, error=f"Directory '{directory}' does not exist in iac workspace")

        args = ["validate", "-no-color", "-json"]
        code, stdout, stderr = await self._run_terraform_cli(args, cwd=target_dir)
        stdout = _sanitize_output(stdout)
        stderr = _sanitize_output(stderr)

        # Try to parse json output
        import json
        try:
            val_data = json.loads(stdout)
            is_valid = val_data.get("valid", False)
            error_count = val_data.get("error_count", 0)
            warning_count = val_data.get("warning_count", 0)
            diagnostics = val_data.get("diagnostics", [])

            return ToolResult(
                success=is_valid,
                data={
                    "valid": is_valid,
                    "error_count": error_count,
                    "warning_count": warning_count,
                    "diagnostics": diagnostics,
                },
                error=None if is_valid else f"Validation failed with {error_count} error(s)",
            )
        except Exception:
            # Fallback to plain text output if not valid JSON
            return ToolResult(
                success=(code == 0),
                data={"output": stdout, "directory": directory},
                error=stderr if code != 0 else None,
            )

    async def _plan(self, params: dict) -> ToolResult:
        directory = params.get("directory", "environments/dev")
        var_file = params.get("var_file")
        target_dir = self._resolve_safe_path(directory)

        if not target_dir.exists() or not target_dir.is_dir():
            return ToolResult(success=False, error=f"Directory '{directory}' does not exist in iac workspace")

        args = ["plan", "-no-color"]
        if var_file:
            # Validate var_file path stays inside directory or iac root
            vf_path = self._resolve_safe_path(f"{directory}/{var_file}" if not var_file.startswith("/") else var_file)
            if vf_path.exists():
                args.append(f"-var-file={vf_path.name}")

        code, stdout, stderr = await self._run_terraform_cli(args, cwd=target_dir)
        clean_plan = _sanitize_output(stdout)
        clean_stderr = _sanitize_output(stderr)

        if code != 0:
            return ToolResult(
                success=False,
                error=f"terraform plan failed (code {code}):\n{clean_stderr}\n{clean_plan}",
                data={"output": clean_plan, "stderr": clean_stderr},
            )

        return ToolResult(
            success=True,
            data={
                "directory": directory,
                "plan_output": clean_plan,
                "message": "Terraform plan generated successfully (sanitized)",
            },
        )
