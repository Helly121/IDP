"""
Central MCP Tool Registry — Aggregates all MCP servers and provides
a unified interface for the Agent Orchestrator.

Responsibilities:
- Instantiate all MCP server modules on startup
- Collect tool definitions into a unified list for Gemini function declarations
- Provide dispatch(tool_name, params) to route calls to the correct server
- Tag each tool with is_mutating for the HITL engine
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.mcp_servers.base import MCPServerBase, ToolDefinition, ToolResult
from app.mcp_servers.github_server import GitHubMCPServer
from app.mcp_servers.kubernetes_server import KubernetesMCPServer
from app.mcp_servers.argocd_server import ArgoCDMCPServer
from app.mcp_servers.policy_server import PolicyMCPServer
from app.mcp_servers.terraform_server import TerraformMCPServer
from app.mcp_servers.workflow_server import WorkflowMCPServer

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Singleton-like registry that holds all MCP servers and their tools.
    Initialised once at app startup via `initialize()`.
    """

    def __init__(self) -> None:
        self._servers: dict[str, MCPServerBase] = {}
        self._tool_map: dict[str, tuple[MCPServerBase, ToolDefinition]] = {}
        self._initialized = False

    def initialize(self, config_path: str | None = None) -> None:
        """
        Instantiate all MCP servers and build the tool index.
        Optionally reads mcp_config.json for enable/disable flags.
        """
        if self._initialized:
            return

        # Load optional config
        enabled: dict[str, bool] = {}
        if config_path:
            p = Path(config_path)
            if p.is_file():
                try:
                    cfg = json.loads(p.read_text())
                    for name, server_cfg in cfg.get("servers", {}).items():
                        enabled[name] = server_cfg.get("enabled", True)
                    logger.info("Loaded MCP config from %s", config_path)
                except Exception as e:
                    logger.warning("Failed to load MCP config: %s", e)

        # Register servers
        server_classes: list[tuple[str, type[MCPServerBase]]] = [
            ("github", GitHubMCPServer),
            ("kubernetes", KubernetesMCPServer),
            ("argocd", ArgoCDMCPServer),
            ("policy", PolicyMCPServer),
            ("terraform", TerraformMCPServer),
            ("cicd", WorkflowMCPServer),
        ]

        for name, cls in server_classes:
            if not enabled.get(name, True):
                logger.info("MCP server '%s' is disabled in config", name)
                continue

            try:
                server = cls()
                if server.is_available():
                    self._servers[name] = server
                    for tool in server.list_tools():
                        self._tool_map[tool.name] = (server, tool)
                    logger.info(
                        "MCP server '%s' registered with %d tools",
                        name,
                        len(server.list_tools()),
                    )
                else:
                    logger.warning(
                        "MCP server '%s' is not available (missing credentials?)",
                        name,
                    )
            except Exception as e:
                logger.error("Failed to initialize MCP server '%s': %s", name, e)

        self._initialized = True
        logger.info(
            "Tool registry initialized: %d servers, %d tools",
            len(self._servers),
            len(self._tool_map),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_all_tools(self) -> list[ToolDefinition]:
        """Return all registered tool definitions."""
        return [td for _, td in self._tool_map.values()]

    def get_tool(self, name: str) -> ToolDefinition | None:
        """Look up a tool definition by name."""
        entry = self._tool_map.get(name)
        return entry[1] if entry else None

    def is_mutating(self, tool_name: str) -> bool:
        """Check if a tool is mutating (requires HITL approval)."""
        tool = self.get_tool(tool_name)
        return tool.is_mutating if tool else False

    async def dispatch(self, tool_name: str, params: dict) -> ToolResult:
        """Execute a tool by name, routing to the correct MCP server."""
        entry = self._tool_map.get(tool_name)
        if entry is None:
            return ToolResult(success=False, error=f"Tool '{tool_name}' not found in registry")

        server, tool_def = entry
        logger.info("Dispatching tool '%s' (mutating=%s)", tool_name, tool_def.is_mutating)
        return await server.execute_tool(tool_name, params)

    def get_gemini_declarations(self) -> list[dict]:
        """
        Return all tool definitions formatted as Gemini function declarations.
        Ready to pass to GenerativeModel(tools=[...]).
        """
        return [td.to_gemini_declaration() for td in self.get_all_tools()]

    def get_server_status(self) -> dict[str, Any]:
        """Return status info for all registered servers (for health checks)."""
        return {
            name: {
                "available": server.is_available(),
                "tool_count": len(server.list_tools()),
                "tools": [t.name for t in server.list_tools()],
            }
            for name, server in self._servers.items()
        }


# Module-level singleton
registry = ToolRegistry()
