"""
Marketplace models — Agent Store for publishing and discovering agents.

Users can publish agents to the marketplace, discover agents created
by others, rate them, and clone them into their own workspace.
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean, Float, ForeignKey, Integer, String, Text, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class MarketplaceAgent(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "marketplace_agents"

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    publisher_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    tagline: Mapped[str] = mapped_column(String(256), nullable=True, default="")
    description: Mapped[str] = mapped_column(Text, nullable=True, default="")
    icon: Mapped[str] = mapped_column(String(8), nullable=False, default="🤖")
    cover_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    category: Mapped[str] = mapped_column(String(64), default="general", nullable=False)
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)  # pending, published, rejected
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Stats
    downloads: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    avg_rating: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_ratings: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Snapshot of agent config at publish time
    config_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    ratings: Mapped[list["MarketplaceRating"]] = relationship(
        "MarketplaceRating", back_populates="marketplace_agent", cascade="all, delete-orphan"
    )


class MarketplaceRating(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "marketplace_ratings"

    marketplace_agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("marketplace_agents.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    rating: Mapped[float] = mapped_column(Float, nullable=False)
    review: Mapped[str | None] = mapped_column(Text, nullable=True)

    marketplace_agent: Mapped[MarketplaceAgent] = relationship("MarketplaceAgent", back_populates="ratings")
