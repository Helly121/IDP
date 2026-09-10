"""
Policy & Cost MCP Server — RBAC validation, cost estimation, and user role queries.

Interfaces with the existing User, Project, and Deployment database tables
to enforce institution-specific rules (student quotas vs faculty approvals).
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.models.user import User, UserRole
from app.models.project import Project
from app.models.deployment import Deployment, DeploymentStatus, DatabaseType
from app.mcp_servers.base import (
    MCPServerBase,
    ToolCategory,
    ToolDefinition,
    ToolParameter,
    ToolResult,
)

logger = logging.getLogger(__name__)

# Cost constants
COST_PER_REPLICA = 2.50  # USD/month
DB_COSTS = {
    "postgres": 10.00,
    "mongodb": 12.00,
    "redis": 5.00,
    "none": 0.00,
}

# RBAC limits
STUDENT_MAX_REPLICAS = 3
STUDENT_MAX_PROJECTS = 5
GUIDE_MAX_REPLICAS = 10


class PolicyMCPServer(MCPServerBase):
    """MCP server that exposes the platform's RBAC and cost-estimation engine."""

    def is_available(self) -> bool:
        return True

    def list_tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="policy_check_quota",
                description=(
                    "Validate whether a user is allowed to provision the requested resources. "
                    "Checks role-based limits on replicas and project counts. "
                    "Returns allowed=true/false with a reason."
                ),
                parameters=[
                    ToolParameter(name="user_id", type="string", description="UUID of the requesting user"),
                    ToolParameter(name="requested_replicas", type="integer", description="Number of replicas requested"),
                    ToolParameter(name="db_type", type="string", description="Database type: postgres, mongodb, redis, none", required=False),
                ],
                is_mutating=False,
                category=ToolCategory.POLICY,
            ),
            ToolDefinition(
                name="policy_estimate_cost",
                description="Estimate the monthly cost (USD) for a given resource configuration.",
                parameters=[
                    ToolParameter(name="replicas", type="integer", description="Number of pod replicas"),
                    ToolParameter(name="db_type", type="string", description="Database type: postgres, mongodb, redis, none"),
                ],
                is_mutating=False,
                category=ToolCategory.POLICY,
            ),
            ToolDefinition(
                name="policy_get_user_role",
                description="Get a user's role, current project count, and total resource usage across all projects.",
                parameters=[
                    ToolParameter(name="user_id", type="string", description="UUID of the user"),
                ],
                is_mutating=False,
                category=ToolCategory.POLICY,
            ),
            ToolDefinition(
                name="policy_approve_escalation",
                description=(
                    "Record that a guide or admin has approved an over-quota resource request. "
                    "This allows the student's request to proceed."
                ),
                parameters=[
                    ToolParameter(name="user_id", type="string", description="UUID of the student whose request is being approved"),
                    ToolParameter(name="approver_id", type="string", description="UUID of the guide/admin approving"),
                    ToolParameter(name="requested_replicas", type="integer", description="Number of replicas being approved"),
                ],
                is_mutating=True,
                category=ToolCategory.POLICY,
            ),
        ]

    async def execute_tool(self, tool_name: str, params: dict) -> ToolResult:
        dispatch = {
            "policy_check_quota": self._check_quota,
            "policy_estimate_cost": self._estimate_cost,
            "policy_get_user_role": self._get_user_role,
            "policy_approve_escalation": self._approve_escalation,
        }
        handler = dispatch.get(tool_name)
        if handler is None:
            return ToolResult(success=False, error=f"Unknown tool: {tool_name}")
        try:
            return await handler(params)
        except Exception as e:
            logger.exception("Policy tool %s failed", tool_name)
            return ToolResult(success=False, error=str(e))

    # ------------------------------------------------------------------
    # Tool implementations
    # ------------------------------------------------------------------

    async def _check_quota(self, params: dict) -> ToolResult:
        user_id = uuid.UUID(params["user_id"])
        requested_replicas = params["requested_replicas"]

        async with async_session_factory() as db:
            user = await db.get(User, user_id)
            if user is None:
                return ToolResult(success=True, data={"allowed": False, "reason": "User not found"})

            # Count existing projects
            count_stmt = select(func.count(Project.id)).where(Project.owner_id == user_id)
            result = await db.execute(count_stmt)
            project_count = result.scalar() or 0

            if user.role == UserRole.STUDENT:
                if requested_replicas > STUDENT_MAX_REPLICAS:
                    return ToolResult(success=True, data={
                        "allowed": False,
                        "reason": f"Students are limited to {STUDENT_MAX_REPLICAS} replicas. You requested {requested_replicas}. A guide or admin must approve this escalation.",
                        "user_role": user.role.value,
                        "max_replicas": STUDENT_MAX_REPLICAS,
                    })
                if project_count >= STUDENT_MAX_PROJECTS:
                    return ToolResult(success=True, data={
                        "allowed": False,
                        "reason": f"Students are limited to {STUDENT_MAX_PROJECTS} projects. You currently have {project_count}.",
                        "user_role": user.role.value,
                    })
            elif user.role == UserRole.GUIDE:
                if requested_replicas > GUIDE_MAX_REPLICAS:
                    return ToolResult(success=True, data={
                        "allowed": False,
                        "reason": f"Guides are limited to {GUIDE_MAX_REPLICAS} replicas per project. Admin approval required.",
                        "user_role": user.role.value,
                    })

            return ToolResult(success=True, data={
                "allowed": True,
                "reason": "Request is within quota limits",
                "user_role": user.role.value,
                "current_projects": project_count,
            })

    async def _estimate_cost(self, params: dict) -> ToolResult:
        replicas = params["replicas"]
        db_type = params.get("db_type", "none")
        compute = replicas * COST_PER_REPLICA
        database = DB_COSTS.get(db_type, 0.0)
        total = round(compute + database, 2)
        return ToolResult(success=True, data={
            "compute_cost": compute,
            "database_cost": database,
            "total_monthly_cost_usd": total,
            "breakdown": f"{replicas} replicas × ${COST_PER_REPLICA}/mo + {db_type} DB ${database}/mo",
        })

    async def _get_user_role(self, params: dict) -> ToolResult:
        user_id = uuid.UUID(params["user_id"])

        async with async_session_factory() as db:
            user = await db.get(User, user_id)
            if user is None:
                return ToolResult(success=True, data={"error": "User not found"})

            # Count projects and total replicas
            stmt = (
                select(func.count(Project.id), func.coalesce(func.sum(Deployment.replicas), 0))
                .outerjoin(Deployment, Deployment.project_id == Project.id)
                .where(Project.owner_id == user_id)
            )
            result = await db.execute(stmt)
            row = result.one()

            return ToolResult(success=True, data={
                "user_id": str(user.id),
                "email": user.email,
                "role": user.role.value,
                "full_name": user.full_name,
                "project_count": row[0],
                "total_replicas": int(row[1]),
            })

    async def _approve_escalation(self, params: dict) -> ToolResult:
        approver_id = uuid.UUID(params["approver_id"])

        async with async_session_factory() as db:
            approver = await db.get(User, approver_id)
            if approver is None:
                return ToolResult(success=False, error="Approver not found")
            if approver.role not in (UserRole.GUIDE, UserRole.ADMIN):
                return ToolResult(success=False, error="Only guides and admins can approve escalations")

            return ToolResult(success=True, data={
                "approved": True,
                "user_id": params["user_id"],
                "approved_by": str(approver_id),
                "approved_replicas": params["requested_replicas"],
                "message": f"Escalation approved by {approver.full_name or approver.email}",
            })
