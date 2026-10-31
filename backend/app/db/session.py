"""
Async SQLAlchemy database session management.

Uses SQLAlchemy 2.0 async engine with connection pooling configured
for production workloads. The DatabaseManager lifecycle is tied to
the FastAPI application lifespan.
"""

from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.logging import get_logger

logger = get_logger(__name__)


class DatabaseManager:
    """
    Manages the async SQLAlchemy engine and session factory.

    Connection pool settings:
    - pool_size=20: concurrent connections for normal load
    - max_overflow=10: burst capacity above pool_size
    - pool_recycle=3600: recycle connections after 1 hour (prevents stale connections)
    - pool_pre_ping=True: verify connections before use (handles network interruptions)
    """

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    async def initialize(self) -> None:
        self._engine = create_async_engine(
            self._database_url,
            echo=False,
            pool_size=20,
            max_overflow=10,
            pool_recycle=3600,
            pool_pre_ping=True,
        )
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        logger.info("database_engine_created", pool_size=20, max_overflow=10)

    async def close(self) -> None:
        if self._engine:
            await self._engine.dispose()
            logger.info("database_engine_disposed")

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        if self._session_factory is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self._session_factory

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Yield an async session with automatic cleanup."""
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
