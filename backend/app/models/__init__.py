"""
Models package — re-export all ORM models so that Alembic and
Base.metadata.create_all() can discover them in a single import.
"""

from app.models.user import User, UserRole
from app.models.project import Project
from app.models.deployment import Deployment, DeploymentStatus, DatabaseType

__all__ = [
    "User",
    "UserRole",
    "Project",
    "Deployment",
    "DeploymentStatus",
    "DatabaseType",
]
