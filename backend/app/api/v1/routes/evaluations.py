"""
Evaluations & Call Replay API — Agent scoring, LLM-as-Judge, call timeline.

Endpoints:
  POST   /evaluations              — Run evaluation on a call
  GET    /evaluations              — List evaluations
  GET    /evaluations/summary      — Aggregate metrics
  GET    /evaluations/{id}         — Get eval detail
  POST   /calls/replay             — Create call replay
  GET    /calls/replay             — List call replays
  GET    /calls/replay/{id}        — Get call replay with timeline
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.models.evaluation import AgentEvaluation, CallReplay

router = APIRouter(prefix="/evaluations")


# ── Schemas ───────────────────────────────────────────────────────

from pydantic import BaseModel, Field
from typing import Optional, List


class EvalCreate(BaseModel):
    agent_id: str
    call_log_id: Optional[str] = None
    overall_score: float = 0
    conversation_quality: float = 0
    task_completion: float = 0
    hallucination_score: float = 0
    latency_score: float = 0
    tool_success_rate: float = 0
    csat_score: float = 0
    avg_latency_ms: int = 0
    p95_latency_ms: int = 0
    talk_ratio: float = 0.5
    interruption_count: int = 0
    judge_model: str = "gpt-4o"
    judge_reasoning: Optional[str] = None
    judge_suggestions: List[str] = []


class CallReplayCreate(BaseModel):
    agent_id: str
    session_id: str
    duration_ms: int = 0
    timeline: List[dict] = []
    transcript: List[dict] = []
    audio_segments: List[dict] = []
    summary: Optional[str] = None
    tags: List[str] = []


# ── Evaluation Endpoints ──────────────────────────────────────────

@router.post("")
async def create_evaluation(data: EvalCreate, db: AsyncSession = Depends(get_db_session)):
    """Create/store an evaluation result."""
    evaluation = AgentEvaluation(
        id=uuid.uuid4(),
        agent_id=uuid.UUID(data.agent_id),
        call_log_id=uuid.UUID(data.call_log_id) if data.call_log_id else None,
        overall_score=data.overall_score,
        conversation_quality=data.conversation_quality,
        task_completion=data.task_completion,
        hallucination_score=data.hallucination_score,
        latency_score=data.latency_score,
        tool_success_rate=data.tool_success_rate,
        csat_score=data.csat_score,
        avg_latency_ms=data.avg_latency_ms,
        p95_latency_ms=data.p95_latency_ms,
        talk_ratio=data.talk_ratio,
        interruption_count=data.interruption_count,
        judge_model=data.judge_model,
        judge_reasoning=data.judge_reasoning,
        judge_suggestions=data.judge_suggestions,
    )
    db.add(evaluation)
    await db.commit()
    return {"id": str(evaluation.id), "overall_score": evaluation.overall_score}


@router.get("")
async def list_evaluations(
    agent_id: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db_session),
):
    """List evaluations."""
    query = select(AgentEvaluation)
    if agent_id:
        query = query.where(AgentEvaluation.agent_id == uuid.UUID(agent_id))
    query = query.order_by(AgentEvaluation.evaluated_at.desc()).limit(limit)
    result = await db.execute(query)
    evals = result.scalars().all()
    return [
        {
            "id": str(e.id),
            "agent_id": str(e.agent_id),
            "overall_score": e.overall_score,
            "conversation_quality": e.conversation_quality,
            "task_completion": e.task_completion,
            "hallucination_score": e.hallucination_score,
            "csat_score": e.csat_score,
            "judge_model": e.judge_model,
            "evaluated_at": e.evaluated_at.isoformat() if e.evaluated_at else None,
        }
        for e in evals
    ]


@router.get("/summary")
async def evaluation_summary(
    agent_id: Optional[str] = None,
    days: int = 7,
    db: AsyncSession = Depends(get_db_session),
):
    """Aggregate evaluation metrics."""
    query = select(
        func.count(AgentEvaluation.id).label("total_evals"),
        func.avg(AgentEvaluation.overall_score).label("avg_overall"),
        func.avg(AgentEvaluation.conversation_quality).label("avg_quality"),
        func.avg(AgentEvaluation.task_completion).label("avg_task"),
        func.avg(AgentEvaluation.hallucination_score).label("avg_hallucination"),
        func.avg(AgentEvaluation.latency_score).label("avg_latency"),
        func.avg(AgentEvaluation.tool_success_rate).label("avg_tool_success"),
        func.avg(AgentEvaluation.csat_score).label("avg_csat"),
        func.avg(AgentEvaluation.avg_latency_ms).label("avg_latency_ms"),
    )
    if agent_id:
        query = query.where(AgentEvaluation.agent_id == uuid.UUID(agent_id))
    result = await db.execute(query)
    row = result.one()
    return {
        "total_evaluations": row.total_evals or 0,
        "avg_overall_score": round(float(row.avg_overall or 0), 1),
        "avg_conversation_quality": round(float(row.avg_quality or 0), 1),
        "avg_task_completion": round(float(row.avg_task or 0), 1),
        "avg_hallucination": round(float(row.avg_hallucination or 0), 1),
        "avg_latency_score": round(float(row.avg_latency or 0), 1),
        "avg_tool_success": round(float(row.avg_tool_success or 0), 1),
        "avg_csat": round(float(row.avg_csat or 0), 2),
        "avg_latency_ms": round(float(row.avg_latency_ms or 0), 0),
    }


@router.get("/{eval_id}")
async def get_evaluation(eval_id: str, db: AsyncSession = Depends(get_db_session)):
    """Get evaluation detail."""
    result = await db.execute(select(AgentEvaluation).where(AgentEvaluation.id == uuid.UUID(eval_id)))
    ev = result.scalar_one_or_none()
    if not ev:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    return {
        "id": str(ev.id),
        "agent_id": str(ev.agent_id),
        "overall_score": ev.overall_score,
        "conversation_quality": ev.conversation_quality,
        "task_completion": ev.task_completion,
        "hallucination_score": ev.hallucination_score,
        "latency_score": ev.latency_score,
        "tool_success_rate": ev.tool_success_rate,
        "csat_score": ev.csat_score,
        "avg_latency_ms": ev.avg_latency_ms,
        "p95_latency_ms": ev.p95_latency_ms,
        "talk_ratio": ev.talk_ratio,
        "interruption_count": ev.interruption_count,
        "judge_model": ev.judge_model,
        "judge_reasoning": ev.judge_reasoning,
        "judge_suggestions": ev.judge_suggestions,
        "evaluated_at": ev.evaluated_at.isoformat() if ev.evaluated_at else None,
    }


# ── Call Replay Endpoints ─────────────────────────────────────────

replay_router = APIRouter(prefix="/calls/replay")


@replay_router.post("")
async def create_call_replay(data: CallReplayCreate, db: AsyncSession = Depends(get_db_session)):
    """Store a call replay."""
    replay = CallReplay(
        id=uuid.uuid4(),
        agent_id=uuid.UUID(data.agent_id),
        session_id=data.session_id,
        duration_ms=data.duration_ms,
        timeline=data.timeline,
        transcript=data.transcript,
        audio_segments=data.audio_segments,
        summary=data.summary,
        tags=data.tags,
    )
    db.add(replay)
    await db.commit()
    return {"id": str(replay.id)}


@replay_router.get("")
async def list_call_replays(
    agent_id: Optional[str] = None,
    limit: int = 30,
    db: AsyncSession = Depends(get_db_session),
):
    """List call replays."""
    query = select(CallReplay)
    if agent_id:
        query = query.where(CallReplay.agent_id == uuid.UUID(agent_id))
    query = query.order_by(CallReplay.created_at.desc()).limit(limit)
    result = await db.execute(query)
    replays = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "agent_id": str(r.agent_id),
            "session_id": r.session_id,
            "duration_ms": r.duration_ms,
            "summary": r.summary,
            "tags": r.tags,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in replays
    ]


@replay_router.get("/{replay_id}")
async def get_call_replay(replay_id: str, db: AsyncSession = Depends(get_db_session)):
    """Get full call replay with timeline."""
    result = await db.execute(select(CallReplay).where(CallReplay.id == uuid.UUID(replay_id)))
    replay = result.scalar_one_or_none()
    if not replay:
        raise HTTPException(status_code=404, detail="Call replay not found")
    return {
        "id": str(replay.id),
        "agent_id": str(replay.agent_id),
        "session_id": replay.session_id,
        "duration_ms": replay.duration_ms,
        "timeline": replay.timeline,
        "transcript": replay.transcript,
        "audio_segments": replay.audio_segments,
        "summary": replay.summary,
        "tags": replay.tags,
        "created_at": replay.created_at.isoformat() if replay.created_at else None,
    }
