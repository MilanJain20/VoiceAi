"""
Application lifecycle events — startup and shutdown hooks.

Manages connection pools, background tasks, and graceful cleanup.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from app.core.logging import get_logger, setup_logging
from app.db.redis import RedisManager
from app.db.session import DatabaseManager
from app.services.conversation_service import ConversationService

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.

    Startup: initialize logging, DB pool, Redis pool.
    Shutdown: drain connections, cleanup resources.
    """
    # ---- Startup ----
    setup_logging()
    logger.info("application_starting", env=app.state.settings.app_env)

    # Initialize database
    db_manager = DatabaseManager(app.state.settings.database_url)
    await db_manager.initialize()
    app.state.db = db_manager
    logger.info("database_connected")

    # Initialize cache/state (Redis or in-memory fallback)
    redis_manager = RedisManager(
        redis_url=app.state.settings.redis_url,
        use_redis=app.state.settings.use_redis,
    )
    await redis_manager.initialize()
    app.state.redis = redis_manager
    logger.info("cache_initialized", backend="redis" if redis_manager.is_redis else "memory")

    # Initialize conversation service
    conversation_service = ConversationService(db_manager.session_factory)
    app.state.conversation_service = conversation_service
    logger.info("conversation_service_initialized")

    # Wire conversation service into the audio pipeline
    from app.services.audio.pipeline import audio_pipeline
    audio_pipeline.set_conversation_service(conversation_service)
    audio_pipeline.set_db_manager(db_manager)

    # Register built-in tools
    from app.services.tools.builtin import register_builtin_tools
    register_builtin_tools()
    from app.services.tools import tool_registry
    logger.info("tools_registered", count=tool_registry.count, tools=tool_registry.list_names())

    # Initialize Redis broadcaster for cross-instance WebSocket delivery
    if redis_manager.is_redis:
        from app.websocket.broadcaster import create_broadcaster
        from app.websocket.manager import connection_manager
        broadcaster = create_broadcaster(redis_manager)
        connection_manager.set_broadcaster(broadcaster)
        await broadcaster.start()
        logger.info("redis_broadcaster_started")
    else:
        logger.info("redis_broadcaster_skipped", reason="no redis backend")

    logger.info(
        "application_started",
        host=app.state.settings.backend_host,
        port=app.state.settings.backend_port,
    )

    yield

    # ---- Shutdown ----
    logger.info("application_shutting_down")

    # Stop Redis broadcaster
    from app.websocket.broadcaster import get_broadcaster
    bc = get_broadcaster()
    if bc:
        await bc.stop()
        logger.info("redis_broadcaster_stopped")

    await redis_manager.close()
    logger.info("cache_closed")

    await db_manager.close()
    logger.info("database_disconnected")

    logger.info("application_stopped")
