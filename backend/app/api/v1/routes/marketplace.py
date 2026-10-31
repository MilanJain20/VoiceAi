"""
Marketplace API — Browse, publish, clone & rate agents.

Endpoints:
  POST   /marketplace              — Publish agent to marketplace
  GET    /marketplace              — Browse marketplace
  GET    /marketplace/featured     — Featured agents
  GET    /marketplace/{id}         — Get marketplace agent detail
  POST   /marketplace/{id}/clone   — Clone agent to your workspace
  POST   /marketplace/{id}/rate    — Rate/review an agent
  GET    /marketplace/{id}/ratings — List ratings
"""

from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session
from app.models.agent import Agent
from app.models.marketplace import MarketplaceAgent, MarketplaceRating

router = APIRouter(prefix="/marketplace")


# ── Schemas ───────────────────────────────────────────────────────


from pydantic import BaseModel, Field  # noqa: E402


class PublishRequest(BaseModel):
    agent_id: str
    title: str = Field(..., min_length=1, max_length=200)
    tagline: str | None = None
    description: str | None = None
    icon: str | None = None
    category: str | None = "general"
    tags: list[str] = []


class RateRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    review: str | None = None


# ── Endpoints ─────────────────────────────────────────────────────


@router.post("")
async def publish_to_marketplace(data: PublishRequest, db: AsyncSession = Depends(get_db_session)):
    """Publish an agent to the marketplace."""
    # Verify agent exists
    result = await db.execute(select(Agent).where(Agent.id == uuid.UUID(data.agent_id)))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    marketplace_agent = MarketplaceAgent(
        id=uuid.uuid4(),
        agent_id=agent.id,
        publisher_id=agent.created_by,
        title=data.title,
        tagline=data.tagline,
        description=data.description or agent.description,
        icon=data.icon or "🤖",
        category=data.category,
        tags=data.tags,
        status="pending",
        config_snapshot={
            "system_prompt": agent.system_prompt,
            "welcome_message": agent.welcome_message,
            "tts_voice": agent.tts_voice,
            "tools": agent.tools_config,
        },
    )
    db.add(marketplace_agent)
    await db.commit()
    return {"id": str(marketplace_agent.id), "status": "pending"}


@router.get("")
async def browse_marketplace(
    category: str | None = None,
    search: str | None = None,
    sort: str = "downloads",
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db_session),
):
    """Browse marketplace agents."""
    query = select(MarketplaceAgent).where(MarketplaceAgent.status == "published")
    if category:
        query = query.where(MarketplaceAgent.category == category)
    if search:
        query = query.where(MarketplaceAgent.title.ilike(f"%{search}%"))
    if sort == "downloads":
        query = query.order_by(MarketplaceAgent.downloads.desc())
    elif sort == "rating":
        query = query.order_by(MarketplaceAgent.avg_rating.desc())
    else:
        query = query.order_by(MarketplaceAgent.created_at.desc())
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    agents = result.scalars().all()
    return [
        {
            "id": str(a.id),
            "title": a.title,
            "tagline": a.tagline,
            "icon": a.icon,
            "category": a.category,
            "tags": a.tags,
            "downloads": a.downloads,
            "avg_rating": a.avg_rating,
            "total_ratings": a.total_ratings,
            "is_featured": a.is_featured,
        }
        for a in agents
    ]


@router.get("/featured")
async def featured_agents(db: AsyncSession = Depends(get_db_session)):
    """Get featured marketplace agents."""
    result = await db.execute(
        select(MarketplaceAgent)
        .where(MarketplaceAgent.is_featured == True, MarketplaceAgent.status == "published")
        .order_by(MarketplaceAgent.downloads.desc())
        .limit(8)
    )
    agents = result.scalars().all()
    return [
        {
            "id": str(a.id),
            "title": a.title,
            "tagline": a.tagline,
            "icon": a.icon,
            "category": a.category,
            "downloads": a.downloads,
            "avg_rating": a.avg_rating,
        }
        for a in agents
    ]


