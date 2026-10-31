"""
Redis pub/sub broadcaster for horizontal WebSocket scaling.

When multiple backend instances run behind a load balancer, a WebSocket
session lives on ONE instance, but messages may need to reach sessions
on OTHER instances (e.g., broadcast, admin notifications).

This module:
1. Publishes outbound messages to a Redis channel
2. Subscribes to that channel and delivers messages to local sessions
3. Maintains a "session → instance" registry in Redis hashes

When USE_REDIS=false, this is entirely bypassed.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from typing import Any, TYPE_CHECKING

from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.db.redis import RedisManager

logger = get_logger(__name__)

# Each backend instance gets a unique ID
INSTANCE_ID = f"voiceai-{os.getpid()}-{uuid.uuid4().hex[:8]}"

# Redis channel names
BROADCAST_CHANNEL = "voiceai:ws:broadcast"
DIRECT_CHANNEL_PREFIX = "voiceai:ws:direct:"

# Session registry key
SESSION_REGISTRY = "voiceai:sessions"

# Session TTL in Redis (seconds)
SESSION_TTL = 600  # 10 minutes


class RedisBroadcaster:
    """
    Redis-backed message broadcaster for cross-instance WebSocket delivery.

    Architecture:
    - Each instance subscribes to BROADCAST_CHANNEL (for broadcasts)
      and its own DIRECT_CHANNEL (for targeted messages)
    - When sending to a session, check if it's local first;
      if not, publish to the owning instance's direct channel
    - Session ownership is tracked in a Redis hash
    """

    def __init__(self, redis_manager: "RedisManager") -> None:
        self._redis = redis_manager
        self._instance_id = INSTANCE_ID
        self._listener_task: asyncio.Task | None = None
        self._local_handler: Any = None  # Set by ConnectionManager

    @property
    def instance_id(self) -> str:
        return self._instance_id

    def set_local_handler(self, handler: Any) -> None:
        """
        Set a callback that receives messages for local delivery.
        handler(session_id: str, message_dict: dict) -> awaitable
        """
        self._local_handler = handler

    async def start(self) -> None:
        """Start listening for pub/sub messages."""
        if not self._redis.is_redis:
            logger.info("redis_broadcaster_disabled", reason="no redis backend")
            return

        self._listener_task = asyncio.create_task(self._listen())
        logger.info(
            "redis_broadcaster_started",
            instance_id=self._instance_id,
        )

    async def stop(self) -> None:
        """Stop the listener."""
        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        logger.info("redis_broadcaster_stopped")

    async def register_session(self, session_id: str) -> None:
        """Register a session as owned by this instance."""
        if not self._redis.is_redis:
            return
        await self._redis.hset(SESSION_REGISTRY, {session_id: self._instance_id})
        logger.debug(
            "redis_session_registered",
            session_id=session_id,
            instance_id=self._instance_id,
        )

    async def unregister_session(self, session_id: str) -> None:
        """Remove a session from the registry."""
        if not self._redis.is_redis:
            return
        await self._redis.hdel(SESSION_REGISTRY, session_id)

    async def get_session_instance(self, session_id: str) -> str | None:
        """Find which instance owns a session."""
        if not self._redis.is_redis:
            return None
        return await self._redis.hget(SESSION_REGISTRY, session_id)

    async def publish_to_session(self, session_id: str, message: dict) -> bool:
        """
        Send a message to a specific session, potentially on another instance.
        Returns True if published.
        """
        if not self._redis.is_redis:
            return False

        owner = await self.get_session_instance(session_id)
        if owner is None:
            return False

        payload = json.dumps({
            "target": "session",
            "session_id": session_id,
            "message": message,
            "source_instance": self._instance_id,
        })

        if owner == self._instance_id:
            # Local delivery via handler
            if self._local_handler:
                await self._local_handler(session_id, message)
            return True

        # Publish to the owning instance's direct channel
        channel = f"{DIRECT_CHANNEL_PREFIX}{owner}"
        await self._redis.publish(channel, payload)
        logger.debug(
            "redis_message_published",
            target_instance=owner,
            session_id=session_id,
        )
        return True

    async def publish_broadcast(self, message: dict, exclude_sessions: set[str] | None = None) -> None:
        """Broadcast a message to all instances."""
        if not self._redis.is_redis:
            return

        payload = json.dumps({
            "target": "broadcast",
            "message": message,
            "exclude_sessions": list(exclude_sessions) if exclude_sessions else [],
            "source_instance": self._instance_id,
        })
        await self._redis.publish(BROADCAST_CHANNEL, payload)

    async def _listen(self) -> None:
        """Listen for messages on broadcast + direct channels."""
        try:
            # Use MemoryStore's subscribe for fallback, or real Redis pubsub
            if hasattr(self._redis, '_backend') and hasattr(self._redis._backend, 'pubsub'):
                # Real Redis
                pubsub = self._redis._backend.pubsub()
                my_channel = f"{DIRECT_CHANNEL_PREFIX}{self._instance_id}"
                await pubsub.subscribe(BROADCAST_CHANNEL, my_channel)

                logger.info(
                    "redis_pubsub_subscribed",
                    channels=[BROADCAST_CHANNEL, my_channel],
                )

                async for raw_message in pubsub.listen():
                    if raw_message["type"] != "message":
                        continue
                    try:
                        data = json.loads(raw_message["data"])
                        await self._handle_incoming(data)
                    except Exception as e:
                        logger.error("redis_pubsub_parse_error", error=str(e))
            else:
                # MemoryStore fallback — subscribe to broadcast queue
                queue = await self._redis._backend.subscribe(BROADCAST_CHANNEL)
                while True:
                    raw = await queue.get()
                    try:
                        data = json.loads(raw)
                        await self._handle_incoming(data)
                    except Exception as e:
                        logger.error("redis_pubsub_parse_error", error=str(e))

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("redis_listener_error", error=str(e))

    async def _handle_incoming(self, data: dict) -> None:
        """Process an incoming pub/sub message."""
        if data.get("source_instance") == self._instance_id:
            return  # Ignore our own messages

        target = data.get("target")
        message = data.get("message", {})

        if target == "session":
            session_id = data.get("session_id", "")
            if self._local_handler:
                await self._local_handler(session_id, message)

        elif target == "broadcast":
            exclude = set(data.get("exclude_sessions", []))
            if self._local_handler:
                # The local handler should broadcast to all local sessions
                # For now, we'll handle this in the connection manager
                pass


# Singleton — created during app startup when Redis is available
broadcaster: RedisBroadcaster | None = None


def create_broadcaster(redis_manager: "RedisManager") -> RedisBroadcaster:
    """Create and store the global broadcaster instance."""
    global broadcaster
    broadcaster = RedisBroadcaster(redis_manager)
    return broadcaster


def get_broadcaster() -> RedisBroadcaster | None:
    """Get the global broadcaster (may be None if Redis disabled)."""
    return broadcaster
