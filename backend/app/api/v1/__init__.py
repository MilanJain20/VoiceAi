"""API v1 package."""

from fastapi import APIRouter

from app.api.v1.routes import (
    agents,
    analytics,
    auth,
    calls,
    conversations,
    evaluations,
    health,
    knowledge,
    marketplace,
    tools,
    workflows,
)
from app.api.v1.websockets import voice

router = APIRouter(prefix="/api/v1")

# REST routes
router.include_router(health.router, tags=["health"])
router.include_router(auth.router, tags=["auth"])
router.include_router(conversations.router, tags=["conversations"])
router.include_router(agents.router, tags=["agents"])
router.include_router(calls.router, tags=["calls"])
router.include_router(analytics.router, tags=["analytics"])
router.include_router(tools.router, tags=["tools"])
router.include_router(workflows.router, tags=["workflows"])
router.include_router(knowledge.router, tags=["knowledge"])
router.include_router(marketplace.router, tags=["marketplace"])
router.include_router(evaluations.router, tags=["evaluations"])
router.include_router(evaluations.replay_router, tags=["call-replay"])

# WebSocket routes
router.include_router(voice.router, tags=["voice"])
