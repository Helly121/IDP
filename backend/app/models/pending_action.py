"""
PendingAction ORM model — Tracks mutating tool calls awaiting HITL approval.

When the AI agent wants to perform a mutating action (create repo, apply manifest, etc.),
execution pauses and a PendingAction record is created. A guide or admin must approve
the action before the tool is actually executed.
"""

import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import String, ForeignKey, DateTime, Uuid, JSON
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class ActionStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PendingAction(Base):
    __tablename__ = "pending_actions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), nullable=True, index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    tool_params: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[ActionStatus] = mapped_column(
        SAEnum(ActionStatus, name="action_status", create_constraint=True),
        nullable=False,
        default=ActionStatus.PENDING,
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    requester = relationship("User", foreign_keys=[user_id], backref="pending_actions")

    def __repr__(self) -> str:
        return f"<PendingAction {self.tool_name} ({self.status.value})>"