@router.get("/{marketplace_id}")
async def get_marketplace_agent(marketplace_id: str, db: AsyncSession = Depends(get_db_session)):
    """Get marketplace agent detail."""
    result = await db.execute(
        select(MarketplaceAgent).where(MarketplaceAgent.id == uuid.UUID(marketplace_id))
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Marketplace agent not found")
    return {
        "id": str(agent.id),
        "title": agent.title,
        "tagline": agent.tagline,
        "description": agent.description,
        "icon": agent.icon,
        "category": agent.category,
        "tags": agent.tags,
        "downloads": agent.downloads,
        "avg_rating": agent.avg_rating,
        "total_ratings": agent.total_ratings,
        "is_featured": agent.is_featured,
        "config_snapshot": agent.config_snapshot,
        "created_at": agent.created_at.isoformat() if agent.created_at else None,
    }


@router.post("/{marketplace_id}/clone")
async def clone_marketplace_agent(marketplace_id: str, db: AsyncSession = Depends(get_db_session)):
    """Clone a marketplace agent to user's workspace."""
    result = await db.execute(
        select(MarketplaceAgent).where(MarketplaceAgent.id == uuid.UUID(marketplace_id))
    )
    mp_agent = result.scalar_one_or_none()
    if not mp_agent:
        raise HTTPException(status_code=404, detail="Marketplace agent not found")

    # Create a new agent from the config snapshot
    config = mp_agent.config_snapshot or {}
    base_name = f"{mp_agent.title} (cloned)"
    slug = re.sub(r"[^\w\s-]", "", base_name.lower()).strip()
    slug = re.sub(r"[\s_]+", "-", slug)[:120] or f"clone-{uuid.uuid4().hex[:6]}"
    existing = await db.execute(select(Agent).where(Agent.slug == slug))
    if existing.scalar_one_or_none():
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"
    new_agent = Agent(
        id=uuid.uuid4(),
        name=base_name,
        slug=slug,
        description=mp_agent.description or "",
        system_prompt=config.get("system_prompt", ""),
        welcome_message=config.get("welcome_message", "Hello!"),
        tts_voice=config.get("tts_voice", "en-US-JennyNeural"),
        tools_config=config.get("tools") if isinstance(config.get("tools"), dict) else {},
        current_version=1,
    )
    db.add(new_agent)
    mp_agent.downloads += 1
    await db.commit()
    return {"agent_id": str(new_agent.id), "name": new_agent.name, "cloned_from": mp_agent.title}


@router.post("/{marketplace_id}/rate")
async def rate_marketplace_agent(
    marketplace_id: str, data: RateRequest, db: AsyncSession = Depends(get_db_session)
):
    """Rate a marketplace agent."""
    result = await db.execute(
        select(MarketplaceAgent).where(MarketplaceAgent.id == uuid.UUID(marketplace_id))
    )
    mp_agent = result.scalar_one_or_none()
    if not mp_agent:
        raise HTTPException(status_code=404, detail="Marketplace agent not found")

    rating = MarketplaceRating(
        id=uuid.uuid4(),
        marketplace_agent_id=mp_agent.id,
        rating=data.rating,
        review=data.review,
    )
    db.add(rating)

    # Update average
    mp_agent.total_ratings += 1
    mp_agent.avg_rating = round(
        ((mp_agent.avg_rating or 0) * (mp_agent.total_ratings - 1) + data.rating)
        / mp_agent.total_ratings,
        2,
    )
    await db.commit()
    return {"rating_id": str(rating.id), "new_avg": mp_agent.avg_rating}


@router.get("/{marketplace_id}/ratings")
async def list_ratings(
    marketplace_id: str, limit: int = 20, db: AsyncSession = Depends(get_db_session)
):
    """List ratings for a marketplace agent."""
    query = (
        select(MarketplaceRating)
        .where(MarketplaceRating.marketplace_agent_id == uuid.UUID(marketplace_id))
        .order_by(MarketplaceRating.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    ratings = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "rating": r.rating,
            "review": r.review,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in ratings
    ]
