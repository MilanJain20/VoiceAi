"""
Conversation persistence service — saves voice sessions to the database.

Handles:
- Creating conversations when sessions start
- Saving user messages (STT transcripts)
- Saving assistant messages (LLM responses)
- Updating conversation metadata and metrics
- Querying conversation history
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.conversation import (
    Conversation,
    ConversationStatus,
    Message,
    MessageRole,
)

logger = get_logger(__name__)


class ConversationService:
    """Manages conversation persistence."""

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    async def create_conversation(
        self,
        session_id: str,
        agent_id: str | None = None,
        metadata: dict | None = None,
    ) -> Conversation:
        """Create a new conversation record."""
        async with self._session_factory() as session:
            conversation = Conversation(
                session_id=session_id,
                agent_id=agent_id,
                metadata_=metadata or {},
                status=ConversationStatus.ACTIVE,
            )
            session.add(conversation)
            await session.commit()
            await session.refresh(conversation)
            logger.info(
                "conversation_created",
                session_id=session_id,
                conversation_id=str(conversation.id),
            )
            return conversation

    async def add_message(
        self,
        session_id: str,
        role: MessageRole,
        content: str,
        audio_duration_ms: int | None = None,
        stt_confidence: float | None = None,
        token_count: int | None = None,
        model: str | None = None,
        latency_ms: int | None = None,
        tool_calls: dict | None = None,
    ) -> Message | None:
        """Add a message to a conversation."""
        async with self._session_factory() as session:
            # Find conversation by session_id
            result = await session.execute(
                select(Conversation).where(Conversation.session_id == session_id)
            )
            conversation = result.scalar_one_or_none()
            if not conversation:
                logger.warning("conversation_not_found_for_message", session_id=session_id)
                return None

            message = Message(
                conversation_id=conversation.id,
                role=role,
                content=content,
                audio_duration_ms=audio_duration_ms,
                stt_confidence=stt_confidence,
                token_count=token_count,
                model=model,
                latency_ms=latency_ms,
                tool_calls=tool_calls,
                sequence=conversation.message_count,
            )
            session.add(message)

            # Update conversation counters
            conversation.message_count += 1
            if token_count:
                conversation.total_tokens += token_count

            await session.commit()
            await session.refresh(message)
            return message

    async def end_conversation(
        self, session_id: str, total_duration_ms: int = 0
    ) -> None:
        """Mark a conversation as completed."""
        async with self._session_factory() as session:
            await session.execute(
                update(Conversation)
                .where(Conversation.session_id == session_id)
                .values(
                    status=ConversationStatus.COMPLETED,
                    ended_at=datetime.now(timezone.utc),
                    total_duration_ms=total_duration_ms,
                )
            )
            await session.commit()
            logger.info("conversation_ended", session_id=session_id)

    async def get_conversation(self, session_id: str) -> Conversation | None:
        """Get a conversation by session ID."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(Conversation).where(Conversation.session_id == session_id)
            )
            return result.scalar_one_or_none()

    async def list_conversations(
        self, limit: int = 50, offset: int = 0
    ) -> list[Conversation]:
        """List recent conversations."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(Conversation)
                .order_by(Conversation.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            return list(result.scalars().all())
