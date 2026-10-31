"""
Health check endpoints.

Provides:
- /health: basic liveness check
- /ready: deep readiness check (DB + Redis connectivity)
- /metrics: connection and system metrics
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text

from app.api.deps import get_redis_manager, get_ws_manager
from app.db.redis import RedisManager
from app.services.audio.pipeline import audio_pipeline
from app.websocket.manager import ConnectionManager

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    """Liveness probe — returns 200 if the process is running."""
    return {"status": "healthy"}


@router.get("/ready")
async def readiness_check(
    request: Request,
    redis: RedisManager = Depends(get_redis_manager),
) -> dict:
    """
    Readiness probe — verifies all dependencies are accessible.
    Used by Docker/K8s to determine if the instance can accept traffic.
    """
    checks = {}

    # Check PostgreSQL
    try:
        db_manager = request.app.state.db
        async with db_manager.session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"error: {str(e)}"

    # Check Redis
    try:
        redis_ok = await redis.health_check()
        checks["redis"] = "ok" if redis_ok else "error"
    except Exception as e:
        checks["redis"] = f"error: {str(e)}"

    all_ok = all(v == "ok" for v in checks.values())
    return {
        "status": "ready" if all_ok else "degraded",
        "checks": checks,
    }


@router.get("/metrics")
async def connection_metrics(
    ws_manager: ConnectionManager = Depends(get_ws_manager),
) -> dict:
    """Expose WebSocket connection and audio pipeline metrics."""
    metrics = ws_manager.get_metrics()
    metrics["audio_sessions"] = audio_pipeline.active_sessions
    return metrics
