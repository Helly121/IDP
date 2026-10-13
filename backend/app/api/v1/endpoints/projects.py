"""
Project management endpoints — create projects and check deployment status.
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.project import Project
from app.schemas.project import (
    ProjectCreate,
    ProjectResponse,
    ProjectCatalogResponse,
    ProjectStatusResponse,
)
from app.services import project_service

router = APIRouter(prefix="/projects", tags=["Projects"])
DEMO_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _get_owner_id(current_user: dict | None) -> uuid.UUID:
    if current_user and "sub" in current_user:
        return uuid.UUID(current_user["sub"])
    return DEMO_USER_ID


def _serialize_project(project: Project) -> ProjectCatalogResponse:
    latest = (
        max(project.deployments, key=lambda deployment: deployment.created_at)
        if project.deployments
        else None
    )
    return ProjectCatalogResponse(
        **ProjectResponse.model_validate(project).model_dump(),
        status=latest.status.value if latest else None,
        replicas=latest.replicas if latest else None,
        db_type=latest.db_type.value if latest else None,
        cost_estimate=float(latest.cost_estimate) if latest and latest.cost_estimate is not None else None,
        namespace=latest.namespace if latest else None,
        deployment_id=latest.id if latest else None,
    )


@router.post(
    "/create",
    response_model=ProjectStatusResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new project from the self-service form",
)
async def create_project(
    payload: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict | None = Depends(get_current_user),
):
    """
    Accepts the multi-step form payload and creates:
    1. A Project record
    2. An initial Deployment record (status: PENDING)

    If no auth token is provided, uses a default demo user.
    """
    owner_id = _get_owner_id(current_user)

    # RBAC check (stub — will be expanded in Phase 2)
    allowed, reason = await project_service.check_rbac(db, owner_id, payload.replicas)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=reason,
        )

    project, deployment = await project_service.create_project(db, payload, owner_id)

    return ProjectStatusResponse(
        project=ProjectResponse.model_validate(project),
        deployment_id=deployment.id,
        status=deployment.status.value,
        replicas=deployment.replicas,
        db_type=deployment.db_type.value,
        cost_estimate=float(deployment.cost_estimate),
        namespace=deployment.namespace,
    )


@router.get(
    "",
    response_model=list[ProjectCatalogResponse],
    summary="List the current user's projects and deployment metadata",
)
async def list_projects(
    db: AsyncSession = Depends(get_db),
    current_user: dict | None = Depends(get_current_user),
):
    """Return only projects owned by the authenticated user (or demo user)."""
    projects = await project_service.list_projects(db, _get_owner_id(current_user))
    return [_serialize_project(project) for project in projects]


@router.get(
    "/{project_id}/status",
    response_model=ProjectStatusResponse,
    summary="Get project deployment status",
)
async def get_project_status(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Returns the current project details and latest deployment status,
    including replicas, database type, cost estimate, and namespace.
    """
    result = await project_service.get_project_status(db, project_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )
    return result
