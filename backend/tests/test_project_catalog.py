import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1.endpoints.projects import _serialize_project
from app.core.database import Base
from app.models.deployment import DatabaseType, Deployment, DeploymentStatus
from app.models.project import Project
from app.models.user import User, UserRole
from app.services.project_service import list_projects


@pytest.mark.asyncio
async def test_project_catalog_is_owner_scoped_and_uses_persisted_deployment_data():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        owner_id = uuid.uuid4()
        other_owner_id = uuid.uuid4()
        async with session_factory() as db:
            owner_project = Project(
                service_name="owned-service",
                owner_id=owner_id,
                language="python",
                framework="fastapi",
            )
            no_deployment_project = Project(
                service_name="pending-service",
                owner_id=owner_id,
                language="go",
                framework=None,
            )
            private_project = Project(
                service_name="private-service",
                owner_id=other_owner_id,
                language="rust",
                framework="axum",
            )
            db.add_all([
                User(id=owner_id, email="owner@example.com", role=UserRole.STUDENT),
                User(id=other_owner_id, email="other@example.com", role=UserRole.STUDENT),
                owner_project,
                no_deployment_project,
                private_project,
            ])
            await db.flush()
            db.add(Deployment(
                project_id=owner_project.id,
                replicas=3,
                db_type=DatabaseType.POSTGRES,
                cost_estimate=17.50,
                status=DeploymentStatus.FAILED,
                namespace="idp-owned-service",
            ))
            await db.commit()

            projects = await list_projects(db, owner_id)
            catalog = {project.service_name: _serialize_project(project) for project in projects}

        assert set(catalog) == {"owned-service", "pending-service"}
        deployed = catalog["owned-service"]
        assert deployed.status == "failed"
        assert deployed.replicas == 3
        assert deployed.db_type == "postgres"
        assert deployed.cost_estimate == 17.5
        assert deployed.namespace == "idp-owned-service"

        no_deployment = catalog["pending-service"]
        assert no_deployment.status is None
        assert no_deployment.replicas is None
        assert no_deployment.db_type is None
        assert no_deployment.cost_estimate is None
        assert no_deployment.namespace is None
    finally:
        await engine.dispose()


def test_catalog_tool_is_read_only_and_registered_by_policy_server():
    from app.mcp_servers.policy_server import PolicyMCPServer

    catalog_tool = next(
        tool for tool in PolicyMCPServer().list_tools()
        if tool.name == "catalog_list_projects"
    )
    assert catalog_tool.is_mutating is False
