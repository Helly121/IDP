"""
Project management endpoints — create projects and check deployment status.
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectStatusResponse, ProjectCatalogResponse
from app.models.project import Project
from app.services import project_service

router = APIRouter(prefix="/projects", tags=["Projects"])


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
    # Use authenticated user ID or fallback to a demo UUID
    if current_user and "sub" in current_user:
        owner_id = uuid.UUID(current_user["sub"])
    else:
        # Demo mode — create with a fixed demo user ID
        owner_id = uuid.UUID("00000000-0000-0000-0000-000000000001")

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


@router.get(
    "",
    response_model=list[ProjectCatalogResponse],
    summary="List the current user's services and deployment metadata",
)
async def list_projects(
    db: AsyncSession = Depends(get_db),
    current_user: dict | None = Depends(get_current_user),
):
    """Return only projects owned by the caller, with deployment data eagerly loaded."""
    owner_id = (
        uuid.UUID(current_user["sub"])
        if current_user and current_user.get("sub")
        else uuid.UUID("00000000-0000-0000-0000-000000000001")
    )
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.deployments))
        .where(Project.owner_id == owner_id)
        .order_by(Project.created_at.desc())
    )
    projects = result.scalars().all()
    catalog = []
    for project in projects:
        latest = max(project.deployments, key=lambda d: d.created_at) if project.deployments else None
        catalog.append(ProjectCatalogResponse(
            id=project.id,
            service_name=project.service_name,
            owner_id=project.owner_id,
            language=project.language,
            framework=project.framework,
            description=project.description,
            created_at=project.created_at,
            updated_at=project.updated_at,
            status=latest.status.value if latest else "pending",
            replicas=latest.replicas if latest else 1,
            db_type=latest.db_type.value if latest else "none",
            cost_estimate=float(latest.cost_estimate or 0) if latest else 0.0,
            namespace=latest.namespace if latest else f"idp-{project.service_name}",
            deployment_id=latest.id if latest else None,
        ))
    return catalog
