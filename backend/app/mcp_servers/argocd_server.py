"""
ArgoCD MCP Server — Stub/Mock mode for Phase 1.5.

When ARGOCD_URL and ARGOCD_TOKEN are provided, calls the real ArgoCD API.
Otherwise, returns realistic mock data simulating sync status monitoring.
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timezone

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


class ArgoCDMCPServer(MCPServerBase):
    """MCP server for ArgoCD GitOps monitoring and sync management."""

    def __init__(self) -> None:
        self._url = settings.ARGOCD_URL.rstrip("/") if settings.ARGOCD_URL else ""
        self._token = settings.ARGOCD_TOKEN
        self._live = bool(self._url and self._token)
        if self._live:
            logger.info("ArgoCD MCP: live mode — %s", self._url)
        else:
            logger.info("ArgoCD MCP: stub/mock mode (no ARGOCD_URL or ARGOCD_TOKEN)")

    def is_available(self) -> bool:
        # Always available — falls back to mock mode
        return True

    def list_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="argocd_get_app_status",
                description="Get the sync and health status of an ArgoCD application.",
                parameters=[
                    ToolParameter(name="app_name", type="string", description="ArgoCD application name"),
                ],
                is_mutating=False,
                category=ToolCategory.ARGOCD,
            ),
            ToolDefinition(
                name="argocd_list_apps",
                description="List all ArgoCD applications with their sync and health status.",
                parameters=[],
                is_mutating=False,
                category=ToolCategory.ARGOCD,
            ),
            ToolDefinition(
                name="argocd_sync_app",
                description="Trigger a manual sync for an ArgoCD application. This reconciles the live cluster state with the desired state in Git.",
                parameters=[
                    ToolParameter(name="app_name", type="string", description="ArgoCD application name"),
                ],
                is_mutating=True,
                category=ToolCategory.ARGOCD,
            ),
            ToolDefinition(
                name="argocd_get_sync_diff",
                description="Preview what would change on the next sync for an ArgoCD application.",
                parameters=[
                    ToolParameter(name="app_name", type="string", description="ArgoCD application name"),
                ],
                is_mutating=False,
                category=ToolCategory.ARGOCD,
            ),
        ]

    async def execute_tool(self, tool_name: str, params: dict) -> ToolResult:
        dispatch = {
            "argocd_get_app_status": self._get_app_status,
            "argocd_list_apps": self._list_apps,
            "argocd_sync_app": self._sync_app,
            "argocd_get_sync_diff": self._get_sync_diff,
        }
        handler = dispatch.get(tool_name)
        if handler is None:
            return ToolResult(success=False, error=f"Unknown tool: {tool_name}")
        try:
            return await handler(params)
        except Exception as e:
            logger.exception("ArgoCD tool %s failed", tool_name)
            return ToolResult(success=False, error=str(e))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _api_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    async def _get_app_status(self, params: dict) -> ToolResult:
        app_name = params["app_name"]

        if self._live:
            async with httpx.AsyncClient(verify=False) as client:
                resp = await client.get(
                    f"{self._url}/api/v1/applications/{app_name}",
                    headers=self._api_headers(),
                    timeout=15,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    status = data.get("status", {})
                    return ToolResult(success=True, data={
                        "app_name": app_name,
                        "sync_status": status.get("sync", {}).get("status", "Unknown"),
                        "health_status": status.get("health", {}).get("status", "Unknown"),
                        "revision": status.get("sync", {}).get("revision", "N/A"),
                        "source_repo": data.get("spec", {}).get("source", {}).get("repoURL", "N/A"),
                    })
                return ToolResult(success=False, error=f"ArgoCD API {resp.status_code}: {resp.text}")

        # Mock mode
        sync_statuses = ["Synced", "OutOfSync", "Synced", "Synced"]
        health_statuses = ["Healthy", "Degraded", "Healthy", "Healthy"]
        idx = hash(app_name) % len(sync_statuses)
        return ToolResult(success=True, data={
            "app_name": app_name,
            "sync_status": sync_statuses[idx],
            "health_status": health_statuses[idx],
            "revision": "abc1234",
            "source_repo": f"https://github.com/{settings.GITHUB_ORG}/{app_name}.git",
            "_mock": True,
        })

    async def _list_apps(self, params: dict) -> ToolResult:
        if self._live:
            async with httpx.AsyncClient(verify=False) as client:
                resp = await client.get(
                    f"{self._url}/api/v1/applications",
                    headers=self._api_headers(),
                    timeout=15,
                )
                if resp.status_code == 200:
                    items = resp.json().get("items", [])
                    apps = []
                    for item in items:
                        status = item.get("status", {})
                        apps.append({
                            "name": item["metadata"]["name"],
                            "sync_status": status.get("sync", {}).get("status", "Unknown"),
                            "health_status": status.get("health", {}).get("status", "Unknown"),
                        })
                    return ToolResult(success=True, data=apps)
                return ToolResult(success=False, error=f"ArgoCD API {resp.status_code}: {resp.text}")

        # Mock mode — return a few simulated apps
        mock_apps = [
            {"name": "idp-frontend", "sync_status": "Synced", "health_status": "Healthy"},
            {"name": "idp-backend", "sync_status": "Synced", "health_status": "Healthy"},
            {"name": "student-project-alpha", "sync_status": "OutOfSync", "health_status": "Degraded"},
        ]
        return ToolResult(success=True, data={"apps": mock_apps, "_mock": True})

    async def _sync_app(self, params: dict) -> ToolResult:
        app_name = params["app_name"]

        if self._live:
            async with httpx.AsyncClient(verify=False) as client:
                resp = await client.post(
                    f"{self._url}/api/v1/applications/{app_name}/sync",
                    headers=self._api_headers(),
                    json={},
                    timeout=30,
                )
                if resp.status_code == 200:
                    return ToolResult(success=True, data={
                        "app_name": app_name,
                        "message": "Sync triggered successfully",
                        "phase": resp.json().get("status", {}).get("operationState", {}).get("phase", "Running"),
                    })
                return ToolResult(success=False, error=f"ArgoCD API {resp.status_code}: {resp.text}")

        # Mock mode
        return ToolResult(success=True, data={
            "app_name": app_name,
            "message": "Sync triggered (mock mode)",
            "phase": "Succeeded",
            "_mock": True,
        })

    async def _get_sync_diff(self, params: dict) -> ToolResult:
        app_name = params["app_name"]

        if self._live:
            async with httpx.AsyncClient(verify=False) as client:
                resp = await client.get(
                    f"{self._url}/api/v1/applications/{app_name}/managed-resources",
                    headers=self._api_headers(),
                    timeout=15,
                )
                if resp.status_code == 200:
                    resources = resp.json().get("items", [])
                    diffs = [
                        {"kind": r.get("kind"), "name": r.get("name"), "status": r.get("status")}
                        for r in resources
                    ]
                    return ToolResult(success=True, data=diffs)
                return ToolResult(success=False, error=f"ArgoCD API {resp.status_code}: {resp.text}")

        # Mock mode
        return ToolResult(success=True, data={
            "diffs": [
                {"kind": "Deployment", "name": app_name, "status": "OutOfSync", "change": "replicas: 2 -> 3"},
                {"kind": "Service", "name": f"{app_name}-svc", "status": "Synced", "change": "none"},
            ],
            "_mock": True,
        })
