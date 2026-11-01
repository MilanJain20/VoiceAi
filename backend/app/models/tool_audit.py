"""Append-only record of tool executions during voice turns."""

from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class ToolAuditLog(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "tool_audit_logs"

    session_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    agent_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    turn_id: Mapped[str] = mapped_column(String(64), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False)
    arguments: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
