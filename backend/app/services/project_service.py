"""
Business logic for project creation, status retrieval, and RBAC evaluation.
Keeps API routers thin by encapsulating all DB operations here.
"""

import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.project import Project
from app.models.deployment import Deployment, DeploymentStatus, DatabaseType
from app.models.user import User, UserRole
from app.schemas.project import ProjectCreate, ProjectStatusResponse, ProjectResponse


# ── Cost estimation heuristic (placeholder) ────────────────────
COST_PER_REPLICA = 2.50  # USD/month
DB_COSTS = {
    DatabaseType.POSTGRES: 10.00,
    DatabaseType.MONGODB: 12.00,
    DatabaseType.REDIS: 5.00,
    DatabaseType.NONE: 0.00,
}


def _estimate_cost(replicas: int, db_type: DatabaseType) -> float:
    return round(replicas * COST_PER_REPLICA + DB_COSTS.get(db_type, 0.0), 2)


async def create_project(
    db: AsyncSession,
    payload: ProjectCreate,
    owner_id: uuid.UUID,
) -> tuple[Project, Deployment]:
    """
    Create a new project and its initial deployment record.
    Returns both the Project and Deployment ORM objects.
    """
    db_type = DatabaseType(payload.db_type)

    project = Project(
        service_name=payload.service_name,
        owner_id=owner_id,
        language=payload.language,
        framework=payload.framework,
        description=payload.description,
    )
    db.add(project)
    await db.flush()  # populate project.id

    deployment = Deployment(
        project_id=project.id,
        replicas=payload.replicas,
        db_type=db_type,
        cost_estimate=_estimate_cost(payload.replicas, db_type),
        status=DeploymentStatus.PENDING,
        namespace=f"idp-{payload.service_name}",
    )
    db.add(deployment)
    await db.flush()

    return project, deployment


async def get_project_status(
    db: AsyncSession,
    project_id: uuid.UUID,
) -> ProjectStatusResponse | None:
    """
    Fetch a project and its latest deployment status.
    Returns None if the project doesn't exist.
    """
    stmt = (
        select(Project)
        .options(selectinload(Project.deployments))
        .where(Project.id == project_id)
    )
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()

    if project is None:
        return None

    # Get the most recent deployment
    latest = max(project.deployments, key=lambda d: d.created_at) if project.deployments else None

    return ProjectStatusResponse(
        project=ProjectResponse.model_validate(project),
        deployment_id=latest.id if latest else None,
        status=latest.status.value if latest else "no_deployment",
        replicas=latest.replicas if latest else 0,
        db_type=latest.db_type.value if latest else "none",
        cost_estimate=float(latest.cost_estimate) if latest else 0.0,
        namespace=latest.namespace if latest else None,
        error_message=latest.error_message if latest else None,
    )


async def check_rbac(
    db: AsyncSession,
    user_id: uuid.UUID,
    requested_replicas: int,
) -> tuple[bool, str]:
    """
    Stub RBAC check. In Phase 2 this will query a full policy engine.
    Current rules:
      - Students: max 3 replicas without guide approval
      - Guides/Admins: unlimited
    """
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        return False, "User not found"

    if user.role == UserRole.STUDENT and requested_replicas > 3:
        return False, "Students require guide approval for more than 3 replicas"

    return True, "Authorized"
