"""Cross-agent analytics computed from CallLog and message timings."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.core.security import get_current_user
from app.models.agent import Agent, AgentStatus, CallLog
from app.services.metrics import percentile

router = APIRouter(prefix="/analytics", dependencies=[Depends(get_current_user)])


@router.get("/overview")
async def overview(db: AsyncSession = Depends(get_db_session)) -> dict:
    agent_count = (await db.execute(select(func.count(Agent.id)))).scalar() or 0
    active = (
        await db.execute(select(func.count(Agent.id)).where(Agent.status == AgentStatus.ACTIVE))
    ).scalar() or 0
    calls = (await db.execute(select(func.count(CallLog.id)))).scalar() or 0
    duration = (
        await db.execute(select(func.coalesce(func.sum(CallLog.duration_ms), 0)))
    ).scalar() or 0
    rows = await db.execute(select(CallLog.turn_latencies))
    totals: list[float] = []
    for (latencies,) in rows.all():
        if isinstance(latencies, list):
            totals.extend(float(value) for value in latencies)
    return {
        "total_agents": agent_count,
        "active_agents": active,
        "total_calls": calls,
        "total_duration_ms": int(duration),
        "latency_p50_ms": round(percentile(totals, 50), 1),
        "latency_p95_ms": round(percentile(totals, 95), 1),
        "turn_count": len(totals),
    }
