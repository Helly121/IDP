"""
SQLAlchemy ORM model for the Users table.
Roles: Student, Guide, Admin — mapped via Python Enum.
"""

import uuid
import enum
from datetime import datetime, timezone
from sqlalchemy import String, Enum as SAEnum, DateTime, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class UserRole(str, enum.Enum):
    STUDENT = "student"
    GUIDE = "guide"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role", create_constraint=True),
        nullable=False,
        default=UserRole.STUDENT,
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    projects = relationship("Project", back_populates="owner", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role.value})>"
