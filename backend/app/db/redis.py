"""
Cache/state manager with pluggable backends.

In production: connects to Redis for distributed state.
In local dev (no Redis): uses an in-memory dict with TTL support.

The interface is identical — all callers use the same methods
regardless of backend. Swap to Redis later by setting REDIS_URL
and USE_REDIS=true in .env.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


class MemoryStore:
    """
    In-memory cache that mirrors the Redis API surface.

    Features:
    - Key-value with optional TTL (auto-expiry)
    - Hash operations for session state
    - Pub/sub stub (single-instance, no-op for now)

    Limitations vs Redis:
    - Not shared across processes (single-instance only)
    - Data lost on restart
    - No distributed pub/sub

    This is sufficient for local development and single-process deployment.
    """

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}
        self._expiry: dict[str, float] = {}
        self._hashes: dict[str, dict[str, str]] = {}
        self._subscribers: dict[str, list[asyncio.Queue[str]]] = {}

    def _is_expired(self, key: str) -> bool:
        if key in self._expiry and time.time() > self._expiry[key]:
            self._store.pop(key, None)
            self._expiry.pop(key, None)
            return True
        return False

    # ---- Key-Value Operations ----

    async def get(self, key: str) -> str | None:
        if self._is_expired(key):
            return None
        return self._store.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        self._store[key] = value
        if ttl:
            self._expiry[key] = time.time() + ttl
        elif key in self._expiry:
            del self._expiry[key]

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)
        self._expiry.pop(key, None)

    async def exists(self, key: str) -> bool:
        if self._is_expired(key):
            return False
        return key in self._store

    # ---- Hash Operations (for session state) ----

    async def hset(self, name: str, mapping: dict[str, Any]) -> None:
        if name not in self._hashes:
            self._hashes[name] = {}
        self._hashes[name].update({k: str(v) for k, v in mapping.items()})

    async def hget(self, name: str, key: str) -> str | None:
        return self._hashes.get(name, {}).get(key)

    async def hgetall(self, name: str) -> dict[str, str]:
        return dict(self._hashes.get(name, {}))

    async def hdel(self, name: str, *keys: str) -> None:
        if name in self._hashes:
            for key in keys:
                self._hashes[name].pop(key, None)

    # ---- Pub/Sub (single-instance stub) ----

    async def publish(self, channel: str, message: str) -> None:
        for queue in self._subscribers.get(channel, []):
            await queue.put(message)

    async def subscribe(self, *channels: str) -> asyncio.Queue[str]:
        queue: asyncio.Queue[str] = asyncio.Queue()
        for channel in channels:
            if channel not in self._subscribers:
                self._subscribers[channel] = []
            self._subscribers[channel].append(queue)
        return queue

    # ---- Health Check ----

    async def health_check(self) -> bool:
        return True


class RedisManager:
    """
    Manages cache/state backend.

    Tries to connect to Redis if USE_REDIS=true and REDIS_URL is set.
    Falls back to in-memory MemoryStore for local development.
    """

    def __init__(self, redis_url: str = "", use_redis: bool = False) -> None:
        self._redis_url = redis_url
        self._use_redis = use_redis
        self._backend: MemoryStore | Any = None

    async def initialize(self) -> None:
        if self._use_redis and self._redis_url:
            try:
                import redis.asyncio as aioredis

                client = aioredis.from_url(
                    self._redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    max_connections=50,
                    health_check_interval=30,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True,
                )
                await client.ping()
                self._backend = client
                logger.info("redis_connected", url=self._redis_url)
                return
            except Exception as e:
                logger.warning("redis_connection_failed", error=str(e))
                logger.info("falling_back_to_memory_store")

        # Fallback: in-memory store
        self._backend = MemoryStore()
        logger.info("memory_store_initialized")

    async def close(self) -> None:
        if self._use_redis and hasattr(self._backend, "aclose"):
            await self._backend.aclose()
            logger.info("redis_disconnected")

    @property
    def is_redis(self) -> bool:
        return self._use_redis and not isinstance(self._backend, MemoryStore)

    # ---- Delegate all operations to the backend ----

    async def get(self, key: str) -> str | None:
        return await self._backend.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        if isinstance(self._backend, MemoryStore):
            await self._backend.set(key, value, ttl)
        elif ttl:
            await self._backend.setex(key, ttl, value)
        else:
            await self._backend.set(key, value)

    async def delete(self, key: str) -> None:
        await self._backend.delete(key)

    async def exists(self, key: str) -> bool:
        if isinstance(self._backend, MemoryStore):
            return await self._backend.exists(key)
        return bool(await self._backend.exists(key))

    async def hset(self, name: str, mapping: dict[str, Any]) -> None:
        await self._backend.hset(name, mapping=mapping)

    async def hget(self, name: str, key: str) -> str | None:
        return await self._backend.hget(name, key)

    async def hgetall(self, name: str) -> dict[str, str]:
        return await self._backend.hgetall(name)

    async def hdel(self, name: str, *keys: str) -> None:
        await self._backend.hdel(name, *keys)

    async def publish(self, channel: str, message: str) -> None:
        if isinstance(self._backend, MemoryStore):
            await self._backend.publish(channel, message)
        else:
            await self._backend.publish(channel, message)

    async def health_check(self) -> bool:
        if isinstance(self._backend, MemoryStore):
            return True
        try:
            return await self._backend.ping()
        except Exception:
            return False
