"""
Evaluation models — Agent performance scoring and LLM-as-judge system.

Tracks per-call metrics and runs automated quality evaluation
using a judge LLM to score conversation quality.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime, Float, ForeignKey, Integer, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class AgentEvaluation(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "agent_evaluations"

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    call_log_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("call_logs.id", ondelete="SET NULL"), nullable=True
    )
    session_id: Mapped[str] = mapped_column(String(64), nullable=True)

    # Metric scores (0.0 - 1.0)
    overall_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    conversation_quality: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    task_completion: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    hallucination_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    latency_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    tool_success_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    interruption_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    csat_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Latency details
    avg_latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    p95_latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    talk_ratio: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)  # agent vs user

    # LLM judge output
    judge_model: Mapped[str] = mapped_column(String(64), default="gpt-4o", nullable=False)
    judge_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    judge_suggestions: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Raw metrics
    metrics_raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class CallReplay(Base, UUIDMixin, TimestampMixin):
    """Full call replay data for timeline playback."""
    __tablename__ = "call_replays"

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Timeline events: [{ time_ms, type, data }]
    # Types: user_speech, agent_speech, tool_call, tool_result, latency, emotion, sentiment
    timeline: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    transcript: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # Audio references (paths or URLs)
    audio_segments: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # Summary
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True)
