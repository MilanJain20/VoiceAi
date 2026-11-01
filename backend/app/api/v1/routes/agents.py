"""
Agent Studio API — full CRUD + versioning + analytics + voice catalog.

Endpoints:
  POST   /agents                  — Create a new agent
  GET    /agents                  — List all agents (with filters)
  GET    /agents/templates        — List template agents
  GET    /agents/voices           — Voice catalog
  GET    /agents/{id}             — Get agent detail
  PUT    /agents/{id}             — Update agent (auto-versions)
  DELETE /agents/{id}             — Delete agent
  POST   /agents/{id}/duplicate   — Duplicate an agent
  POST   /agents/{id}/publish     — Publish (draft → active)
  GET    /agents/{id}/versions    — List agent versions
  POST   /agents/{id}/rollback/{v}— Rollback to a version
  GET    /agents/{id}/analytics   — Agent analytics
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.core.security import TokenPayload, get_current_user
from app.models.agent import Agent, AgentCategory, AgentStatus, AgentVersion, CallLog
from app.models.conversation import Conversation, Message
from app.schemas.agent import (
    VOICE_CATALOG,
    AgentCreate,
    AgentDuplicate,
    AgentUpdate,
)
from app.services.metrics import percentile

router = APIRouter(prefix="/agents", dependencies=[Depends(get_current_user)])


def _actor_id(user: TokenPayload | None) -> uuid.UUID | None:
    if user is None:
        return None
    try:
        return uuid.UUID(user.sub)
    except (ValueError, AttributeError):
        return None


def _slugify(name: str) -> str:
    """Convert name to URL-safe slug."""
    slug = re.sub(r"[^\w\s-]", "", name.lower().strip())
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug[:128]


def _agent_to_snapshot(agent: Agent) -> dict:
    """Serialize full agent config to a JSON snapshot for versioning."""
    return {
        "name": agent.name,
        "description": agent.description,
        "category": agent.category.value if agent.category else "general",
        "system_prompt": agent.system_prompt,
        "welcome_message": agent.welcome_message,
        "tts_voice": agent.tts_voice,
        "tts_rate": agent.tts_rate,
        "tts_pitch": agent.tts_pitch,
        "tts_volume": agent.tts_volume,
        "language": agent.language,
        "llm_model": agent.llm_model,
        "temperature": agent.temperature,
        "max_tokens": agent.max_tokens,
        "top_p": agent.top_p,
        "tools_config": agent.tools_config or {},
        "memory_config": agent.memory_config or {},
        "workflow_config": agent.workflow_config or {},
    }


def _serialize_summary(agent: Agent) -> dict:
    return {
        "id": str(agent.id),
        "name": agent.name,
        "slug": agent.slug,
        "description": agent.description or "",
        "category": agent.category.value if agent.category else "general",
        "status": agent.status.value if agent.status else "draft",
        "tts_voice": agent.tts_voice,
        "language": agent.language,
        "total_calls": agent.total_calls,
        "total_duration_ms": agent.total_duration_ms,
        "avg_rating": agent.avg_rating,
        "current_version": agent.current_version,
        "is_template": agent.is_template,
        "created_at": agent.created_at.isoformat() if agent.created_at else "",
        "updated_at": agent.updated_at.isoformat() if agent.updated_at else "",
    }


def _serialize_detail(agent: Agent) -> dict:
    return {
        **_serialize_summary(agent),
        "system_prompt": agent.system_prompt,
        "welcome_message": agent.welcome_message or "",
        "tts_rate": agent.tts_rate,
        "tts_pitch": agent.tts_pitch,
        "tts_volume": agent.tts_volume,
        "llm_model": agent.llm_model,
        "temperature": agent.temperature,
        "max_tokens": agent.max_tokens,
        "top_p": agent.top_p,
        "tools_config": agent.tools_config or {},
        "memory_config": agent.memory_config or {},
        "workflow_config": agent.workflow_config or {},
        "total_duration_ms": agent.total_duration_ms,
    }


# ── CRUD ─────────────────────────────────────────────────────────────


@router.post("", status_code=201)
async def create_agent(
    body: AgentCreate,
    db: AsyncSession = Depends(get_db_session),
    user: TokenPayload = Depends(get_current_user),
) -> dict:
    """Create a new voice agent."""
    slug = _slugify(body.name)

    existing = await db.execute(select(Agent).where(Agent.slug == slug))
    if existing.scalar_one_or_none():
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"

    agent = Agent(
        name=body.name,
        slug=slug,
        description=body.description,
        category=AgentCategory(body.category)
        if body.category in [e.value for e in AgentCategory]
        else AgentCategory.GENERAL,
        system_prompt=body.system_prompt,
        welcome_message=body.welcome_message,
        tts_voice=body.tts_voice,
        tts_rate=body.tts_rate,
        tts_pitch=body.tts_pitch,
        tts_volume=body.tts_volume,
        language=body.language,
        llm_model=body.llm_model,
        temperature=body.temperature,
        max_tokens=body.max_tokens,
        top_p=body.top_p,
        tools_config=body.tools_config,
        memory_config=body.memory_config,
        workflow_config=body.workflow_config,
        is_template=body.is_template,
        current_version=1,
        created_by=_actor_id(user),
    )
    db.add(agent)
    await db.flush()

    version = AgentVersion(
        agent_id=agent.id,
        version=1,
        change_note="Initial version",
        config_snapshot=_agent_to_snapshot(agent),
    )
    db.add(version)
    await db.commit()
    await db.refresh(agent)

    return _serialize_detail(agent)


@router.get("")
async def list_agents(
    status: str | None = None,
    category: str | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db_session),
) -> list[dict]:
    """List all agents with optional filters."""
    query = select(Agent).where(Agent.is_template == False).order_by(Agent.updated_at.desc())

    if status:
        query = query.where(Agent.status == AgentStatus(status))
    if category:
        query = query.where(Agent.category == AgentCategory(category))
    if search:
        query = query.where(Agent.name.ilike(f"%{search}%"))

    result = await db.execute(query)
    agents = result.scalars().all()
    return [_serialize_summary(a) for a in agents]


@router.get("/templates")
async def list_templates(
    db: AsyncSession = Depends(get_db_session),
) -> list[dict]:
    """List template agents (pre-built starting points)."""
    result = await db.execute(select(Agent).where(Agent.is_template == True).order_by(Agent.name))
    return [_serialize_summary(a) for a in result.scalars().all()]


@router.get("/voices")
async def list_voices() -> list[dict]:
    """Return the voice catalog for voice selection UI."""
    return [v.model_dump() for v in VOICE_CATALOG]


@router.get("/{agent_id}")
async def get_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Get full agent configuration."""
    agent = await _get_agent_or_404(db, agent_id)
    return _serialize_detail(agent)


