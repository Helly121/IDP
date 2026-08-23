"""
JWT authentication stub for Phase 1.
Provides token creation, verification, and a FastAPI dependency for protected routes.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings

security_scheme = HTTPBearer(auto_error=False)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a signed JWT access token.

    Args:
        data: Payload claims (must include 'sub' for user ID).
        expires_delta: Custom expiration; defaults to config value.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_token(token: str) -> dict:
    """Decode and validate a JWT token. Raises HTTPException on failure."""
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
) -> Optional[dict]:
    """
    FastAPI dependency to extract the current user from the Authorization header.
    Returns None if no token is provided (allows unauthenticated access where needed).
    """
    if credentials is None:
        return None
    return verify_token(credentials.credentials)


async def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
) -> dict:
    """FastAPI dependency that enforces authentication. Returns the decoded payload."""
    return verify_token(credentials.credentials)
