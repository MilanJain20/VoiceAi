"""
Security utilities — JWT handling, password hashing, auth dependencies.

Provides:
- Password hashing via bcrypt (passlib)
- JWT access/refresh token creation and verification
- FastAPI dependency for extracting the current user from Bearer tokens
- Optional auth enforcement (controlled by settings.auth_enabled)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt as pyjwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ── Password Hashing ─────────────────────────────────────────────────


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


# ── JWT Tokens ────────────────────────────────────────────────────────


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT access token."""
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return pyjwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)  # type: ignore[union-attr]


def create_refresh_token(data: dict[str, Any]) -> str:
    """Create a signed JWT refresh token (longer lived)."""
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_token_expire_days)
    to_encode.update({"exp": expire, "type": "refresh"})
    return pyjwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)  # type: ignore[union-attr]


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and verify a JWT token. Raises HTTPException on failure."""
    settings = get_settings()
    try:
        payload = pyjwt.decode(  # type: ignore[union-attr]
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


# ── FastAPI Auth Dependencies ─────────────────────────────────────────

_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class TokenPayload:
    """Decoded token contents."""

    sub: str  # user ID
    email: str = ""
    role: str = "viewer"
    type: str = "access"


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> TokenPayload | None:
    """
    Extract user from Bearer token if present.
    Returns None if no token provided (for optional auth routes).
    """
    if credentials is None:
        return None

    payload = decode_access_token(credentials.credentials)
    return TokenPayload(
        sub=payload.get("sub", ""),
        email=payload.get("email", ""),
        role=payload.get("role", "viewer"),
        type=payload.get("type", "access"),
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> TokenPayload:
    """
    Require a valid Bearer token. Raises 401 if missing/invalid.
    When auth_enabled=False, returns a dummy admin user for development.
    """
    settings = get_settings()

    if not settings.auth_enabled:
        # Auth disabled — return dev user
        return TokenPayload(sub="dev-user", email="dev@localhost", role="admin")

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    return TokenPayload(
        sub=payload.get("sub", ""),
        email=payload.get("email", ""),
        role=payload.get("role", "viewer"),
        type=payload.get("type", "access"),
    )


async def require_admin(
    user: TokenPayload = Depends(get_current_user),
) -> TokenPayload:
    """Require the current user to have admin role."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
