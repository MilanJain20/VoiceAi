"""Call history read from CallLog rows written by the voice pipeline."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.core.security import get_current_user
from app.models.agent import Agent, CallLog

router = APIRouter(prefix="/calls", dependencies=[Depends(get_current_user)])


@router.get("")
async def list_calls(
    limit: int = 50,
    db: AsyncSession = Depends(get_db_session),
) -> list[dict]:
    result = await db.execute(select(CallLog).order_by(CallLog.created_at.desc()).limit(limit))
    logs = result.scalars().all()
    agent_ids = {row.agent_id for row in logs}
    names: dict = {}
    if agent_ids:
        agents = await db.execute(select(Agent).where(Agent.id.in_(agent_ids)))
        names = {agent.id: agent.name for agent in agents.scalars().all()}
    return [
        {
            "id": str(row.id),
            "agent_id": str(row.agent_id),
            "agent_name": names.get(row.agent_id, "Agent"),
            "session_id": row.session_id,
            "duration_ms": row.duration_ms,
            "message_count": row.message_count,
            "total_tokens": row.total_tokens,
            "avg_latency_ms": row.avg_latency_ms,
            "p95_latency_ms": row.p95_latency_ms,
            "status": row.status,
            "rating": row.rating,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in logs
    ]
