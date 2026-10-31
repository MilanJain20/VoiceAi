"""
Auth REST API — registration, login, token refresh, profile.

Works with JWT tokens. When auth_enabled=False, registration/login
still work but protected routes return a dev user.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import (
    TokenPayload,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.models.user import User, UserRole

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


# ── Request / Response Schemas ────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=6, max_length=128)
    full_name: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class RefreshRequest(BaseModel):
    refresh_token: str


class UserProfile(BaseModel):
    id: str
    email: str
    full_name: str | None
    role: str
    is_active: bool


# ── Dependency to get DB session ──────────────────────────────────────

async def _get_db(request: Request):
    """Yield an async DB session from the app's database manager."""
    db_manager = request.app.state.db
    async with db_manager.session_factory() as session:
        yield session


# ── Routes ────────────────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(_get_db)):
    """Register a new user account."""
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == body.email))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Create user
    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        role=UserRole.VIEWER,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    logger.info("user_registered", user_id=str(user.id), email=user.email)

    # Generate tokens
    token_data = {"sub": str(user.id), "email": user.email, "role": user.role.value}
    from app.config import get_settings
    settings = get_settings()

    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(_get_db)):
    """Authenticate and get tokens."""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    logger.info("user_logged_in", user_id=str(user.id), email=user.email)

    token_data = {"sub": str(user.id), "email": user.email, "role": user.role.value}
    from app.config import get_settings
    settings = get_settings()

    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest):
    """Refresh an access token using a refresh token."""
    payload = decode_access_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    token_data = {
        "sub": payload["sub"],
        "email": payload.get("email", ""),
        "role": payload.get("role", "viewer"),
    }
    from app.config import get_settings
    settings = get_settings()

    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
        expires_in=settings.jwt_access_token_expire_minutes * 60,
    )


@router.get("/me", response_model=UserProfile)
async def get_me(current_user: TokenPayload = Depends(get_current_user)):
    """Get the current user's profile."""
    return UserProfile(
        id=current_user.sub,
        email=current_user.email,
        full_name=None,
        role=current_user.role,
        is_active=True,
    )
