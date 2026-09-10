"""
MCP Server Base Classes and Tool Envelope.

Provides the abstract interface that all MCP tool servers implement,
along with structured data classes for tool definitions and results.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ToolCategory(str, Enum):
    """Categorises tools for UI grouping and filtering."""
    GITHUB = "github"
    KUBERNETES = "kubernetes"
    ARGOCD = "argocd"
    POLICY = "policy"


@dataclass
class ToolParameter:
    """Schema for a single tool parameter."""
    name: str
    type: str  # "string", "integer", "boolean", "number", "array", "object"
    description: str
    required: bool = True
    enum: list[str] | None = None
    default: Any = None


@dataclass
class ToolDefinition:
    """
    Complete definition of a tool that the AI agent can invoke.
    Maps directly to a Gemini function declaration.
    """
    name: str
    description: str
    parameters: list[ToolParameter]
    is_mutating: bool = False
    category: ToolCategory = ToolCategory.POLICY

    def to_gemini_declaration(self) -> dict:
        """Convert to the dict format expected by google-generativeai."""
        properties = {}
        required = []
        for p in self.parameters:
            prop: dict[str, Any] = {
                "type": p.type.upper(),
                "description": p.description,
            }
            if p.enum:
                prop["enum"] = p.enum
            properties[p.name] = prop
            if p.required:
                required.append(p.name)

        schema: dict[str, Any] = {
            "type": "OBJECT",
            "properties": properties,
        }
        if required:
            schema["required"] = required

        return {
            "name": self.name,
            "description": self.description,
            "parameters": schema,
        }


@dataclass
class ToolResult:
    """Envelope returned by every tool execution."""
    success: bool
    data: Any = None
    error: str | None = None

    def to_dict(self) -> dict:
        result: dict[str, Any] = {"success": self.success}
        if self.data is not None:
            result["data"] = self.data
        if self.error is not None:
            result["error"] = self.error
        return result


class MCPServerBase(ABC):
    """
    Abstract base class for all MCP tool servers.

    Each server:
    - Declares a list of tools it provides (with schemas and mutating flags).
    - Implements execute_tool() to dispatch a tool call by name.
    """

    @abstractmethod
    def list_tools(self) -> list[ToolDefinition]:
        """Return all tool definitions this server provides."""
        ...

    @abstractmethod
    async def execute_tool(self, tool_name: str, params: dict) -> ToolResult:
        """Execute a named tool with the given parameters."""
        ...

    def is_available(self) -> bool:
        """Check whether this server is properly configured and ready."""
        return True
