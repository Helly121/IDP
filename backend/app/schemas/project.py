"""
Pydantic v2 schemas for Project request/response serialization.
"""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    """Payload from the multi-step form."""
    service_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z][a-z0-9\-]{0,98}[a-z0-9]$",
        description="DNS-safe service name (lowercase, hyphens allowed)",
        json_schema_extra={"examples": ["my-flask-api"]},
    )
    language: str = Field(
        ...,
        max_length=50,
        description="Programming language",
        json_schema_extra={"examples": ["python"]},
    )
    framework: str | None = Field(
        None,
        max_length=50,
        description="Framework (optional)",
        json_schema_extra={"examples": ["fastapi"]},
    )
    db_type: str = Field(
        "none",
        description="Database type: postgres, mongodb, redis, none",
        json_schema_extra={"examples": ["postgres"]},
    )
    replicas: int = Field(
        1,
        ge=1,
        le=10,
        description="Number of pod replicas (1–10)",
    )
    description: str | None = Field(None, max_length=500)


class ProjectResponse(BaseModel):
    id: UUID
    service_name: str
    owner_id: UUID
    language: str
    framework: str | None
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectStatusResponse(BaseModel):
    project: ProjectResponse
    deployment_id: UUID | None = None
    status: str
    replicas: int
    db_type: str
    cost_estimate: float
    namespace: str | None = None
    error_message: str | None = None
