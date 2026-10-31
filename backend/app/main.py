"""
FastAPI application factory.

Assembles the application from components:
- Configuration injection
- Lifespan events (startup/shutdown)
- Middleware stack
- Exception handlers
- API routers
- WebSocket manager

This is the single entry point for all HTTP and WebSocket traffic.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

from app.api.v1 import router as v1_router
from app.config import get_settings
from app.core.events import lifespan
from app.core.exceptions import register_exception_handlers
from app.core.middleware import setup_middleware


def create_app() -> FastAPI:
    """Application factory — creates and configures the FastAPI instance."""
    settings = get_settings()

    app = FastAPI(
        title="Voice AI Platform",
        description="Realtime conversational AI voice agent platform",
        version="0.1.0",
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
    )

    # Attach settings to app state for access in lifespan and deps
    app.state.settings = settings

    # Setup middleware (CORS, request logging, request IDs)
    setup_middleware(app, settings)

    # Register exception handlers
    register_exception_handlers(app)

    # Mount API routers
    app.include_router(v1_router)

    return app


# Module-level instance for uvicorn: `uvicorn app.main:app`
app = create_app()
