"""
SQLAlchemy ORM model for the Deployments table.
Tracks the infrastructure state and cost estimate for each project deployment.
"""

import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Numeric, ForeignKey, DateTime, Enum as SAEnum, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class DeploymentStatus(str, enum.Enum):
    PENDING = "pending"
    PROVISIONING = "provisioning"
    RUNNING = "running"
    FAILED = "failed"
    STOPPED = "stopped"
    TERMINATED = "terminated"


class DatabaseType(str, enum.Enum):
    POSTGRES = "postgres"
    MONGODB = "mongodb"
    REDIS = "redis"
    NONE = "none"


class Deployment(Base):
    __tablename__ = "deployments"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    replicas: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    db_type: Mapped[DatabaseType] = mapped_column(
        SAEnum(DatabaseType, name="database_type", create_constraint=True),
        nullable=False,
        default=DatabaseType.NONE,
    )
    cost_estimate: Mapped[float] = mapped_column(
        Numeric(10, 2), nullable=True, default=0.00
    )
    status: Mapped[DeploymentStatus] = mapped_column(
        SAEnum(DeploymentStatus, name="deployment_status", create_constraint=True),
        nullable=False,
        default=DeploymentStatus.PENDING,
    )
    namespace: Mapped[str] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    project = relationship("Project", back_populates="deployments")

    def __repr__(self) -> str:
        return f"<Deployment {self.id} ({self.status.value})>"
