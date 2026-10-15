"""
Authentication endpoints — register, login, Google OAuth, current-user lookup,
and administrator role management.

Routes:
    GET   /api/v1/auth/config          — Public auth config (e.g. Google client ID)
    POST  /api/v1/auth/register        — Email + password sign-up (STUDENT only)
    POST  /api/v1/auth/login           — Email + password sign-in
    POST  /api/v1/auth/google          — Google ID token exchange
    GET   /api/v1/auth/me              — Return current authenticated user
    GET   /api/v1/auth/users           — List users (ADMIN only)
    PATCH /api/v1/auth/users/{id}/role — Update user role (ADMIN only)
"""

import uuid
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    require_auth,
    require_role,
)
from app.models.user import User, UserRole
from app.schemas.user import (
    UserCreate,
    UserLogin,
    UserResponse,
    TokenResponse,
    RoleUpdate,
    AuthConfigResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])


# ── Internal helpers ──────────────────────────────────────────────

def _mint_token(user: User) -> TokenResponse:
    """Create a JWT for *user* and return the full token response."""
    token = create_access_token(
        {"sub": str(user.id), "email": user.email, "role": user.role.value}
    )
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


# ── Config ────────────────────────────────────────────────────────

@router.get(
    "/config",
    response_model=AuthConfigResponse,
    summary="Get public authentication configuration",
)
async def get_auth_config():
    """
    Returns public authentication configuration so frontend can gracefully
    enable/disable providers like Google Sign-In without hardcoding keys.
    """
    client_id = settings.GOOGLE_CLIENT_ID if settings.GOOGLE_CLIENT_ID else None
    return AuthConfigResponse(
        google_auth_enabled=bool(client_id),
        google_client_id=client_id,
    )


# ── Register ──────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new account with email and password",
)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    Register a new user.

    - Public signup creates STUDENT accounts only.
    - Callers cannot choose GUIDE or ADMIN roles during registration.
    - GUIDE/ADMIN role changes must be performed by an authorized admin.
    - Returns a JWT access token and the created user object.
    """
    # Enforce policy: public registration creates STUDENT accounts only
    if payload.role and payload.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Public registration only allows creating STUDENT accounts. GUIDE or ADMIN accounts must be granted by an administrator.",
        )

    # Enforce unique email
    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        role=UserRole.STUDENT,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    await db.flush()

    logger.info("New user registered: %s (role=%s)", user.email, user.role.value)
    return _mint_token(user)


# ── Login ─────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Sign in with email and password",
)
async def login(payload: UserLogin, db: AsyncSession = Depends(get_db)):
    """
    Authenticate with email and password.

    Returns a JWT access token on success. Returns HTTP 401 on any
    credential mismatch (consistently vague to prevent user enumeration).
    """
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if (
        user is None
        or not user.hashed_password
        or not verify_password(payload.password, user.hashed_password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.info("User signed in: %s", user.email)
    return _mint_token(user)


# ── Google OAuth ──────────────────────────────────────────────────

class GoogleAuthRequest(BaseModel):
    id_token: str = Field(..., description="Google ID token from the GSI client library")


@router.post(
    "/google",
    response_model=TokenResponse,
    summary="Sign in or register via Google ID token",
)
async def google_auth(body: GoogleAuthRequest, db: AsyncSession = Depends(get_db)):
    """
    Verify a Google ID token server-side and exchange it for a platform JWT.

    Flow:
      1. Frontend obtains an ID token via Google Identity Services.
      2. Frontend sends the ID token to this endpoint.
      3. Server verifies token with google-auth against GOOGLE_CLIENT_ID.
      4. Provider identity is established via Google's stable 'sub' claim.
      5. Email and name are retrieved from verified Google token payload (not trusted from frontend).
      6. If user does not exist, a new STUDENT account is created.
      7. Returns platform JWT and user profile.
    """
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google Sign-In is not configured on this server. Set GOOGLE_CLIENT_ID.",
        )

    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests

        id_info = google_id_token.verify_oauth2_token(
            body.id_token,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
    except Exception as exc:
        logger.warning("Google token verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google ID token.",
        )

    google_sub: str = id_info.get("sub", "")
    google_email: str = id_info.get("email", "")
    google_name: str = id_info.get("name", "")
    email_verified: bool = id_info.get("email_verified", False)

    if not google_sub or not google_email or not email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google token missing verified email or identity subject.",
        )

    # 1. Lookup by stable Google 'sub'
    result = await db.execute(select(User).where(User.google_sub == google_sub))
    user = result.scalar_one_or_none()

    if user is None:
        # 2. Lookup by verified email
        result = await db.execute(select(User).where(User.email == google_email))
        user = result.scalar_one_or_none()

        if user is not None:
            # Link existing account to Google sub
            user.google_sub = google_sub
            if google_name and not user.full_name:
                user.full_name = google_name
            await db.flush()
            logger.info("Linked Google identity to existing user: %s", google_email)
        else:
            # 3. Create new STUDENT account
            user = User(
                email=google_email,
                full_name=google_name or google_email.split("@")[0],
                role=UserRole.STUDENT,
                google_sub=google_sub,
                hashed_password=None,
            )
            db.add(user)
            await db.flush()
            logger.info("New Google user registered: %s (sub=%s)", google_email, google_sub)
    else:
        if google_name and not user.full_name:
            user.full_name = google_name
            await db.flush()
        logger.info("Google user signed in: %s", google_email)

    return _mint_token(user)


# ── Current user ──────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=UserResponse,
    summary="Return the currently authenticated user",
)
async def get_me(
    payload: dict = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """
    Decode the Bearer token and return the full user record from the database.
    """
    try:
        user_uuid = uuid.UUID(payload["sub"])
    except (ValueError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user token subject.",
        )

    user = await db.get(User, user_uuid)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found. The account may have been deleted.",
        )
    return UserResponse.model_validate(user)


# ── Admin Workflow: Manage Users & Roles ──────────────────────────

@router.get(
    "/users",
    response_model=List[UserResponse],
    summary="List all users (Admin only)",
)
async def list_users(
    payload: dict = Depends(require_role([UserRole.ADMIN.value])),
    db: AsyncSession = Depends(get_db),
):
    """List all registered users. Only accessible by ADMIN users."""
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return [UserResponse.model_validate(u) for u in users]


@router.patch(
    "/users/{user_id}/role",
    response_model=UserResponse,
    summary="Update a user's role (Admin only)",
)
async def update_user_role(
    user_id: uuid.UUID,
    body: RoleUpdate,
    payload: dict = Depends(require_role([UserRole.ADMIN.value])),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a user's role (e.g. promote STUDENT to GUIDE or ADMIN).
    Only accessible by ADMIN users.
    """
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    user.role = body.role
    await db.flush()
    logger.info("Admin %s updated role of %s to %s", payload.get("email"), user.email, body.role.value)
    return UserResponse.model_validate(user)
