"""
WebSocket connection wrapper.

Encapsulates a raw WebSocket with:
- Session identity
- State tracking (connected, authenticated, streaming)
- Typed send/receive methods
- Heartbeat management
- Metrics collection
"""

from __future__ import annotations

import asyncio
import time
import uuid
from enum import Enum
from typing import Any

import orjson
from fastapi import WebSocket
from starlette.websockets import WebSocketState

from app.core.logging import get_logger
from app.schemas.websocket import WSMessage, WSMessageType

logger = get_logger(__name__)


class ConnectionState(str, Enum):
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATED = "authenticated"
    STREAMING = "streaming"
    CLOSING = "closing"
    CLOSED = "closed"


class VoiceConnection:
    """
    Wraps a FastAPI WebSocket with session context and lifecycle management.

    Each browser tab/client gets one VoiceConnection. The connection tracks:
    - session_id: unique ID for this voice session
    - state: lifecycle state machine
    - last_ping: for heartbeat timeout detection
    - metrics: latency, message counts
    """

    def __init__(self, websocket: WebSocket, session_id: str | None = None) -> None:
        self.websocket = websocket
        self.session_id = session_id or str(uuid.uuid4())
        self.state = ConnectionState.CONNECTING
        self.connected_at = time.time()
        self.last_ping = time.time()
        self.last_activity = time.time()

        # Metrics
        self.messages_sent = 0
        self.messages_received = 0
        self.bytes_received = 0
        self.bytes_sent = 0

        # Cancellation support: tasks can check this
        self._cancel_event = asyncio.Event()

    @property
    def is_connected(self) -> bool:
        return self.state in (
            ConnectionState.CONNECTED,
            ConnectionState.AUTHENTICATED,
            ConnectionState.STREAMING,
        )

    @property
    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def cancel(self) -> None:
        """Signal all pipeline tasks to stop (e.g., on interruption)."""
        self._cancel_event.set()

    def reset_cancel(self) -> None:
        """Clear cancellation flag for next turn."""
        self._cancel_event.clear()

    async def accept(self) -> None:
        await self.websocket.accept()
        self.state = ConnectionState.CONNECTED
        logger.info("ws_connection_accepted", session_id=self.session_id)

    async def send_message(self, message: WSMessage) -> None:
        """Send a typed message as JSON text frame."""
        if not self.is_connected:
            return
        try:
            data = orjson.dumps(message.model_dump(mode="json")).decode("utf-8")
            await self.websocket.send_text(data)
            self.messages_sent += 1
            self.bytes_sent += len(data)
        except Exception as e:
            logger.warning("ws_send_failed", session_id=self.session_id, error=str(e))

    async def send_json(self, data: dict[str, Any]) -> None:
        """Send raw JSON dict as text frame."""
        if not self.is_connected:
            return
        try:
            raw = orjson.dumps(data).decode("utf-8")
            await self.websocket.send_text(raw)
            self.messages_sent += 1
            self.bytes_sent += len(raw)
        except Exception as e:
            logger.warning("ws_send_json_failed", session_id=self.session_id, error=str(e))

    async def send_audio(self, audio_data: bytes) -> None:
        """Send binary audio data."""
        if not self.is_connected:
            return
        try:
            await self.websocket.send_bytes(audio_data)
            self.bytes_sent += len(audio_data)
        except Exception as e:
            logger.warning("ws_send_audio_failed", session_id=self.session_id, error=str(e))

    async def receive_message(self) -> WSMessage | bytes:
        """
        Receive the next message — either JSON (control) or binary (audio).

        Binary messages are raw audio chunks.
        Text/JSON messages are control messages parsed into WSMessage.
        Disconnect frames raise WebSocketDisconnect so the outer handler catches them.
        """
        self.last_activity = time.time()
        raw = await self.websocket.receive()

        # Handle disconnect frames from Starlette
        if raw.get("type") == "websocket.disconnect":
            from fastapi import WebSocketDisconnect
            raise WebSocketDisconnect(code=raw.get("code", 1000))

        if "bytes" in raw and raw["bytes"]:
            audio_bytes = raw["bytes"]
            self.bytes_received += len(audio_bytes)
            self.messages_received += 1
            return audio_bytes

        if "text" in raw and raw["text"]:
            text = raw["text"]
            self.messages_received += 1
            self.bytes_received += len(text)
            parsed = orjson.loads(text)
            return WSMessage(**parsed)

        raise ValueError("Empty WebSocket message received")

    async def close(self, code: int = 1000, reason: str = "normal closure") -> None:
        if self.state == ConnectionState.CLOSED:
            return
        self.state = ConnectionState.CLOSING
        try:
            if self.websocket.client_state != WebSocketState.DISCONNECTED:
                await self.websocket.close(code=code, reason=reason)
        except Exception:
            pass
        finally:
            self.state = ConnectionState.CLOSED
            duration = round(time.time() - self.connected_at, 2)
            logger.info(
                "ws_connection_closed",
                session_id=self.session_id,
                duration_s=duration,
                messages_sent=self.messages_sent,
                messages_received=self.messages_received,
            )

    def touch_ping(self) -> None:
        self.last_ping = time.time()

    @property
    def idle_seconds(self) -> float:
        return time.time() - self.last_activity

    @property
    def ping_age_seconds(self) -> float:
        return time.time() - self.last_ping
