"""
FastAPI dependency injection providers.

Centralized dependency functions used by route handlers.
Dependencies are resolved per-request by FastAPI's DI system.
"""

from __future__ import annotations

from typing import AsyncGenerator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.redis import RedisManager
from app.db.session import DatabaseManager
from app.websocket.manager import ConnectionManager, connection_manager


def get_db_manager(request: Request) -> DatabaseManager:
    return request.app.state.db


def get_redis_manager(request: Request) -> RedisManager:
    return request.app.state.redis


async def get_db_session(
    db_manager: DatabaseManager = Depends(get_db_manager),
) -> AsyncGenerator[AsyncSession, None]:
    async for session in db_manager.get_session():
        yield session


def get_ws_manager() -> ConnectionManager:
    return connection_manager


def get_app_settings() -> Settings:
    return get_settings()
