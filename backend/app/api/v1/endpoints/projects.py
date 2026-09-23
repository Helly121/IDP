"""
Project management endpoints — create projects, list projects, and check deployment status.
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_auth
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectStatusResponse
from app.services import project_service

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get(
    "",
    response_model=list[ProjectResponse],
    summary="List projects (students view own; guides/admins view all)",
)
async def list_projects(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_auth),
):
    """
    Returns list of projects.
    - STUDENT: access only their own projects.
    - GUIDE / ADMIN: access all projects across the platform.
    """
    user_id = uuid.UUID(current_user["sub"])
    role = current_user.get("role", "student")

    if role in ("guide", "admin"):
        stmt = select(Project).order_by(Project.created_at.desc())
    else:
        stmt = select(Project).where(Project.owner_id == user_id).order_by(Project.created_at.desc())

    result = await db.execute(stmt)
    projects = result.scalars().all()
    return [ProjectResponse.model_validate(p) for p in projects]


@router.post(
    "/create",
    response_model=ProjectStatusResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new project from the self-service form",
)
async def create_project(
    payload: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_auth),
):
    """
    Accepts the multi-step form payload and creates:
    1. A Project record
    2. An initial Deployment record (status: PENDING)

    Requires authentication. The project owner is set to the authenticated user.
    """
    owner_id = uuid.UUID(current_user["sub"])

    # RBAC check — enforced via the User's role in the database
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
    current_user: dict = Depends(require_auth),
):
    """
    Returns the current project details and latest deployment status,
    including replicas, database type, cost estimate, and namespace.
    Enforces RBAC: students can only access their own projects.
    """
    result = await project_service.get_project_status(db, project_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    if current_user.get("role") == "student" and str(result.project.owner_id) != current_user["sub"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: students may only view their own projects.",
        )

    return result
