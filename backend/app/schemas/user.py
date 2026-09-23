"""
Pydantic v2 schemas for User request/response serialization.
"""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field
from app.models.user import UserRole


class UserCreate(BaseModel):
    """Schema for public user registration. Only STUDENT role is granted."""
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=100)
    full_name: str | None = None
    role: UserRole | None = Field(
        default=UserRole.STUDENT,
        description="Public registration role is always STUDENT. Other roles will be rejected.",
    )


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class RoleUpdate(BaseModel):
    """Schema for admin role modifications."""
    role: UserRole


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str | None = None
    role: UserRole
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class AuthConfigResponse(BaseModel):
    google_auth_enabled: bool
    google_client_id: str | None = None
