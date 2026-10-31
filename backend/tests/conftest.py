"""
Test configuration and fixtures.

Provides:
- Async test client (httpx)
- Test database session (isolated per test)
- Redis mock/fixture
- WebSocket test client
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncGenerator  # noqa: TC003

# Settings are constructed at import time. Provide test credentials before that.
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("POSTGRES_PASSWORD", "voiceai_dev_password")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://voiceai:voiceai_dev_password@localhost:5432/voiceai",
)
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-not-for-production-use")
os.environ.setdefault("AUTH_ENABLED", "false")
os.environ.setdefault("INSECURE_SKIP_TLS_VERIFY", "false")

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for all tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def app():
    """Create a test application instance."""
    test_app = create_app()
    yield test_app


@pytest_asyncio.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Isolated database session for tests.
    Uses a test database and rolls back after each test.
    """
    settings = get_settings()
    test_db_url = settings.database_url.replace("/voiceai", "/voiceai_test")

    engine = create_async_engine(test_db_url, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()