@router.put("/{agent_id}")
async def update_agent(
    agent_id: str,
    body: AgentUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Update an agent. Creates a new version if change_note is provided."""
    agent = await _get_agent_or_404(db, agent_id)

    update_data = body.model_dump(exclude_unset=True, exclude={"change_note"})
    for field, value in update_data.items():
        if field == "status" and value:
            setattr(agent, field, AgentStatus(value))
        elif field == "category" and value:
            setattr(agent, field, AgentCategory(value))
        else:
            setattr(agent, field, value)

    if "name" in update_data:
        new_slug = _slugify(update_data["name"])
        existing = await db.execute(
            select(Agent).where(Agent.slug == new_slug, Agent.id != agent.id)
        )
        if existing.scalar_one_or_none():
            new_slug = f"{new_slug}-{uuid.uuid4().hex[:6]}"
        agent.slug = new_slug

    agent.current_version += 1
    version = AgentVersion(
        agent_id=agent.id,
        version=agent.current_version,
        change_note=body.change_note or "Updated",
        config_snapshot=_agent_to_snapshot(agent),
    )
    db.add(version)

    await db.commit()
    await db.refresh(agent)
    return _serialize_detail(agent)


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete an agent and all its versions."""
    agent = await _get_agent_or_404(db, agent_id)
    await db.delete(agent)
    await db.commit()


@router.post("/{agent_id}/duplicate", status_code=201)
async def duplicate_agent(
    agent_id: str,
    body: AgentDuplicate,
    db: AsyncSession = Depends(get_db_session),
    user: TokenPayload = Depends(get_current_user),
) -> dict:
    """Duplicate an agent with a new name."""
    source = await _get_agent_or_404(db, agent_id)
    slug = _slugify(body.name)

    existing = await db.execute(select(Agent).where(Agent.slug == slug))
    if existing.scalar_one_or_none():
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"

    clone = Agent(
        name=body.name,
        slug=slug,
        description=f"Copy of {source.name}: {source.description}",
        category=source.category,
        status=AgentStatus.DRAFT,
        system_prompt=source.system_prompt,
        welcome_message=source.welcome_message,
        tts_voice=source.tts_voice,
        tts_rate=source.tts_rate,
        tts_pitch=source.tts_pitch,
        tts_volume=source.tts_volume,
        language=source.language,
        llm_model=source.llm_model,
        temperature=source.temperature,
        max_tokens=source.max_tokens,
        top_p=source.top_p,
        tools_config=source.tools_config,
        memory_config=source.memory_config,
        workflow_config=source.workflow_config,
        current_version=1,
        created_by=_actor_id(user),
    )
    db.add(clone)
    await db.flush()

    version = AgentVersion(
        agent_id=clone.id,
        version=1,
        change_note=f"Duplicated from {source.name}",
        config_snapshot=_agent_to_snapshot(clone),
    )
    db.add(version)
    await db.commit()
    await db.refresh(clone)
    return _serialize_detail(clone)


@router.post("/{agent_id}/publish")
async def publish_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Set agent status to active."""
    agent = await _get_agent_or_404(db, agent_id)
    agent.status = AgentStatus.ACTIVE
    agent.current_version += 1
    db.add(
        AgentVersion(
            agent_id=agent.id,
            version=agent.current_version,
            change_note="Published",
            config_snapshot=_agent_to_snapshot(agent),
        )
    )
    await db.commit()
    await db.refresh(agent)
    return _serialize_detail(agent)


# ── Versioning ───────────────────────────────────────────────────────


@router.get("/{agent_id}/versions")
async def list_versions(
    agent_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> list[dict]:
    agent = await _get_agent_or_404(db, agent_id)
    result = await db.execute(
        select(AgentVersion)
        .where(AgentVersion.agent_id == agent.id)
        .order_by(AgentVersion.version.desc())
    )
    versions = result.scalars().all()
    return [
        {
            "id": str(v.id),
            "version": v.version,
            "change_note": v.change_note,
            "created_at": v.created_at.isoformat(),
            "config_snapshot": v.config_snapshot,
        }
        for v in versions
    ]


@router.post("/{agent_id}/rollback/{version}")
async def rollback_agent(
    agent_id: str,
    version: int,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    agent = await _get_agent_or_404(db, agent_id)

    result = await db.execute(
        select(AgentVersion).where(
            AgentVersion.agent_id == agent.id,
            AgentVersion.version == version,
        )
    )
    ver = result.scalar_one_or_none()
    if not ver:
        raise HTTPException(status_code=404, detail=f"Version {version} not found")

    snap = ver.config_snapshot
    for key, value in snap.items():
        if key == "category":
            agent.category = AgentCategory(value)
        elif hasattr(agent, key):
            setattr(agent, key, value)

    agent.current_version += 1
    new_ver = AgentVersion(
        agent_id=agent.id,
        version=agent.current_version,
        change_note=f"Rolled back to version {version}",
        config_snapshot=snap,
    )
    db.add(new_ver)
    await db.commit()
    await db.refresh(agent)
    return _serialize_detail(agent)


# ── Analytics ────────────────────────────────────────────────────────


@router.get("/{agent_id}/analytics")
async def get_analytics(
    agent_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    agent = await _get_agent_or_404(db, agent_id)

    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())

    calls_today_q = await db.execute(
        select(func.count(CallLog.id)).where(
            CallLog.agent_id == agent.id, CallLog.created_at >= today_start
        )
    )
    calls_today = calls_today_q.scalar() or 0

    calls_week_q = await db.execute(
        select(func.count(CallLog.id)).where(
            CallLog.agent_id == agent.id, CallLog.created_at >= week_start
        )
    )
    calls_week = calls_week_q.scalar() or 0

    recent_q = await db.execute(
        select(CallLog)
        .where(CallLog.agent_id == agent.id)
        .order_by(CallLog.created_at.desc())
        .limit(20)
    )
    recent = recent_q.scalars().all()

    avg_dur_q = await db.execute(
        select(func.avg(CallLog.duration_ms)).where(CallLog.agent_id == agent.id)
    )
    avg_duration = avg_dur_q.scalar() or 0

    latency_rows = await db.execute(
        select(CallLog.turn_latencies).where(CallLog.agent_id == agent.id)
    )
    turn_totals: list[float] = []
    for (latencies,) in latency_rows.all():
        if isinstance(latencies, list):
            turn_totals.extend(float(value) for value in latencies)

    breakdown_rows = await db.execute(
        select(Message.latency_breakdown)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(Conversation.agent_id == str(agent.id), Message.latency_breakdown.is_not(None))
    )
    stages: dict[str, list[float]] = {
        "stt_ms": [],
        "llm_first_token_ms": [],
        "tts_first_byte_ms": [],
        "total_ms": [],
    }
    for (breakdown,) in breakdown_rows.all():
        if not isinstance(breakdown, dict):
            continue
        for key in stages:
            if breakdown.get(key) is not None:
                stages[key].append(float(breakdown[key]))
    if not turn_totals:
        turn_totals = stages["total_ms"]

    return {
        "total_calls": agent.total_calls,
        "total_duration_ms": agent.total_duration_ms,
        "avg_duration_ms": round(float(avg_duration), 1),
        "avg_rating": agent.avg_rating,
        "calls_today": calls_today,
        "calls_this_week": calls_week,
        "top_intents": [],
        "latency_p50_ms": round(percentile(turn_totals, 50), 1),
        "latency_p95_ms": round(percentile(turn_totals, 95), 1),
        "stage_p50_ms": {key: round(percentile(values, 50), 1) for key, values in stages.items()},
        "stage_p95_ms": {key: round(percentile(values, 95), 1) for key, values in stages.items()},
        "recent_calls": [
            {
                "id": str(c.id),
                "agent_id": str(c.agent_id),
                "session_id": c.session_id,
                "duration_ms": c.duration_ms,
                "message_count": c.message_count,
                "total_tokens": c.total_tokens,
                "avg_latency_ms": c.avg_latency_ms,
                "status": c.status,
                "rating": c.rating,
                "created_at": c.created_at.isoformat(),
            }
            for c in recent
        ],
    }


# ── Helpers ──────────────────────────────────────────────────────────


async def _get_agent_or_404(db: AsyncSession, agent_id: str) -> Agent:
    try:
        uid = uuid.UUID(agent_id)
        result = await db.execute(select(Agent).where(Agent.id == uid))
    except ValueError:
        result = await db.execute(select(Agent).where(Agent.slug == agent_id))

    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent
