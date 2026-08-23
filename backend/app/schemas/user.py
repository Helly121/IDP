"""
Pydantic v2 schemas for User request/response serialization.
"""

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field
from app.models.user import UserRole


class UserBase(BaseModel):
    email: EmailStr
    full_name: str | None = None
    role: UserRole = UserRole.STUDENT


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=100)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(UserBase):
    id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
