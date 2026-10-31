"""
Conversation schemas — API request/response DTOs.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ConversationCreate(BaseModel):
    agent_id: str | None = None
    metadata: dict[str, Any] = {}


class ConversationResponse(BaseModel):
    id: uuid.UUID
    session_id: str
    status: str
    agent_id: str | None
    total_tokens: int
    total_duration_ms: int
    message_count: int
    created_at: datetime
    updated_at: datetime
    ended_at: datetime | None

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    audio_duration_ms: int | None
    stt_confidence: float | None
    token_count: int | None
    model: str | None
    latency_ms: int | None
    tool_calls: dict | None
    sequence: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationDetailResponse(ConversationResponse):
    messages: list[MessageResponse] = []


class ConversationListResponse(BaseModel):
    items: list[ConversationResponse]
    total: int
    page: int
    page_size: int
