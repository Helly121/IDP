"""
SQLAlchemy ORM model for the Projects table.
Each project belongs to a User (owner) and has one or more Deployments.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, ForeignKey, DateTime, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), primary_key=True, default=uuid.uuid4
    )
    service_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    language: Mapped[str] = mapped_column(String(50), nullable=False)
    framework: Mapped[str] = mapped_column(String(50), nullable=True)
    description: Mapped[str] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    owner = relationship("User", back_populates="projects")
    deployments = relationship("Deployment", back_populates="project", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Project {self.service_name}>"
