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

    def _resolve_safe_path(self, relative_path: str = "", root: Path | None = None) -> Path:
        """
        Safely resolve a path within the allowed IaC root (or staging root).
        Rejects path traversal (e.g. ../), absolute paths outside root,
        or any target outside base_root.
        """
        base_root = (root or self._iac_root).resolve()
        clean_rel = relative_path.strip().lstrip("/\\")
        target = (base_root / clean_rel).resolve()

        try:
            target.relative_to(base_root)
        except ValueError:
            raise PermissionError(
                f"Access denied: Path '{relative_path}' escapes IaC workspace '{base_root}'"
            )

        return target

    def _get_active_root(self, ctx: dict | None = None) -> Path:
        """Return the session staging iac root if staged files exist, else the base iac root."""
        if ctx and ctx.get("session_id"):
            from app.services.staging_service import has_staged_terraform, get_staged_iac_root
            sid = ctx["session_id"]
            if has_staged_terraform(sid):
                staged = get_staged_iac_root(sid)
                if staged:
                    return staged
        return self._iac_root

    # ------------------------------------------------------------------
    # MCPServerBase interface
    # ------------------------------------------------------------------

    

    def is_available(self) -> bool:
        """Always register Terraform tools; CLI operations check availability when invoked."""
        return True

    def list_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="terraform_list_files",
                description="List files and directories within iac/.",
                parameters=[
                    ToolParameter(
                        name="subpath",
                        type="string",
                        description="Optional subdirectory within iac/ (e.g. 'environments/dev')",
                        required=False,
                        default="",
                    ),
                ],
                is_mutating=False,
                category=ToolCategory.TERRAFORM,
            ),
            ToolDefinition(
                name="terraform_get_file",
                description="Read file in iac/ with optional start_line/end_line pagination.",
                parameters=[
                    ToolParameter(
                        name="file_path",
                        type="string",
                        description="Relative path within iac/ (e.g. 'environments/dev/main.tf')",
                        required=True,
                    ),
                    ToolParameter(
                        name="start_line",
                        type="integer",
                        description="Optional starting line number (1-indexed)",
                        required=False,
                    ),
                    ToolParameter(
                        name="end_line",
                        type="integer",
                        description="Optional ending line number (1-indexed)",
                        required=False,
                    ),
                ],
                is_mutating=False,
                category=ToolCategory.TERRAFORM,
            ),
            ToolDefinition(
                name="terraform_write_file",
                description="Create or update file in iac/.",
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
                        description="Complete file content to write",
                        required=True,
                    ),
                ],
                is_mutating=True,
                category=ToolCategory.TERRAFORM,
            ),
            ToolDefinition(
                name="terraform_fmt",
                description="Format Terraform files in iac/, or check formatting.",
                parameters=[
                    ToolParameter(
                        name="path",
                        type="string",
                        description="Target directory or file path within iac/",
                        required=False,
                        default="",
                    ),
                    ToolParameter(
                        name="check",
                        type="boolean",
                        description="If true, only checks formatting without modifying files",
                        required=False,
                        default=False,
                    ),
                ],
                is_mutating=False,
                category=ToolCategory.TERRAFORM,
            ),
            ToolDefinition(
                name="terraform_init",
                description="Run 'terraform init -backend=false' on an iac/ directory.",
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
                description="Run 'terraform validate' on an initialized directory.",
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
                description="Run speculative 'terraform plan -no-color' to preview changes.",
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
                        description="Optional var-file path relative to directory",
                        required=False,
                    ),
                ],
                is_mutating=False,
                category=ToolCategory.TERRAFORM,
            ),
            ToolDefinition(
                name="terraform_patch_file",
                description="Patch file in iac/ by replacing old_string with new_string. Fails if old_string is not found exactly once.",
                parameters=[
                    ToolParameter(
                        name="file_path",
                        type="string",
                        description="Relative path within iac/ (e.g. 'environments/dev/main.tf')",
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
                category=ToolCategory.TERRAFORM,
            ),
            ToolDefinition(
                name="render_template",
                description="Render template in iac/templates/*.tpl with variables using Jinja2.",
                parameters=[
                    ToolParameter(
                        name="template_name",
                        type="string",
                        description="Template file name under iac/templates/ (e.g. 'deployment.yaml.tpl')",
                        required=True,
                    ),
                    ToolParameter(
                        name="variables",
                        type="object",
                        description="Dictionary of variables to render into the Jinja2 template",
                        required=False,
                        default={},
                    ),
                ],
                is_mutating=False,
                category=ToolCategory.TERRAFORM,
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
            "terraform_list_files": lambda p: self._list_files(p, root=effective_root),
            "terraform_get_file": lambda p: self._get_file(p, root=effective_root),
            "terraform_write_file": self._write_file,
            "terraform_patch_file": self._patch_file,
            "render_template": lambda p: self._render_template(p, root=effective_root),
            "terraform_fmt": lambda p: self._fmt(p, root=effective_root),
            "terraform_init": lambda p: self._init(p, root=effective_root),
            "terraform_validate": lambda p: self._validate(p, root=effective_root),
            "terraform_plan": lambda p: self._plan(p, root=effective_root),
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

    async def _list_files(self, params: dict, root: Path | None = None) -> ToolResult:
        subpath = params.get("subpath", "")
        base_root = (root or self._iac_root).resolve()
        target_dir = self._resolve_safe_path(subpath, root=base_root)

        if not target_dir.exists():
            return ToolResult(success=False, error=f"Directory '{subpath}' does not exist in iac workspace")

        if not target_dir.is_dir():
            return ToolResult(success=False, error=f"Path '{subpath}' is not a directory")

        files_list = []
        for r, dirs, files in os.walk(target_dir):
            # Skip hidden dirs like .terraform
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for file in files:
                if file.startswith("."):
                    continue
                full_p = Path(r) / file
                rel_p = full_p.relative_to(base_root).as_posix()
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

    async def _get_file(self, params: dict, root: Path | None = None) -> ToolResult:
        file_path = params["file_path"]
        target_file = self._resolve_safe_path(file_path, root=root)

        if not target_file.exists():
            return ToolResult(success=False, error=f"File '{file_path}' does not exist in iac workspace")

        if not target_file.is_file():
            return ToolResult(success=False, error=f"Path '{file_path}' is not a file")

        raw_content = target_file.read_text(encoding="utf-8", errors="replace")
        lines = raw_content.splitlines(keepends=True)
        total_lines = len(lines)

        start_line = params.get("start_line")
        end_line = params.get("end_line")

        start = max(1, int(start_line)) if start_line is not None else 1
        end = min(total_lines, int(end_line)) if end_line is not None else min(200, total_lines)
        if start > total_lines:
            sliced_content = ""
        else:
            sliced_content = "".join(lines[start - 1 : end])

        return ToolResult(
            success=True,
            data={
                "path": file_path,
                "content": sliced_content,
                "start_line": start,
                "end_line": end,
                "total_lines": total_lines,
                "size_bytes": len(sliced_content),
            },
        )

    async def _write_file(self, params: dict) -> ToolResult:
        file_path = params["file_path"]
        content = params["content"]
        target_file = self._resolve_safe_path(file_path, root=self._iac_root)

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

    async def _patch_file(self, params: dict) -> ToolResult:
        file_path = params.get("file_path", "")
        old_string = params.get("old_string", "")
        new_string = params.get("new_string", "")

        target_file = self._resolve_safe_path(file_path, root=self._iac_root)
        if not target_file.exists() or not target_file.is_file():
            return ToolResult(
                success=False,
                error=f"Patch failed on approval: real file '{file_path}' not found.",
            )

        content = target_file.read_text(encoding="utf-8")
        count = content.count(old_string)
        if count == 0:
            return ToolResult(
                success=False,
                error=(
                    f"Patch failed on approval: old_string not found in real file '{file_path}'. "
                    f"The real file has changed since the patch was proposed."
                ),
            )
        if count > 1:
            return ToolResult(
                success=False,
                error=(
                    f"Patch failed on approval: old_string occurs {count} times in real file '{file_path}'. "
                    f"The real file has changed since the patch was proposed."
                ),
            )

        patched = content.replace(old_string, new_string, 1)
        target_file.write_text(patched, encoding="utf-8")
        logger.info("Terraform file patched on approval: %s", file_path)

        return ToolResult(
            success=True,
            data={
                "path": file_path,
                "status": "patched",
                "size_bytes": len(patched),
                "message": f"Successfully patched {file_path}",
            },
        )

    async def _render_template(self, params: dict, root: Path | None = None) -> ToolResult:
        import jinja2

        template_name = str(params.get("template_name", "")).strip()
        variables = params.get("variables") or {}
        if not isinstance(variables, dict):
            return ToolResult(success=False, error="Parameter 'variables' must be a JSON object / dict.")

        clean_name = template_name.lstrip("/\\")
        if clean_name.startswith("templates/"):
            clean_name = clean_name[len("templates/"):]
        elif clean_name.startswith("templates\\"):
            clean_name = clean_name[len("templates\\"):]

        base_templates_root = ((root or self._iac_root) / "templates").resolve()
        base_templates_root.mkdir(parents=True, exist_ok=True)

        try:
            target_file = self._resolve_safe_path(clean_name, root=base_templates_root)
            if not target_file.exists() or not target_file.is_file():
                if not clean_name.endswith(".tpl"):
                    target_file = self._resolve_safe_path(clean_name + ".tpl", root=base_templates_root)
        except PermissionError as pe:
            return ToolResult(success=False, error=str(pe))

        if not target_file.exists() or not target_file.is_file():
            # Fallback check against self._iac_root/templates
            try:
                real_tpl = (self._iac_root / "templates" / clean_name).resolve()
                if real_tpl.exists() and real_tpl.is_file():
                    target_file = real_tpl
                elif not clean_name.endswith(".tpl") and (self._iac_root / "templates" / (clean_name + ".tpl")).is_file():
                    target_file = (self._iac_root / "templates" / (clean_name + ".tpl")).resolve()
                else:
                    return ToolResult(success=False, error=f"Template '{template_name}' not found under iac/templates/.")
            except Exception:
                return ToolResult(success=False, error=f"Template '{template_name}' not found under iac/templates/.")

        try:
            tpl_text = target_file.read_text(encoding="utf-8")
            env = jinja2.Environment(undefined=jinja2.Undefined)
            rendered = env.from_string(tpl_text).render(**variables)
            return ToolResult(
                success=True,
                data={
                    "template_name": clean_name,
                    "rendered": rendered,
                },
            )
        except Exception as e:
            logger.exception("Failed to render template %s", template_name)
            return ToolResult(success=False, error=f"Template rendering failed: {e}")

    async def _run_terraform_cli(self, args: list[str], cwd: Path) -> tuple[int, str, str]:
        """Execute the real Terraform CLI directly using asyncio subprocess with plugin caching."""
        terraform_bin = shutil.which("terraform") or "/usr/local/bin/terraform"

        env = os.environ.copy()
        plugin_cache = settings.TF_PLUGIN_CACHE_DIR or str(Path.home() / ".terraform.d" / "plugin-cache")
        try:
            Path(plugin_cache).mkdir(parents=True, exist_ok=True)
            env["TF_PLUGIN_CACHE_DIR"] = plugin_cache
        except Exception as e:
            logger.warning("Failed to initialize TF_PLUGIN_CACHE_DIR '%s': %s", plugin_cache, e)

        proc = await asyncio.create_subprocess_exec(
            terraform_bin,
            *args,
            cwd=str(cwd),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout_b, stderr_b = await proc.communicate()
        stdout = stdout_b.decode("utf-8", errors="replace")
        stderr = stderr_b.decode("utf-8", errors="replace")
        return proc.returncode or 0, stdout, stderr

    async def _fmt(self, params: dict, root: Path | None = None) -> ToolResult:
        subpath = params.get("path", "")
        check = bool(params.get("check", False))
        target_path = self._resolve_safe_path(subpath, root=root)

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

    async def _init(self, params: dict, root: Path | None = None) -> ToolResult:
        directory = params.get("directory", "environments/dev")
        target_dir = self._resolve_safe_path(directory, root=root)

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

    async def _validate(self, params: dict, root: Path | None = None) -> ToolResult:
        directory = params.get("directory", "environments/dev")
        target_dir = self._resolve_safe_path(directory, root=root)

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

    async def _plan(self, params: dict, root: Path | None = None) -> ToolResult:
        directory = params.get("directory", "environments/dev")
        var_file = params.get("var_file")
        target_dir = self._resolve_safe_path(directory, root=root)

        if not target_dir.exists() or not target_dir.is_dir():
            return ToolResult(success=False, error=f"Directory '{directory}' does not exist in iac workspace")

        args = ["plan", "-no-color"]
        if var_file:
            # Validate var_file path stays inside directory or iac root
            vf_path = self._resolve_safe_path(f"{directory}/{var_file}" if not var_file.startswith("/") else var_file, root=root)
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
