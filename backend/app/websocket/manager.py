"""
WebSocket Connection Manager.

Central registry for all active WebSocket connections. Responsibilities:
- Track active connections by session_id
- Broadcast messages to specific sessions or all clients
- Heartbeat monitoring with automatic cleanup of stale connections
- Metrics: active connection count, total connections served
- Thread-safe connection add/remove for concurrent access

This is a single-instance manager. For horizontal scaling, Redis pub/sub
coordinates across multiple backend instances (Phase 12).
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.logging import get_logger
from app.schemas.websocket import WSMessage, WSMessageType
from app.websocket.connection import ConnectionState, VoiceConnection

logger = get_logger(__name__)

# Heartbeat config
HEARTBEAT_INTERVAL_S = 15
HEARTBEAT_TIMEOUT_S = 45
IDLE_TIMEOUT_S = 300  # 5 minutes without any activity


class ConnectionManager:
    """
    Manages all active WebSocket connections.

    Thread-safe via asyncio locks. Supports:
    - Per-session connection tracking
    - Broadcast and targeted messaging
    - Background heartbeat loop
    - Graceful shutdown with drain
    - Redis pub/sub for cross-instance delivery (Phase 12)
    """

    def __init__(self) -> None:
        self._connections: dict[str, VoiceConnection] = {}
        self._lock = asyncio.Lock()
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._total_connections_served = 0
        self._broadcaster: Any = None  # RedisBroadcaster, set during startup

    @property
    def active_count(self) -> int:
        return len(self._connections)

    @property
    def total_served(self) -> int:
        return self._total_connections_served

    def set_broadcaster(self, broadcaster: Any) -> None:
        """Wire the Redis broadcaster for cross-instance messaging."""
        self._broadcaster = broadcaster
        broadcaster.set_local_handler(self._handle_remote_message)
        logger.info("ws_broadcaster_attached")

    async def _handle_remote_message(self, session_id: str, message: dict) -> None:
        """Handle a message from another instance via Redis pub/sub."""
        conn = self._connections.get(session_id)
        if conn and conn.is_connected:
            msg = WSMessage(**message)
            await conn.send_message(msg)

    async def connect(self, connection: VoiceConnection) -> None:
        """Register a new connection and accept it."""
        await connection.accept()
        async with self._lock:
            # If a session_id collision occurs (reconnect), close the old one
            if connection.session_id in self._connections:
                old = self._connections[connection.session_id]
                logger.warning(
                    "ws_session_replaced",
                    session_id=connection.session_id,
                )
                await old.close(code=1012, reason="session replaced by new connection")
            self._connections[connection.session_id] = connection
            self._total_connections_served += 1

        logger.info(
            "ws_connection_registered",
            session_id=connection.session_id,
            active_connections=self.active_count,
        )

        # Register session in Redis for cross-instance routing
        if self._broadcaster:
            await self._broadcaster.register_session(connection.session_id)

    async def disconnect(self, session_id: str) -> None:
        """Unregister and close a connection."""
        async with self._lock:
            connection = self._connections.pop(session_id, None)
        if connection:
            await connection.close()
            # Unregister from Redis
            if self._broadcaster:
                await self._broadcaster.unregister_session(session_id)
            logger.info(
                "ws_connection_unregistered",
                session_id=session_id,
                active_connections=self.active_count,
            )

    def get_connection(self, session_id: str) -> VoiceConnection | None:
        """Retrieve a connection by session ID."""
        return self._connections.get(session_id)

    async def send_to_session(self, session_id: str, message: WSMessage) -> bool:
        """Send a message to a specific session. Returns True if sent."""
        conn = self._connections.get(session_id)
        if conn and conn.is_connected:
            await conn.send_message(message)
            return True
        return False

    async def broadcast(self, message: WSMessage, exclude: set[str] | None = None) -> int:
        """Broadcast a message to all connected sessions. Returns count sent."""
        exclude = exclude or set()
        sent = 0
        for session_id, conn in list(self._connections.items()):
            if session_id not in exclude and conn.is_connected:
                await conn.send_message(message)
                sent += 1
        return sent

    # ---- Heartbeat System ----

    async def start_heartbeat(self) -> None:
        """Start the background heartbeat loop."""
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            logger.info("ws_heartbeat_started", interval_s=HEARTBEAT_INTERVAL_S)

    async def stop_heartbeat(self) -> None:
        """Stop the heartbeat loop."""
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass
            logger.info("ws_heartbeat_stopped")

    async def _heartbeat_loop(self) -> None:
        """Periodically ping all connections and clean up stale ones."""
        while True:
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL_S)
                stale: list[str] = []

                for session_id, conn in list(self._connections.items()):
                    if not conn.is_connected:
                        stale.append(session_id)
                        continue

                    # Check for heartbeat timeout
                    if conn.ping_age_seconds > HEARTBEAT_TIMEOUT_S:
                        logger.warning(
                            "ws_heartbeat_timeout",
                            session_id=session_id,
                            age_s=round(conn.ping_age_seconds, 1),
                        )
                        stale.append(session_id)
                        continue

                    # Check for idle timeout
                    if conn.idle_seconds > IDLE_TIMEOUT_S:
                        logger.warning(
                            "ws_idle_timeout",
                            session_id=session_id,
                            idle_s=round(conn.idle_seconds, 1),
                        )
                        stale.append(session_id)
                        continue

                    # Send ping
                    pong = WSMessage(
                        type=WSMessageType.PONG,
                        session_id=session_id,
                        data={"server_time": asyncio.get_event_loop().time()},
                    )
                    await conn.send_message(pong)

                # Clean up stale connections
                for session_id in stale:
                    await self.disconnect(session_id)

                if stale:
                    logger.info("ws_stale_cleaned", count=len(stale))

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("ws_heartbeat_error", error=str(e))
                await asyncio.sleep(5)

    # ---- Shutdown ----

    async def close_all(self) -> None:
        """Gracefully close all connections (for shutdown)."""
        await self.stop_heartbeat()
        session_ids = list(self._connections.keys())
        for session_id in session_ids:
            await self.disconnect(session_id)
        logger.info("ws_all_connections_closed", count=len(session_ids))

    # ---- Metrics ----

    def get_metrics(self) -> dict[str, Any]:
        """Return current connection metrics."""
        connections_info = []
        for sid, conn in self._connections.items():
            connections_info.append({
                "session_id": sid,
                "state": conn.state.value,
                "idle_s": round(conn.idle_seconds, 1),
                "messages_sent": conn.messages_sent,
                "messages_received": conn.messages_received,
            })
        return {
            "active_connections": self.active_count,
            "total_served": self._total_connections_served,
            "connections": connections_info,
        }


# Singleton instance — shared across the application
connection_manager = ConnectionManager()
