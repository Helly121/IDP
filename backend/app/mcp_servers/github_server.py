"""
GitHub MCP Server — Tools for repository and file management via GitHub REST API.

Configured via GITHUB_TOKEN (PAT) and GITHUB_ORG environment variables.
All write operations are flagged as mutating for HITL approval gates.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings
from app.mcp_servers.base import (
    MCPServerBase,
    ToolCategory,
    ToolDefinition,
    ToolParameter,
    ToolResult,
)

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


class GitHubMCPServer(MCPServerBase):
    """MCP server that wraps the GitHub REST API."""

    def __init__(self) -> None:
        self._token = settings.GITHUB_TOKEN
        self._org = settings.GITHUB_ORG
        self._headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            self._headers["Authorization"] = f"Bearer {self._token}"

    # ------------------------------------------------------------------
    # MCPServerBase interface
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        return bool(self._token)

    def list_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="github_create_repo",
                description=(
                    "Create a new GitHub repository under the configured organisation. "
                    "Returns the repo URL and clone URL."
                ),
                parameters=[
                    ToolParameter(name="repo_name", type="string", description="Repository name (e.g. my-service)"),
                    ToolParameter(name="description", type="string", description="Short repository description", required=False),
                    ToolParameter(name="private", type="boolean", description="Whether the repo should be private", required=False),
                ],
                is_mutating=True,
                category=ToolCategory.GITHUB,
            ),
            ToolDefinition(
                name="github_push_file",
                description=(
                    "Create or update a single file in a GitHub repository. "
                    "Use this to commit Dockerfiles, Kubernetes manifests, CI configs, etc."
                ),
                parameters=[
                    ToolParameter(name="repo_name", type="string", description="Repository name"),
                    ToolParameter(name="file_path", type="string", description="Path within the repo (e.g. k8s/deployment.yaml)"),
                    ToolParameter(name="content", type="string", description="File content to commit"),
                    ToolParameter(name="commit_message", type="string", description="Git commit message"),
                    ToolParameter(name="branch", type="string", description="Target branch", required=False),
                ],
                is_mutating=True,
                category=ToolCategory.GITHUB,
            ),
            ToolDefinition(
                name="github_list_repos",
                description="List repositories under the configured GitHub organisation.",
                parameters=[
                    ToolParameter(name="per_page", type="integer", description="Results per page (max 100)", required=False),
                ],
                is_mutating=False,
                category=ToolCategory.GITHUB,
            ),
            ToolDefinition(
                name="github_get_file_content",
                description="Read the contents of a file from a GitHub repository.",
                parameters=[
                    ToolParameter(name="repo_name", type="string", description="Repository name"),
                    ToolParameter(name="file_path", type="string", description="Path within the repo"),
                    ToolParameter(name="branch", type="string", description="Branch to read from", required=False),
                ],
                is_mutating=False,
                category=ToolCategory.GITHUB,
            ),
        ]

    async def execute_tool(self, tool_name: str, params: dict) -> ToolResult:
        dispatch = {
            "github_create_repo": self._create_repo,
            "github_push_file": self._push_file,
            "github_list_repos": self._list_repos,
            "github_get_file_content": self._get_file_content,
        }
        handler = dispatch.get(tool_name)
        if handler is None:
            return ToolResult(success=False, error=f"Unknown tool: {tool_name}")
        try:
            return await handler(params)
        except Exception as e:
            logger.exception("GitHub tool %s failed", tool_name)
            return ToolResult(success=False, error=str(e))

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    async def _create_repo(self, params: dict) -> ToolResult:
        url = f"{GITHUB_API}/orgs/{self._org}/repos"
        body: dict[str, Any] = {
            "name": params["repo_name"],
            "auto_init": True,
        }
        if params.get("description"):
            body["description"] = params["description"]
        if params.get("private") is not None:
            body["private"] = params["private"]

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=body, headers=self._headers, timeout=30)
            if resp.status_code == 201:
                data = resp.json()
                return ToolResult(
                    success=True,
                    data={
                        "html_url": data["html_url"],
                        "clone_url": data["clone_url"],
                        "full_name": data["full_name"],
                    },
                )
            return ToolResult(success=False, error=f"GitHub API {resp.status_code}: {resp.text}")

    async def _push_file(self, params: dict) -> ToolResult:
        import base64

        repo = params["repo_name"]
        path = params["file_path"]
        branch = params.get("branch", "main")

        # Check if file already exists (to get its SHA for update)
        get_url = f"{GITHUB_API}/repos/{self._org}/{repo}/contents/{path}?ref={branch}"
        async with httpx.AsyncClient() as client:
            existing = await client.get(get_url, headers=self._headers, timeout=15)
            sha = existing.json().get("sha") if existing.status_code == 200 else None

            put_url = f"{GITHUB_API}/repos/{self._org}/{repo}/contents/{path}"
            body: dict[str, Any] = {
                "message": params["commit_message"],
                "content": base64.b64encode(params["content"].encode()).decode(),
                "branch": branch,
            }
            if sha:
                body["sha"] = sha

            resp = await client.put(put_url, json=body, headers=self._headers, timeout=30)
            if resp.status_code in (200, 201):
                data = resp.json()
                return ToolResult(
                    success=True,
                    data={
                        "path": data["content"]["path"],
                        "sha": data["content"]["sha"],
                        "commit_sha": data["commit"]["sha"],
                    },
                )
            return ToolResult(success=False, error=f"GitHub API {resp.status_code}: {resp.text}")

    async def _list_repos(self, params: dict) -> ToolResult:
        per_page = params.get("per_page", 30)
        url = f"{GITHUB_API}/orgs/{self._org}/repos?per_page={per_page}&sort=updated"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self._headers, timeout=15)
            if resp.status_code == 200:
                repos = [
                    {"name": r["name"], "html_url": r["html_url"], "updated_at": r["updated_at"]}
                    for r in resp.json()
                ]
                return ToolResult(success=True, data=repos)
            return ToolResult(success=False, error=f"GitHub API {resp.status_code}: {resp.text}")

    async def _get_file_content(self, params: dict) -> ToolResult:
        import base64

        repo = params["repo_name"]
        path = params["file_path"]
        branch = params.get("branch", "main")
        url = f"{GITHUB_API}/repos/{self._org}/{repo}/contents/{path}?ref={branch}"

        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self._headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
                return ToolResult(success=True, data={"path": path, "content": content, "sha": data["sha"]})
            return ToolResult(success=False, error=f"GitHub API {resp.status_code}: {resp.text}")
