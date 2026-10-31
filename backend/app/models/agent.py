"""
Agent model — core entity for the Agent Studio.

Each agent represents a configurable voice AI persona with:
- System prompt & personality
- Voice settings (TTS voice, rate, pitch)
- LLM settings (temperature, max tokens, model)
- Tool configuration (which tools are enabled)
- Memory config (window size, summarization)
- Versioning (each save creates a new version)
- Analytics metadata (call count, avg duration)
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class AgentStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


class AgentCategory(str, enum.Enum):
    GENERAL = "general"
    SALES = "sales"
    SUPPORT = "support"
    HR = "hr"
    INTERVIEW = "interview"
    EDUCATION = "education"
    HEALTHCARE = "healthcare"
    CUSTOM = "custom"


class Agent(Base, UUIDMixin, TimestampMixin):
    """A configurable voice AI agent."""

    __tablename__ = "agents"

    # ── Identity ──
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True, default="")
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    category: Mapped[AgentCategory] = mapped_column(
        Enum(AgentCategory, values_callable=lambda e: [x.value for x in e]),
        default=AgentCategory.GENERAL, nullable=False,
    )
    status: Mapped[AgentStatus] = mapped_column(
        Enum(AgentStatus, values_callable=lambda e: [x.value for x in e]),
        default=AgentStatus.DRAFT, nullable=False,
    )

    # ── Prompt ──
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    welcome_message: Mapped[str] = mapped_column(
        Text, nullable=True, default="Hello! How can I help you today?"
    )

    # ── Voice settings ──
    tts_voice: Mapped[str] = mapped_column(String(128), default="en-US-AriaNeural", nullable=False)
    tts_rate: Mapped[str] = mapped_column(String(16), default="-5%", nullable=False)
    tts_pitch: Mapped[str] = mapped_column(String(16), default="+0Hz", nullable=False)
    tts_volume: Mapped[str] = mapped_column(String(16), default="+10%", nullable=False)
    language: Mapped[str] = mapped_column(String(16), default="en-US", nullable=False)

    # ── LLM settings ──
    llm_model: Mapped[str] = mapped_column(String(64), default="gpt-4o", nullable=False)
    temperature: Mapped[float] = mapped_column(Float, default=0.3, nullable=False)
    max_tokens: Mapped[int] = mapped_column(Integer, default=4096, nullable=False)
    top_p: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)

    # ── Tools config (list of tool names or custom tool defs) ──
    tools_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)
    # Format: { "enabled_tools": ["get_weather", "calculator"], "custom_tools": [...] }

    # ── Memory config ──
    memory_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)
    # Format: { "type": "window", "window_size": 20, "summarize": false, "max_context_tokens": 8000 }

    # ── Workflow / conversation flow ──
    workflow_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)
    # Format: { "nodes": [...], "edges": [...], "initial_node": "greeting" }

    # ── Analytics (denormalized for fast reads) ──
    total_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    avg_rating: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # ── Ownership ──
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # ── Current version number ──
    current_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # ── Relationships ──
    versions: Mapped[list["AgentVersion"]] = relationship(
        "AgentVersion", back_populates="agent", cascade="all, delete-orphan",
        lazy="selectin", order_by="AgentVersion.version.desc()"
    )

    is_template: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class AgentVersion(Base, UUIDMixin, TimestampMixin):
    """Immutable snapshot of an agent configuration at a point in time."""

    __tablename__ = "agent_versions"

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    change_note: Mapped[str] = mapped_column(Text, nullable=True, default="")

    # Full config snapshot (JSON blob of the entire agent config at this version)
    config_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Who created this version
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # ── Relationships ──
    agent: Mapped[Agent] = relationship("Agent", back_populates="versions")


class CallLog(Base, UUIDMixin, TimestampMixin):
    """Log of every voice call to an agent — for analytics."""

    __tablename__ = "call_logs"

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )

    # Metrics
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Latency
    avg_latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    p95_latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Outcome
    status: Mapped[str] = mapped_column(String(32), default="completed", nullable=False)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)

    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
