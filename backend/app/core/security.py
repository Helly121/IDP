"""
Security utilities for JWT authentication, password hashing, and RBAC.

Provides:
- JWT token creation and verification
- Argon2 password hashing via pwdlib with Bcrypt backward-compatibility
- FastAPI dependencies: get_current_user, require_auth, require_role
"""

from datetime import datetime, timedelta, timezone
from typing import Callable, List, Optional
import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Password hashing ──────────────────────────────────────────────
# Primary hasher is Argon2 for new hashes; Bcrypt hasher is included for backward compatibility
_password_hash = PasswordHash((Argon2Hasher(), BcryptHasher()))

security_scheme = HTTPBearer(auto_error=False)


def hash_password(plain: str) -> str:
    """Return an Argon2 hash of *plain*. Never store plain passwords."""
    return _password_hash.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """
    Return True if *plain* matches *hashed* (constant-time comparison).
    Supports Argon2 and legacy Bcrypt hashes safely.
    """
    try:
        return _password_hash.verify(plain, hashed)
    except Exception as exc:
        logger.warning("Password verification error: %s", exc)
        return False


# ── JWT helpers ───────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a signed JWT access token.

    Args:
        data: Payload claims (must include 'sub' for user UUID).
              Recommended additional claims: 'email', 'role'.
        expires_delta: Custom expiration; defaults to config value.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_token(token: str) -> dict:
    """Decode and validate a JWT token. Raises HTTP 401 on failure."""
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


# ── FastAPI dependencies ──────────────────────────────────────────

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
    """FastAPI dependency that enforces authentication. Returns the decoded JWT payload."""
    return verify_token(credentials.credentials)


def require_role(allowed_roles: List[str]) -> Callable:
    """
    FastAPI dependency factory for role-based access control (RBAC).

    Usage:
        @router.post("/admin-only")
        async def admin_endpoint(payload=Depends(require_role(["admin"]))):
            ...

    Args:
        allowed_roles: List of role strings (e.g. ["guide", "admin"]).

    Returns:
        A FastAPI dependency that validates the authenticated user's role.
    """
    async def _check_role(payload: dict = Depends(require_auth)) -> dict:
        role = payload.get("role", "")
        if role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access requires one of the following roles: {allowed_roles}",
            )
        return payload

    return _check_role
